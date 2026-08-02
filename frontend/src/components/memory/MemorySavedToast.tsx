'use client'

import { useTranslations } from 'next-intl'

export function MemorySavedToast({
  visible,
  announcementId,
}: {
  visible: boolean
  announcementId: number
}) {
  const t = useTranslations('common')
  if (!visible) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 top-16 z-50 flex justify-center px-4">
      <div
        key={announcementId}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="border-fl-border bg-fl-surface text-fl-muted-1 animate-in fade-in slide-in-from-top-2 border px-4 py-3 font-mono text-xs shadow-lg"
      >
        <span>{t('memorySavedToast')}</span>
      </div>
    </div>
  )
}
