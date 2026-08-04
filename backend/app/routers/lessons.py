import copy
import json
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    check_subscription_or_freemium_access,
    get_current_user,
    get_redis,
)
from app.core.limiter import limiter
from app.models.lesson import Exercise, Lesson
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.lessons import (
    ExerciseAnswerRequest,
    ExerciseAnswerResponse,
    ExerciseResponse,
    LessonDetailResponse,
    LessonResponse,
    NativeExerciseExplanationResponse,
    NativeExerciseHintResponse,
    NativeExplanationResponse,
)
from app.services.language_helpers import get_language_name, get_native_language_name
from app.services.lesson_generator import (
    evaluate_fill_blank,
    evaluate_free_write,
    evaluate_pronunciation,
    hint_reveals_answer,
    regenerate_exercise,
)
from app.services.llm_adapter import (
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
    llm_adapter,
)
from app.services.progress_service import update_daily_progress, upsert_unit_competency

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


_ANSWER_FEEDBACK: dict[str, dict[str, str]] = {
    "en": {
        "correct": "Correct!",
        "correct_answer": "The correct answer is: {answer}",
        "free_write_unavailable": "Could not evaluate free-write answer at this time.",
        "good_pronunciation": "Good pronunciation!",
        "target_phrase": "The target phrase was: {answer}",
    },
    "es": {
        "correct": "Correcto!",
        "correct_answer": "La respuesta correcta es: {answer}",
        "free_write_unavailable": "No se pudo evaluar la respuesta escrita en este momento.",
        "good_pronunciation": "Buena pronunciacion!",
        "target_phrase": "La frase objetivo era: {answer}",
    },
    "de": {
        "correct": "Richtig!",
        "correct_answer": "Die richtige Antwort ist: {answer}",
        "free_write_unavailable": "Die schriftliche Antwort konnte momentan nicht bewertet werden.",
        "good_pronunciation": "Gute Aussprache!",
        "target_phrase": "Der Zielsatz war: {answer}",
    },
    "fr": {
        "correct": "Correct !",
        "correct_answer": "La bonne reponse est : {answer}",
        "free_write_unavailable": "Impossible d'evaluer la reponse ecrite pour le moment.",
        "good_pronunciation": "Bonne prononciation !",
        "target_phrase": "La phrase cible etait : {answer}",
    },
    "it": {
        "correct": "Corretto!",
        "correct_answer": "La risposta corretta e: {answer}",
        "free_write_unavailable": "Non e possibile valutare la risposta scritta in questo momento.",
        "good_pronunciation": "Buona pronuncia!",
        "target_phrase": "La frase obiettivo era: {answer}",
    },
    "pt": {
        "correct": "Correto!",
        "correct_answer": "A resposta correta e: {answer}",
        "free_write_unavailable": "Nao foi possivel avaliar a resposta escrita neste momento.",
        "good_pronunciation": "Boa pronuncia!",
        "target_phrase": "A frase-alvo era: {answer}",
    },
    "ru": {
        "correct": "Правильно!",
        "correct_answer": "Правильный ответ: {answer}",
        "free_write_unavailable": "Сейчас не удалось оценить письменный ответ.",
        "good_pronunciation": "Хорошее произношение!",
        "target_phrase": "Целевая фраза была: {answer}",
    },
    "nl": {
        "correct": "Correct!",
        "correct_answer": "Het juiste antwoord is: {answer}",
        "free_write_unavailable": "Het geschreven antwoord kan momenteel niet worden beoordeeld.",
        "good_pronunciation": "Goede uitspraak!",
        "target_phrase": "De doelzin was: {answer}",
    },
    "pl": {
        "correct": "Poprawnie!",
        "correct_answer": "Prawidlowa odpowiedz to: {answer}",
        "free_write_unavailable": "Nie mozna teraz ocenic odpowiedzi pisemnej.",
        "good_pronunciation": "Dobra wymowa!",
        "target_phrase": "Fraza docelowa to: {answer}",
    },
    "ro": {
        "correct": "Corect!",
        "correct_answer": "Raspunsul corect este: {answer}",
        "free_write_unavailable": "Nu s-a putut evalua raspunsul scris momentan.",
        "good_pronunciation": "Pronuntie buna!",
        "target_phrase": "Fraza tinta a fost: {answer}",
    },
}


def _answer_feedback(native_language: str, key: str, *, answer: str = "") -> str:
    messages = _ANSWER_FEEDBACK.get(native_language, _ANSWER_FEEDBACK["en"])
    return messages[key].format(answer=answer)


