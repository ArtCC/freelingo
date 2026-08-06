'use client'

import { useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Megaphone, X } from 'lucide-react'

import { apiFetch } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { useConfigStore } from '@/store/config'

export function DashboardAnnouncement() {
  const locale = useLocale()
  const t = useTranslations('dashboard')
  const banner = useConfigStore((state) => state.dashboardBanner)
  const dismissedRevision = useAuthStore(
    (state) => state.user?.dismissed_dashboard_banner_revision
  )
  const setDismissedRevision = useAuthStore(
    (state) => state.setDismissedDashboardBannerRevision
  )
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(false)

  if (!banner || dismissedRevision === banner.revision) return null

  const translation =
    banner.translations[locale] ??
    banner.translations.en ??
    Object.values(banner.translations)[0]

  if (!translation) return null

  async function dismiss() {
    setPending(true)
    setError(false)
    try {
      const response = await apiFetch('/api/dashboard-banner/dismiss', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: banner!.revision }),
      })
      if (!response.ok) throw new Error('dismiss failed')
      setDismissedRevision(banner!.revision)
    } catch {
      setError(true)
    } finally {
      setPending(false)
    }
  }

  return (
    <section
      aria-labelledby="dashboard-announcement-title"
      className="border-fl-accent/50 bg-fl-accent/5 relative mb-6 border p-5 pr-14"
    >
      <div className="flex gap-3">
        <Megaphone
          className="text-fl-accent mt-0.5 size-5 shrink-0"
          aria-hidden="true"
        />
        <div className="min-w-0">
          <h2
            id="dashboard-announcement-title"
            className="text-fl-fg font-mono text-lg font-bold whitespace-pre-wrap"
          >
            {translation.title}
          </h2>
          <p className="text-fl-accent mt-1 font-mono text-xs font-bold tracking-wide whitespace-pre-wrap">
            {translation.subtitle}
          </p>
          <p className="text-fl-muted-1 mt-3 font-mono text-sm leading-relaxed whitespace-pre-wrap">
            {translation.description}
          </p>
          {error && (
            <p role="alert" className="text-fl-error mt-3 font-mono text-xs">
              {t('announcementDismissError')}
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={dismiss}
        disabled={pending}
        aria-label={t('announcementDismiss')}
        className="text-fl-muted-2 hover:text-fl-fg absolute top-3 right-3 inline-flex size-9 items-center justify-center transition-colors disabled:cursor-wait disabled:opacity-40"
      >
        <X className="size-5" aria-hidden="true" />
      </button>
    </section>
  )
}
