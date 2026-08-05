'use client'

import { useEffect, useEffectEvent, useId, useRef } from 'react'
import { useTranslations } from 'next-intl'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  confirming?: boolean
  error?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel,
  danger = false,
  confirming = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const tCommon = useTranslations('common')
  const titleId = useId()
  const descriptionId = useId()
  const cancelRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelIfIdle = useEffectEvent(() => {
    if (!confirming) onCancel()
  })
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    cancelRef.current?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') cancelIfIdle()
      if (e.key !== 'Tab') return
      const controls = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
      )
      if (!controls?.length) {
        e.preventDefault()
        return
      }
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      opener?.focus()
    }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{
        backgroundColor: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(2px)',
      }}
      onClick={() => !confirming && onCancel()}
    >
      <div
        ref={dialogRef}
        className="border-fl-border bg-fl-surface w-full max-w-sm border shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        {/* Header */}
        <div className="border-fl-border flex items-center gap-2 border-b px-6 py-4">
          <span
            className={`text-fl-label ${danger ? 'text-fl-error-fg' : 'text-fl-muted-2'}`}
          >
            ●
          </span>
          <span
            id={titleId}
            className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase"
          >
            {title}
          </span>
        </div>

        {/* Body */}
        <div className="px-6 py-6">
          <p
            id={descriptionId}
            className="text-fl-muted-0 font-mono text-xs leading-relaxed"
          >
            {message}
          </p>
          {error && (
            <p role="alert" className="text-fl-error-fg mt-3 font-mono text-xs">
              {error}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2 px-6 pb-6">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={confirming}
            className="border-fl-border text-fl-label text-fl-muted-2 hover:border-fl-border-2 hover:text-fl-fg flex-1 border py-3 font-mono font-bold tracking-widest uppercase transition-colors"
          >
            {cancelLabel ?? tCommon('cancel')}
          </button>
          <button
            onClick={onConfirm}
            disabled={confirming}
            aria-busy={confirming}
            className={`text-fl-label flex-1 py-3 font-mono font-bold tracking-widest uppercase transition-colors ${
              danger
                ? 'bg-fl-error text-fl-fg-bright hover:bg-fl-error-hover'
                : 'bg-fl-fg text-fl-bg hover:bg-fl-fg-bright'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
