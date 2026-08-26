'use client'

import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import Image from 'next/image'
import { useTranslations } from 'next-intl'
import {
  Activity,
  BadgeCheck,
  CreditCard,
  Languages,
  Loader2,
  MailCheck,
  Settings2,
  User,
} from 'lucide-react'
import { AdminNav } from '@/components/admin/AdminNav'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { PageLoading } from '@/components/ui/page-loading'
import { apiFetch } from '@/lib/api'
import { getLanguageByCode } from '@/lib/target-languages'
import { useConfigStore } from '@/store/config'
import { type QuotaStatus } from '@/types/api'

interface LanguageStats {
  target_language: string
  cefr_level: string | null
  xp_total: number
  streak_current: number
  active_days: number
  lessons_completed: number
  exercises_correct: number
  exercises_total: number
}

interface UserStats {
  user_id: number
  current_cefr: string | null
  current_unit: string | null
  plan_duration_weeks: number | null
  completion_test_score: number | null
  xp_total: number
  streak_current: number
  active_days: number
  lessons_completed: number
  exercises_correct: number
  exercises_total: number
  chat_messages_sent: number
  tokens_total: number
  tokens_chat: number
  tokens_conversation: number
  per_language: LanguageStats[]
}

interface AdminUser {
  id: number
  username: string
  display_name: string
  email: string | null
  role: string
  native_language: string
  is_active: boolean
  is_verified: boolean
  subscription_status: string
  subscription_ends_at: string | null
  stripe_customer_id: string | null
  conversation_weekly_sessions: number
  conversation_daily_minutes: number
  conversation_weekly_minutes: number
  monthly_tokens_limit: number
}

type TabKey = 'profile' | 'languages' | 'activity' | 'quota' | 'subscription'
type PlanKey = 'none' | 'monthly' | 'yearly'

const tabs: {
  key: TabKey
  labelKey: string
  icon: typeof User
}[] = [
  { key: 'profile', labelKey: 'tabProfile', icon: User },
  { key: 'languages', labelKey: 'tabLanguages', icon: Languages },
  { key: 'activity', labelKey: 'tabActivity', icon: Activity },
  { key: 'quota', labelKey: 'tabQuota', icon: Settings2 },
  { key: 'subscription', labelKey: 'tabSubscription', icon: CreditCard },
]

function StatRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border-fl-border flex items-center justify-between gap-4 border-b py-3 last:border-0">
      <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
        {label}
      </span>
      <span className="text-fl-fg min-w-0 text-right font-mono text-sm break-words">
        {value}
      </span>
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="border-fl-border bg-fl-surface border">
      <div className="border-fl-border flex items-center gap-2 border-b px-5 py-4">
        <span className="text-fl-label text-fl-muted-2">●</span>
        <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
          {title}
        </span>
      </div>
      <div className="px-5">{children}</div>
    </div>
  )
}

function SummaryCard({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <div className="border-fl-border bg-fl-surface border px-4 py-3">
      <p className="text-fl-label text-fl-muted-4 mb-1 font-mono tracking-widest uppercase">
        {label}
      </p>
      <p className="text-fl-fg font-mono text-lg">{value}</p>
    </div>
  )
}

function subscriptionStatusClass(status: string) {
  switch (status) {
    case 'active':
      return 'border-green-500/40 text-green-400'
    case 'trialing':
      return 'border-blue-500/40 text-blue-400'
    case 'past_due':
    case 'unpaid':
    case 'paused':
      return 'border-yellow-500/40 text-yellow-400'
    case 'incomplete':
    case 'incomplete_expired':
      return 'border-orange-500/40 text-orange-400'
    case 'canceled':
      return 'border-fl-border text-fl-muted-2'
    default:
      return 'border-fl-border text-fl-muted-3'
  }
}

