import Link from 'next/link'
import Image from 'next/image'
import { cookies } from 'next/headers'
import { getTranslations } from 'next-intl/server'
import type { Metadata } from 'next'
import {
  Sparkles,
  ArrowRight,
  Bot,
  Mic,
  Volume2,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react'
import PricingSection from '@/components/billing/PricingSection'
import { LandingFAQ } from '@/components/ui/landing-faq'
import { LandingNav } from '@/components/ui/landing-nav'
import { ScrollReveal } from '@/components/ui/scroll-reveal'
import { LanguageBubbles } from '@/components/LanguageBubbles'
import { LandingReviewsCarousel } from '@/components/reviews/LandingReviewsCarousel'
import { BentoFeatures } from '@/components/landing/BentoFeatures'
import { AiConversationShowcase } from '@/components/landing/AiConversationShowcase'
import { DashboardPreview } from '@/components/landing/DashboardPreview'
import { LanguageShowcase } from '@/components/landing/LanguageShowcase'
import { LearningExperience } from '@/components/landing/LearningExperience'
import { LandingFooter } from '@/components/landing/LandingFooter'
import type { ReviewPublic } from '@/types/api'

export const metadata: Metadata = {
  title: 'JUBA LISAN: AI-Powered Language Learning Platform',
  description:
    'Learn languages naturally with your personal AI tutor. Master real-time voice conversations, structured CEFR lessons, interactive reading & listening, and smart flashcards.',
  robots: { index: true, follow: true },
  openGraph: {
    title: 'JUBA LISAN: AI-Powered Language Learning Platform',
    description:
      'Learn languages naturally with your personal AI tutor. Master real-time voice conversations, structured CEFR lessons, interactive reading & listening, and smart flashcards.',
    url: 'https://jubalisan.com',
    type: 'website',
    images: [
      {
        url: '/og-image-v2.png',
        width: 1200,
        height: 630,
        alt: 'JUBA LISAN: AI-Powered Language Learning Platform',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'JUBA LISAN: AI-Powered Language Learning Platform',
    description:
      'Learn languages naturally with your personal AI tutor. Master real-time voice conversations, structured CEFR lessons, interactive reading & listening, and smart flashcards.',
    images: ['/og-image-v2.png'],
  },
}

const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'JUBA LISAN',
  applicationCategory: 'EducationApplication',
  operatingSystem: 'Web',
  url: 'https://jubalisan.com',
  description:
    'AI-powered language learning platform with real-time voice conversation, spaced-repetition flashcards, structured CEFR lessons, and interactive AI tutor.',
  offers: {
    '@type': 'Offer',
    price: '0',
    priceCurrency: 'USD',
  },
}

export default async function Home() {
  const cookieStore = await cookies()
  const hasSession = cookieStore.has('refresh_token')
  const t = await getTranslations('landing')
  const tCommon = await getTranslations('common')
  const tBilling = await getTranslations('billing')

  let stripeEnabled = false
  let trialDays = 7
  let priceMonthly = 0.0
  let priceYearly = 0.0
  let totalPriceMonthly = 0.0
  let totalPriceYearly = 0.0
  let reviews: ReviewPublic[] = []
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://backend:8000'
    const [configRes, reviewsRes] = await Promise.all([
      fetch(`${backendUrl}/api/config`, { next: { revalidate: 3600 } }),
      fetch(`${backendUrl}/api/reviews/public?limit=100`, {
        next: { revalidate: 300 },
      }),
    ])
    if (configRes.ok) {
      const cfg = await configRes.json()
      stripeEnabled = cfg.stripe_enabled ?? false
      trialDays = cfg.stripe_trial_days ?? 7
      priceMonthly = cfg.price_monthly ?? 0.0
      priceYearly = cfg.price_yearly ?? 0.0
      totalPriceMonthly = cfg.total_price_monthly ?? 0.0
      totalPriceYearly = cfg.total_price_yearly ?? 0.0
    }
    if (reviewsRes.ok) {
      reviews = await reviewsRes.json()
    }
  } catch {
    /* non-fatal */
  }

  return (
    <div className="min-h-screen flex flex-col bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100 font-sans selection:bg-amber-500/20 selection:text-amber-600 overflow-x-hidden">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Nav */}
      <LandingNav
        hasSession={hasSession}
        stripeEnabled={stripeEnabled}
        navFeatures={t('navFeatures')}
        navReviews={t('navReviews')}
        navPricing={t('navPricing')}
        navFAQ={t('navFAQ')}
        showReviews={reviews.length > 0}
        signIn={t('signIn')}
        dashboard={t('dashboard')}
      />

      {/* Hero Section */}
      <section className="relative pt-12 pb-20 md:pt-20 md:pb-32 overflow-hidden bg-gradient-to-b from-amber-500/5 via-white to-neutral-50 dark:from-neutral-900/50 dark:via-neutral-950 dark:to-neutral-950">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">

            {/* Left Column: Hero Text & Actions */}
            <div className="lg:col-span-7 flex flex-col items-center lg:items-start text-center lg:text-left">

              {/* Floating Language Pills Header */}
              <div className="mb-4">
                <LanguageBubbles />
              </div>

              {/* Badge */}
              <div className="inline-flex items-center gap-2 rounded-full bg-amber-500/10 border border-amber-500/20 px-3.5 py-1.5 text-xs font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-6">
                <Sparkles className="h-4 w-4" />
                {t('heroBadge')}
              </div>

              {/* Main Headline */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight text-neutral-900 dark:text-white leading-[1.15] mb-6">
                {t('heroTitle')}
              </h1>

              {/* Subtitle */}
              <p className="text-lg sm:text-xl text-neutral-600 dark:text-neutral-400 font-normal leading-relaxed max-w-2xl mb-8">
                {t('heroSub')}
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
                <Link
                  href={hasSession ? '/dashboard' : '/register'}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-2xl bg-amber-500 hover:bg-amber-600 text-neutral-950 px-8 py-4 text-base font-bold shadow-lg shadow-amber-500/25 transition-all hover:shadow-amber-500/40 active:scale-95"
                >
                  {hasSession ? t('dashboard') : t('ctaStart')}
                  <ArrowRight className="w-5 h-5" />
                </Link>
                <a
                  href="#features"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-2xl border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-neutral-900 hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-800 dark:text-neutral-200 px-8 py-4 text-base font-bold transition-all shadow-sm"
                >
                  {t('ctaExplore')}
                </a>
              </div>

              {/* Key Trust Highlights */}
              <div className="mt-10 pt-8 border-t border-neutral-200/60 dark:border-neutral-800/60 flex flex-wrap items-center justify-center lg:justify-start gap-6 text-xs font-semibold text-neutral-500 dark:text-neutral-400">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-500" /> Free 7-Day Access
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" /> Real-time Voice VAD
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" /> CEFR Structured Curriculum
                </div>
              </div>
            </div>

            {/* Right Column: AI Tutor Card Showcase */}
            <div className="lg:col-span-5 relative flex justify-center">
              <div className="w-full max-w-md juba-card p-6 bg-white/90 dark:bg-neutral-900/90 backdrop-blur-xl relative z-10">
                <div className="flex items-center justify-between pb-4 border-b border-neutral-100 dark:border-neutral-800 mb-6">
                  <div className="flex items-center gap-3">
                    <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-500 text-white font-extrabold text-xl shadow-md">
                      <Bot className="w-6 h-6" />
                      <span className="absolute -bottom-0.5 -right-0.5 flex h-3.5 w-3.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500"></span>
                      </span>
                    </div>
                    <div>
                      <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">JUBA AI Tutor</h3>
                      <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Active & Ready to speak</p>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold border border-amber-500/20">
                    B2 Upper Intermediate
                  </span>
                </div>

                {/* Simulated Conversation Preview */}
                <div className="space-y-4 mb-6">
                  <div className="bg-neutral-50 dark:bg-neutral-950 p-4 rounded-2xl border border-neutral-100 dark:border-neutral-800">
                    <p className="text-xs text-neutral-500 font-semibold mb-1">JUBA Tutor says:</p>
                    <p className="text-sm text-neutral-800 dark:text-neutral-200 font-medium leading-relaxed">
                      "Bonjour ! Comment puis-je vous aider aujourd'hui ?"
                    </p>
                  </div>

                  {/* Audio Waveform Widget */}
                  <div className="flex items-center justify-between bg-amber-50 dark:bg-amber-950/30 p-4 rounded-2xl border border-amber-500/20">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-amber-500 text-neutral-950 flex items-center justify-center shrink-0 shadow-md">
                        <Mic className="w-5 h-5 animate-pulse" />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-amber-900 dark:text-amber-200">Voice Input Ready</p>
                        <p className="text-[11px] text-amber-700 dark:text-amber-400">Speech detection active</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 h-5">
                      <span className="w-1 bg-amber-500 h-3 rounded-full animate-pulse"></span>
                      <span className="w-1 bg-amber-500 h-5 rounded-full animate-pulse delay-75"></span>
                      <span className="w-1 bg-amber-500 h-2 rounded-full animate-pulse delay-150"></span>
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <Link
                    href={hasSession ? '/dashboard' : '/register'}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-neutral-900 hover:bg-neutral-800 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-white font-bold text-xs transition-all"
                  >
                    Try Conversation Mode <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* Bento Features Section */}
      <ScrollReveal>
        <BentoFeatures t={t} />
      </ScrollReveal>

      {/* AI Conversation Showcase Section */}
      <ScrollReveal>
        <AiConversationShowcase t={t} />
      </ScrollReveal>

      {/* Dashboard Preview Mockup Section */}
      <ScrollReveal>
        <DashboardPreview t={t} />
      </ScrollReveal>

      {/* Supported Languages Showcase Section */}
      <ScrollReveal>
        <LanguageShowcase t={t} />
      </ScrollReveal>

      {/* Learning Experience Timeline Section */}
      <ScrollReveal>
        <LearningExperience t={t} />
      </ScrollReveal>

      {/* Reviews Section */}
      <ScrollReveal>
        <div id="reviews" className="scroll-mt-20">
          <LandingReviewsCarousel reviews={reviews} />
        </div>
      </ScrollReveal>

      {/* Pricing Section */}
      <ScrollReveal>
        <div id="pricing" className="scroll-mt-20">
          <PricingSection
            stripeEnabled={stripeEnabled}
            trialDays={trialDays}
            hasSession={hasSession}
            priceMonthly={priceMonthly}
            priceYearly={priceYearly}
            totalPriceMonthly={totalPriceMonthly}
            totalPriceYearly={totalPriceYearly}
          />
        </div>
      </ScrollReveal>

      {/* Open Source Banner */}
      <ScrollReveal>
        <section className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 pb-16 pt-8">
          <div className="juba-card p-8 flex flex-col items-center justify-between gap-6 sm:flex-row bg-gradient-to-r from-neutral-900 to-neutral-950 text-white">
            <div className="flex items-center gap-4">
              <Image
                src="/github_white.svg"
                alt="GitHub"
                width={28}
                height={28}
                className="opacity-90"
              />
              <div className="text-left">
                <p className="font-bold text-base tracking-tight text-white">
                  {tBilling('openSourceTitle')}
                </p>
                <p className="text-xs text-neutral-400 mt-1">
                  {tBilling('openSourceDesc')}
                </p>
              </div>
            </div>
            <a
              href="https://github.com/ArtCC/freelingo"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl border border-neutral-700 bg-neutral-800 hover:bg-neutral-700 text-white px-6 py-2.5 text-xs font-bold tracking-wider uppercase transition-colors whitespace-nowrap"
            >
              {tBilling('openSourceCta')}
            </a>
          </div>
        </section>
      </ScrollReveal>

      {/* FAQ Section */}
      <ScrollReveal>
        <section
          id="faq"
          className="mx-auto w-full max-w-5xl scroll-mt-20 px-4 sm:px-6 pb-20"
        >
          <div className="text-center mb-12">
            <h2 className="text-3xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
              {t('faqTitle')}
            </h2>
          </div>
          <LandingFAQ />
        </section>
      </ScrollReveal>

      {/* Redesigned Footer */}
      <LandingFooter t={t} />
    </div>
  )
}