def _exercise_has_technical_error(exercise: Exercise) -> bool:
    if not exercise.question.strip() or not exercise.correct_answer.strip():
        return True
    if exercise.exercise_type == "multiple_choice":
        options = [opt for opt in (exercise.options or []) if isinstance(opt, str) and opt.strip()]
        return len(options) < 2 or exercise.correct_answer not in options
    if exercise.exercise_type == "fill_blank":
        return "___" not in exercise.question
    return False


async def _get_lesson_for_user(
    lesson_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    for_update: bool = False,
) -> Lesson:
    """Fetch a lesson and verify it belongs to the requesting user via its study plan."""
    from app.models.user_language import UserLanguage

    query = (
        select(Lesson)
        .join(StudyPlan, Lesson.study_plan_id == StudyPlan.id)
        .join(UserLanguage, StudyPlan.user_language_id == UserLanguage.id)
        .where(Lesson.id == lesson_id, UserLanguage.user_id == user_id)
    )
    if for_update:
        query = query.with_for_update(of=Lesson)
    result = await db.execute(query)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


async def _get_exercise_content_entry(
    exercise: Exercise,
    lesson: Lesson,
    db: AsyncSession,
) -> tuple[dict, list, dict]:
    result = await db.execute(
        select(Exercise).where(Exercise.lesson_id == lesson.id).order_by(Exercise.id)
    )
    lesson_exercises = result.scalars().all()
    exercise_index = next(
        (index for index, item in enumerate(lesson_exercises) if item.id == exercise.id),
        None,
    )
    if exercise_index is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    content = copy.deepcopy(lesson.content or {})
    content_exercises = content.get("exercises")
    if not isinstance(content_exercises, list):
        content_exercises = []
    while len(content_exercises) <= exercise_index:
        content_exercises.append({})

    content_exercise = content_exercises[exercise_index]
    if not isinstance(content_exercise, dict):
        content_exercise = {}
        content_exercises[exercise_index] = content_exercise

    return content, content_exercises, content_exercise


async def _get_exercise_index(exercise: Exercise, lesson: Lesson, db: AsyncSession) -> int:
    result = await db.execute(
        select(Exercise).where(Exercise.lesson_id == lesson.id).order_by(Exercise.id)
    )
    lesson_exercises = result.scalars().all()
    exercise_index = next(
        (index for index, item in enumerate(lesson_exercises) if item.id == exercise.id),
        None,
    )
    if exercise_index is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return exercise_index


@router.get("/{lesson_id}", response_model=LessonDetailResponse)
@limiter.limit("60/minute")
async def get_lesson(
    request: Request,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db)

    result = await db.execute(
        select(Exercise).where(Exercise.lesson_id == lesson_id).order_by(Exercise.id)
    )
    exercises = result.scalars().all()

    # Sanitize fill_blank exercises that were generated before constraint #6 was enforced:
    # if `question` is an instruction text (no ___) but `explanation` has the gapped sentence,
    # swap them so the user sees the sentence — without touching the DB.
    content_exercises = []
    if isinstance(lesson.content, dict) and isinstance(lesson.content.get("exercises"), list):
        content_exercises = lesson.content["exercises"]

    fixed: list[ExerciseResponse] = []
    for index, ex in enumerate(exercises):
        q, exp = ex.question, ex.explanation
        if ex.exercise_type == "fill_blank" and "___" not in q:
            if exp and "___" in exp:
                q, exp = exp, q
        native_exp = None
        native_hint = None
        if index < len(content_exercises) and isinstance(content_exercises[index], dict):
            native_exp = content_exercises[index].get("native_explanation")
            native_hint = content_exercises[index].get("native_hint")
        fixed.append(
            ExerciseResponse(
                id=ex.id,
                lesson_id=ex.lesson_id,
                exercise_type=ex.exercise_type,
                question=q,
                options=ex.options,
                correct_answer=ex.correct_answer,
                user_answer=ex.user_answer,
                score=ex.score,
                feedback=ex.feedback,
                explanation=exp,
                native_explanation=native_exp if isinstance(native_exp, str) else None,
                native_hint=native_hint if isinstance(native_hint, str) else None,
                answered_at=ex.answered_at,
            )
        )

    return LessonDetailResponse(lesson=lesson, exercises=fixed)


@router.post("/{lesson_id}/start", response_model=LessonResponse)
@limiter.limit("60/minute")
async def start_lesson(
    request: Request,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db)
    return lesson


