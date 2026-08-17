'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslations, useMessages } from 'next-intl'
import { CircleDot, Sparkles } from 'lucide-react'

const WHATS_NEW_VERSION = 'v1.8.40'
const STORAGE_KEY = `fl_whats_new_seen_${WHATS_NEW_VERSION}`
const TOUR_KEY = 'fl_tour_done'

export default function WhatsNew() {
  const t = useTranslations('whatsNew')
  const messages = useMessages()
  const [visible, setVisible] = useState(false)

  // Derive entries from raw messages — avoids relying on next-intl throwing on
  // missing keys (it doesn't: it returns the key path as a string instead).
  const entries = useMemo(() => {
    const ns = ((messages as Record<string, unknown>)['whatsNew'] ??
      {}) as Record<string, unknown>
    return Object.keys(ns)
      .filter((k) => /^entry\d+$/.test(k))
      .sort((a, b) => parseInt(a.slice(5)) - parseInt(b.slice(5)))
      .map((k) => {
        const entry = ns[k] as { label: string; desc: string }
        return { key: k, label: entry.label, desc: entry.desc }
      })
  }, [messages])

  useEffect(() => {
    const tourDone = localStorage.getItem(TOUR_KEY)
    const seen = localStorage.getItem(STORAGE_KEY)
    if (tourDone && !seen) {
      setVisible(true)
    }
  }, [])

  const dismiss = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1')
    setVisible(false)
  }, [])

  if (!visible) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="bg-fl-bg/80 absolute inset-0 backdrop-blur-sm"
        onClick={dismiss}
      />

      {/* Modal */}
      <div className="border-fl-border bg-fl-surface relative z-10 w-full max-w-md border shadow-2xl">
        {/* Header */}
        <div className="border-fl-border flex items-center gap-3 border-b px-5 pt-5 pb-4">
          <Sparkles
            className="text-fl-accent h-[1.125rem] w-[1.125rem]"
            aria-hidden="true"
          />
          <div>
            <p className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
              {t('title')}
            </p>
            <p className="text-fl-hint text-fl-muted-4 font-mono tracking-widest">
              {t('version')}
            </p>
          </div>
        </div>

        {/* Entries */}
        <div className="max-h-[50vh] space-y-5 overflow-y-auto px-5 py-5">
          {entries.map((entry, idx) => (
            <div key={idx} className="flex gap-3">
              <CircleDot
                className="text-fl-accent mt-0.5 h-3.5 w-3.5 shrink-0"
                aria-hidden="true"
              />
              <div>
                <p className="text-fl-label text-fl-muted-2 mb-1 font-mono tracking-widest uppercase">
                  {entry.label}
                </p>
                <p className="text-fl-muted-1 font-mono text-xs leading-relaxed">
                  {t.rich(`${entry.key}.desc`, {
                    bold: (chunks) => (
                      <strong className="text-fl-muted-2 font-semibold">
                        {chunks}
                      </strong>
                    ),
                  })}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-fl-border flex justify-end border-t px-5 pt-3 pb-5">
          <button
            onClick={dismiss}
            className="text-fl-label bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 px-5 py-2 font-mono tracking-widest uppercase transition-colors"
          >
            {t('cta')} →
          </button>
        </div>
      </div>
    </div>
  )
}