export default function AdminUserStatsPage() {
  const t = useTranslations('admin')
  const tLang = useTranslations('languages')
  const tBilling = useTranslations('billing')
  const params = useParams()
  const userId = params?.id as string
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)

  const [user, setUser] = useState<AdminUser | null>(null)
  const [stats, setStats] = useState<UserStats | null>(null)
  const [quota, setQuota] = useState<QuotaStatus | null>(null)
  const [quotaWeekly, setQuotaWeekly] = useState('')
  const [quotaDaily, setQuotaDaily] = useState('')
  const [quotaWeeklyMinutes, setQuotaWeeklyMinutes] = useState('')
  const [quotaMonthlyTokens, setQuotaMonthlyTokens] = useState('')
  const [quotaSaving, setQuotaSaving] = useState(false)
  const [quotaSaved, setQuotaSaved] = useState(false)
  const [quotaError, setQuotaError] = useState('')
  const [subscriptionSaving, setSubscriptionSaving] = useState(false)
  const [currentPlan, setCurrentPlan] = useState<PlanKey>('none')
  const [pendingPlan, setPendingPlan] = useState<PlanKey | null>(null)
  const [verifyPending, setVerifyPending] = useState(false)
  const [verifySaving, setVerifySaving] = useState(false)
  const [activeTab, setActiveTab] = useState<TabKey>('profile')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    Promise.all([
      apiFetch(`/api/admin/users/${userId}`),
      apiFetch(`/api/admin/users/${userId}/stats`),
      apiFetch(`/api/admin/users/${userId}/quota`),
    ])
      .then(async ([uRes, sRes, qRes]) => {
        if (!uRes.ok || !sRes.ok) {
          setError('loadError')
          return
        }
        const [uData, sData] = await Promise.all([uRes.json(), sRes.json()])
        setUser(uData)
        setStats(sData)
        setQuotaWeekly(String(uData.conversation_weekly_sessions))
        setQuotaDaily(String(uData.conversation_daily_minutes))
        setQuotaWeeklyMinutes(String(uData.conversation_weekly_minutes))
        setQuotaMonthlyTokens(String(uData.monthly_tokens_limit))
        if (qRes.ok) {
          const qData: QuotaStatus = await qRes.json()
          setQuota(qData)
        }
      })
      .catch(() => setError('loadError'))
      .finally(() => setLoading(false))
  }, [userId])

  useEffect(() => {
    if (!user) {
      setCurrentPlan('none')
      return
    }
    if (
      user.subscription_status !== 'active' &&
      user.subscription_status !== 'trialing'
    ) {
      setCurrentPlan('none')
      return
    }
    if (user.subscription_ends_at) {
      const diffDays = Math.round(
        (new Date(user.subscription_ends_at).getTime() - Date.now()) /
          (1000 * 60 * 60 * 24)
      )
      setCurrentPlan(diffDays > 60 ? 'yearly' : 'monthly')
      return
    }
    setCurrentPlan('monthly')
  }, [user])

  const exercisePct = useMemo(() => {
    if (!stats || stats.exercises_total === 0) return null
    return Math.round((stats.exercises_correct / stats.exercises_total) * 100)
  }, [stats])

  const quotaValuesValid = useMemo(
    () =>
      [quotaWeekly, quotaDaily, quotaWeeklyMinutes, quotaMonthlyTokens].every(
        (value) => {
          const parsed = Number(value)
          return value.trim() !== '' && Number.isInteger(parsed) && parsed >= 0
        }
      ),
    [quotaDaily, quotaMonthlyTokens, quotaWeekly, quotaWeeklyMinutes]
  )

  async function toggleVerified() {
    if (!userId || !user) return
    setVerifySaving(true)
    setError('')
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_verified: !user.is_verified }),
      })
      if (!res.ok) {
        setError(t('updateUserError'))
        return
      }
      const updated: AdminUser = await res.json()
      setUser(updated)
    } finally {
      setVerifySaving(false)
      setVerifyPending(false)
    }
  }

  async function saveQuota() {
    if (!userId) return
    setQuotaSaved(false)
    setQuotaError('')
    if (!quotaValuesValid) {
      setQuotaError(t('quotaValidationError'))
      return
    }
    setQuotaSaving(true)
    const weekly = Number(quotaWeekly)
    const daily = Number(quotaDaily)
    const weeklyMin = Number(quotaWeeklyMinutes)
    const monthlyTok = Number(quotaMonthlyTokens)
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_weekly_sessions: weekly,
          conversation_daily_minutes: daily,
          conversation_weekly_minutes: weeklyMin,
          monthly_tokens_limit: monthlyTok,
        }),
      })
      if (!res.ok) {
        setQuotaError(t('quotaSaveError'))
        return
      }
      const updated: AdminUser = await res.json()
      setUser(updated)
      setQuotaWeekly(String(updated.conversation_weekly_sessions))
      setQuotaDaily(String(updated.conversation_daily_minutes))
      setQuotaWeeklyMinutes(String(updated.conversation_weekly_minutes))
      setQuotaMonthlyTokens(String(updated.monthly_tokens_limit))
      const qRes = await apiFetch(`/api/admin/users/${userId}/quota`)
      if (qRes.ok) {
        const qData: QuotaStatus = await qRes.json()
        setQuota(qData)
      }
      setQuotaSaved(true)
      setTimeout(() => setQuotaSaved(false), 3000)
    } finally {
      setQuotaSaving(false)
    }
  }

  async function handleSubscriptionChange(plan: PlanKey) {
    if (!userId) return
    setSubscriptionSaving(true)
    setError('')
    try {
      const body: Record<string, string | null> = {}
      if (plan === 'none') {
        body.subscription_status = 'none'
        body.subscription_ends_at = null
      } else {
        body.subscription_status = 'active'
        const days = plan === 'monthly' ? 30 : 365
        const endDate = new Date(Date.now() + days * 24 * 60 * 60 * 1000)
        body.subscription_ends_at = endDate.toISOString()
      }
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        setError(t('subscriptionUpdateError'))
        return
      }
      const updated: AdminUser = await res.json()
      setUser(updated)
    } finally {
      setSubscriptionSaving(false)
      setPendingPlan(null)
    }
  }

  if (loading) {
    return <PageLoading label={t('loading')} />
  }

  if (error === 'loadError' || !user || !stats) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="border-fl-error/40 text-fl-error border px-4 py-3 font-mono text-xs">
          {t('loadError')}
        </div>
      </div>
    )
  }

  const subscriptionLabel = getSubscriptionLabel(
    user.subscription_status,
    tBilling
  )
  const activeLanguageCount = stats.per_language.filter(
    (lang) => lang.cefr_level !== null
  ).length

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Link
            href="/admin/users"
            className="text-fl-label text-fl-muted-2 hover:text-fl-fg font-mono tracking-widest uppercase transition-colors"
          >
            {t('users')}
          </Link>
          <span className="text-fl-muted-4 text-fl-label font-mono">/</span>
          <span className="text-fl-label text-fl-fg truncate font-mono tracking-widest uppercase">
            {user.display_name}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`text-fl-hint border px-2 py-0.5 font-mono tracking-widest uppercase ${
              user.is_active
                ? 'border-green-500/40 text-green-400'
                : 'border-fl-error/30 text-fl-error-fg'
            }`}
          >
            {user.is_active ? t('active') : t('inactive')}
          </span>
          <span
            className={`text-fl-hint border px-2 py-0.5 font-mono tracking-widest uppercase ${
              user.role === 'admin'
                ? 'border-fl-fg/40 text-fl-fg'
                : 'border-fl-border text-fl-muted-2'
            }`}
          >
            {user.role === 'admin' ? t('roleAdmin') : t('roleUser')}
          </span>
          {stripeEnabled && (
            <span
              className={`text-fl-hint border px-2 py-0.5 font-mono tracking-widest uppercase ${subscriptionStatusClass(user.subscription_status)}`}
            >
              {subscriptionLabel}
            </span>
          )}
        </div>
      </div>

      <AdminNav />

      <div className="border-fl-border bg-fl-surface border p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <p className="text-fl-fg truncate font-mono text-xl">
              {user.display_name}
            </p>
            <p className="text-fl-muted-2 mt-1 font-mono text-xs break-all">
              #{user.id} / @{user.username.toLowerCase()}
              {user.email ? ` / ${user.email}` : ''}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <SummaryCard
              label={t('statsXp')}
              value={stats.xp_total.toLocaleString()}
            />
            <SummaryCard
              label={t('statsStreak')}
              value={`${stats.streak_current} ${t('statsDays')}`}
            />
            <SummaryCard
              label={t('sectionLanguages')}
              value={`${activeLanguageCount}/${stats.per_language.length}`}
            />
            <SummaryCard
              label={t('statsExercises')}
              value={exercisePct != null ? `${exercisePct}%` : '-'}
            />
          </div>
        </div>
      </div>

      {error && error !== 'loadError' && (
        <div className="border-fl-error/40 text-fl-error border px-4 py-3 font-mono text-xs">
          {error}
        </div>
      )}

      <div className="border-fl-border bg-fl-surface flex gap-1 overflow-x-auto border p-1">
        {tabs
          .filter((tab) => stripeEnabled || tab.key !== 'subscription')
          .map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.key
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`text-fl-label flex min-h-9 shrink-0 items-center gap-2 px-3 py-2 font-mono tracking-widest uppercase transition-colors ${
                  active
                    ? 'bg-fl-bg text-fl-fg border-fl-accent border-l-2'
                    : 'text-fl-muted-2 hover:bg-fl-bg hover:text-fl-fg border-l-2 border-transparent'
                }`}
              >
                <Icon className="size-3.5" aria-hidden="true" />
                {t(tab.labelKey)}
              </button>
            )
          })}
      </div>

      {activeTab === 'profile' && (
        <Section title={t('tabProfile')}>
          <StatRow label="ID" value={`#${user.id}`} />
          <StatRow
            label={t('fieldUsername')}
            value={user.username.toLowerCase()}
          />
          {user.email && <StatRow label={t('fieldEmail')} value={user.email} />}
          {user.email && (
            <div className="border-fl-border flex flex-wrap items-center justify-between gap-3 border-b py-3">
              <div className="flex items-center gap-2">
                {user.is_verified ? (
                  <BadgeCheck
                    className="size-4 text-green-400"
                    aria-hidden="true"
                  />
                ) : (
                  <MailCheck
                    className="text-fl-muted-3 size-4"
                    aria-hidden="true"
                  />
                )}
                <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
                  {user.is_verified
                    ? t('emailVerified')
                    : t('emailNotVerified')}
                </span>
              </div>
              <button
                onClick={() => setVerifyPending(true)}
                disabled={verifySaving}
                className="text-fl-hint hover:border-fl-fg hover:text-fl-fg border-fl-border text-fl-muted-2 inline-flex items-center gap-2 border px-2 py-1 font-mono tracking-widest uppercase transition-colors disabled:opacity-40"
              >
                {verifySaving && (
                  <Loader2
                    className="size-3.5 animate-spin"
                    aria-hidden="true"
                  />
                )}
                {user.is_verified ? t('unverifyEmail') : t('verifyEmail')}
              </button>
            </div>
          )}
          <StatRow
            label={t('fieldNativeLanguage')}
            value={tLang(user.native_language as Parameters<typeof tLang>[0])}
          />
          <StatRow
            label={t('status')}
            value={user.is_active ? t('active') : t('inactive')}
          />
          <StatRow
            label={t('role')}
            value={user.role === 'admin' ? t('roleAdmin') : t('roleUser')}
          />
        </Section>
      )}

      {activeTab === 'languages' && (
        <Section title={t('sectionLanguages')}>
          {stats.per_language.length === 0 ? (
            <p className="text-fl-muted-2 py-6 text-center font-mono text-xs">
              {t('statsNoData')}
            </p>
          ) : (
            <div className="grid gap-3 py-4 md:grid-cols-2">
              {stats.per_language.map((pl) => {
                const lang = getLanguageByCode(pl.target_language)
                const isActive = pl.cefr_level !== null
                const pct =
                  pl.exercises_total > 0
                    ? Math.round(
                        (pl.exercises_correct / pl.exercises_total) * 100
                      )
                    : null
                return (
                  <div
                    key={pl.target_language}
                    className={`bg-fl-bg border px-4 py-3 ${
                      isActive ? 'border-fl-accent/50' : 'border-fl-border'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {lang && (
                        <Image
                          src={lang.flagPath}
                          alt={lang.code}
                          width={24}
                          height={17}
                          className="shrink-0 object-cover"
                        />
                      )}
                      <span className="text-fl-fg min-w-0 flex-1 truncate font-mono text-sm font-bold">
                        {lang?.name ?? pl.target_language}
                      </span>
                      {isActive ? (
                        <span className="text-fl-label bg-fl-accent/20 text-fl-accent shrink-0 px-2 py-0.5 font-mono text-xs tracking-widest uppercase">
                          {pl.cefr_level} / {t('statsActive')}
                        </span>
                      ) : (
                        <span className="text-fl-label text-fl-muted-2 shrink-0 font-mono text-xs tracking-widest uppercase">
                          -
                        </span>
                      )}
                    </div>
                    <div className="text-fl-muted-2 mt-3 grid grid-cols-2 gap-2 font-mono text-xs">
                      <span>
                        {t('statsXp')}: {pl.xp_total.toLocaleString()}
                      </span>
                      <span>
                        {t('statsStreak')}: {pl.streak_current} {t('statsDays')}
                      </span>
                      <span>
                        {t('statsLessons')}: {pl.lessons_completed}
                      </span>
                      <span>
                        {t('statsExercises')}: {pl.exercises_correct}/
                        {pl.exercises_total}
                        {pct != null && ` (${pct}%)`}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Section>
      )}

      {activeTab === 'activity' && (
        <div className="grid gap-4 md:grid-cols-2">
          <Section title={t('sectionActivity')}>
            <StatRow
              label={t('statsXp')}
              value={stats.xp_total.toLocaleString()}
            />
            <StatRow
              label={t('statsStreak')}
              value={`${stats.streak_current} ${t('statsDays')}`}
            />
            <StatRow label={t('statsActiveDays')} value={stats.active_days} />
            <StatRow
              label={t('statsExercises')}
              value={
                exercisePct != null
                  ? `${stats.exercises_correct} / ${stats.exercises_total} (${exercisePct}%)`
                  : '-'
              }
            />
          </Section>

          <Section title={t('sectionCommunication')}>
            <StatRow
              label={t('statsMessages')}
              value={stats.chat_messages_sent}
            />
            {stats.tokens_total === 0 ? (
              <p className="text-fl-muted-2 py-4 font-mono text-xs">
                {t('statsTokensNote')}
              </p>
            ) : (
              <>
                <StatRow
                  label={t('statsTokensTotal')}
                  value={stats.tokens_total.toLocaleString()}
                />
                <StatRow
                  label={t('statsTokensChat')}
                  value={stats.tokens_chat.toLocaleString()}
                />
                <StatRow
                  label={t('statsTokensConversation')}
                  value={stats.tokens_conversation.toLocaleString()}
                />
              </>
            )}
          </Section>
        </div>
      )}

      {activeTab === 'quota' && (
        <div className="grid gap-4 md:grid-cols-2">
          <Section title={t('quotaCurrentUsage')}>
            {quota ? (
              <>
                <StatRow
                  label={t('quotaUsedSessions')}
                  value={
                    quota.sessions_unlimited
                      ? t('quotaUnlimitedLabel')
                      : `${quota.sessions_this_week} / ${quota.sessions_limit}`
                  }
                />
                <StatRow
                  label={t('quotaUsedMinutes')}
                  value={
                    quota.time_unlimited
                      ? t('quotaUnlimitedLabel')
                      : `${quota.minutes_today} / ${quota.minutes_limit} ${t('unitMinutes')}`
                  }
                />
                <StatRow
                  label={t('quotaUsedWeeklyMinutes')}
                  value={
                    quota.weekly_minutes_unlimited
                      ? t('quotaUnlimitedLabel')
                      : `${quota.minutes_this_week} / ${quota.weekly_minutes_limit} ${t('unitMinutes')}`
                  }
                />
              </>
            ) : (
              <p className="text-fl-muted-2 py-4 font-mono text-xs">
                {t('statsNoData')}
              </p>
            )}
          </Section>

          <Section title={t('quotaConfiguredLimits')}>
            <div className="space-y-4 py-4">
              <QuotaInput
                label={t('quotaWeeklySessions')}
                unit={t('unitSessions')}
                value={quotaWeekly}
                onChange={setQuotaWeekly}
              />
              <QuotaInput
                label={t('quotaDailyMinutes')}
                unit={t('unitMinutes')}
                value={quotaDaily}
                onChange={setQuotaDaily}
              />
              <QuotaInput
                label={t('quotaWeeklyMinutes')}
                unit={t('unitMinutes')}
                value={quotaWeeklyMinutes}
                onChange={setQuotaWeeklyMinutes}
              />
              <QuotaInput
                label={t('quotaMonthlyTokens')}
                unit={t('unitTokens')}
                value={quotaMonthlyTokens}
                onChange={setQuotaMonthlyTokens}
              />
              <p className="text-fl-hint text-fl-muted-4 font-mono">
                {t('quotaZeroMeansUnlimited')}
              </p>
              {quotaError && (
                <p className="border-fl-error/40 text-fl-error border px-3 py-2 font-mono text-xs">
                  {quotaError}
                </p>
              )}
              <button
                onClick={saveQuota}
                disabled={quotaSaving || !quotaValuesValid}
                className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 inline-flex w-full items-center justify-center gap-2 px-4 py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors disabled:opacity-40"
              >
                {quotaSaving && (
                  <Loader2
                    className="size-3.5 animate-spin"
                    aria-hidden="true"
                  />
                )}
                {quotaSaved ? t('quotaSaved') : t('quotaSave')}
              </button>
            </div>
          </Section>
        </div>
      )}

      {stripeEnabled && activeTab === 'subscription' && (
        <Section title={t('tabSubscription')}>
          <StatRow label={t('fieldSubscription')} value={subscriptionLabel} />
          {user.subscription_ends_at && (
            <StatRow
              label={t('fieldEndsRenews')}
              value={new Date(user.subscription_ends_at).toLocaleDateString()}
            />
          )}
          {user.stripe_customer_id && (
            <StatRow
              label={t('fieldStripeCustomer')}
              value={user.stripe_customer_id}
            />
          )}
          <div className="space-y-2 py-4">
            <label className="block">
              <span className="text-fl-label text-fl-muted-3 mb-1 block font-mono text-xs tracking-widest uppercase">
                {t('subscriptionOverride')}
              </span>
              <select
                value={currentPlan}
                onChange={(e) => setPendingPlan(e.target.value as PlanKey)}
                disabled={subscriptionSaving}
                className="bg-fl-bg border-fl-border text-fl-fg focus:border-fl-accent w-full border px-3 py-2 font-mono text-xs tracking-widest uppercase focus:outline-none disabled:opacity-40"
              >
                <option value="none">{tBilling('statusNone')}</option>
                <option value="monthly">{tBilling('planMonthlyName')}</option>
                <option value="yearly">{tBilling('planYearlyName')}</option>
              </select>
            </label>
            <p className="text-fl-hint text-fl-muted-4 font-mono">
              {t('subscriptionOverrideDesc')}
            </p>
            {subscriptionSaving && (
              <p className="text-fl-muted-2 inline-flex items-center gap-2 font-mono text-xs">
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                {t('saving')}
              </p>
            )}
          </div>
        </Section>
      )}

      <ConfirmDialog
        open={verifyPending}
        title={user.is_verified ? t('unverifyEmail') : t('verifyEmail')}
        message={
          user.is_verified
            ? t('unverifyEmailConfirmMessage')
            : t('verifyEmailConfirmMessage')
        }
        confirmLabel={user.is_verified ? t('unverifyEmail') : t('verifyEmail')}
        danger={user.is_verified}
        onConfirm={toggleVerified}
        onCancel={() => setVerifyPending(false)}
      />

      {stripeEnabled && (
        <ConfirmDialog
          open={pendingPlan !== null}
          title={t('subscriptionConfirmTitle')}
          message={
            pendingPlan
              ? t('subscriptionConfirmMessage', {
                  plan: planLabel(pendingPlan, tBilling),
                })
              : ''
          }
          confirmLabel={t('subscriptionConfirm')}
          danger={pendingPlan === 'none'}
          onConfirm={() => pendingPlan && handleSubscriptionChange(pendingPlan)}
          onCancel={() => setPendingPlan(null)}
        />
      )}
    </div>
  )
}

function QuotaInput({
  label,
  unit,
  value,
  onChange,
}: {
  label: string
  unit: string
  value: string
  onChange: (value: string) => void
}) {
  const invalid =
    value.trim() === '' || !Number.isInteger(Number(value)) || Number(value) < 0

  return (
    <label className="grid gap-2 sm:grid-cols-[1fr_9rem] sm:items-center">
      <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
        {label}
      </span>
      <span className="flex">
        <input
          type="number"
          min={0}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={invalid}
          className={`bg-fl-bg text-fl-fg focus:border-fl-accent min-w-0 flex-1 border px-3 py-2 text-right font-mono text-sm focus:outline-none ${
            invalid ? 'border-fl-error/50' : 'border-fl-border'
          }`}
        />
        <span className="border-fl-border bg-fl-surface-2 text-fl-muted-2 border border-l-0 px-3 py-2 font-mono text-xs">
          {unit}
        </span>
      </span>
    </label>
  )
}

function getSubscriptionLabel(
  status: string,
  tBilling: (
    key:
      | 'statusActive'
      | 'statusTrialing'
      | 'statusPastDue'
      | 'statusUnpaid'
      | 'statusPaused'
      | 'statusIncomplete'
      | 'statusIncompleteExpired'
      | 'statusCanceled'
      | 'statusNone'
  ) => string
) {
  switch (status) {
    case 'active':
      return tBilling('statusActive')
    case 'trialing':
      return tBilling('statusTrialing')
    case 'past_due':
      return tBilling('statusPastDue')
    case 'unpaid':
      return tBilling('statusUnpaid')
    case 'paused':
      return tBilling('statusPaused')
    case 'incomplete':
      return tBilling('statusIncomplete')
    case 'incomplete_expired':
      return tBilling('statusIncompleteExpired')
    case 'canceled':
      return tBilling('statusCanceled')
    default:
      return tBilling('statusNone')
  }
}

function planLabel(
  plan: PlanKey,
  tBilling: (key: 'statusNone' | 'planMonthlyName' | 'planYearlyName') => string
) {
  if (plan === 'monthly') return tBilling('planMonthlyName')
  if (plan === 'yearly') return tBilling('planYearlyName')
  return tBilling('statusNone')
}
