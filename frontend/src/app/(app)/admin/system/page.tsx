'use client'

import { useEffect, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Loader2, Megaphone, ShieldAlert } from 'lucide-react'

import { AdminNav } from '@/components/admin/AdminNav'
import { AdminPageHeader } from '@/components/admin/AdminShell'
import { apiFetch } from '@/lib/api'
import type { DashboardBannerTranslation } from '@/store/config'
import { useConfigStore } from '@/store/config'

const BANNER_LOCALES = [
  'en',
  'es',
  'fr',
  'pt',
  'de',
  'it',
  'ru',
  'nl',
  'pl',
  'ro',
] as const

type BannerLocale = (typeof BANNER_LOCALES)[number]
type BannerTranslations = Record<BannerLocale, DashboardBannerTranslation>

interface AdminDashboardBanner {
  source_locale: BannerLocale
  is_active: boolean
  revision: number
  translations: BannerTranslations
  created_at: string
  updated_at: string
}

const EMPTY_TRANSLATION: DashboardBannerTranslation = {
  title: '',
  subtitle: '',
  description: '',
}

function emptyTranslations(): BannerTranslations {
  return Object.fromEntries(
    BANNER_LOCALES.map((locale) => [locale, { ...EMPTY_TRANSLATION }])
  ) as BannerTranslations
}

