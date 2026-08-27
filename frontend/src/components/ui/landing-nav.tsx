'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { Menu, X } from 'lucide-react'
import { hasActiveLandingSubscription } from '@/lib/landing-subscription'

interface LandingNavProps {
  hasSession: boolean
  stripeEnabled: boolean
  navFeatures: string
  navReviews: string
  navPricing: string
  navFAQ: string
  showReviews: boolean
  signIn: string
  dashboard: string
}

export function LandingNav({
  hasSession,
  stripeEnabled,
  navFeatures,
  navReviews,
  navPricing,
  navFAQ,
  showReviews,
  signIn,
  dashboard,
}: LandingNavProps) {
  const [open, setOpen] = useState(false)
  const [showPricing, setShowPricing] = useState(stripeEnabled && !hasSession)

  useEffect(() => {
    let canceled = false

    if (!stripeEnabled) {
      setShowPricing(false)
      return
    }

    if (!hasSession) {
      setShowPricing(true)
      return
    }

    setShowPricing(false)
    async function checkSubscription() {
      const subscribed = await hasActiveLandingSubscription()
      if (!canceled) setShowPricing(!subscribed)
    }
    checkSubscription()

    return () => {
      canceled = true
    }
  }, [hasSession, stripeEnabled])

  const links = (
    <>
      <a
        href="#features"
        onClick={() => setOpen(false)}
        className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white text-sm font-medium transition-colors"
      >
        {navFeatures}
      </a>
      <a
        href="#demo"
        onClick={() => setOpen(false)}
        className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white text-sm font-medium transition-colors"
      >
        AI Demo
      </a>
      <a
        href="#languages"
        onClick={() => setOpen(false)}
        className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white text-sm font-medium transition-colors"
      >
        Languages
      </a>
      {showReviews && (
        <a
          href="#reviews"
          onClick={() => setOpen(false)}
          className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white text-sm font-medium transition-colors"
        >
          {navReviews}
        </a>
      )}
      {showPricing && (
        <a
          href="#pricing"
          onClick={() => setOpen(false)}
          className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white text-sm font-medium transition-colors"
        >
          {navPricing}
        </a>
      )}
      <a
        href="#faq"
        onClick={() => setOpen(false)}
        className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white text-sm font-medium transition-colors"
      >
        {navFAQ}
      </a>
    </>
  )

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-neutral-200/80 bg-white/80 backdrop-blur-md transition-all dark:border-neutral-800/80 dark:bg-neutral-950/80">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500 text-white font-bold text-lg shadow-md shadow-amber-500/20 group-hover:scale-105 transition-transform">
            J
          </div>
          <span className="font-sans text-lg font-extrabold tracking-tight text-neutral-900 dark:text-white">
            JUBA <span className="text-amber-600 dark:text-amber-400">LISAN</span>
          </span>
        </Link>

        {/* Desktop links */}
        <div className="hidden items-center gap-8 md:flex">
          {links}
        </div>

        {/* Actions */}
        <div className="hidden items-center gap-4 md:flex">
          <Link
            href={hasSession ? '/dashboard' : '/login'}
            className="text-sm font-semibold text-neutral-700 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white transition-colors"
          >
            {hasSession ? dashboard : signIn}
          </Link>
          <Link
            href={hasSession ? '/dashboard' : '/register'}
            className="rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-amber-500/20 hover:bg-amber-600 hover:shadow-lg transition-all active:scale-95"
          >
            {hasSession ? dashboard : 'Get Started'}
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen(!open)}
          className="rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 md:hidden dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-white"
          aria-label="Toggle menu"
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="border-b border-neutral-200 bg-white px-6 pt-4 pb-6 md:hidden dark:border-neutral-800 dark:bg-neutral-950 animate-in slide-in-from-top-2 duration-200">
          <div className="flex flex-col gap-4">
            {links}
            <div className="pt-2 border-t border-neutral-100 dark:border-neutral-900 flex flex-col gap-3">
              <Link
                href={hasSession ? '/dashboard' : '/login'}
                onClick={() => setOpen(false)}
                className="w-full text-center py-2 text-sm font-semibold text-neutral-700 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white"
              >
                {hasSession ? dashboard : signIn}
              </Link>
              <Link
                href={hasSession ? '/dashboard' : '/register'}
                onClick={() => setOpen(false)}
                className="w-full text-center rounded-xl bg-amber-500 py-2.5 text-sm font-semibold text-white shadow-md shadow-amber-500/20 hover:bg-amber-600"
              >
                {hasSession ? dashboard : 'Get Started'}
              </Link>
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}
