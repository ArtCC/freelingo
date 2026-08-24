import type { AssessmentQuestion } from '@/data/types'

/**
 * Sentinel returned by the quiz card when the learner declines to answer.
 *
 * Guessing on a four-option question is right about a quarter of the time, which
 * pushes the placement level up for knowledge the learner does not have. Saying
 * "I don't know" is recorded as a declared gap instead: never correct, and
 * distinguishable from a wrong answer by the evaluator.
 */
export const DONT_KNOW_ANSWER = '__dont_know__'

export interface AnswerRecord {
  question_id: string
  skill: string
  difficulty: string
  correct: boolean
  dont_know: boolean
}

export function isDontKnowAnswer(answer: string): boolean {
  return answer === DONT_KNOW_ANSWER
}

export function buildAnswerRecord(
  question: AssessmentQuestion,
  chosen: string
): AnswerRecord {
  const dontKnow = isDontKnowAnswer(chosen)
  return {
    question_id: question.id,
    skill: question.skill,
    difficulty: question.difficulty,
    correct: !dontKnow && chosen === question.correct,
    dont_know: dontKnow,
  }
}
