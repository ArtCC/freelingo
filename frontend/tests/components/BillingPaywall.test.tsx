import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'

vi.mock('next-intl', () => ({
  useLocale: () => 'en',
  useTranslations: () => (key: string) => key,
}))

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) =>
    React.createElement('a', { href: String(href), ...props }, children),
}))

vi.mock('@/components/tour/OnboardingTour', () => ({
  default: () => null,
}))

vi.mock('@/components/whats-new/WhatsNew', () => ({
  default: () => null,
}))

vi.mock('@/components/ui/page-loading', () => ({
  PageLoading: ({ label }: { label: string }) => <div>{label}</div>,
}))

const { mockApiFetch, mockLandingSubscriptionState } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
  mockLandingSubscriptionState: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

vi.mock('@/lib/landing-subscription', () => ({
  getLandingSubscriptionState: mockLandingSubscriptionState,
}))

import PricingSection from '@/components/billing/PricingSection'
import { PaywallBanner } from '@/components/billing/PaywallBanner'
import { BillingSection } from '@/components/settings/BillingSection'
import DashboardPage from '@/app/(app)/dashboard/page'
import { useAuthStore, type User } from '@/store/auth'
import { useConfigStore } from '@/store/config'
import { useLanguageStore } from '@/store/language'
import { useProgressStore } from '@/store/progress'
import { getLanguageByCode } from '@/lib/target-languages'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function user(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: 'learner',
    displayName: 'Learner',
    email: 'learner@example.com',
    native_language: 'es',
    ui_locale: 'en',
    role: 'user' as const,
    conversation_max_duration: 30,
    conversation_inactivity_timeout: 10,
    avatar: null,
    is_verified: true,
    bio: null,
    learning_goals: [],
    subscription_status: 'none',
    subscription_ends_at: null,
    trial_used: false,
    ...overrides,
  }
}

function resetStores() {
  useAuthStore.setState({ accessToken: 'token', user: user() })
  useConfigStore.setState({
    stripeEnabled: true,
    stripeTrialDays: 7,
    ttsProvider: 'local',
    openaiTtsVoice: 'nova',
    maintenanceMode: false,
    priceMonthly: 9.99,
    priceYearly: 99.99,
    totalPriceMonthly: 119.88,
    totalPriceYearly: 99.99,
    loaded: true,
  })
  useLanguageStore.setState({
    activeLanguage: getLanguageByCode('en-GB') ?? null,
    userLanguages: [],
    supportedLanguages: [],
    availableLanguageCodes: [],
    isSwitching: false,
  })
  useProgressStore.setState({
    streak: 0,
    xp: 0,
    skills: {},
    todayLessons: [],
    completedToday: [],
    currentUnitId: '',
    currentPlanDurationWeeks: 12,
    unitProgress: {},
    levelTestUnlocked: false,
    levelTestResult: null,
  })
}

beforeEach(() => {
  mockApiFetch.mockReset()
  mockLandingSubscriptionState.mockReset()
  resetStores()
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { assign: vi.fn() },
  })
})

