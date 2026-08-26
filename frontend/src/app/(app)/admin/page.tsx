'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import {
  AlertTriangle,
  Bug,
  MessageSquareText,
  ShieldAlert,
  Star,
  Ticket,
  UserPlus,
  Users,
} from 'lucide-react'
import { AdminNav } from '@/components/admin/AdminNav'
import {
  AdminBadge,
  AdminMetric,
  AdminPageHeader,
  AdminPanel,
} from '@/components/admin/AdminShell'
import { apiFetch } from '@/lib/api'
import { useConfigStore } from '@/store/config'

interface AdminOverviewStats {
  users_total: number
  users_active: number
  users_inactive: number
  subscriptions_active: number
  subscriptions_trialing: number
  subscriptions_past_due: number
  feedback_total: number
  feedback_pending: number
  feedback_bug_pending: number
  reviews_pending: number
}

const actions = [
  {
    href: '/admin/users',
    key: 'manageUsers',
    descriptionKey: 'manageUsersDesc',
    icon: Users,
  },
  {
    href: '/admin/users?create=1',
    key: 'createUser',
    descriptionKey: 'createUserDesc',
    icon: UserPlus,
  },
  {
    href: '/admin/feedback',
    key: 'reviewFeedback',
    descriptionKey: 'reviewFeedbackDesc',
    icon: MessageSquareText,
  },
  {
    href: '/admin/reviews',
    key: 'reviewReviews',
    descriptionKey: 'reviewReviewsDesc',
    icon: Star,
  },
] as const