@router.post("/{lesson_id}/complete", response_model=LessonResponse)
@limiter.limit("60/minute")
async def complete_lesson(
    request: Request,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db, for_update=True)

    if lesson.is_completed:
        return lesson

    await check_subscription_or_freemium_access("lessons", redis, current_user)

    lesson.is_completed = True
    lesson.completed_at = datetime.now(UTC).replace(tzinfo=None)

    await update_daily_progress(
        db,
        current_user.id,
        lesson_completed=True,
        skill=lesson.lesson_type,
        study_plan_id=lesson.study_plan_id,
        commit=False,
    )

    if lesson.unit_id:
        from app.data.curriculum import get_curriculum_units  # noqa: PLC0415
        from app.models.study_plan import StudyPlan  # noqa: PLC0415

        plan = await db.get(StudyPlan, lesson.study_plan_id)
        if plan:
            for u in get_curriculum_units(plan.cefr_level, plan.target_language):
                if u.id == lesson.unit_id:
                    # Score this lesson: average of answered exercises
                    result_ex = await db.execute(
                        select(Exercise).where(
                            Exercise.lesson_id == lesson.id,
                            Exercise.score.is_not(None),
                        )
                    )
                    exercises = result_ex.scalars().all()
                    lesson_score = (
                        sum(e.score for e in exercises if e.score is not None) / len(exercises)
                        if exercises
                        else 0.5
                    )
                    await upsert_unit_competency(
                        db,
                        current_user.id,
                        unit_id=lesson.unit_id,
                        competency_texts=u.competency_checklist,
                        lesson_score=lesson_score,
                        study_plan_id=lesson.study_plan_id,
                    )
                    break

    await db.commit()
    await db.refresh(lesson)

    # Record freemium lesson usage only after the database transaction succeeds.
    from app.services.freemium_service import maybe_record_freemium_usage

    await maybe_record_freemium_usage(current_user, "lessons")

    return lesson


@router.post("/exercises/{exercise_id}/answer", response_model=ExerciseAnswerResponse)
@limiter.limit("20/minute")
async def answer_exercise(
    request: Request,
    exercise_id: int,
    data: ExerciseAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    lesson = await _get_lesson_for_user(exercise.lesson_id, current_user.id, db)

    plan = await db.get(StudyPlan, lesson.study_plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Study plan not found for lesson",
        )
    target_language = plan.target_language

    if exercise.answered_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Exercise already answered"
        )

    if exercise.exercise_type == "free_write":
        prompt = exercise.question
        # Bug 4: use exercise-specific criteria from options if available
        criteria = [opt for opt in (exercise.options or []) if isinstance(opt, str) and opt.strip()]
        if not criteria:
            criteria = ["grammar", "spelling", "coherence"]
        try:
            eval_result = await evaluate_free_write(
                cefr_level=lesson.cefr_level,
                prompt=prompt,
                criteria=criteria,
                answer=data.answer,
                target_language=target_language,
                native_language=current_user.native_language,
            )
            sco = eval_result.score if hasattr(eval_result, "score") else eval_result["score"]
            fb = (
                eval_result.feedback
                if hasattr(eval_result, "feedback")
                else eval_result["feedback"]
            )
            exercise.score = sco
            exercise.feedback = fb
        except LLMTimeoutError, LLMUnavailableError, LLMError:
            exercise.score = 0.5
            exercise.feedback = _answer_feedback(
                current_user.native_language, "free_write_unavailable"
            )
    elif exercise.exercise_type == "fill_blank":
        try:
            eval_result = await evaluate_fill_blank(
                cefr_level=lesson.cefr_level,
                question=exercise.question,
                correct_answer=exercise.correct_answer,
                student_answer=data.answer,
                target_language=target_language,
                native_language=current_user.native_language,
            )
            exercise.score = eval_result.score
            exercise.feedback = eval_result.feedback
        except LLMTimeoutError, LLMUnavailableError, LLMError:
            # Fallback: normalised string comparison
            ua = data.answer.strip().lower().rstrip(".,!?")
            ca = exercise.correct_answer.strip().lower().rstrip(".,!?")
            alternatives = [a.strip().lower() for a in ca.split("/")]
            is_correct = ua == ca or ua in alternatives
            exercise.score = 1.0 if is_correct else 0.0
            exercise.feedback = (
                _answer_feedback(current_user.native_language, "correct")
                if is_correct
                else _answer_feedback(
                    current_user.native_language,
                    "correct_answer",
                    answer=exercise.correct_answer,
                )
            )
    elif exercise.exercise_type == "pronunciation":
        transcription = data.answer
        try:
            eval_result = await evaluate_pronunciation(
                cefr_level=lesson.cefr_level,
                target=exercise.correct_answer,
                transcription=transcription,
                target_language=target_language,
                native_language=current_user.native_language,
            )
            exercise.score = eval_result.score
            exercise.feedback = eval_result.feedback
        except LLMTimeoutError, LLMUnavailableError, LLMError:
            # Fallback: normalised comparison stripping punctuation
            norm_target = re.sub(r"[^\w\s]", "", exercise.correct_answer).strip().lower()
            norm_answer = re.sub(r"[^\w\s]", "", transcription).strip().lower()
            is_close = (
                norm_target == norm_answer
                or norm_target in norm_answer
                or norm_answer in norm_target
            )
            exercise.score = 1.0 if is_close else 0.0
            exercise.feedback = (
                _answer_feedback(current_user.native_language, "good_pronunciation")
                if is_close
                else _answer_feedback(
                    current_user.native_language,
                    "target_phrase",
                    answer=exercise.correct_answer,
                )
            )
    else:
        user_ans = data.answer.strip().lower()
        correct_ans = exercise.correct_answer.strip().lower()
        # Compatibility: old exercises may store correct_answer as bare letter ("a")
        # while clients now submit full option text ("a. works"). Accept both.
        _stripped = re.sub(r"^[a-z]\. *", "", user_ans)
        is_correct = (
            user_ans == correct_ans
            or _stripped == correct_ans
            or user_ans == re.sub(r"^[a-z]\. *", "", correct_ans)
        )
        exercise.score = 1.0 if is_correct else 0.0
        exercise.feedback = (
            _answer_feedback(current_user.native_language, "correct")
            if is_correct
            else _answer_feedback(
                current_user.native_language,
                "correct_answer",
                answer=exercise.correct_answer,
            )
        )

    exercise.user_answer = data.answer
    exercise.answered_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(exercise)

    await update_daily_progress(
        db,
        current_user.id,
        exercise_correct=exercise.score >= 0.5,
        skill=lesson.lesson_type,
        skill_score=exercise.score,
        study_plan_id=lesson.study_plan_id,
    )

    return ExerciseAnswerResponse(
        id=exercise.id,
        score=exercise.score,
        feedback=exercise.feedback,
        correct_answer=exercise.correct_answer,
    )


