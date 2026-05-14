'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslations, useMessages } from 'next-intl'

const WHATS_NEW_VERSION = 'v1.4.16'
const STORAGE_KEY = `fl_whats_new_seen_${WHATS_NEW_VERSION}`
const TOUR_KEY = 'fl_tour_done'

const ENTRY_ICONS = ['◎', '▣', '△', '◇', '✦', '◈']

export default function WhatsNew() {
  const t = useTranslations('whatsNew')
  const messages = useMessages()
  const [visible, setVisible] = useState(false)

  // Derive entries from raw messages — avoids relying on next-intl throwing on
  // missing keys (it doesn't: it returns the key path as a string instead).
  const entries = useMemo(() => {
    const ns = ((messages as Record<string, unknown>)['whatsNew'] ?? {}) as Record<string, unknown>
    return Object.keys(ns)
      .filter(k => /^entry\d+$/.test(k))
      .sort((a, b) => parseInt(a.slice(5)) - parseInt(b.slice(5)))
      .map(k => {
        const entry = ns[k] as { label: string; desc: string }
        return { label: entry.label, desc: entry.desc }
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
        className="absolute inset-0 bg-fl-bg/80 backdrop-blur-sm"
        onClick={dismiss}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md border border-fl-border bg-fl-surface shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 pt-5 pb-4 border-b border-fl-border">
          <span className="text-fl-accent text-lg">✦</span>
          <div>
            <p className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">
              {t('title')}
            </p>
            <p className="font-mono text-fl-hint text-fl-muted-4 tracking-widest">
              {t('version')}
            </p>
          </div>
        </div>

        {/* Entries */}
        <div className="px-5 py-5 max-h-[50vh] overflow-y-auto space-y-5">
          {entries.map((entry, idx) => (
            <div key={idx} className="flex gap-3">
              <span className="text-fl-accent text-sm mt-0.5 shrink-0">
                {ENTRY_ICONS[idx % ENTRY_ICONS.length]}
              </span>
              <div>
                <p className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase mb-1">
                  {entry.label}
                </p>
                <p className="font-mono text-xs text-fl-muted-1 leading-relaxed">
                  {entry.desc}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex justify-end px-5 pb-5 pt-3 border-t border-fl-border">
          <button
            onClick={dismiss}
            className="font-mono text-fl-label tracking-widest uppercase px-5 py-2 bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 transition-colors"
          >
            {t('cta')} →
          </button>
        </div>
      </div>
    </div>
  )
}
