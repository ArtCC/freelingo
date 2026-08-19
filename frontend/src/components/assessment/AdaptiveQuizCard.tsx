'use client'

import { useTranslations } from 'next-intl'
import type { AssessmentQuestion } from '@/data/types'
import { TargetLanguageText } from '@/components/TargetLanguageText'
import { DONT_KNOW_ANSWER } from '@/lib/assessment-answers'

interface Props {
  question: AssessmentQuestion
  questionNumber: number
  totalQuestions: number
  onAnswer: (answer: string) => void
  languageCode?: string | null
}

export default function AdaptiveQuizCard({
  question,
  questionNumber,
  totalQuestions,
  onAnswer,
  languageCode,
}: Props) {
  const t = useTranslations('assessment')
  const progress = Math.round((questionNumber / totalQuestions) * 100)

  const skillLabelMap: Record<string, string> = {
    grammar: t('skills.grammar'),
    vocabulary: t('skills.vocabulary'),
    reading: t('skills.reading'),
  }

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6">
      <div className="border-fl-border bg-fl-surface w-full max-w-lg border">
        {/* Header */}
        <div className="border-fl-border flex items-center justify-between border-b px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="text-fl-label text-fl-muted-3">●</span>
            <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
              {t('step2', { questionNumber, totalQuestions })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-fl-hint text-fl-muted-3 border-fl-border border px-2 py-1 font-mono tracking-widest uppercase">
              {question.difficulty}
            </span>
            <span className="text-fl-hint text-fl-muted-3 border-fl-border border px-2 py-1 font-mono tracking-widest uppercase">
              {skillLabelMap[question.skill] ?? question.skill}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="bg-fl-border h-px">
          <div
            className="bg-fl-fg h-px transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Question */}
        <div className="space-y-6 p-8">
          <TargetLanguageText
            as="p"
            languageCode={languageCode}
            className="text-fl-fg"
          >
            {question.question}
          </TargetLanguageText>

          {/* Options */}
          <div className="space-y-2">
            {question.options.map((option, i) => {
              const labels = ['A', 'B', 'C', 'D']
              return (
                <button
                  key={option}
                  onClick={() => onAnswer(option)}
                  className="border-fl-border text-fl-muted-1 hover:border-fl-border-2 hover:text-fl-fg hover:bg-fl-surface-2 flex w-full items-start gap-3 border px-4 py-3 text-left transition-colors"
                >
                  <span className="text-fl-label text-fl-muted-3 shrink-0 font-mono">
                    {labels[i]}.
                  </span>
                  <TargetLanguageText languageCode={languageCode}>
                    {option}
                  </TargetLanguageText>
                </button>
              )
            })}
          </div>

          {/* Declared gap — kept apart from A-D so it does not read as a fifth option */}
          <button
            onClick={() => onAnswer(DONT_KNOW_ANSWER)}
            className="text-fl-label text-fl-muted-4 hover:text-fl-muted-2 w-full font-mono tracking-widest uppercase transition-colors"
          >
            {t('dontKnow')}
          </button>
        </div>
      </div>
    </div>
  )
}