@router.post("/exercises/{exercise_id}/regenerate", response_model=ExerciseResponse)
@limiter.limit("5/hour")
async def regenerate_invalid_exercise(
    request: Request,
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    lesson = await _get_lesson_for_user(exercise.lesson_id, current_user.id, db)
    if lesson.is_completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed lesson exercises cannot be regenerated",
        )
    if exercise.answered_at is not None or exercise.score is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Answered exercises cannot be regenerated",
        )
    if not _exercise_has_technical_error(exercise):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exercise does not need regeneration",
        )

    plan = await db.get(StudyPlan, lesson.study_plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Study plan not found for lesson",
        )

    content, content_exercises, _content_exercise = await _get_exercise_content_entry(
        exercise, lesson, db
    )
    exercise_index = await _get_exercise_index(exercise, lesson, db)
    invalid_exercise = {
        "type": exercise.exercise_type,
        "question": exercise.question,
        "options": exercise.options,
        "correct": exercise.correct_answer,
        "explanation": exercise.explanation,
    }

    try:
        regenerated = await regenerate_exercise(
            cefr_level=lesson.cefr_level,
            lesson_type=lesson.lesson_type,
            topic=lesson.title,
            exercise_type=exercise.exercise_type,
            lesson_explanation=(content.get("explanation") if isinstance(content, dict) else {}),
            lesson_vocabulary=(content.get("vocabulary") if isinstance(content, dict) else []),
            invalid_exercise=invalid_exercise,
            target_language=plan.target_language,
            native_language=current_user.native_language,
        )
    except (LLMError, LLMTimeoutError, LLMUnavailableError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not regenerate exercise at this time",
        ) from exc

    exercise.question = regenerated.question
    exercise.options = regenerated.options
    exercise.correct_answer = regenerated.correct
    exercise.explanation = regenerated.explanation
    exercise.feedback = None
    exercise.user_answer = None
    exercise.score = None
    exercise.answered_at = None

    content_exercises[exercise_index] = regenerated.model_dump()
    content["exercises"] = content_exercises
    lesson.content = content

    await db.commit()
    await db.refresh(exercise)

    return ExerciseResponse(
        id=exercise.id,
        lesson_id=exercise.lesson_id,
        exercise_type=exercise.exercise_type,
        question=exercise.question,
        options=exercise.options,
        correct_answer=exercise.correct_answer,
        user_answer=exercise.user_answer,
        score=exercise.score,
        feedback=exercise.feedback,
        explanation=exercise.explanation,
        native_explanation=regenerated.native_explanation,
        native_hint=regenerated.native_hint,
        answered_at=exercise.answered_at,
    )