export default function AdminOverviewPage() {
  const t = useTranslations('admin')
  const maintenanceMode = useConfigStore((s) => s.maintenanceMode)
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const [stats, setStats] = useState<AdminOverviewStats | null>(null)
  const [loadingStats, setLoadingStats] = useState(true)
  const [statsError, setStatsError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function loadStats() {
      setLoadingStats(true)
      setStatsError('')
      try {
        const res = await apiFetch('/api/admin/stats')
        if (!res.ok) throw new Error()
        const data = await res.json()
        if (!cancelled) setStats(data)
      } catch {
        if (!cancelled) setStatsError(t('adminStatsError'))
      } finally {
        if (!cancelled) setLoadingStats(false)
      }
    }
    loadStats()
    return () => {
      cancelled = true
    }
  }, [t])

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <AdminPageHeader
        eyebrow={`${t('title')} / ${t('overview')}`}
        title={t('title')}
      />

      <AdminNav />

      <div
        className={`grid gap-3 md:grid-cols-2 ${stripeEnabled ? 'xl:grid-cols-5' : 'xl:grid-cols-4'}`}
      >
        <AdminMetric
          label={t('users')}
          value={loadingStats ? t('loading') : (stats?.users_total ?? '—')}
          icon={Users}
        />
        <AdminMetric
          label={t('activeUsers')}
          value={loadingStats ? t('loading') : (stats?.users_active ?? '—')}
          icon={ShieldAlert}
        />
        {stripeEnabled && (
          <AdminMetric
            label={t('paidAccess')}
            value={
              loadingStats
                ? t('loading')
                : `${stats?.subscriptions_active ?? 0} / ${stats?.subscriptions_trialing ?? 0}`
            }
            icon={Ticket}
          />
        )}
        <AdminMetric
          label={t('pendingFeedback')}
          value={loadingStats ? t('loading') : (stats?.feedback_pending ?? '—')}
          icon={MessageSquareText}
        />
        <AdminMetric
          label={t('pendingReviews')}
          value={loadingStats ? t('loading') : (stats?.reviews_pending ?? '—')}
          icon={Star}
        />
      </div>

      {statsError && (
        <div className="border-fl-error/40 text-fl-error border px-4 py-3 font-mono text-xs">
          {statsError}
        </div>
      )}

      <div
        className={`border px-5 py-4 ${
          maintenanceMode
            ? 'border-yellow-500/40 bg-yellow-500/5'
            : 'border-fl-border bg-fl-surface'
        }`}
      >
        <div className="flex flex-wrap items-center gap-3">
          <ShieldAlert
            className={`size-5 ${
              maintenanceMode ? 'text-yellow-500' : 'text-fl-muted-3'
            }`}
            aria-hidden="true"
          />
          <div className="min-w-0">
            <p className="text-fl-muted-1 font-mono text-xs tracking-widest uppercase">
              {t('maintenanceTitle')}
            </p>
            <p className="text-fl-hint text-fl-muted-3 mt-1 font-mono">
              {maintenanceMode
                ? t('maintenanceOnDesc')
                : t('maintenanceOffDesc')}
            </p>
          </div>
          <Link
            href="/admin/system"
            className="border-fl-border text-fl-label text-fl-muted-1 hover:text-fl-fg hover:border-fl-border-2 ml-auto border px-3 py-2 font-mono tracking-widest uppercase transition-colors"
          >
            {t('openSystemControls')}
          </Link>
        </div>
      </div>

      <AdminPanel title={t('operationalAlerts')}>
        <div className="divide-fl-border divide-y">
          <Link
            href="/admin/feedback?status=pending&type=bug"
            className="hover:bg-fl-bg/60 flex flex-wrap items-center gap-3 px-5 py-4 transition-colors"
          >
            <Bug
              className={`size-5 ${stats?.feedback_bug_pending ? 'text-fl-error-fg' : 'text-fl-muted-3'}`}
              aria-hidden="true"
            />
            <div className="min-w-0 flex-1">
              <p className="text-fl-fg font-mono text-sm">{t('pendingBugs')}</p>
              <p className="text-fl-muted-3 mt-1 font-mono text-xs">
                {t('pendingBugsDesc')}
              </p>
            </div>
            <AdminBadge
              tone={stats?.feedback_bug_pending ? 'danger' : 'neutral'}
            >
              {loadingStats ? t('loading') : (stats?.feedback_bug_pending ?? 0)}
            </AdminBadge>
          </Link>
          {stripeEnabled && (
            <Link
              href="/admin/users?subscription=past_due"
              className="hover:bg-fl-bg/60 flex flex-wrap items-center gap-3 px-5 py-4 transition-colors"
            >
              <AlertTriangle
                className={`size-5 ${stats?.subscriptions_past_due ? 'text-yellow-500' : 'text-fl-muted-3'}`}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <p className="text-fl-fg font-mono text-sm">
                  {t('pastDueSubscriptions')}
                </p>
                <p className="text-fl-muted-3 mt-1 font-mono text-xs">
                  {t('pastDueSubscriptionsDesc')}
                </p>
              </div>
              <AdminBadge
                tone={stats?.subscriptions_past_due ? 'warning' : 'neutral'}
              >
                {loadingStats
                  ? t('loading')
                  : (stats?.subscriptions_past_due ?? 0)}
              </AdminBadge>
            </Link>
          )}
        </div>
      </AdminPanel>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {actions.map((action) => {
          const Icon = action.icon
          return (
            <Link
              key={action.href}
              href={action.href}
              className="border-fl-border bg-fl-surface hover:border-fl-border-2 group border p-5 transition-colors"
            >
              <div className="mb-5 flex items-center justify-between">
                <Icon
                  className="text-fl-muted-2 group-hover:text-fl-fg size-5 transition-colors"
                  aria-hidden="true"
                />
                <Ticket
                  className="text-fl-muted-4 group-hover:text-fl-muted-2 size-4 transition-colors"
                  aria-hidden="true"
                />
              </div>
              <p className="text-fl-fg font-mono text-sm tracking-widest uppercase">
                {t(action.key)}
              </p>
              <p className="text-fl-muted-2 mt-2 font-mono text-xs leading-relaxed">
                {t(action.descriptionKey)}
              </p>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
