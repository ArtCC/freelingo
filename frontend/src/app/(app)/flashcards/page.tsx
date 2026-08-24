'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { apiFetch } from '@/lib/api'
import { useLanguageStore } from '@/store/language'
import { AudioPlayer } from '@/components/ui/AudioPlayer'
import { VoiceRecorder } from '@/components/ui/VoiceRecorder'
import { PageLoading } from '@/components/ui/page-loading'
import { TargetLanguageText } from '@/components/TargetLanguageText'
import { CEFR_LEVELS } from '@/data/curriculum'

interface CardData {
  id: number
  study_plan_id: number
  word: string
  definition: string
  example_sentence: string
  translation: string
  ease_factor: number
  interval: number
  repetitions: number
  source?: string | null
}

export default function FlashcardsPage() {
  const t = useTranslations('flashcards')
  const tCommon = useTranslations('common')
  const activeLanguage = useLanguageStore((s) => s.activeLanguage)
  const [cards, setCards] = useState<CardData[]>([])
  const [current, setCurrent] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [showGenerate, setShowGenerate] = useState(false)
  const [genTopic, setGenTopic] = useState('')
  const [genCount, setGenCount] = useState(10)
  const [genCefr, setGenCefr] = useState('B1')
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState('')
  const [speakingMode, setSpeakingMode] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const reviewingRef = useRef(false)

  const loadDue = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/api/flashcards/due')
      if (res.ok) {
        const data = await res.json()
        setCards(data.due)
        setTotal(data.total)
        setCurrent(0)
        setFlipped(false)
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }, [])

  const activeLangCode = activeLanguage?.code

  useEffect(() => {
    loadDue()
  }, [loadDue, activeLangCode])

  async function reviewCard(quality: number) {
    if (cards.length === 0 || reviewingRef.current) return
    reviewingRef.current = true
    setReviewing(true)
    const card = cards[current]
    try {
      const response = await apiFetch(`/api/flashcards/${card.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality }),
      })
      if (!response.ok) return
      if (current < cards.length - 1) {
        setCurrent(current + 1)
        setFlipped(false)
      } else {
        await loadDue()
      }
    } catch {
      return
    } finally {
      reviewingRef.current = false
      setReviewing(false)
    }
  }

  async function handleSpeakingTranscription(transcription: string) {
    if (cards.length === 0) return
    const card = cards[current]
    const norm = (s: string) =>
      s
        .trim()
        .toLowerCase()
        .replace(/[\p{P}\p{S}\s]+/gu, '')
    const isCorrect = norm(transcription) === norm(card.word)
    await reviewCard(isCorrect ? 5 : 2)
  }

  async function generateCards(e: React.FormEvent) {
    e.preventDefault()
    if (!genTopic.trim()) return
    setGenerating(true)
    setGenError('')
    try {
      const res = await apiFetch('/api/flashcards/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: genTopic.trim(),
          count: genCount,
          cefr_level: genCefr,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Error ${res.status}`)
      }
      setShowGenerate(false)
      setGenTopic('')
      await loadDue()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      setGenError(
        msg === 'No active study plan found'
          ? tCommon('noActivePlan')
          : tCommon('errorMessage')
      )
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return <PageLoading />
  }

  const targetLanguageCode = activeLanguage?.code ?? 'en-GB'

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-fl-label text-fl-muted-3">●</span>
          <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
            {t('title')}
          </span>
          <span className="text-fl-hint text-fl-muted-2 font-mono tracking-widest">
            {total} {t('total')} · {cards.length} {t('due')}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/flashcards/vocabulary"
            className="text-fl-label border-fl-border text-fl-muted-2 hover:text-fl-fg hover:border-fl-border-2 border px-4 py-2 font-mono tracking-widest uppercase transition-colors"
          >
            {t('myVocabularyBtn')}
          </Link>
          <button
            onClick={() => {
              setShowGenerate(!showGenerate)
            }}
            className={`text-fl-label border px-4 py-2 font-mono tracking-widest uppercase transition-colors ${
              showGenerate
                ? 'border-fl-border-2 text-fl-fg'
                : 'border-fl-border text-fl-muted-2 hover:text-fl-fg hover:border-fl-border-2'
            }`}
          >
            + {t('generateBtn')}
          </button>
        </div>
      </div>

      {/* Generate panel */}
      {showGenerate && (
        <div className="border-fl-border bg-fl-surface border">
          <div className="border-fl-border flex items-center gap-2 border-b px-5 py-4">
            <span className="text-fl-label text-fl-muted-3">●</span>
            <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
              {t('generate')}
            </span>
          </div>
          {genError && (
            <div className="border-fl-error/40 text-fl-error-fg mx-5 mt-4 border px-4 py-3 font-mono text-xs">
              ✕ {genError}
            </div>
          )}
          <form onSubmit={generateCards} className="space-y-3 p-5">
            <div>
              <label className="text-fl-label text-fl-muted-3 mb-2 block font-mono tracking-widest uppercase">
                {t('topic')}
              </label>
              <input
                type="text"
                value={genTopic}
                onChange={(e) => setGenTopic(e.target.value)}
                required
                placeholder={t('topicPlaceholder')}
                className="bg-fl-bg border-fl-border text-fl-fg placeholder:text-fl-border-2 focus:border-fl-border-2 w-full border px-4 py-3 font-mono text-sm transition-colors focus:outline-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-fl-label text-fl-muted-3 mb-2 block font-mono tracking-widest uppercase">
                  {t('count')}
                </label>
                <select
                  value={genCount}
                  onChange={(e) => setGenCount(Number(e.target.value))}
                  className="bg-fl-bg border-fl-border text-fl-fg focus:border-fl-border-2 w-full appearance-none border px-4 py-3 font-mono text-sm focus:outline-none"
                >
                  {[5, 10, 15, 20].map((n) => (
                    <option key={n} value={n}>
                      {n} {t('cards')}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-fl-label text-fl-muted-3 mb-2 block font-mono tracking-widest uppercase">
                  {t('level')}
                </label>
                <select
                  value={genCefr}
                  onChange={(e) => setGenCefr(e.target.value)}
                  className="bg-fl-bg border-fl-border text-fl-fg focus:border-fl-border-2 w-full appearance-none border px-4 py-3 font-mono text-sm focus:outline-none"
                >
                  {CEFR_LEVELS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <button
              type="submit"
              disabled={generating || !genTopic.trim()}
              className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors disabled:opacity-40"
            >
              {generating ? t('generating') : t('submit')}
            </button>
          </form>
        </div>
      )}

      {/* No cards */}
      {cards.length === 0 && (
        <div className="border-fl-border bg-fl-surface border px-6 py-10 text-center">
          <p className="text-fl-muted-1 font-mono text-sm">{t('noDue')}</p>
          {total === 0 && (
            <p className="text-fl-muted-2 mt-2 font-mono text-xs">
              {t('noCardsHint')}
            </p>
          )}
          <button
            onClick={loadDue}
            className="border-fl-border text-fl-label text-fl-muted-2 hover:text-fl-fg hover:border-fl-border-2 mt-6 border px-6 py-2 font-mono tracking-widest uppercase transition-colors"
          >
            {t('refresh')}
          </button>
        </div>
      )}

      {/* Card review */}
      {cards.length > 0 && (
        <>
          <div className="text-fl-label text-fl-muted-3 flex items-center justify-between font-mono tracking-widest uppercase">
            <span>
              {current + 1} / {cards.length} due
            </span>
            {/* Mode toggle */}
            <div className="flex gap-1">
              <button
                disabled={reviewing}
                onClick={() => {
                  setSpeakingMode(false)
                  setFlipped(false)
                }}
                className={`text-fl-hint border px-3 py-1 tracking-widest transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${!speakingMode ? 'border-fl-border-2 text-fl-fg' : 'border-fl-border text-fl-muted-3 hover:text-fl-muted-1'}`}
              >
                {t('standardMode')}
              </button>
              <button
                disabled={reviewing}
                onClick={() => {
                  setSpeakingMode(true)
                  setFlipped(false)
                }}
                className={`text-fl-hint border px-3 py-1 tracking-widest transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${speakingMode ? 'border-fl-border-2 text-fl-fg' : 'border-fl-border text-fl-muted-3 hover:text-fl-muted-1'}`}
              >
                {t('speakingMode')}
              </button>
            </div>
          </div>

          {/* ── Standard mode ── */}
          {!speakingMode && (
            <>
              <div
                className="border-fl-border bg-fl-surface hover:border-fl-border-2 min-h-[220px] cursor-pointer border transition-colors select-none"
                onClick={() => setFlipped(!flipped)}
              >
                <div className="border-fl-border flex items-center justify-between border-b px-6 py-4">
                  <div className="flex items-center gap-2">
                    <span className="text-fl-label text-fl-muted-3">●</span>
                    <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
                      {flipped ? t('back') : t('front')}
                    </span>
                  </div>
                  <span className="text-fl-hint text-fl-border-2 font-mono tracking-widest uppercase">
                    {flipped ? t('tapToHide') : t('tapToReveal')}
                  </span>
                </div>

                <div className="flex flex-col items-center justify-center gap-4 p-10 text-center">
                  {!flipped ? (
                    <div className="flex items-center gap-3">
                      <TargetLanguageText
                        as="p"
                        languageCode={targetLanguageCode}
                        className="text-fl-fg text-3xl font-bold"
                      >
                        {cards[current].word}
                      </TargetLanguageText>
                      <span onClick={(e) => e.stopPropagation()}>
                        <AudioPlayer text={cards[current].word} size="md" />
                      </span>
                    </div>
                  ) : (
                    <>
                      <TargetLanguageText
                        as="p"
                        languageCode={targetLanguageCode}
                        className="text-fl-fg-2"
                      >
                        {cards[current].definition}
                      </TargetLanguageText>
                      {cards[current].example_sentence && (
                        <TargetLanguageText
                          as="p"
                          languageCode={targetLanguageCode}
                          className="text-fl-muted-1 italic"
                        >
                          {cards[current].example_sentence}
                        </TargetLanguageText>
                      )}
                      {cards[current].translation && (
                        <p className="text-fl-label text-fl-muted-3 border-fl-border mt-1 border-t pt-3 font-mono tracking-widest uppercase">
                          {cards[current].translation}
                        </p>
                      )}
                    </>
                  )}
                </div>
              </div>

              {flipped && (
                <div className="flex flex-wrap gap-2">
                  {[
                    { key: 'again', q: 0, color: '#ff5555' },
                    { key: 'hard', q: 3, color: 'var(--fl-muted-1)' },
                    { key: 'good', q: 4, color: 'var(--fl-muted-0)' },
                    { key: 'easy', q: 5, color: 'var(--fl-fg)' },
                  ].map(({ key, q, color }) => (
                    <button
                      key={q}
                      disabled={reviewing}
                      onClick={() => reviewCard(q)}
                      className="border-fl-border text-fl-label hover:border-fl-border-2 min-w-[80px] flex-1 border py-3 font-mono tracking-widest uppercase transition-all disabled:cursor-not-allowed disabled:opacity-50"
                      style={{ color }}
                    >
                      {t(key)}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ── Speaking mode ── */}
          {speakingMode && (
            <div className="border-fl-border bg-fl-surface border">
              <div className="border-fl-border flex items-center justify-between border-b px-6 py-4">
                <div className="flex items-center gap-2">
                  <span className="text-fl-label text-fl-muted-3">●</span>
                  <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
                    {t('speakingMode')}
                  </span>
                </div>
                <span className="text-fl-hint text-fl-border-2 font-mono tracking-widest uppercase">
                  {t('sayWord')}
                </span>
              </div>

              <div className="flex flex-col items-center justify-center gap-5 p-10 text-center">
                <TargetLanguageText
                  as="p"
                  languageCode={targetLanguageCode}
                  className="text-fl-fg-2"
                >
                  {cards[current].definition}
                </TargetLanguageText>
                {cards[current].example_sentence && (
                  <TargetLanguageText
                    as="p"
                    languageCode={targetLanguageCode}
                    className="text-fl-muted-1 italic"
                  >
                    {cards[current].example_sentence}
                  </TargetLanguageText>
                )}
                {cards[current].translation && (
                  <p className="text-fl-label text-fl-muted-3 border-fl-border mt-1 border-t pt-3 font-mono tracking-widest uppercase">
                    {cards[current].translation}
                  </p>
                )}
                <VoiceRecorder
                  studyPlanId={cards[current].study_plan_id}
                  onTranscription={handleSpeakingTranscription}
                  maxSeconds={5}
                  disabled={reviewing}
                  className="mt-2"
                />
              </div>
            </div>
          )}

          <p className="text-fl-hint text-fl-border-2 text-center font-mono tracking-widest uppercase">
            EF {cards[current].ease_factor.toFixed(2)} · {t('interval')}{' '}
            {cards[current].interval}d · {t('repetitions')}{' '}
            {cards[current].repetitions}
          </p>
        </>
      )}
    </div>
  )
}
