'use client'

import { useEffect, useState, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { apiFetch } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { AudioPlayer } from '@/components/ui/AudioPlayer'
import { VoiceRecorder } from '@/components/ui/VoiceRecorder'
import { CEFR_LEVELS } from '@/data/curriculum'

interface CardData {
  id: number
  word: string
  definition: string
  example_sentence: string
  translation: string
  ease_factor: number
  interval: number
  repetitions: number
}

const QUALITY_BUTTONS = [
  { label: 'BLACKOUT', q: 0, color: '#ff5555' },
  { label: 'WRONG', q: 1, color: '#ff8855' },
  { label: 'HARD', q: 3, color: 'var(--fl-muted-1)' },
  { label: 'GOOD', q: 4, color: 'var(--fl-muted-0)' },
  { label: 'PERFECT', q: 5, color: 'var(--fl-fg)' },
]

export default function FlashcardsPage() {
  const t = useTranslations('flashcards')
  const tCommon = useTranslations('common')
  const user = useAuthStore((s) => s.user)
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
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadDue() }, [loadDue])

  async function reviewCard(quality: number) {
    if (cards.length === 0) return
    const card = cards[current]
    await apiFetch(`/api/flashcards/${card.id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quality }),
    })
    if (current < cards.length - 1) {
      setCurrent(current + 1)
      setFlipped(false)
    } else {
      await loadDue()
    }
  }

  async function handleSpeakingTranscription(transcription: string) {
    if (cards.length === 0) return
    const card = cards[current]
    const norm = (s: string) => s.trim().toLowerCase().replace(/[^a-z0-9 ]/g, '')
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
          native_language: user?.native_language ?? 'es',
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
      setGenError(err instanceof Error ? err.message : 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span className="font-mono text-xs text-fl-muted-3 tracking-widest uppercase animate-pulse">{tCommon('loading')}</span>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-fl-label text-fl-muted-3">●</span>
          <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">{t('title')}</span>
          <span className="font-mono text-fl-hint text-fl-muted-2 tracking-widest">— {total} {t('total')} · {cards.length} {t('due')}</span>
        </div>
        <button
          onClick={() => setShowGenerate(!showGenerate)}
          className={`border px-4 py-2 font-mono text-fl-label tracking-widest uppercase transition-colors ${showGenerate
            ? 'border-fl-border-2 text-fl-fg'
            : 'border-fl-border text-fl-muted-2 hover:text-fl-fg hover:border-fl-border-2'
            }`}
        >
          + {t('generateBtn')}
        </button>
      </div>

      {/* Generate panel */}
      {showGenerate && (
        <div className="border border-fl-border bg-fl-surface">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-fl-border">
            <span className="text-fl-label text-fl-muted-3">●</span>
            <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">{t('generate')}</span>
          </div>
          {genError && (
            <div className="mx-5 mt-4 border border-fl-error/40 px-4 py-3 font-mono text-xs text-fl-error-fg">✕ {genError}</div>
          )}
          <form onSubmit={generateCards} className="p-5 space-y-3">
            <div>
              <label className="block font-mono text-fl-label tracking-widest text-fl-muted-3 uppercase mb-2">{t('topic')}</label>
              <input
                type="text"
                value={genTopic}
                onChange={(e) => setGenTopic(e.target.value)}
                required
                placeholder={t('topicPlaceholder')}
                className="w-full bg-fl-bg border border-fl-border px-4 py-3 font-mono text-sm text-fl-fg placeholder:text-fl-border-2 focus:outline-none focus:border-fl-border-2 transition-colors"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-mono text-fl-label tracking-widest text-fl-muted-3 uppercase mb-2">{t('count')}</label>
                <select
                  value={genCount}
                  onChange={(e) => setGenCount(Number(e.target.value))}
                  className="w-full bg-fl-bg border border-fl-border px-4 py-3 font-mono text-sm text-fl-fg focus:outline-none focus:border-fl-border-2 appearance-none"
                >
                  {[5, 10, 15, 20].map(n => <option key={n} value={n}>{n} {t('cards')}</option>)}
                </select>
              </div>
              <div>
                <label className="block font-mono text-fl-label tracking-widest text-fl-muted-3 uppercase mb-2">{t('level')}</label>
                <select
                  value={genCefr}
                  onChange={(e) => setGenCefr(e.target.value)}
                  className="w-full bg-fl-bg border border-fl-border px-4 py-3 font-mono text-sm text-fl-fg focus:outline-none focus:border-fl-border-2 appearance-none"
                >
                  {CEFR_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
            </div>
            <button
              type="submit"
              disabled={generating || !genTopic.trim()}
              className="w-full bg-fl-accent text-fl-accent-fg font-mono text-xs font-bold tracking-widest uppercase py-3 hover:bg-fl-accent/90 disabled:opacity-40 transition-colors"
            >
              {generating ? `— ${t('generating')}` : `— ${t('submit')}`}
            </button>
          </form>
        </div>
      )}

      {/* No cards */}
      {cards.length === 0 && (
        <div className="border border-fl-border bg-fl-surface px-6 py-10 text-center">
          <p className="font-mono text-sm text-fl-muted-1">{t('noDue')}</p>
          {total === 0 && (
            <p className="font-mono text-xs text-fl-muted-2 mt-2">Use <span className="text-fl-muted-1">+ Generate</span> to create your first cards with AI</p>
          )}
          <button
            onClick={loadDue}
            className="mt-6 border border-fl-border px-6 py-2 font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase hover:text-fl-fg hover:border-fl-border-2 transition-colors"
          >
            — {t('refresh')}
          </button>
        </div>
      )}

      {/* Card review */}
      {cards.length > 0 && (
        <>
          <div className="flex items-center justify-between font-mono text-fl-label text-fl-muted-3 tracking-widest uppercase">
            <span>{current + 1} / {cards.length} due</span>
            {/* Mode toggle */}
            <div className="flex gap-1">
              <button
                onClick={() => { setSpeakingMode(false); setFlipped(false) }}
                className={`border px-3 py-1 text-fl-hint tracking-widest transition-colors ${!speakingMode ? 'border-fl-border-2 text-fl-fg' : 'border-fl-border text-fl-muted-3 hover:text-fl-muted-1'}`}
              >
                {t('standardMode')}
              </button>
              <button
                onClick={() => { setSpeakingMode(true); setFlipped(false) }}
                className={`border px-3 py-1 text-fl-hint tracking-widest transition-colors ${speakingMode ? 'border-fl-border-2 text-fl-fg' : 'border-fl-border text-fl-muted-3 hover:text-fl-muted-1'}`}
              >
                {t('speakingMode')}
              </button>
            </div>
          </div>

          {/* ── Standard mode ── */}
          {!speakingMode && (
            <>
              <div
                className="min-h-[220px] border border-fl-border bg-fl-surface cursor-pointer select-none transition-colors hover:border-fl-border-2"
                onClick={() => setFlipped(!flipped)}
              >
                <div className="flex items-center justify-between px-6 py-4 border-b border-fl-border">
                  <div className="flex items-center gap-2">
                    <span className="text-fl-label text-fl-muted-3">●</span>
                    <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">
                      {flipped ? 'Definition' : 'Word'}
                    </span>
                  </div>
                  <span className="font-mono text-fl-hint text-fl-border-2 uppercase tracking-widest">
                    tap to {flipped ? 'hide' : 'reveal'}
                  </span>
                </div>

                <div className="flex flex-col items-center justify-center p-10 gap-4 text-center">
                  {!flipped ? (
                    <div className="flex items-center gap-3">
                      <p className="font-mono text-3xl font-bold text-fl-fg tracking-wide">{cards[current].word}</p>
                      <span onClick={(e) => e.stopPropagation()}>
                        <AudioPlayer text={cards[current].word} size="md" />
                      </span>
                    </div>
                  ) : (
                    <>
                      <p className="font-mono text-base text-fl-fg-2 leading-relaxed">{cards[current].definition}</p>
                      {cards[current].example_sentence && (
                        <p className="font-mono text-xs text-fl-muted-1 italic">{cards[current].example_sentence}</p>
                      )}
                      {cards[current].translation && (
                        <p className="font-mono text-fl-label text-fl-muted-3 tracking-widest border-t border-fl-border pt-3 mt-1 uppercase">{cards[current].translation}</p>
                      )}
                    </>
                  )}
                </div>
              </div>

              {flipped && (
                <div className="flex gap-2 flex-wrap">
                  {QUALITY_BUTTONS.map(({ label, q, color }) => (
                    <button
                      key={q}
                      onClick={() => reviewCard(q)}
                      className="flex-1 min-w-[80px] border border-fl-border py-3 font-mono text-fl-label tracking-widest uppercase transition-all hover:border-fl-border-2"
                      style={{ color }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ── Speaking mode ── */}
          {speakingMode && (
            <div className="border border-fl-border bg-fl-surface">
              <div className="flex items-center justify-between px-6 py-4 border-b border-fl-border">
                <div className="flex items-center gap-2">
                  <span className="text-fl-label text-fl-muted-3">●</span>
                  <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">Speaking</span>
                </div>
                <span className="font-mono text-fl-hint text-fl-border-2 uppercase tracking-widest">{t('sayWord')}</span>
              </div>

              <div className="flex flex-col items-center justify-center p-10 gap-5 text-center">
                <p className="font-mono text-base text-fl-fg-2 leading-relaxed">{cards[current].definition}</p>
                {cards[current].example_sentence && (
                  <p className="font-mono text-xs text-fl-muted-1 italic">{cards[current].example_sentence}</p>
                )}
                {cards[current].translation && (
                  <p className="font-mono text-fl-label text-fl-muted-3 tracking-widest border-t border-fl-border pt-3 mt-1 uppercase">{cards[current].translation}</p>
                )}
                <VoiceRecorder
                  onTranscription={handleSpeakingTranscription}
                  maxSeconds={5}
                  className="mt-2"
                />
              </div>
            </div>
          )}

          <p className="font-mono text-fl-hint text-fl-border-2 tracking-widest uppercase text-center">
            EF {cards[current].ease_factor.toFixed(2)} · Interval {cards[current].interval}d · Rep {cards[current].repetitions}
          </p>
        </>
      )}
    </div>
  )
}
