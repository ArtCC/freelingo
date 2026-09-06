from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest


async def _seed_plan(
    db_session,
    user_id: int,
    *,
    target_language: str = "en-US",
    is_active: bool = True,
):
    """Create a minimal active A1 plan so flashcard endpoints have a study_plan_id."""
    from tests.conftest import make_study_plan

    return await make_study_plan(
        db_session,
        user_id=user_id,
        cefr_level="A1",
        target_language=target_language,
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=is_active,
    )


from app.services.flashcard_sm2 import sm2_update


class MockCard:
    def __init__(self, ease_factor=2.5, interval=0, repetitions=0):
        self.ease_factor = ease_factor
        self.interval = interval
        self.repetitions = repetitions
        self.next_review = date.today()


def test_sm2_quality_0_resets():
    card = MockCard(ease_factor=2.5, interval=10, repetitions=3)
    card = sm2_update(card, 0)
    assert card.repetitions == 0
    assert card.interval == 1


def test_sm2_quality_3_first_correct():
    card = MockCard()
    card = sm2_update(card, 3)
    assert card.repetitions == 1
    assert card.interval == 1


def test_sm2_quality_3_second_correct():
    card = MockCard(repetitions=1, interval=1)
    card = sm2_update(card, 3)
    assert card.repetitions == 2
    assert card.interval == 6


def test_sm2_quality_3_progression():
    card = MockCard(ease_factor=2.5, interval=6, repetitions=2)
    card = sm2_update(card, 3)
    assert card.repetitions == 3
    assert card.interval == 15


def test_sm2_ease_factor_decreases_on_fail():
    card = MockCard(ease_factor=2.5)
    card = sm2_update(card, 2)
    assert card.ease_factor < 2.5


def test_sm2_ease_factor_increases_on_perfect():
    card = MockCard(ease_factor=2.5)
    card = sm2_update(card, 5)
    assert card.ease_factor > 2.5


def test_sm2_ease_factor_floor():
    card = MockCard(ease_factor=1.3)
    card = sm2_update(card, 1)
    assert card.ease_factor == 1.3


def test_sm2_next_review_is_future():
    card = MockCard(interval=3)
    card = sm2_update(card, 4)
    assert card.next_review == date.today() + timedelta(days=card.interval)


