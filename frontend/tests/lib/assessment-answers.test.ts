import { describe, it, expect } from 'vitest'
import {
  DONT_KNOW_ANSWER,
  buildAnswerRecord,
  isDontKnowAnswer,
} from '@/lib/assessment-answers'
import type { AssessmentQuestion } from '@/data/types'

const question: AssessmentQuestion = {
  id: 'q1',
  skill: 'grammar',
  difficulty: 'B2',
  question: 'Wir ___ nach Berlin gefahren.',
  options: ['haben', 'sind', 'werden', 'seid'],
  correct: 'sind',
}

describe('isDontKnowAnswer', () => {
  it('recognises the sentinel only', () => {
    expect(isDontKnowAnswer(DONT_KNOW_ANSWER)).toBe(true)
    expect(isDontKnowAnswer('sind')).toBe(false)
    expect(isDontKnowAnswer('')).toBe(false)
  })

  it('does not collide with a real option', () => {
    expect(question.options).not.toContain(DONT_KNOW_ANSWER)
  })
})

describe('buildAnswerRecord', () => {
  it('records a correct answer', () => {
    expect(buildAnswerRecord(question, 'sind')).toEqual({
      question_id: 'q1',
      skill: 'grammar',
      difficulty: 'B2',
      correct: true,
      dont_know: false,
    })
  })

  it('records a wrong answer without a declared gap', () => {
    const record = buildAnswerRecord(question, 'haben')
    expect(record.correct).toBe(false)
    expect(record.dont_know).toBe(false)
  })

  it('records a declared gap as its own signal', () => {
    const record = buildAnswerRecord(question, DONT_KNOW_ANSWER)
    expect(record.correct).toBe(false)
    expect(record.dont_know).toBe(true)
  })
})
