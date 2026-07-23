'use client'

import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { useFreemiumStore } from '@/store/freemium'
import { useAuthStore, isSubscribed, isFreemiumTrialActive } from '@/store/auth'
import { useConfigStore } from '@/store/config'

interface FreemiumQuotaBannerProps {
  feature: 'chat' | 'lessons' | 'listening' | 'reading' | 'voice'
  className?: string
}

export function FreemiumQuotaBanner({
  feature,
  className = '',
}: FreemiumQuotaBannerProps) {
  const t = useTranslations('freemium')
  const user = useAuthStore((s) => s.user)
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const status = useFreemiumStore((s) => s.status)
  const [trialDaysLeft, setTrialDaysLeft] = useState(0)

  const trial = isFreemiumTrialActive(user, stripeEnabled)

  useEffect(() => {
    if (trial && user?.freemium_trial_ends_at) {
      const endsAt = new Date(user.freemium_trial_ends_at)
      const days = Math.max(
        1,
        Math.ceil((endsAt.getTime() - Date.now()) / 86400000)
      )
      setTrialDaysLeft(days)
    }
  }, [trial, user?.freemium_trial_ends_at])

  if (!stripeEnabled) return null
  if (isSubscribed(user, stripeEnabled)) return null

  if (trial) {
    return (
      <div
        className={`border-fl-border bg-fl-surface flex items-center justify-between border px-3 py-2 font-mono text-xs ${className}`}
      >
        <span className="text-fl-muted-2">
          ★ {t('trialDaysLeft', { days: trialDaysLeft })}
        </span>
        <span className="text-fl-accent tracking-widest uppercase">
          {t('trialUnlimited')}
        </span>
      </div>
    )
  }

  if (!status) return null

  const limits: Record<
    string,
    { remaining: number; limit: number; label: string }
  > = {
    chat: {
      remaining: status.chat_remaining,
      limit: status.chat_limit,
      label: t('chatLabel'),
    },
    lessons: {
      remaining: status.lessons_remaining,
      limit: status.lessons_limit,
      label: t('lessonsLabel'),
    },
    listening: {
      remaining: status.listening_remaining,
      limit: status.listening_limit,
      label: t('listeningLabel'),
    },
    reading: {
      remaining: status.reading_remaining,
      limit: status.reading_limit,
      label: t('readingLabel'),
    },
    voice: {
      remaining: Math.ceil(status.voice_remaining_seconds / 60),
      limit: Math.ceil(status.voice_limit_seconds / 60),
      label: t('voiceLabel'),
    },
  }

  const info = limits[feature]
  if (!info) return null

  // Feature blocked entirely for free users (limit === 0)
  if (info.limit === 0) {
    return (
      <div
        className={`border-fl-border bg-fl-surface flex items-center justify-between border px-3 py-2 font-mono text-xs ${className}`}
      >
        <span className="text-fl-muted-2">{info.label}</span>
        <span className="text-fl-accent tracking-widest uppercase">
          {t('requiresSubscription')}
        </span>
      </div>
    )
  }

  const pct = info.limit > 0 ? (info.remaining / info.limit) * 100 : 100
  const low = pct <= 25

  return (
    <div
      className={`border-fl-border bg-fl-surface flex items-center justify-between border px-3 py-2 font-mono text-xs ${className}`}
    >
      <span className="text-fl-muted-2">
        {info.label}:{' '}
        <span className={low ? 'text-red-500' : 'text-fl-muted-1'}>
          {info.remaining}/{info.limit}
        </span>
      </span>
      {low && (
        <span className="text-fl-accent tracking-widest uppercase">
          {t('freeLimit')}
        </span>
      )}
    </div>
  )
}