@router.post("/exercises/{exercise_id}/native-explanation")
@limiter.limit("10/minute")
async def generate_exercise_native_explanation(
    request: Request,
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    lesson = await _get_lesson_for_user(exercise.lesson_id, current_user.id, db)
    content, content_exercises, content_exercise = await _get_exercise_content_entry(
        exercise, lesson, db
    )

    cached = content_exercise.get("native_explanation")
    if isinstance(cached, str) and cached.strip():
        return {"native_explanation": cached}

    if not exercise.explanation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exercise has no explanation to translate",
        )

    plan = await db.get(StudyPlan, lesson.study_plan_id)
    target_language = plan.target_language if plan else "en-GB"

    from app.services.prompts.lesson import (
        build_native_exercise_explanation_on_demand_prompt,
    )

    prompt = build_native_exercise_explanation_on_demand_prompt(
        target_language_name=get_language_name(target_language),
        native_language_name=get_native_language_name(current_user.native_language),
        exercise_type=exercise.exercise_type,
        question=exercise.question,
        correct_answer=exercise.correct_answer,
        explanation=exercise.explanation,
    )

    try:
        result_native = await llm_adapter.structured_output(
            [{"role": "user", "content": prompt}],
            NativeExerciseExplanationResponse,
        )
        native_exp = result_native.native_explanation
    except LLMError, LLMTimeoutError, LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate native exercise explanation at this time",
        )

    content_exercise["native_explanation"] = native_exp
    content["exercises"] = content_exercises
    lesson.content = content
    await db.commit()

    return {"native_explanation": native_exp}


@router.post("/exercises/{exercise_id}/native-hint")
@limiter.limit("10/minute")
async def generate_exercise_native_hint(
    request: Request,
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    lesson = await _get_lesson_for_user(exercise.lesson_id, current_user.id, db)
    content, content_exercises, content_exercise = await _get_exercise_content_entry(
        exercise, lesson, db
    )

    cached = content_exercise.get("native_hint")
    if isinstance(cached, str) and cached.strip():
        return {"native_hint": cached}

    plan = await db.get(StudyPlan, lesson.study_plan_id)
    target_language = plan.target_language if plan else "en-GB"

    from app.services.prompts.lesson import build_native_exercise_hint_on_demand_prompt

    prompt = build_native_exercise_hint_on_demand_prompt(
        target_language_name=get_language_name(target_language),
        native_language_name=get_native_language_name(current_user.native_language),
        exercise_type=exercise.exercise_type,
        question=exercise.question,
        options=json.dumps(exercise.options or [], ensure_ascii=False),
        correct_answer=exercise.correct_answer,
        explanation=exercise.explanation or "",
    )

    try:
        result_native = await llm_adapter.structured_output(
            [{"role": "user", "content": prompt}],
            NativeExerciseHintResponse,
        )
        native_hint = result_native.native_hint
        if hint_reveals_answer(native_hint, exercise.correct_answer):
            raise LLMError("Generated hint revealed the answer")
    except LLMError, LLMTimeoutError, LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate native exercise hint at this time",
        )

    content_exercise["native_hint"] = native_hint
    content["exercises"] = content_exercises
    lesson.content = content
    await db.commit()

    return {"native_hint": native_hint}


@router.post("/{lesson_id}/native-explanation")
@limiter.limit("10/minute")
async def generate_native_explanation(
    request: Request,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db)

    content = dict(lesson.content or {})
    if content.get("native_explanation"):
        return {"native_explanation": content["native_explanation"]}

    explanation = content.get("explanation")
    if not explanation or not isinstance(explanation, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lesson has no explanation to translate",
        )

    plan = await db.get(StudyPlan, lesson.study_plan_id)
    target_language = plan.target_language if plan else "en-GB"

    from app.services.prompts.lesson import build_native_explanation_on_demand_prompt

    prompt = build_native_explanation_on_demand_prompt(
        target_language_name=get_language_name(target_language),
        native_language_name=get_native_language_name(current_user.native_language),
        source_explanation=json.dumps(explanation, ensure_ascii=False),
    )

    try:
        result = await llm_adapter.structured_output(
            [{"role": "user", "content": prompt}],
            NativeExplanationResponse,
        )
        native_exp: dict = result.model_dump() if hasattr(result, "model_dump") else result
    except LLMError, LLMTimeoutError, LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate native explanation at this time",
        )

    content["native_explanation"] = native_exp
    lesson.content = content
    await db.commit()
    await db.refresh(lesson)

    return {"native_explanation": native_exp}