@pytest.mark.asyncio
async def test_create_flashcard(client, test_user, db_session):
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    response = await client.post(
        "/api/flashcards",
        headers=headers,
        json={
            "word": "hello",
            "definition": "a greeting",
            "example_sentence": "Hello, how are you?",
            "translation": "hola",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["word"] == "hello"
    assert data["study_plan_id"] == plan.id
    assert data["ease_factor"] == 2.5
    assert data["interval"] == 0


@pytest.mark.asyncio
async def test_get_due_flashcards(client, test_user, db_session):
    user, headers = test_user

    from app.models.flashcard import Flashcard

    plan = await _seed_plan(db_session, user.id)

    card = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="test",
        definition="a test",
        example_sentence="This is a test.",
        translation="prueba",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.get("/api/flashcards/due", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["due"]) == 1
    assert data["total"] == 1
    assert data["due"][0]["study_plan_id"] == plan.id


@pytest.mark.asyncio
async def test_review_flashcard(client, test_user, db_session):
    user, headers = test_user

    from app.models.flashcard import Flashcard

    plan = await _seed_plan(db_session, user.id)

    card = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="test",
        definition="a test",
        example_sentence="Test.",
        translation="prueba",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.post(
        f"/api/flashcards/{card.id}/review",
        headers=headers,
        json={"quality": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["repetitions"] == 1
    assert data["interval"] == 1


@pytest.mark.asyncio
async def test_review_flashcard_credits_owning_plan_after_language_switch(
    client,
    test_user,
    db_session,
):
    user, headers = test_user

    from app.models.flashcard import Flashcard

    card_plan = await _seed_plan(
        db_session,
        user.id,
        target_language="en-US",
        is_active=False,
    )
    await _seed_plan(db_session, user.id, target_language="it-IT")
    card = Flashcard(
        user_id=user.id,
        study_plan_id=card_plan.id,
        word="hello",
        definition="a greeting",
        example_sentence="Hello there.",
        translation="ciao",
    )
    db_session.add(card)
    await db_session.commit()

    progress_mock = AsyncMock()
    with patch("app.routers.flashcards.update_daily_progress", new=progress_mock):
        response = await client.post(
            f"/api/flashcards/{card.id}/review",
            headers=headers,
            json={"quality": 5},
        )

    assert response.status_code == 200
    assert progress_mock.await_args.kwargs["study_plan_id"] == card_plan.id


@pytest.mark.asyncio
async def test_get_vocabulary_flashcards(client, test_user, db_session):
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    from app.models.flashcard import Flashcard

    # from_text card
    card_vocab = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="ephemeral",
        definition="lasting a very short time",
        example_sentence="The joy was ephemeral.",
        translation="efímero",
        source="from_text",
    )
    # regular card (should not appear in vocabulary endpoint)
    card_regular = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="run",
        definition="to move fast",
        example_sentence="I run every day.",
        translation="correr",
    )
    db_session.add(card_vocab)
    db_session.add(card_regular)
    await db_session.commit()

    response = await client.get("/api/flashcards/vocabulary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["word"] == "ephemeral"
    assert data["items"][0]["source"] == "from_text"


@pytest.mark.asyncio
async def test_delete_flashcard(client, test_user, db_session):
    user, headers = test_user

    from app.models.flashcard import Flashcard

    plan = await _seed_plan(db_session, user.id)

    card = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="obsolete",
        definition="no longer in use",
        example_sentence="This word is obsolete.",
        translation="obsoleto",
        source="from_text",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.delete(f"/api/flashcards/{card.id}", headers=headers)
    assert response.status_code == 204

    # Confirm deletion
    response = await client.get("/api/flashcards/vocabulary", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_delete_flashcard_not_found(client, test_user):
    _, headers = test_user
    response = await client.delete("/api/flashcards/99999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_flashcard_other_user(client, test_user, db_session):
    user, headers = test_user

    from app.core.security import hash_password
    from app.models.flashcard import Flashcard
    from app.models.user import User

    other_user = User(
        username="other",
        email="other@example.com",
        display_name="Other",
        hashed_password=hash_password("pass"),
        role="user",
        native_language="es",
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_plan = await _seed_plan(db_session, other_user.id)

    card = Flashcard(
        user_id=other_user.id,
        study_plan_id=other_plan.id,
        word="word",
        definition="def",
        example_sentence="example",
        translation="traducción",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.delete(f"/api/flashcards/{card.id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_flashcard_from_word(client, test_user, db_session, monkeypatch):
    _, headers = test_user
    await _seed_plan(db_session, test_user[0].id)

    from app.schemas.flashcards import FlashcardCreate

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        return FlashcardCreate(
            word=kwargs["word"],
            definition="lasting a very short time",
            example_sentence="The fame was fleeting.",
            translation="efímero",
        )

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={
            "word": "fleeting",
            "context": "The fame was fleeting.",
            "cefr_level": "B2",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["word"] == "fleeting"
    assert data["source"] == "from_text"
    assert data["definition"] == "lasting a very short time"
    assert data["already_saved"] is False


@pytest.mark.asyncio
async def test_create_flashcard_from_word_existing_input_word_skips_llm(
    client, test_user, db_session, monkeypatch
):
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    from app.models.flashcard import Flashcard

    existing = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="Fleeting ",
        definition="lasting a very short time",
        example_sentence="The fame was fleeting.",
        translation="efímero",
        source="from_text",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        raise AssertionError("lookup_word should not be called")

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={"word": "fleeting", "context": "", "cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["already_saved"] is True
    assert data["id"] == existing.id

    from sqlalchemy import func, select

    count_result = await db_session.execute(
        select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    )
    assert count_result.scalar() == 1


@pytest.mark.asyncio
async def test_create_flashcard_from_word_lemma_collision_skips_insert(
    client, test_user, db_session, monkeypatch
):
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    from app.models.flashcard import Flashcard

    existing = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="run",
        definition="to move fast",
        example_sentence="I run every day.",
        translation="correr",
        source="from_text",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    from app.schemas.flashcards import FlashcardCreate

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        return FlashcardCreate(
            word="run",
            definition="to move fast",
            example_sentence="I was running.",
            translation="correr",
        )

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={"word": "running", "context": "I was running.", "cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["already_saved"] is True
    assert data["id"] == existing.id
    assert data["word"] == "run"

    from sqlalchemy import func, select

    count_result = await db_session.execute(
        select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    )
    assert count_result.scalar() == 1


@pytest.mark.asyncio
async def test_create_flashcard_from_word_other_plan_does_not_suppress_save(
    client, test_user, db_session, monkeypatch
):
    user, headers = test_user
    await _seed_plan(db_session, user.id)
    other_plan = await _seed_plan(db_session, user.id, target_language="it-IT", is_active=False)

    from app.models.flashcard import Flashcard

    other_plan_card = Flashcard(
        user_id=user.id,
        study_plan_id=other_plan.id,
        word="fleeting",
        definition="lasting a very short time",
        example_sentence="The fame was fleeting.",
        translation="fugace",
        source="from_text",
    )
    db_session.add(other_plan_card)
    await db_session.commit()

    from app.schemas.flashcards import FlashcardCreate

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        return FlashcardCreate(
            word=kwargs["word"],
            definition="lasting a very short time",
            example_sentence="The fame was fleeting.",
            translation="efímero",
        )

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={"word": "fleeting", "context": "", "cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["already_saved"] is False

    from sqlalchemy import func, select

    count_result = await db_session.execute(
        select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    )
    assert count_result.scalar() == 2


@pytest.mark.asyncio
async def test_create_flashcard_from_word_fresh_word_inserts(
    client, test_user, db_session, monkeypatch
):
    user, headers = test_user
    await _seed_plan(db_session, user.id)

    from app.schemas.flashcards import FlashcardCreate

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        return FlashcardCreate(
            word=kwargs["word"],
            definition="a state of being alone",
            example_sentence="She enjoyed the solitude.",
            translation="soledad",
        )

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={"word": "solitude", "context": "", "cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["already_saved"] is False
    assert data["word"] == "solitude"

    from sqlalchemy import func, select

    from app.models.flashcard import Flashcard

    count_result = await db_session.execute(
        select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    )
    assert count_result.scalar() == 1


@pytest.mark.asyncio
async def test_create_flashcard_from_word_generated_card_collision_promotes_source(
    client, test_user, db_session, monkeypatch
):
    """A generated/imported card (source=None) is not in My Vocabulary yet: saving the
    same word promotes it to from_text instead of duplicating it or reporting it as
    already saved."""
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    from app.models.flashcard import Flashcard

    generated = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="Harbor",
        definition="a sheltered port",
        example_sentence="The ship entered the harbor.",
        translation="puerto",
        source=None,
    )
    db_session.add(generated)
    await db_session.commit()
    await db_session.refresh(generated)

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        raise AssertionError("lookup_word should not be called")

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    before = await client.get("/api/flashcards/vocabulary", headers=headers)
    assert before.json()["total"] == 0

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={"word": "harbor", "context": "", "cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == generated.id
    assert data["already_saved"] is False
    assert data["source"] == "from_text"

    after = await client.get("/api/flashcards/vocabulary", headers=headers)
    assert [item["id"] for item in after.json()["items"]] == [generated.id]

    from sqlalchemy import func, select

    count_result = await db_session.execute(
        select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    )
    assert count_result.scalar() == 1


@pytest.mark.asyncio
async def test_create_flashcard_from_word_lemma_collision_with_generated_card_promotes(
    client, test_user, db_session, monkeypatch
):
    """The post-LLM check follows the same promotion rule as the pre-LLM one."""
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    from app.models.flashcard import Flashcard

    generated = Flashcard(
        user_id=user.id,
        study_plan_id=plan.id,
        word="run",
        definition="to move fast",
        example_sentence="I run every day.",
        translation="correr",
        source=None,
    )
    db_session.add(generated)
    await db_session.commit()
    await db_session.refresh(generated)

    from app.schemas.flashcards import FlashcardCreate

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        return FlashcardCreate(
            word="run",
            definition="to move fast",
            example_sentence="I was running.",
            translation="correr",
        )

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    response = await client.post(
        "/api/flashcards/from-word",
        headers=headers,
        json={"word": "running", "context": "I was running.", "cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == generated.id
    assert data["already_saved"] is False
    assert data["source"] == "from_text"

    from sqlalchemy import func, select

    count_result = await db_session.execute(
        select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    )
    assert count_result.scalar() == 1


@pytest.mark.asyncio
async def test_create_flashcard_from_word_existing_duplicates_return_oldest(
    client, test_user, db_session, monkeypatch
):
    """When duplicates already exist in the plan, the lowest id wins deterministically."""
    user, headers = test_user
    plan = await _seed_plan(db_session, user.id)

    from app.models.flashcard import Flashcard

    cards = [
        Flashcard(
            user_id=user.id,
            study_plan_id=plan.id,
            word=word,
            definition="a sheltered port",
            example_sentence="The ship entered the harbor.",
            translation="puerto",
            source="from_text",
        )
        for word in ("harbor", "Harbor", " HARBOR ")
    ]
    db_session.add_all(cards)
    await db_session.commit()
    for card in cards:
        await db_session.refresh(card)
    oldest_id = min(card.id for card in cards)

    async def mock_lookup_word(**kwargs):  # noqa: ANN002
        raise AssertionError("lookup_word should not be called")

    import app.routers.flashcards as fc_router

    monkeypatch.setattr(fc_router, "lookup_word", mock_lookup_word)

    for _ in range(3):
        response = await client.post(
            "/api/flashcards/from-word",
            headers=headers,
            json={"word": "harbor", "context": "", "cefr_level": "B1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == oldest_id
        assert data["already_saved"] is True
