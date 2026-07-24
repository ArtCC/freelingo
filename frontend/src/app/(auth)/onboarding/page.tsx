'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Image from 'next/image'
import { useTranslations } from 'next-intl'
import { Loader2 } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { splitYearlyCta, type BillingInterval } from '@/lib/billing-copy'
import { mapUser } from '@/lib/mappers'
import { useAuthStore, isSubscribed, isFreemiumTrialActive } from '@/store/auth'
import { useConfigStore } from '@/store/config'
import { useLanguageStore } from '@/store/language'
import TargetLanguageSelector from '@/components/TargetLanguageSelector'
import { DEFAULT_TARGET_LANGUAGE } from '@/lib/target-languages'

const LEARNING_GOALS = [
  'travel',
  'work',
  'academic',
  'daily',
  'media',
  'emigration',
  'exams',
  'social',
] as const

type LearningGoal = (typeof LEARNING_GOALS)[number]

function getSelectedPlan(plan: string | null): BillingInterval | null {
  return plan === 'monthly' || plan === 'yearly' ? plan : null
}

export default function OnboardingPage() {
  const t = useTranslations('onboarding')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((s) => s.setUser)
  const user = useAuthStore((s) => s.user)
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const stripeTrialDays = useConfigStore((s) => s.stripeTrialDays)
  const priceMonthly = useConfigStore((s) => s.priceMonthly)
  const priceYearly = useConfigStore((s) => s.priceYearly)
  const loadConfig = useConfigStore((s) => s.load)
  const fetchLanguages = useLanguageStore((s) => s.fetchLanguages)
  const availableLanguageCodes = useLanguageStore(
    (s) => s.availableLanguageCodes
  )

  const isNewLanguage = searchParams.get('new') === 'true'
  const queryLanguage = searchParams.get('language')
  const selectedPlan = getSelectedPlan(searchParams.get('plan'))

  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [targetLanguage, setTargetLanguage] = useState(
    queryLanguage ?? DEFAULT_TARGET_LANGUAGE
  )
  const [selectedGoals, setSelectedGoals] = useState<LearningGoal[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [languagesLoaded, setLanguagesLoaded] = useState(false)
  const [checkoutLoading, setCheckoutLoading] =
    useState<BillingInterval | null>(null)
  const [checkoutError, setCheckoutError] = useState('')

  useEffect(() => {
    loadConfig()
    fetchLanguages().then(() => {
      setLanguagesLoaded(true)
      const codes = useLanguageStore.getState().availableLanguageCodes
      if (codes.length > 0 && !codes.includes(targetLanguage)) {
        setTargetLanguage(codes[0])
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchLanguages])

  function toggleGoal(goal: LearningGoal) {
    setSelectedGoals((prev) =>
      prev.includes(goal) ? prev.filter((g) => g !== goal) : [...prev, goal]
    )
  }

  async function handleStep1(e: React.FormEvent) {
    e.preventDefault()
    setStep(2)
  }

  const subscribed = isSubscribed(user, stripeEnabled)
  const showTrial = stripeEnabled && !subscribed
  const freemiumTrialActive = isFreemiumTrialActive(user, stripeEnabled)
  const totalSteps = showTrial || freemiumTrialActive ? 3 : 2

  async function handleStep2() {
    setLoading(true)
    setError('')
    try {
      const body: Record<string, unknown> = {
        target_language: targetLanguage,
        learning_goals: selectedGoals,
      }
      const res = await apiFetch('/api/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(t('saveFailed'))
      const updated = await res.json()
      const mapped = mapUser(updated, user)
      setUser(mapped)
      const trialActive = isFreemiumTrialActive(mapped, stripeEnabled)
      if (trialActive || showTrial) {
        setStep(3)
        setStep(3)
      } else {
        router.push('/dashboard')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('saveFailed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleCheckout(interval: BillingInterval) {
    setCheckoutLoading(interval)
    setCheckoutError('')
    try {
      if (!useAuthStore.getState().accessToken) {
        const refreshRes = await fetch('/api/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        })
        if (!refreshRes.ok) {
          router.push('/login')
          return
        }
        const { access_token } = await refreshRes.json()
        useAuthStore.getState().setTokens(access_token)
      }

      const res = await apiFetch('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: interval }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? t('trialError'))
      }
      const { url } = await res.json()
      window.location.assign(url)
    } catch (err: unknown) {
      setCheckoutError(err instanceof Error ? err.message : t('trialError'))
      setCheckoutLoading(null)
    }
  }

  const checkoutPlans: BillingInterval[] =
    selectedPlan === 'monthly' ? ['monthly', 'yearly'] : ['yearly', 'monthly']
  const trialEligible = !user?.trial_used
  const yearlyCta = splitYearlyCta(
    t(trialEligible ? 'trialCtaYearly' : 'trialCtaYearlyTrialUsed', {
      price: String(priceYearly),
    })
  )

  return (
    <div className="bg-fl-bg bg-dot-grid flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-10 flex flex-col items-center">
          <Image
            src="/logo.png"
            alt="FreeLingo"
            width={80}
            height={80}
            className="mb-4"
          />
          <h1 className="text-fl-fg font-mono text-xl font-bold tracking-widest uppercase">
            FreeLingo
          </h1>
          <p className="text-fl-caption text-fl-muted-2 mt-1 font-mono tracking-widest uppercase">
            {tCommon('tagline')}
          </p>
        </div>

        <div className="border-fl-border bg-fl-surface border p-8">
          {/* Step indicator */}
          <div className="border-fl-border mb-6 flex items-center justify-between gap-2 border-b pb-4">
            <div className="flex items-center gap-2">
              <span className="text-fl-label text-fl-muted-2">●</span>
              <span className="text-fl-muted-2 font-mono text-xs tracking-widest uppercase">
                {step === 1
                  ? isNewLanguage
                    ? t('newLanguageHeadline')
                    : t('title')
                  : step === 2
                    ? t('goals.title')
                    : t(
                        trialEligible
                          ? 'trialHeadline'
                          : 'trialHeadlineTrialUsed'
                      )}
              </span>
            </div>
            <span className="text-fl-hint text-fl-muted-4 font-mono tabular-nums">
              {step}/{totalSteps}
            </span>
          </div>

          {error && (
            <div className="border-fl-error/40 text-fl-error mb-5 border px-4 py-3 font-mono text-xs tracking-wide">
              ✕ {error}
            </div>
          )}

          {/* Step 1: Language */}
          {step === 1 && (
            <form onSubmit={handleStep1} className="space-y-6">
              <p className="text-fl-fg mb-4 font-mono text-sm">
                {isNewLanguage ? t('newLanguageSubtitle') : t('subtitle')}
              </p>
              <div>
                <label className="text-fl-label text-fl-muted-2 mb-3 block font-mono tracking-widest uppercase">
                  {t('chooseVariant')}
                </label>
                {!languagesLoaded ? (
                  <div className="border-fl-border text-fl-muted-2 border px-4 py-3 font-mono text-xs tracking-widest">
                    ...
                  </div>
                ) : availableLanguageCodes.length > 0 ? (
                  <TargetLanguageSelector
                    value={targetLanguage}
                    onChange={setTargetLanguage}
                    availableCodes={availableLanguageCodes}
                  />
                ) : (
                  <div className="space-y-3 text-center">
                    <p className="text-fl-muted-2 font-mono text-xs">
                      {t('saveFailed')}
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setLanguagesLoaded(false)
                        fetchLanguages()
                      }}
                      className="text-fl-label text-fl-accent font-mono text-xs tracking-widest uppercase underline"
                    >
                      {tCommon('retry')}
                    </button>
                  </div>
                )}
              </div>
              <button
                type="submit"
                className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors"
              >
                {tCommon('next')}
              </button>
            </form>
          )}

          {/* Step 2: Learning goals */}
          {step === 2 && (
            <div className="space-y-5">
              <p className="text-fl-fg font-mono text-sm">
                {t('goals.subtitle')}
              </p>
              <div className="grid grid-cols-2 gap-2">
                {LEARNING_GOALS.map((goal) => {
                  const active = selectedGoals.includes(goal)
                  return (
                    <button
                      key={goal}
                      type="button"
                      onClick={() => toggleGoal(goal)}
                      className={`text-fl-label border px-3 py-3 text-left font-mono tracking-widest uppercase transition-colors ${
                        active
                          ? 'border-fl-accent bg-fl-accent text-fl-accent-fg'
                          : 'border-fl-border text-fl-muted-2 hover:border-fl-border-2 hover:text-fl-fg'
                      }`}
                    >
                      {t(`goals.${goal}`)}
                    </button>
                  )
                })}
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={() => handleStep2()}
                className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors disabled:opacity-40"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
                    {tCommon('saving')}
                  </>
                ) : (
                  t('continue')
                )}
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => handleStep2()}
                className="text-fl-label text-fl-muted-4 hover:text-fl-muted-2 w-full py-1 font-mono tracking-widest uppercase transition-colors disabled:opacity-40"
              >
                {t('goals.skip')}
              </button>
            </div>
          )}

          {/* Step 3: Trial confirmation */}
          {step === 3 && freemiumTrialActive && (
            <div className="space-y-5 text-center">
              <div className="mb-2 flex justify-center">
                <span className="inline-flex h-12 w-12 items-center justify-center text-2xl">
                  ★
                </span>
              </div>
              <h2 className="text-fl-fg font-mono text-base font-bold">
                {t('freemiumTrialTitle')}
              </h2>
              <p className="text-fl-muted-1 font-mono text-xs leading-relaxed">
                {t('freemiumTrialDesc')}
              </p>
              <div className="border-fl-border bg-fl-surface-2 border px-4 py-3">
                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-left font-mono text-[0.65rem]">
                  <span className="text-fl-muted-2">
                    ✓ {t('freemiumChatLabel')}
                  </span>
                  <span className="text-fl-muted-2">
                    ✓ {t('freemiumVoiceLabel')}
                  </span>
                  <span className="text-fl-muted-2">
                    ✓ {t('freemiumListeningLabel')}
                  </span>
                  <span className="text-fl-muted-2">
                    ✓ {t('freemiumReadingLabel')}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => router.push('/dashboard')}
                className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors"
              >
                {t('goToDashboard')}
              </button>
              {stripeEnabled && (
                <button
                  type="button"
                  onClick={() => router.push('/dashboard')}
                  className="text-fl-label text-fl-muted-4 hover:text-fl-muted-2 w-full py-1 font-mono tracking-widest uppercase transition-colors"
                >
                  {t('upgradeLater')}
                </button>
              )}
            </div>
          )}

          {/* Step 3: Stripe subscription */}
          {step === 3 && !freemiumTrialActive && (
            <div className="space-y-5 text-center">
              <h2 className="text-fl-fg font-mono text-base font-bold">
                {t(trialEligible ? 'trialTitle' : 'trialTitleTrialUsed', {
                  days: stripeTrialDays,
                })}
              </h2>
              <p className="text-fl-muted-1 font-mono text-xs leading-relaxed">
                {t(trialEligible ? 'trialDesc' : 'trialDescTrialUsed', {
                  days: stripeTrialDays,
                })}
              </p>
              <div className="flex flex-col gap-3">
                {checkoutPlans.map((plan, index) => {
                  const isPrimary = index === 0
                  return (
                    <button
                      key={plan}
                      type="button"
                      disabled={checkoutLoading !== null}
                      onClick={() => handleCheckout(plan)}
                      className={`w-full py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors disabled:opacity-50 ${
                        isPrimary
                          ? 'bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90'
                          : 'border-fl-border text-fl-muted-1 hover:text-fl-fg hover:border-fl-border-2 border'
                      }`}
                    >
                      {checkoutLoading === plan ? (
                        '...'
                      ) : plan === 'monthly' ? (
                        t(
                          trialEligible
                            ? 'trialCtaMonthly'
                            : 'trialCtaMonthlyTrialUsed',
                          {
                            price: String(priceMonthly),
                          }
                        )
                      ) : (
                        <span className="flex flex-col items-center gap-0.5 leading-relaxed">
                          <span>{yearlyCta.main}</span>
                          {yearlyCta.savings && (
                            <span
                              className={`text-[0.68rem] ${
                                isPrimary
                                  ? 'text-fl-accent-fg/80'
                                  : 'text-fl-muted-3'
                              }`}
                            >
                              {yearlyCta.savings}
                            </span>
                          )}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
              {checkoutError && (
                <p className="text-fl-hint font-mono text-red-500">
                  {checkoutError}
                </p>
              )}
              <p className="text-fl-hint text-fl-muted-3 font-mono tracking-widest uppercase">
                {t(trialEligible ? 'trialNoCharge' : 'trialNoChargeTrialUsed')}
              </p>
              <button
                type="button"
                disabled={checkoutLoading !== null}
                onClick={() => router.push('/dashboard')}
                className="text-fl-label text-fl-muted-4 hover:text-fl-muted-2 w-full py-1 font-mono tracking-widest uppercase transition-colors disabled:opacity-40"
              >
                {t('trialSkip')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
