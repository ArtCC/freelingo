'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { useAuthStore } from '@/store/auth'
import { useConfigStore } from '@/store/config'
import { apiFetch } from '@/lib/api'
import Image from 'next/image'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { LoadingBar } from '@/components/ui/loading-bar'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const tNav = useTranslations('nav')
  const tCommon = useTranslations('common')
  const pathname = usePathname()

  const mainNavItems = [
    { href: '/dashboard', label: tNav('home') },
    { href: '/plan', label: tNav('myPlan') },
    { href: '/progress', label: tNav('progress') },
    { href: '/flashcards', label: tNav('flashcards') },
    { href: '/chat', label: tNav('tutor') },
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
  ]

  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)
  const setTokens = useAuthStore((s) => s.setTokens)
  const setUser = useAuthStore((s) => s.setUser)
  const logout = useAuthStore((s) => s.logout)
  const [initializing, setInitializing] = useState(true)
  const loadConfig = useConfigStore((s) => s.load)
  const [logoutConfirm, setLogoutConfirm] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [resourcesOpen, setResourcesOpen] = useState(false)
  const [resendSent, setResendSent] = useState(false)

  async function handleResendVerification() {
    const res = await apiFetch('/api/auth/resend-verification', { method: 'POST' })
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
        setUser({
          id: me.id,
          username: me.username,
          displayName: me.display_name,
          email: me.email,
          native_language: me.native_language,
          target_language: me.target_language,
          role: me.role,
          conversation_max_duration: me.conversation_max_duration,
          conversation_inactivity_timeout: me.conversation_inactivity_timeout,
          avatar: me.avatar ?? null,
          is_verified: me.is_verified ?? true,
          bio: me.bio ?? null,
          learning_goals: me.learning_goals ?? [],
          subscription_status: me.subscription_status ?? 'none',
          subscription_ends_at: me.subscription_ends_at ?? null,
        })
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

  async function handleLogout() {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    logout()
    router.push('/login')
  }

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-fl-bg"
        style={{ backgroundImage: 'radial-gradient(circle, var(--fl-dot) 1px, transparent 1px)', backgroundSize: '24px 24px' }}>
        <span className="font-mono text-xs text-fl-muted-2 tracking-widest uppercase animate-pulse">● {tCommon('initializing')}</span>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-fl-bg">
      {/* Sidebar */}
      <aside className="hidden md:flex w-52 flex-col border-r border-fl-border bg-fl-bg px-0 py-0 shrink-0">
        {/* Logo area */}
        <div className="flex items-center gap-2 px-5 py-5 border-b border-fl-border">
          <span className="text-fl-label text-fl-muted-2">●</span>
          <span className="font-mono text-sm font-bold tracking-widest text-fl-fg uppercase">FreeLingo</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {/* Main items */}
          {mainNavItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-5 py-3 text-xs font-mono tracking-widest transition-colors ${active
                  ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                  : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                  }`}
              >
                <span className={`text-fl-label ${active ? 'text-fl-accent' : 'text-fl-muted-4'}`}>●</span>
                {item.label}
              </Link>
            )
          })}

          {/* Resources group */}
          <div className="mt-2">
            <button
              onClick={() => setResourcesOpen((o) => !o)}
              className="w-full flex items-center justify-between px-5 py-2 text-xs font-mono tracking-widest text-fl-muted-4 hover:text-fl-muted-2 transition-colors uppercase border-l-2 border-transparent"
            >
              <span>{tNav('resources')}</span>
              <span className="text-fl-label">{resourcesOpen ? '▴' : '▾'}</span>
            </button>
            {resourcesOpen && resourceNavItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 pl-8 pr-5 py-2.5 text-xs font-mono tracking-widest transition-colors ${active
                    ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                    : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                    }`}
                >
                  <span className={`text-fl-label ${active ? 'text-fl-accent' : 'text-fl-muted-4'}`}>·</span>
                  {item.label}
                </Link>
              )
            })}
          </div>

          {/* Bottom items */}
          <div className="mt-2 border-t border-fl-border pt-2">
            {bottomNavItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-5 py-3 text-xs font-mono tracking-widest transition-colors ${active
                    ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                    : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                    }`}
                >
                  <span className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}>●</span>
                  {item.label}
                </Link>
              )
            })}
          </div>

          {user?.role === 'admin' && (
            <Link
              href="/admin/users"
              className={`flex items-center gap-3 px-5 py-3 text-xs font-mono tracking-widest transition-colors ${pathname.startsWith('/admin')
                ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                }`}
            >
              <span className="text-fl-label text-fl-muted-4">●</span>
              {tNav('admin')}
            </Link>
          )}
        </nav>

        {/* User + logout */}
        <div className="border-t border-fl-border px-5 py-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full overflow-hidden border border-fl-border flex-shrink-0">
              {user?.avatar ? (
                <Image src={user.avatar} alt="" width={32} height={32} className="w-full h-full object-cover" unoptimized />
              ) : (
                <div className="w-full h-full bg-fl-surface-2 flex items-center justify-center">
                  <span className="font-mono text-xs text-fl-muted-1 select-none">
                    {(user?.displayName || user?.username || '?')[0].toUpperCase()}
                  </span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <p className="text-fl-caption font-mono text-fl-muted-2 tracking-widest uppercase truncate">
                {user?.displayName || user?.username}
              </p>
              <p className="text-fl-label font-mono text-fl-muted-4 truncate">@{user?.username}</p>
            </div>
          </div>
          <p className="font-mono text-fl-label text-fl-muted-4 tracking-wider mb-2">v1.4.17</p>
          <button
            onClick={() => setLogoutConfirm(true)}
            className="w-full text-left text-fl-label font-mono tracking-widest text-fl-muted-2 hover:text-fl-fg transition-colors uppercase"
          >
            — {tCommon('logout')}
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 border-b border-fl-border bg-fl-bg">
        <div className="flex items-center justify-between px-4 py-3">
          <span className="font-mono text-xs font-bold tracking-widest text-fl-fg uppercase">FreeLingo</span>
          <button
            onClick={() => setMobileMenuOpen((o) => !o)}
            className="font-mono text-fl-muted-2 hover:text-fl-fg transition-colors p-1"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            <span className="text-base leading-none">{mobileMenuOpen ? '✕' : '☰'}</span>
          </button>
        </div>

        {/* Dropdown */}
        {mobileMenuOpen && (
          <nav className="border-t border-fl-border bg-fl-bg pb-2">
            {mainNavItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${active
                    ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                    : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                    }`}
                >
                  <span className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}>●</span>
                  {item.label}
                </Link>
              )
            })}

            {/* Resources group (mobile) */}
            <div>
              <button
                onClick={() => setResourcesOpen((o) => !o)}
                className="w-full flex items-center justify-between px-5 py-2 font-mono text-xs tracking-widest text-fl-muted-4 hover:text-fl-muted-2 transition-colors uppercase border-l-2 border-transparent"
              >
                <span>{tNav('resources')}</span>
                <span className="text-fl-label">{resourcesOpen ? '▴' : '▾'}</span>
              </button>
              {resourcesOpen && resourceNavItems.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + '/')
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 pl-8 pr-5 py-2.5 font-mono text-xs tracking-widest uppercase transition-colors ${active
                      ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                      : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                      }`}
                  >
                    <span className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}>·</span>
                    {item.label}
                  </Link>
                )
              })}
            </div>

            {/* Bottom items (mobile) */}
            {bottomNavItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${active
                    ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                    : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                    }`}
                >
                  <span className={`text-fl-label ${active ? 'text-fl-fg' : 'text-fl-muted-4'}`}>●</span>
                  {item.label}
                </Link>
              )
            })}

            {user?.role === 'admin' && (
              <Link
                href="/admin/users"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 px-5 py-3 font-mono text-xs tracking-widest uppercase transition-colors ${pathname.startsWith('/admin')
                  ? 'text-fl-fg bg-fl-surface-2 border-l-2 border-fl-accent'
                  : 'text-fl-muted-2 hover:text-fl-fg hover:bg-fl-surface border-l-2 border-transparent'
                  }`}
              >
                <span className="text-fl-label text-fl-muted-4">●</span>
                {tNav('admin')}
              </Link>
            )}
            <div className="border-t border-fl-border mx-5 mt-2 pt-3">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-7 h-7 rounded-full overflow-hidden border border-fl-border flex-shrink-0">
                  {user?.avatar ? (
                    <Image src={user.avatar} alt="" width={28} height={28} className="w-full h-full object-cover" unoptimized />
                  ) : (
                    <div className="w-full h-full bg-fl-surface-2 flex items-center justify-center">
                      <span className="font-mono text-fl-hint text-fl-muted-1 select-none">
                        {(user?.displayName || user?.username || '?')[0].toUpperCase()}
                      </span>
                    </div>
                  )}
                </div>
                <p className="font-mono text-fl-label text-fl-muted-4 truncate">@{user?.username}</p>
              </div>
              <p className="font-mono text-fl-label text-fl-muted-4 tracking-wider mb-2">v1.4.17</p>
              <button
                onClick={() => { setMobileMenuOpen(false); setLogoutConfirm(true) }}
                className="font-mono text-fl-label tracking-widest text-fl-muted-2 hover:text-fl-fg transition-colors uppercase"
              >
                — {tCommon('logout')}
              </button>
            </div>
          </nav>
        )}
      </div>

      {/* Main */}
      <main className="flex-1 overflow-y-auto pt-14 md:pt-0 min-h-screen">
        {/* Email verification banner */}
        {user && user.is_verified === false && (
          <div className="border-b border-fl-border bg-fl-surface px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="font-mono text-xs text-fl-muted-1 tracking-wide">
              ● {tCommon('verifyEmailBanner')}
            </span>
            {resendSent ? (
              <span className="font-mono text-xs text-fl-muted-2">{tCommon('verifyEmailSent')}</span>
            ) : (
              <button
                onClick={handleResendVerification}
                className="font-mono text-xs text-fl-accent underline hover:no-underline transition-all"
              >
                {tCommon('resendVerification')}
              </button>
            )}
          </div>
        )}
        {children}
      </main>

      <LoadingBar />

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
