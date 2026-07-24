'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import {
  BookOpen,
  GraduationCap,
  Headphones,
  MessageSquare,
  Mic,
} from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { splitYearlyCta, type BillingInterval } from '@/lib/billing-copy'
import { useConfigStore } from '@/store/config'
import { useAuthStore, isSubscribed, needsPaymentRecovery } from '@/store/auth'

const PAYWALL_CONTEXT = {
  chat: {
    icon: MessageSquare,
    title: 'paywallChatTitle',
    desc: 'paywallChatDesc',
  },
  voice: {
    icon: Mic,
    title: 'paywallConversationTitle',
    desc: 'paywallConversationDesc',
  },
  listening: {
    icon: Headphones,
    title: 'paywallListeningTitle',
    desc: 'paywallListeningDesc',
  },
  reading: {
    icon: BookOpen,
    title: 'paywallReadingTitle',
    desc: 'paywallReadingDesc',
  },
  lessons: {
    icon: GraduationCap,
    title: 'paywallLessonsTitle',
    desc: 'paywallLessonsDesc',
  },
} as const

type FeatureContext = keyof typeof PAYWALL_CONTEXT

interface PaywallBannerProps {
  feature?: FeatureContext
  compact?: boolean
}

export function PaywallBanner({
  feature = 'chat',
  compact = false,
}: PaywallBannerProps) {
  const t = useTranslations('billing')
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const trialDays = useConfigStore((s) => s.stripeTrialDays)
  const priceMonthly = useConfigStore((s) => s.priceMonthly)
  const priceYearly = useConfigStore((s) => s.priceYearly)
  const [loading, setLoading] = useState<BillingInterval | null>(null)
  const [portalLoading, setPortalLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const paymentRecovery = needsPaymentRecovery(user)
  const yearlyCta = splitYearlyCta(
    t('planYearly', { price: String(priceYearly) })
  )

  if (!stripeEnabled || isSubscribed(user, stripeEnabled)) return null

  const context = PAYWALL_CONTEXT[feature] ?? PAYWALL_CONTEXT.chat
  const Icon = context.icon
  const trialEligible = !user?.trial_used

  async function handleCheckout(interval: BillingInterval) {
    setLoading(interval)
    setError(null)
    try {
      const res = await apiFetch('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: interval }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? t('checkoutError'))
      }
      const { url } = await res.json()
      window.location.assign(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('checkoutError'))
      setLoading(null)
    }
  }

  async function handleManageBilling() {
    setPortalLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/api/billing/portal', { method: 'POST' })
      if (!res.ok) throw new Error(t('portalError'))
      const { url } = await res.json()
      window.location.assign(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('portalError'))
      setPortalLoading(false)
    }
  }

  const containerClass = compact
    ? 'border-fl-border bg-fl-surface w-full border p-5 text-center'
    : 'flex min-h-[60vh] flex-col items-center justify-center px-6 py-16 text-center'

  return (
    <div className={containerClass}>
      {compact ? (
        <div className="border-fl-border bg-fl-surface mx-auto w-full max-w-md border p-8">
          <PaywallContent />
        </div>
      ) : (
        <div className="border-fl-border bg-fl-surface w-full max-w-md border p-8">
          <PaywallContent />
        </div>
      )}
    </div>
  )

  function PaywallContent() {
    return (
      <>
        <Icon
          className="text-fl-muted-2 mx-auto mb-4 h-6 w-6"
          aria-hidden="true"
        />

        <p className="text-fl-label text-fl-muted-2 mb-2 font-mono tracking-widest uppercase">
          {t('paywallLabel')}
        </p>
        <h2 className="text-fl-fg mb-3 font-mono text-base font-bold">
          {t(paymentRecovery ? 'premiumBannerPastDueTitle' : context.title)}
        </h2>
        <p className="text-fl-muted-1 mb-6 font-mono text-xs leading-relaxed">
          {paymentRecovery
            ? t('premiumBannerPastDueDesc')
            : t(
                context.desc ??
                  (trialEligible ? 'paywallDesc' : 'paywallDescTrialUsed'),
                { days: trialDays }
              )}
        </p>

        {paymentRecovery ? (
          <button
            onClick={handleManageBilling}
            disabled={portalLoading}
            className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full px-4 py-3 font-mono text-xs tracking-widest uppercase transition-colors disabled:opacity-50"
          >
            {portalLoading ? '...' : t('updatePayment')}
          </button>
        ) : (
          <div className="flex flex-col gap-3">
            <button
              onClick={() => handleCheckout('yearly')}
              disabled={loading !== null}
              className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full px-4 py-3 font-mono text-xs tracking-widest uppercase transition-colors disabled:opacity-50"
            >
              {loading === 'yearly' ? (
                '...'
              ) : (
                <span className="flex flex-col items-center gap-0.5 leading-relaxed">
                  <span>{yearlyCta.main}</span>
                  {yearlyCta.savings && (
                    <span className="text-fl-accent-fg/80 text-[0.68rem]">
                      {yearlyCta.savings}
                    </span>
                  )}
                </span>
              )}
            </button>
            <button
              onClick={() => handleCheckout('monthly')}
              disabled={loading !== null}
              className="border-fl-border text-fl-muted-1 hover:text-fl-fg hover:border-fl-border-2 w-full border px-4 py-3 font-mono text-xs tracking-widest uppercase transition-colors disabled:opacity-50"
            >
              {loading === 'monthly'
                ? '...'
                : t('planMonthly', { price: String(priceMonthly) })}
            </button>
          </div>
        )}

        {error && (
          <p className="text-fl-hint mt-4 font-mono text-red-500">{error}</p>
        )}

        {!paymentRecovery && (
          <p className="text-fl-hint text-fl-muted-3 mt-6 font-mono tracking-widest uppercase">
            {t(trialEligible ? 'paywallNoCharge' : 'paywallNoChargeTrialUsed')}
          </p>
        )}

        <button
          onClick={() => router.push('/dashboard')}
          className="text-fl-hint text-fl-muted-4 hover:text-fl-muted-2 mt-5 w-full font-mono tracking-widest uppercase transition-colors"
        >
          {t('paywallSkip')}
        </button>
      </>
    )
  }
}
