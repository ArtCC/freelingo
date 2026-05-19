'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'

interface PricingSectionProps {
  stripeEnabled: boolean
  trialDays: number
  hasSession: boolean
}

export default function PricingSection({ stripeEnabled, trialDays, hasSession }: PricingSectionProps) {
  const tBilling = useTranslations('billing')
  const tCommon = useTranslations('common')
  // null = checking (only when hasSession=true), true = subscribed (hide pricing), false = show pricing
  const [subscribed, setSubscribed] = useState<boolean | null>(hasSession ? null : false)

  useEffect(() => {
    if (!hasSession) return
    async function checkSubscription() {
      try {
        const refreshRes = await fetch('/api/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        })
        if (!refreshRes.ok) { setSubscribed(false); return }
        const { access_token } = await refreshRes.json()

        const meRes = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` },
          credentials: 'include',
        })
        if (!meRes.ok) { setSubscribed(false); return }
        const me = await meRes.json()
        const status: string = me.subscription_status ?? 'none'
        setSubscribed(status === 'active' || status === 'trialing')
      } catch {
        setSubscribed(false)
      }
    }
    checkSubscription()
  }, [hasSession])

  if (!stripeEnabled) return null

  // Loading state: show full-screen overlay while verifying subscription
  if (subscribed === null) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-fl-bg/80 backdrop-blur-sm" />
        <span className="relative font-mono text-xs tracking-widest text-fl-muted-2 uppercase animate-pulse">
          {tCommon('loading')}
        </span>
      </div>
    )
  }

  if (subscribed) return null

  return (
    <section className="max-w-5xl mx-auto px-6 pb-24 w-full">
      <div className="text-center mb-10">
        <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase mb-4 block">
          {tBilling('pricingLabel')}
        </span>
        <h2 className="font-mono text-base font-bold text-fl-fg mb-2">
          {tBilling('pricingTitle')}
        </h2>
        <p className="font-mono text-xs text-fl-muted-1 tracking-widest">
          {tBilling('pricingDesc', { days: trialDays })}
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Free plan */}
        <div className="border border-fl-border bg-fl-surface p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2 pb-3 border-b border-fl-border">
            <span className="text-fl-muted-2 text-sm">○</span>
            <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">
              {tBilling('planFreeName')}
            </span>
          </div>
          <p className="font-mono text-sm text-fl-muted-2 invisible" aria-hidden="true">&nbsp;</p>
          <p className="font-mono text-xl font-bold text-fl-fg invisible" aria-hidden="true">&nbsp;</p>
          <ul className="flex flex-col gap-1.5">
            {['f1', 'f2', 'f3', 'f4', 'f5'].map((k) => (
              <li key={k} className="font-mono text-xs text-fl-muted-1 flex items-center gap-2">
                <span className="text-fl-accent">✓</span> {tBilling(`freeFeature.${k}`)}
              </li>
            ))}
          </ul>
        </div>

        {/* Monthly plan */}
        <div className="border border-fl-border bg-fl-surface p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-fl-border">
            <div className="flex items-center gap-2">
              <span className="text-fl-muted-2 text-sm">◎</span>
              <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">
                {tBilling('planMonthlyName')}
              </span>
            </div>
            <span className="font-mono text-fl-hint text-fl-accent border border-fl-accent/30 px-2 py-0.5 uppercase tracking-widest">
              {tBilling('trialBadge')}
            </span>
          </div>
          <p className="font-mono text-sm text-fl-muted-2 line-through">19.95 € / {tBilling('month')}</p>
          <p className="font-mono text-xl font-bold text-fl-fg">
            14.95<span className="text-sm text-fl-muted-1"> € / {tBilling('month')}</span>
          </p>
          <ul className="flex flex-col gap-1.5">
            {['f1', 'f2', 'f3', 'f4', 'f5'].map((k) => (
              <li key={k} className="font-mono text-xs text-fl-muted-1 flex items-center gap-2">
                <span className="text-fl-accent">✓</span> {tBilling(`freeFeature.${k}`)}
              </li>
            ))}
          </ul>
          <p className="font-mono text-fl-hint text-fl-muted-2 tracking-widest uppercase border-t border-fl-border pt-3">
            {tBilling('everythingFree')}
          </p>
          <ul className="flex flex-col gap-1.5">
            {['feature1', 'feature2', 'feature3', 'feature4'].map((k) => (
              <li key={k} className="font-mono text-xs text-fl-muted-1 flex items-center gap-2">
                <span className="text-fl-accent">✓</span> {tBilling(`planFeature.${k}`)}
              </li>
            ))}
          </ul>
        </div>

        {/* Yearly plan */}
        <div className="border border-fl-accent/30 bg-fl-surface p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-fl-border">
            <div className="flex items-center gap-2">
              <span className="text-fl-muted-2 text-sm">▣</span>
              <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">
                {tBilling('planYearlyName')}
              </span>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="font-mono text-fl-hint text-fl-accent border border-fl-accent/30 px-2 py-0.5 uppercase tracking-widest">
                {tBilling('bestValue')}
              </span>
              <span className="font-mono text-fl-hint text-fl-accent border border-fl-accent/30 px-2 py-0.5 uppercase tracking-widest">
                {tBilling('trialBadge')}
              </span>
            </div>
          </div>
          <p className="font-mono text-sm text-fl-muted-2 line-through">199.50 € / {tBilling('year')}</p>
          <p className="font-mono text-xl font-bold text-fl-fg">
            149.50<span className="text-sm text-fl-muted-1"> € / {tBilling('year')}</span>
          </p>
          <ul className="flex flex-col gap-1.5">
            {['f1', 'f2', 'f3', 'f4', 'f5'].map((k) => (
              <li key={k} className="font-mono text-xs text-fl-muted-1 flex items-center gap-2">
                <span className="text-fl-accent">✓</span> {tBilling(`freeFeature.${k}`)}
              </li>
            ))}
          </ul>
          <p className="font-mono text-fl-hint text-fl-muted-2 tracking-widest uppercase border-t border-fl-border pt-3">
            {tBilling('everythingFree')}
          </p>
          <ul className="flex flex-col gap-1.5">
            {['feature1', 'feature2', 'feature3', 'feature4'].map((k) => (
              <li key={k} className="font-mono text-xs text-fl-muted-1 flex items-center gap-2">
                <span className="text-fl-accent">✓</span> {tBilling(`planFeature.${k}`)}
              </li>
            ))}
            <li className="font-mono text-xs text-fl-muted-1 flex items-center gap-2">
              <span className="text-fl-accent">✓</span> {tBilling('planFeature.feature5')}
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-8 text-center">
        <Link
          href={hasSession ? '/dashboard' : '/register'}
          className="inline-block font-mono text-xs font-bold tracking-widest uppercase py-3 px-10 bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 transition-colors"
        >
          — {tBilling('ctaRegister')}
        </Link>
      </div>

      {/* Open Source Banner */}
      <div className="mt-6 border border-fl-border bg-fl-surface px-8 py-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Image
            src="/github.svg"
            alt="GitHub"
            width={20}
            height={20}
            className="block dark:hidden opacity-80"
          />
          <Image
            src="/github_white.svg"
            alt="GitHub"
            width={20}
            height={20}
            className="hidden dark:block opacity-80"
          />
          <div className="text-left">
            <p className="font-mono text-xs font-bold text-fl-fg tracking-widest uppercase">
              {tBilling('openSourceTitle')}
            </p>
            <p className="font-mono text-fl-hint text-fl-muted-2 tracking-widest uppercase mt-0.5">
              {tBilling('openSourceDesc')}
            </p>
          </div>
        </div>
        <a
          href="https://github.com/ArtCC/freelingo"
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-xs font-bold tracking-widest uppercase px-6 py-2.5 border border-fl-border text-fl-muted-1 hover:text-fl-fg hover:border-fl-border-2 transition-colors whitespace-nowrap"
        >
          — {tBilling('openSourceCta')}
        </a>
      </div>
    </section>
  )
}