describe('billing paywall UI', () => {
  it('opens Customer Portal for past_due users in Settings instead of showing plan buttons', async () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'past_due' }),
    })
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({ url: 'https://billing.stripe.com/session/test' })
    )

    render(<BillingSection />)

    expect(screen.getByText('pastDueTitle')).toBeDefined()
    expect(screen.getByText('pastDueDesc')).toBeDefined()
    expect(screen.queryByText('planMonthly')).toBeNull()

    fireEvent.click(screen.getByText('updatePayment'))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/api/billing/portal', {
        method: 'POST',
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://billing.stripe.com/session/test'
    )
  })

  it('opens Customer Portal for unpaid users in Settings instead of showing plan buttons', async () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'unpaid' }),
    })
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({ url: 'https://billing.stripe.com/session/unpaid' })
    )

    render(<BillingSection />)

    expect(screen.getByText('statusUnpaid')).toBeDefined()
    expect(screen.getByText('pastDueTitle')).toBeDefined()
    expect(screen.queryByText('planMonthly')).toBeNull()

    fireEvent.click(screen.getByText('updatePayment'))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/api/billing/portal', {
        method: 'POST',
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://billing.stripe.com/session/unpaid'
    )
  })

  it('opens Customer Portal for paused users in Settings instead of showing plan buttons', async () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'paused' }),
    })
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({ url: 'https://billing.stripe.com/session/paused' })
    )

    render(<BillingSection />)

    expect(screen.getByText('statusPaused')).toBeDefined()
    expect(screen.getByText('pastDueTitle')).toBeDefined()
    expect(screen.queryByText('planMonthly')).toBeNull()

    fireEvent.click(screen.getByText('updatePayment'))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/api/billing/portal', {
        method: 'POST',
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://billing.stripe.com/session/paused'
    )
  })

  it('shows subscription plan buttons for canceled users in Settings', () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'canceled' }),
    })

    render(<BillingSection />)

    expect(screen.getByText('statusCanceled')).toBeDefined()
    expect(screen.getByText('planMonthly')).toBeDefined()
    expect(screen.getByText('planYearly')).toBeDefined()
    expect(screen.queryByText('updatePayment')).toBeNull()
  })

  it.each(['incomplete', 'incomplete_expired'] as const)(
    'shows subscription plan buttons for %s users in Settings',
    (subscriptionStatus) => {
      useAuthStore.setState({
        accessToken: 'token',
        user: user({ subscription_status: subscriptionStatus }),
      })

      render(<BillingSection />)

      expect(
        screen.getByText(
          subscriptionStatus === 'incomplete'
            ? 'statusIncomplete'
            : 'statusIncompleteExpired'
        )
      ).toBeDefined()
      expect(screen.getByText('planMonthly')).toBeDefined()
      expect(screen.getByText('planYearly')).toBeDefined()
      expect(screen.queryByText('updatePayment')).toBeNull()
    }
  )

  it('shows subscription plan buttons for users without a subscription in Settings', () => {
    render(<BillingSection />)

    expect(screen.getByText('planMonthly')).toBeDefined()
    expect(screen.getByText('planYearly')).toBeDefined()
    expect(screen.queryByText('pastDueTitle')).toBeNull()
  })

  it('uses payment-recovery copy and portal action for past_due users on dashboard', async () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'past_due' }),
    })
    mockApiFetch
      .mockResolvedValueOnce(
        jsonResponse({
          current_streak: 0,
          total_xp: 0,
          skills: {},
          total_lessons: 0,
          total_exercises: 0,
          exercises_correct: 0,
          accuracy: 0,
          vocabulary_level: null,
          vocabulary_mastered: 0,
          vocabulary_total: 0,
          vocabulary_progress: 0,
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          cefr_level: 'A1',
          progress_day: 0,
          total_days: 7,
          pending_count: 0,
          lessons: [],
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({ url: 'https://billing.stripe.com/session/dashboard' })
      )

    render(<DashboardPage />)

    await waitFor(() =>
      expect(screen.getByText('premiumBannerPastDueTitle')).toBeDefined()
    )
    expect(screen.getByText('premiumBannerPastDueDesc')).toBeDefined()
    expect(screen.queryByText('planMonthly')).toBeNull()

    fireEvent.click(screen.getByText('updatePayment'))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenLastCalledWith('/api/billing/portal', {
        method: 'POST',
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://billing.stripe.com/session/dashboard'
    )
  })

  it('uses payment-recovery copy and portal action for paused users on dashboard', async () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'paused' }),
    })
    mockApiFetch
      .mockResolvedValueOnce(
        jsonResponse({
          current_streak: 0,
          total_xp: 0,
          skills: {},
          total_lessons: 0,
          total_exercises: 0,
          exercises_correct: 0,
          accuracy: 0,
          vocabulary_level: null,
          vocabulary_mastered: 0,
          vocabulary_total: 0,
          vocabulary_progress: 0,
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          cefr_level: 'A1',
          progress_day: 0,
          total_days: 7,
          pending_count: 0,
          lessons: [],
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({ url: 'https://billing.stripe.com/session/paused' })
      )

    render(<DashboardPage />)

    await waitFor(() =>
      expect(screen.getByText('premiumBannerPastDueTitle')).toBeDefined()
    )
    expect(screen.queryByText('planMonthly')).toBeNull()

    fireEvent.click(screen.getByText('updatePayment'))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenLastCalledWith('/api/billing/portal', {
        method: 'POST',
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://billing.stripe.com/session/paused'
    )
  })

  it('uses Customer Portal instead of checkout buttons for recovery states in PaywallBanner', async () => {
    useAuthStore.setState({
      accessToken: 'token',
      user: user({ subscription_status: 'unpaid' }),
    })
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({ url: 'https://billing.stripe.com/session/paywall' })
    )

    render(<PaywallBanner />)

    expect(screen.getByText('premiumBannerPastDueTitle')).toBeDefined()
    expect(screen.getByText('premiumBannerPastDueDesc')).toBeDefined()
    expect(screen.getByText('updatePayment')).toBeDefined()
    expect(screen.queryByText('planMonthly')).toBeNull()
    expect(screen.queryByText('paywallNoCharge')).toBeNull()
    expect(screen.queryByText('paywallNoChargeTrialUsed')).toBeNull()

    fireEvent.click(screen.getByText('updatePayment'))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/api/billing/portal', {
        method: 'POST',
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://billing.stripe.com/session/paywall'
    )
  })

  it('starts Checkout directly from landing pricing when the user has a session', async () => {
    mockLandingSubscriptionState.mockResolvedValueOnce({
      subscribed: false,
      trialUsed: false,
    })
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({ url: 'https://checkout.stripe.com/pay/monthly' })
    )

    render(
      <PricingSection
        stripeEnabled={true}
        trialDays={7}
        hasSession={true}
        priceMonthly={9.99}
        priceYearly={99.99}
        totalPriceMonthly={119.88}
        totalPriceYearly={99.99}
      />
    )

    await waitFor(() =>
      expect(screen.getAllByText('ctaRegister')).toHaveLength(3)
    )
    fireEvent.click(screen.getAllByText('ctaRegister')[0])

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: 'monthly' }),
      })
    )
    expect(window.location.assign).toHaveBeenCalledWith(
      'https://checkout.stripe.com/pay/monthly'
    )
  })
})
