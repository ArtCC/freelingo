'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { useAuthStore, isSubscribed } from '@/store/auth'
import { useConfigStore } from '@/store/config'
import { apiFetch } from '@/lib/api'
import { mapUser } from '@/lib/mappers'
import { useLogout } from '@/hooks/useLogout'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { ContactFormModal } from '@/components/ui/contact-form-modal'
import { LoadingBar } from '@/components/ui/loading-bar'
import { PageLoading } from '@/components/ui/page-loading'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import { AuthAvatarImage } from '@/components/AuthAvatarImage'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const tNav = useTranslations('nav')
  const tCommon = useTranslations('common')
  const tBilling = useTranslations('billing')
  const pathname = usePathname()

  const mainNavItems = [
    { href: '/dashboard', label: tNav('home') },
    { href: '/plan', label: tNav('myPlan') },
    { href: '/progress', label: tNav('progress') },
    { href: '/flashcards', label: tNav('flashcards') },
    { href: '/chat', label: tNav('tutor') },
    { href: '/listening', label: tNav('listening') },
    { href: '/reading', label: tNav('reading') },
    { href: '/conversation', label: tNav('conversation') },
    { href: '/assessment', label: tNav('assessment') },
  ]

  const resourceNavItems = [
    { href: '/grammar', label: tNav('grammar') },
    { href: '/vocabulary', label: tNav('vocabulary') },
    { href: '/phrasebook', label: tNav('phrasebook') },
  ]

  const bottomNavItems = [
    { href: '/settings', label: tNav('settings') },
    { href: '/faq', label: tNav('faq') },
    { href: '/feedback', label: tNav('feedback') },
  ]

  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)
  const setTokens = useAuthStore((s) => s.setTokens)
  const setUser = useAuthStore((s) => s.setUser)
  const logout = useAuthStore((s) => s.logout)
  const handleLogout = useLogout()
  const [initializing, setInitializing] = useState(true)
  const loadConfig = useConfigStore((s) => s.load)
  const [logoutConfirm, setLogoutConfirm] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [resourcesOpen, setResourcesOpen] = useState(false)
  const [contactOpen, setContactOpen] = useState(false)
  const [resendSent, setResendSent] = useState(false)
  const [feedbackUnreadCount, setFeedbackUnreadCount] = useState(0)

  const PREMIUM_HREFS = new Set([
    '/chat',
    '/listening',
    '/reading',
    '/conversation',
  ])
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const showPremiumBadge = stripeEnabled && !isSubscribed(user, stripeEnabled)
  const [trialDaysLeft, setTrialDaysLeft] = useState(0)

  async function handleResendVerification() {
    const res = await apiFetch('/api/auth/resend-verification', {
      method: 'POST',
    })
    if (res.ok) setResendSent(true)
  }

  // On every page load, Zustand is empty. Use the httpOnly refresh cookie
  // to silently get a new access token, then fetch /me to populate the user.
  useEffect(() => {
    async function init() {
      // Load Stripe config once (non-blocking)
      loadConfig()
      try {
        if (!accessToken) {
          const res = await fetch('/api/auth/refresh', {
            method: 'POST',
            credentials: 'include',
          })
          if (!res.ok) {
            logout()
            router.push('/login')
            return
          }
          const { access_token } = await res.json()
          setTokens(access_token)
        }
        // Fetch user info if not already loaded
        const meRes = await apiFetch('/api/auth/me')
        if (!meRes.ok) {
          logout()
          router.push('/login')
          return
        }
        const me = await meRes.json()
        setUser(mapUser(me))

        if (me.learning_goals === null) {
          router.replace('/onboarding')
          return
        }
      } catch {
        logout()
        router.push('/login')
      } finally {
        setInitializing(false)
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    // Stripe trial countdown
    if (
      user?.subscription_status === 'trialing' &&
      user?.subscription_ends_at &&
      stripeEnabled
    ) {
      const days = Math.max(
        1,
        Math.ceil(
          (new Date(user.subscription_ends_at).getTime() - Date.now()) /
            (1000 * 60 * 60 * 24)
        )
      )
      setTrialDaysLeft(days)
      return
    }
    // Freemium trial countdown
    if (
      user?.freemium_trial_ends_at &&
      stripeEnabled &&
      user?.subscription_status !== 'active' &&
      user?.subscription_status !== 'trialing'
    ) {
      const end = new Date(user.freemium_trial_ends_at)
      if (end > new Date()) {
        const days = Math.max(
          1,
          Math.ceil((end.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
        )
        setTrialDaysLeft(days)
        return
      }
    }
    setTrialDaysLeft(0)
  }, [
    user?.subscription_status,
    user?.subscription_ends_at,
    user?.freemium_trial_ends_at,
    stripeEnabled,
  ])

  useEffect(() => {
    if (initializing) return

    async function loadFeedbackUnreadCount() {
      try {
        const res = await apiFetch('/api/feedback/unread-summary')
        if (!res.ok) return
        const data = await res.json()
        setFeedbackUnreadCount(data.unread_count ?? 0)
      } catch {
        setFeedbackUnreadCount(0)
      }
    }

    loadFeedbackUnreadCount()
    window.addEventListener('freelingo:feedback-read', loadFeedbackUnreadCount)
    return () => {
      window.removeEventListener(
        'freelingo:feedback-read',
        loadFeedbackUnreadCount
      )
    }
  }, [initializing])

  if (initializing) {
    return (
      <PageLoading
        label={tCommon('initializing')}
        minHeight="min-h-screen"
        className="bg-fl-bg"
      />
    )
  }

  const feedbackBadgeText =
    feedbackUnreadCount > 99
      ? '99+'
      : feedbackUnreadCount > 0
        ? String(feedbackUnreadCount)
        : ''

  return (
    <div className="bg-fl-bg flex min-h-screen md:h-screen md:overflow-hidden">
      {/* Sidebar */}
      <aside className="border-fl-border bg-fl-bg hidden w-52 shrink-0 flex-col border-r px-0 py-0 md:flex">
        {/* Logo area */}
        <div className="border-fl-border flex items-center gap-2 border-b px-5 py-5">
          <span className="text-fl-label text-fl-muted-2">●</span>
          <span className="text-fl-fg font-mono text-sm font-bold tracking-widest uppercase">
            FreeLingo
          </span>
        </div>

        {/* Language switcher */}
        <div className="border-fl-border border-b">
          <LanguageSwitcher />
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4">
          {/* Main items */}
          {mainNavItems.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest transition-colors ${
                  active
                    ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                    : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                }`}
              >
                <span
                  className={`text-fl-label ${active ? 'text-fl-accent' : 'text-fl-muted-4'}`}
                >
                  ●
                </span>
                {item.label}
                {showPremiumBadge && PREMIUM_HREFS.has(item.href) && (
                  <span className="text-fl-accent ml-auto text-xs">★</span>
                )}
              </Link>
            )
          })}

          {/* Resources group */}
          <div className="mt-2">
            <button
              onClick={() => setResourcesOpen((o) => !o)}
              className="text-fl-muted-4 hover:text-fl-muted-2 flex w-full items-center justify-between border-l-2 border-transparent px-5 py-2 font-mono text-xs tracking-widest uppercase transition-colors"
            >
              <span>{tNav('resources')}</span>
              <span className="text-fl-label">{resourcesOpen ? '▴' : '▾'}</span>
            </button>
            {resourcesOpen &&
              resourceNavItems.map((item) => {
                const active =
                  pathname === item.href || pathname.startsWith(item.href + '/')
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 py-2.5 pr-5 pl-8 font-mono text-xs tracking-widest transition-colors ${
                      active
                        ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                        : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                    }`}
                  >
                    <span
                      className={`text-fl-label ${active ? 'text-fl-accent' : 'text-fl-muted-4'}`}
                    >
                      ·
                    </span>
                    {item.label}
                  </Link>
                )
              })}
          </div>

          {/* Bottom items */}
          <div className="border-fl-border mt-2 border-t pt-2">
            {bottomNavItems.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest transition-colors ${
                    active
                      ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                      : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                  }`}
                >
                  <span
                    className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}
                  >
                    ●
                  </span>
                  {item.label}
                  {item.href === '/feedback' && feedbackBadgeText && (
                    <span className="ml-auto flex h-6 w-6 -translate-y-0.5 items-center justify-center rounded-full bg-red-600 text-[9px] leading-none font-bold text-white">
                      {feedbackBadgeText}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>

          {user?.role === 'admin' && (
            <Link
              href="/admin"
              className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest transition-colors ${
                pathname.startsWith('/admin')
                  ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                  : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
              }`}
            >
              <span className="text-fl-label text-fl-muted-4">●</span>
              {tNav('admin')}
            </Link>
          )}
        </nav>

        {/* User + logout */}
        <div className="border-fl-border border-t px-5 py-4">
          <div className="mb-3 flex items-center gap-3">
            <div className="border-fl-border h-8 w-8 flex-shrink-0 overflow-hidden rounded-full border">
              {user?.avatar ? (
                <AuthAvatarImage
                  avatar={user.avatar}
                  alt=""
                  width={32}
                  height={32}
                  className="h-full w-full object-cover"
                  fallback={
                    <div className="bg-fl-surface-2 flex h-full w-full items-center justify-center">
                      <span className="text-fl-muted-1 font-mono text-xs select-none">
                        {(user?.displayName ||
                          user?.username ||
                          '?')[0].toUpperCase()}
                      </span>
                    </div>
                  }
                />
              ) : (
                <div className="bg-fl-surface-2 flex h-full w-full items-center justify-center">
                  <span className="text-fl-muted-1 font-mono text-xs select-none">
                    {(user?.displayName ||
                      user?.username ||
                      '?')[0].toUpperCase()}
                  </span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <p className="text-fl-caption text-fl-muted-2 truncate font-mono tracking-widest uppercase">
                {user?.displayName || user?.username}
              </p>
              <p className="text-fl-label text-fl-muted-4 truncate font-mono">
                @{user?.username?.toLowerCase()}
              </p>
              {trialDaysLeft > 0 && (
                <p className="text-fl-label text-fl-accent truncate font-mono text-xs">
                  ★ {tBilling('trialDays', { days: trialDaysLeft })}
                </p>
              )}
            </div>
          </div>
          <p className="text-fl-label text-fl-muted-4 mb-2 font-mono tracking-wider">
            v1.8.26
          </p>
          <button
            onClick={() => setContactOpen(true)}
            className="text-fl-label text-fl-muted-2 hover:text-fl-fg mb-1 w-full text-left font-mono tracking-widest uppercase transition-colors"
          >
            {tNav('contact')}
          </button>
          <button
            onClick={() => setLogoutConfirm(true)}
            className="text-fl-label text-fl-muted-2 hover:text-fl-fg w-full text-left font-mono tracking-widest uppercase transition-colors"
          >
            {tCommon('logout')}
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="border-fl-border bg-fl-bg fixed top-0 right-0 left-0 z-50 border-b md:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <span className="text-fl-fg font-mono text-xs font-bold tracking-widest uppercase">
            FreeLingo
          </span>
          <button
            onClick={() => setMobileMenuOpen((o) => !o)}
            className="text-fl-muted-2 hover:text-fl-fg p-1 font-mono transition-colors"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            <span className="text-base leading-none">
              {mobileMenuOpen ? '✕' : '☰'}
            </span>
          </button>
        </div>

        {/* Dropdown */}
        {mobileMenuOpen && (
          <nav className="border-fl-border bg-fl-bg max-h-[calc(100svh-3.5rem)] overflow-y-auto overscroll-contain border-t pb-2">
            <div className="border-fl-border border-b">
              <LanguageSwitcher />
            </div>
            {mainNavItems.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${
                    active
                      ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                      : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                  }`}
                >
                  <span
                    className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}
                  >
                    ●
                  </span>
                  {item.label}
                  {showPremiumBadge && PREMIUM_HREFS.has(item.href) && (
                    <span className="text-fl-accent ml-auto text-xs">★</span>
                  )}
                </Link>
              )
            })}

            {/* Resources group (mobile) */}
            <div>
              <button
                onClick={() => setResourcesOpen((o) => !o)}
                className="text-fl-muted-4 hover:text-fl-muted-2 flex w-full items-center justify-between border-l-2 border-transparent px-5 py-2 font-mono text-xs tracking-widest uppercase transition-colors"
              >
                <span>{tNav('resources')}</span>
                <span className="text-fl-label">
                  {resourcesOpen ? '▴' : '▾'}
                </span>
              </button>
              {resourcesOpen &&
                resourceNavItems.map((item) => {
                  const active =
                    pathname === item.href ||
                    pathname.startsWith(item.href + '/')
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center gap-3 py-2.5 pr-5 pl-8 font-mono text-xs tracking-widest uppercase transition-colors ${
                        active
                          ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                          : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                      }`}
                    >
                      <span
                        className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}
                      >
                        ·
                      </span>
                      {item.label}
                    </Link>
                  )
                })}
            </div>

            {/* Bottom items (mobile) */}
            {bottomNavItems.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${
                    active
                      ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                      : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                  }`}
                >
                  <span
                    className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}
                  >
                    ●
                  </span>
                  {item.label}
                  {item.href === '/feedback' && feedbackBadgeText && (
                    <span className="ml-auto flex h-6 w-6 -translate-y-0.5 items-center justify-center rounded-full bg-red-600 text-[9px] leading-none font-bold text-white">
                      {feedbackBadgeText}
                    </span>
                  )}
                </Link>
              )
            })}

            {user?.role === 'admin' && (
              <Link
                href="/admin"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${
                  pathname.startsWith('/admin')
                    ? 'text-fl-fg bg-fl-surface-2 border-fl-accent border-l-2'
                    : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                }`}
              >
                <span className="text-fl-label text-fl-muted-4">●</span>
                {tNav('admin')}
              </Link>
            )}
            <div className="border-fl-border mx-5 mt-2 border-t pt-3">
              <div className="mb-2 flex items-center gap-3">
                <div className="border-fl-border h-7 w-7 flex-shrink-0 overflow-hidden rounded-full border">
                  {user?.avatar ? (
                    <AuthAvatarImage
                      avatar={user.avatar}
                      alt=""
                      width={28}
                      height={28}
                      className="h-full w-full object-cover"
                      fallback={
                        <div className="bg-fl-surface-2 flex h-full w-full items-center justify-center">
                          <span className="text-fl-hint text-fl-muted-1 font-mono select-none">
                            {(user?.displayName ||
                              user?.username ||
                              '?')[0].toUpperCase()}
                          </span>
                        </div>
                      }
                    />
                  ) : (
                    <div className="bg-fl-surface-2 flex h-full w-full items-center justify-center">
                      <span className="text-fl-hint text-fl-muted-1 font-mono select-none">
                        {(user?.displayName ||
                          user?.username ||
                          '?')[0].toUpperCase()}
                      </span>
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-fl-caption text-fl-muted-2 truncate font-mono tracking-widest uppercase">
                    {user?.displayName || user?.username}
                  </p>
                  <p className="text-fl-label text-fl-muted-4 truncate font-mono">
                    @{user?.username?.toLowerCase()}
                  </p>
                </div>
              </div>
              {trialDaysLeft > 0 && (
                <p className="text-fl-label text-fl-accent mb-2 font-mono text-xs">
                  ★ {tBilling('trialDays', { days: trialDaysLeft })}
                </p>
              )}
              <p className="text-fl-label text-fl-muted-4 mb-2 font-mono tracking-wider">
                v1.8.26
              </p>
              <button
                onClick={() => {
                  setMobileMenuOpen(false)
                  setContactOpen(true)
                }}
                className="text-fl-label text-fl-muted-2 hover:text-fl-fg mb-1 block font-mono tracking-widest uppercase transition-colors"
              >
                {tNav('contact')}
              </button>
              <button
                onClick={() => {
                  setMobileMenuOpen(false)
                  setLogoutConfirm(true)
                }}
                className="text-fl-label text-fl-muted-2 hover:text-fl-fg font-mono tracking-widest uppercase transition-colors"
              >
                {tCommon('logout')}
              </button>
            </div>
          </nav>
        )}
      </div>

      {/* Main */}
      <main className="flex min-h-[100dvh] flex-1 flex-col overflow-hidden pt-14 md:min-h-screen md:pt-0">
        {/* Email verification banner */}
        {user && user.is_verified === false && (
          <div className="border-fl-border bg-fl-surface flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-4 py-2">
            <span className="text-fl-muted-1 font-mono text-xs tracking-wide">
              ● {tCommon('verifyEmailBanner')}
            </span>
            {resendSent ? (
              <span className="text-fl-muted-2 font-mono text-xs">
                {tCommon('verifyEmailSent')}
              </span>
            ) : (
              <button
                onClick={handleResendVerification}
                className="text-fl-accent font-mono text-xs underline transition-all hover:no-underline"
              >
                {tCommon('resendVerification')}
              </button>
            )}
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </main>

      <LoadingBar />

      <ContactFormModal
        open={contactOpen}
        onClose={() => setContactOpen(false)}
      />

      <ConfirmDialog
        open={logoutConfirm}
        title={tCommon('logoutConfirmTitle')}
        message={tCommon('logoutConfirmMessage')}
        confirmLabel={tCommon('logout')}
        onConfirm={handleLogout}
        onCancel={() => setLogoutConfirm(false)}
      />
    </div>
  )
}