export default function AdminSystemPage() {
  const t = useTranslations('admin')
  const currentLocale = useLocale()
  const defaultLocale = BANNER_LOCALES.includes(currentLocale as BannerLocale)
    ? (currentLocale as BannerLocale)
    : 'en'
  const maintenanceMode = useConfigStore((s) => s.maintenanceMode)
  const [maintenanceLoading, setMaintenanceLoading] = useState(false)
  const [maintenanceError, setMaintenanceError] = useState('')
  const [bannerLoading, setBannerLoading] = useState(true)
  const [bannerError, setBannerError] = useState('')
  const [bannerSuccess, setBannerSuccess] = useState('')
  const [translating, setTranslating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [sourceLocale, setSourceLocale] = useState<BannerLocale>(defaultLocale)
  const [source, setSource] = useState({ ...EMPTY_TRANSLATION })
  const [translations, setTranslations] =
    useState<BannerTranslations>(emptyTranslations)
  const [hasTranslations, setHasTranslations] = useState(false)
  const [editorLocale, setEditorLocale] = useState<BannerLocale>(defaultLocale)
  const [isActive, setIsActive] = useState(true)
  const [revision, setRevision] = useState<number | null>(null)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  useEffect(() => {
    async function loadBanner() {
      try {
        const response = await apiFetch('/api/admin/dashboard-banner')
        if (!response.ok) throw new Error('load failed')
        const banner: AdminDashboardBanner | null = await response.json()
        if (banner) {
          setSourceLocale(banner.source_locale)
          setEditorLocale(banner.source_locale)
          setSource({ ...banner.translations[banner.source_locale] })
          setTranslations(banner.translations)
          setHasTranslations(true)
          setIsActive(banner.is_active)
          setRevision(banner.revision)
          setUpdatedAt(banner.updated_at)
        }
      } catch {
        setBannerError(t('dashboardBanner.loadError'))
      } finally {
        setBannerLoading(false)
      }
    }

    loadBanner()
    // The admin state is loaded once; subsequent edits remain local until Save.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function toggleMaintenance() {
    setMaintenanceLoading(true)
    setMaintenanceError('')
    try {
      const nextMode = !maintenanceMode
      const res = await apiFetch('/api/admin/maintenance', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ maintenance_mode: nextMode }),
      })
      if (res.ok) {
        const data = await res.json()
        useConfigStore.setState({ maintenanceMode: data.maintenance_mode })
      } else {
        setMaintenanceError(t('maintenanceError'))
      }
    } catch {
      setMaintenanceError(t('maintenanceError'))
    } finally {
      setMaintenanceLoading(false)
    }
  }

  async function translateBanner() {
    setTranslating(true)
    setBannerError('')
    setBannerSuccess('')
    try {
      const response = await apiFetch('/api/admin/dashboard-banner/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_locale: sourceLocale, ...source }),
      })
      if (!response.ok) throw new Error('translate failed')
      const data: { translations: BannerTranslations } = await response.json()
      setTranslations(data.translations)
      setHasTranslations(true)
      setEditorLocale(sourceLocale)
      setBannerSuccess(t('dashboardBanner.translateSuccess'))
    } catch {
      setBannerError(t('dashboardBanner.translateError'))
    } finally {
      setTranslating(false)
    }
  }

  async function saveBanner() {
    setSaving(true)
    setBannerError('')
    setBannerSuccess('')
    try {
      const response = await apiFetch('/api/admin/dashboard-banner', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_locale: sourceLocale,
          is_active: isActive,
          translations,
        }),
      })
      if (!response.ok) throw new Error('save failed')
      const saved: AdminDashboardBanner = await response.json()
      setRevision(saved.revision)
      setUpdatedAt(saved.updated_at)
      setTranslations(saved.translations)
      setIsActive(saved.is_active)
      useConfigStore.setState({
        dashboardBanner: saved.is_active
          ? { revision: saved.revision, translations: saved.translations }
          : null,
      })
      setBannerSuccess(t('dashboardBanner.saveSuccess'))
    } catch {
      setBannerError(t('dashboardBanner.saveError'))
    } finally {
      setSaving(false)
    }
  }

  function updateTranslation(
    field: keyof DashboardBannerTranslation,
    value: string
  ) {
    setTranslations((current) => ({
      ...current,
      [editorLocale]: { ...current[editorLocale], [field]: value },
    }))
  }

  const editorTranslation = translations[editorLocale]
  const completedLocales = BANNER_LOCALES.filter((locale) =>
    Object.values(translations[locale]).every((value) => value.trim())
  ).length
  const sourceComplete = Object.values(source).every((value) => value.trim())

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <AdminPageHeader
        eyebrow={`${t('title')} / ${t('system')}`}
        title={t('system')}
      />

      <AdminNav />

      {maintenanceError && (
        <div className="border-fl-error/40 text-fl-error border px-4 py-3 font-mono text-xs">
          {maintenanceError}
        </div>
      )}

      <div
        className={`border px-5 py-4 ${maintenanceMode ? 'border-yellow-500/40 bg-yellow-500/5' : 'border-fl-border bg-fl-surface'}`}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <ShieldAlert
              className={`mt-0.5 size-5 shrink-0 ${maintenanceMode ? 'text-yellow-500' : 'text-fl-muted-3'}`}
              aria-hidden="true"
            />
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="text-fl-muted-1 font-mono text-xs tracking-widest uppercase">
                  {t('maintenanceTitle')}
                </span>
                <span
                  className={`text-fl-hint border px-2 py-0.5 font-mono tracking-widest uppercase ${
                    maintenanceMode
                      ? 'border-yellow-500/40 text-yellow-500'
                      : 'border-fl-border text-fl-muted-3'
                  }`}
                >
                  {maintenanceMode ? t('maintenanceOn') : t('maintenanceOff')}
                </span>
              </div>
              <p className="text-fl-hint text-fl-muted-2 font-mono">
                {t('maintenanceDesc')}
              </p>
            </div>
          </div>
          <button
            onClick={toggleMaintenance}
            disabled={maintenanceLoading}
            className={`inline-flex shrink-0 items-center justify-center gap-2 px-4 py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors ${
              maintenanceMode
                ? 'bg-fl-fg text-fl-bg hover:bg-fl-fg/90'
                : 'bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90'
            } disabled:opacity-50`}
          >
            {maintenanceLoading && (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            )}
            {maintenanceMode ? t('maintenanceDisable') : t('maintenanceEnable')}
          </button>
        </div>
      </div>

      <section className="border-fl-border bg-fl-surface border p-5">
        <div className="border-fl-border mb-5 flex gap-3 border-b pb-4">
          <Megaphone
            className="text-fl-accent mt-0.5 size-5 shrink-0"
            aria-hidden="true"
          />
          <div>
            <h2 className="text-fl-fg font-mono text-sm font-bold tracking-widest uppercase">
              {t('dashboardBanner.title')}
            </h2>
            <p className="text-fl-muted-2 mt-1 font-mono text-xs">
              {t('dashboardBanner.description')}
            </p>
          </div>
        </div>

        {bannerLoading ? (
          <div className="text-fl-muted-2 flex items-center gap-2 font-mono text-xs">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            {t('dashboardBanner.loading')}
          </div>
        ) : (
          <div className="space-y-6">
            {bannerError && (
              <p
                role="alert"
                className="border-fl-error/40 text-fl-error border px-4 py-3 font-mono text-xs"
              >
                {bannerError}
              </p>
            )}
            {bannerSuccess && (
              <p className="border-fl-accent/40 text-fl-accent border px-4 py-3 font-mono text-xs">
                {bannerSuccess}
              </p>
            )}

            <div className="grid gap-4 md:grid-cols-[12rem_1fr]">
              <label className="space-y-2 font-mono text-xs">
                <span className="text-fl-muted-2 block tracking-widest uppercase">
                  {t('dashboardBanner.sourceLocale')}
                </span>
                <select
                  value={sourceLocale}
                  onChange={(event) =>
                    setSourceLocale(event.target.value as BannerLocale)
                  }
                  className="border-fl-border bg-fl-bg text-fl-fg w-full border px-3 py-2"
                >
                  {BANNER_LOCALES.map((locale) => (
                    <option key={locale} value={locale}>
                      {t(`dashboardBanner.locales.${locale}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-end gap-3 pb-2 font-mono text-xs">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(event) => setIsActive(event.target.checked)}
                  className="accent-fl-accent size-4"
                />
                <span>
                  <span className="text-fl-fg block font-bold">
                    {t('dashboardBanner.activeLabel')}
                  </span>
                  <span className="text-fl-muted-3 mt-1 block">
                    {t('dashboardBanner.activeHint')}
                  </span>
                </span>
              </label>
            </div>

            <div className="grid gap-4">
              <label className="space-y-2 font-mono text-xs">
                <span className="text-fl-muted-2 block tracking-widest uppercase">
                  {t('dashboardBanner.fieldTitle')}
                </span>
                <input
                  value={source.title}
                  onChange={(event) =>
                    setSource((current) => ({
                      ...current,
                      title: event.target.value,
                    }))
                  }
                  maxLength={160}
                  className="border-fl-border bg-fl-bg text-fl-fg w-full border px-3 py-2 font-mono text-sm"
                />
              </label>
              <label className="space-y-2 font-mono text-xs">
                <span className="text-fl-muted-2 block tracking-widest uppercase">
                  {t('dashboardBanner.fieldSubtitle')}
                </span>
                <input
                  value={source.subtitle}
                  onChange={(event) =>
                    setSource((current) => ({
                      ...current,
                      subtitle: event.target.value,
                    }))
                  }
                  maxLength={240}
                  className="border-fl-border bg-fl-bg text-fl-fg w-full border px-3 py-2 font-mono text-sm"
                />
              </label>
              <label className="space-y-2 font-mono text-xs">
                <span className="text-fl-muted-2 block tracking-widest uppercase">
                  {t('dashboardBanner.fieldDescription')}
                </span>
                <textarea
                  value={source.description}
                  onChange={(event) =>
                    setSource((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  maxLength={2000}
                  rows={5}
                  className="border-fl-border bg-fl-bg text-fl-fg w-full resize-y border px-3 py-2 font-mono text-sm"
                />
              </label>
              <div>
                <button
                  type="button"
                  onClick={translateBanner}
                  disabled={translating || !sourceComplete}
                  className="bg-fl-fg text-fl-bg hover:bg-fl-accent inline-flex items-center gap-2 px-4 py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors disabled:opacity-40"
                >
                  {translating && (
                    <Loader2
                      className="size-3.5 animate-spin"
                      aria-hidden="true"
                    />
                  )}
                  {t('dashboardBanner.translate')}
                </button>
              </div>
            </div>

            {hasTranslations && (
              <div className="border-fl-border space-y-4 border-t pt-5">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <label className="space-y-2 font-mono text-xs">
                    <span className="text-fl-muted-2 block tracking-widest uppercase">
                      {t('dashboardBanner.editTranslation')}
                    </span>
                    <select
                      value={editorLocale}
                      onChange={(event) =>
                        setEditorLocale(event.target.value as BannerLocale)
                      }
                      className="border-fl-border bg-fl-bg text-fl-fg min-w-52 border px-3 py-2"
                    >
                      {BANNER_LOCALES.map((locale) => {
                        const complete = Object.values(
                          translations[locale]
                        ).every((value) => value.trim())
                        return (
                          <option key={locale} value={locale}>
                            {complete ? '✓ ' : ''}
                            {t(`dashboardBanner.locales.${locale}`)}
                          </option>
                        )
                      })}
                    </select>
                  </label>
                  <p className="text-fl-muted-3 font-mono text-xs">
                    {t('dashboardBanner.completion', {
                      complete: completedLocales,
                      total: BANNER_LOCALES.length,
                    })}
                  </p>
                </div>

                <div className="grid gap-4">
                  <label className="space-y-2 font-mono text-xs">
                    <span className="text-fl-muted-2 block tracking-widest uppercase">
                      {t('dashboardBanner.fieldTitle')}
                    </span>
                    <input
                      value={editorTranslation.title}
                      onChange={(event) =>
                        updateTranslation('title', event.target.value)
                      }
                      maxLength={160}
                      className="border-fl-border bg-fl-bg text-fl-fg w-full border px-3 py-2 font-mono text-sm"
                    />
                  </label>
                  <label className="space-y-2 font-mono text-xs">
                    <span className="text-fl-muted-2 block tracking-widest uppercase">
                      {t('dashboardBanner.fieldSubtitle')}
                    </span>
                    <input
                      value={editorTranslation.subtitle}
                      onChange={(event) =>
                        updateTranslation('subtitle', event.target.value)
                      }
                      maxLength={240}
                      className="border-fl-border bg-fl-bg text-fl-fg w-full border px-3 py-2 font-mono text-sm"
                    />
                  </label>
                  <label className="space-y-2 font-mono text-xs">
                    <span className="text-fl-muted-2 block tracking-widest uppercase">
                      {t('dashboardBanner.fieldDescription')}
                    </span>
                    <textarea
                      value={editorTranslation.description}
                      onChange={(event) =>
                        updateTranslation('description', event.target.value)
                      }
                      maxLength={2000}
                      rows={5}
                      className="border-fl-border bg-fl-bg text-fl-fg w-full resize-y border px-3 py-2 font-mono text-sm"
                    />
                  </label>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-fl-muted-3 font-mono text-xs">
                    {revision !== null && (
                      <span className="mr-4">
                        {t('dashboardBanner.revision', { revision })}
                      </span>
                    )}
                    {updatedAt && (
                      <span>
                        {t('dashboardBanner.updated', {
                          date: new Intl.DateTimeFormat(currentLocale, {
                            dateStyle: 'medium',
                            timeStyle: 'short',
                          }).format(new Date(updatedAt)),
                        })}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={saveBanner}
                    disabled={
                      saving || completedLocales !== BANNER_LOCALES.length
                    }
                    className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 inline-flex items-center justify-center gap-2 px-5 py-3 font-mono text-xs font-bold tracking-widest uppercase transition-colors disabled:opacity-40"
                  >
                    {saving && (
                      <Loader2
                        className="size-3.5 animate-spin"
                        aria-hidden="true"
                      />
                    )}
                    {t('dashboardBanner.save')}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
