import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => 'en',
}))

import AdaptiveQuizCard from '@/components/assessment/AdaptiveQuizCard'
import { DONT_KNOW_ANSWER } from '@/lib/assessment-answers'
import type { AssessmentQuestion } from '@/data/types'

const question: AssessmentQuestion = {
  id: 'q1',
  skill: 'grammar',
  difficulty: 'B2',
  question: 'Wir ___ nach Berlin gefahren.',
  options: ['haben', 'sind', 'werden', 'seid'],
  correct: 'sind',
}

describe('AdaptiveQuizCard', () => {
  const onAnswer = vi.fn()

  beforeEach(() => {
    onAnswer.mockReset()
  })

  function renderCard() {
    render(
      <AdaptiveQuizCard
        question={question}
        questionNumber={1}
        totalQuestions={15}
        onAnswer={onAnswer}
      />
    )
  }

  it('offers a way out besides the four options', () => {
    renderCard()

    for (const option of question.options) {
      expect(screen.getByText(option)).toBeDefined()
    }
    expect(screen.getByText('dontKnow')).toBeDefined()
  })

  it('reports a chosen option as itself', () => {
    renderCard()

    fireEvent.click(screen.getByText('sind'))
    expect(onAnswer).toHaveBeenCalledWith('sind')
  })

  it('reports a declared gap instead of one of the options', () => {
    renderCard()

    fireEvent.click(screen.getByText('dontKnow'))
    expect(onAnswer).toHaveBeenCalledWith(DONT_KNOW_ANSWER)
    expect(onAnswer).not.toHaveBeenCalledWith(question.correct)
  })
})
