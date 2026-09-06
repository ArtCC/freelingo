'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { apiFetch } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SaveState = 'idle' | 'saving' | 'saved' | 'exists' | 'error'

export interface TooltipPos {
  x: number
  y: number
}

// ---------------------------------------------------------------------------
// WordTooltip component
// ---------------------------------------------------------------------------

export function WordTooltip({
  word,
  pos,
  saveState,
  onSave,
  onDismiss,
  labels,
}: {
  word: string
  pos: TooltipPos
  saveState: SaveState
  onSave: () => void
  onDismiss: () => void
  labels: {
    saveWord: string
    wordSaved: string
    wordAlreadySaved: string
    wordSaveError: string
  }
}) {
  return (
    <div
      style={{ left: pos.x, top: pos.y }}
      className="pointer-events-auto fixed z-50 -translate-x-1/2 -translate-y-full"
    >
      <div className="border-fl-border bg-fl-surface flex items-center gap-3 border px-3 py-2 font-mono text-xs shadow-lg">
        <span className="text-fl-fg font-bold">{word}</span>
        {saveState === 'idle' && (
          <button
            onClick={onSave}
            className="text-fl-muted-2 hover:text-fl-fg border-fl-border border px-2 py-0.5 tracking-widest uppercase transition-colors"
          >
            {labels.saveWord}
          </button>
        )}
        {saveState === 'saving' && (
          <span className="text-fl-muted-3 animate-pulse tracking-widest uppercase">
            ...
          </span>
        )}
        {saveState === 'saved' && (
          <span className="tracking-widest text-green-400 uppercase">
            ✓ {labels.wordSaved}
          </span>
        )}
        {saveState === 'exists' && (
          <span className="text-fl-muted-2 tracking-widest uppercase">
            ✓ {labels.wordAlreadySaved}
          </span>
        )}
        {saveState === 'error' && (
          <span className="tracking-widest text-red-400 uppercase">
            {labels.wordSaveError}
          </span>
        )}
        <button
          onClick={onDismiss}
          className="text-fl-muted-3 hover:text-fl-fg ml-1 transition-colors"
          aria-label="dismiss"
        >
          ✕
        </button>
      </div>
      {/* Arrow */}
      <div className="border-t-fl-border mx-auto mt-px h-0 w-0 border-x-4 border-t-4 border-x-transparent" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// useWordSave hook — encapsulates word-selection state & save logic
// ---------------------------------------------------------------------------

export function useWordSave() {
  const [selectedWord, setSelectedWord] = useState<string | null>(null)
  const [selectedContext, setSelectedContext] = useState('')
  const [selectedCefrLevel, setSelectedCefrLevel] = useState('B1')
  const [tooltipPos, setTooltipPos] = useState<TooltipPos>({ x: 0, y: 0 })
  const [saveState, setSaveState] = useState<SaveState>('idle')
  // Every new selection (or dismissal) bumps this id. A save request captures the
  // id it started with and ignores its response if the selection changed meanwhile,
  // so a slow save for word A can never mark word B as saved.
  const selectionIdRef = useRef(0)
  const dismissTimerRef = useRef<number | null>(null)

  const clearDismissTimer = useCallback(() => {
    if (dismissTimerRef.current !== null) {
      window.clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const dismissTooltip = useCallback(() => {
    selectionIdRef.current++
    clearDismissTimer()
    setSelectedWord(null)
    setSaveState('idle')
    window.getSelection()?.removeAllRanges()
  }, [clearDismissTimer])

  useEffect(() => clearDismissTimer, [clearDismissTimer])

  function handleTextSelection(context: string, cefrLevel = 'B1') {
    window.setTimeout(() => {
      const selection = window.getSelection()
      if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
        return
      }

      const raw = selection.toString().trim()
      // Accept only single words (no whitespace)
      if (!raw || /\s/.test(raw)) return

      const range = selection.getRangeAt(0)
      const rect = range.getBoundingClientRect()
      selectionIdRef.current++
      clearDismissTimer()
      setSelectedContext(context)
      setSelectedCefrLevel(cefrLevel)
      setSelectedWord(raw)
      setSaveState('idle')
      setTooltipPos({
        x: rect.left + rect.width / 2,
        y: Math.max(rect.top - 8, 56),
      })
    }, 0)
  }

  async function handleSaveWord() {
    if (!selectedWord) return
    const selectionId = selectionIdRef.current
    setSaveState('saving')
    try {
      const res = await apiFetch('/api/flashcards/from-word', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word: selectedWord,
          context: selectedContext,
          cefr_level: selectedCefrLevel,
        }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      if (selectionId !== selectionIdRef.current) return
      setSaveState(data.already_saved ? 'exists' : 'saved')
      clearDismissTimer()
      dismissTimerRef.current = window.setTimeout(() => {
        dismissTimerRef.current = null
        if (selectionId === selectionIdRef.current) dismissTooltip()
      }, 1500)
    } catch {
      if (selectionId !== selectionIdRef.current) return
      setSaveState('error')
    }
  }

  return {
    selectedWord,
    tooltipPos,
    saveState,
    handleTextSelection,
    handleSaveWord,
    dismissTooltip,
  }
}
