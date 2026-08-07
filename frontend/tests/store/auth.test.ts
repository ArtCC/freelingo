import { describe, it, expect, beforeEach } from 'vitest'
import { isSubscribed, useAuthStore, type User } from '@/store/auth'

describe('isSubscribed', () => {
  const baseUser: User = {
    id: 1,
    username: 'test',
    displayName: 'Test',
    role: 'user',
    conversation_max_duration: 300,
    conversation_inactivity_timeout: 30,
  }

  it('returns true when Stripe is disabled (self-hosted)', () => {
    expect(isSubscribed(null, false)).toBe(true)
    expect(isSubscribed(baseUser, false)).toBe(true)
  })

  it('returns false when Stripe is enabled and user is null', () => {
    expect(isSubscribed(null, true)).toBe(false)
  })

  it('returns true for active subscription', () => {
    const user = { ...baseUser, subscription_status: 'active' as const }
    expect(isSubscribed(user, true)).toBe(true)
  })

  it('returns true for trialing subscription', () => {
    const user = { ...baseUser, subscription_status: 'trialing' as const }
    expect(isSubscribed(user, true)).toBe(true)
  })

  it('returns false for past_due subscription', () => {
    const user = { ...baseUser, subscription_status: 'past_due' as const }
    expect(isSubscribed(user, true)).toBe(false)
  })

  it('returns false for canceled subscription', () => {
    const user = { ...baseUser, subscription_status: 'canceled' as const }
    expect(isSubscribed(user, true)).toBe(false)
  })

  it('returns false for none subscription', () => {
    const user = { ...baseUser, subscription_status: 'none' as const }
    expect(isSubscribed(user, true)).toBe(false)
  })

  it('returns false when subscription_status is undefined', () => {
    expect(isSubscribed(baseUser, true)).toBe(false)
  })
})

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: null, user: null })
    localStorage.clear()
  })

  it('setTokens updates accessToken', () => {
    useAuthStore.getState().setTokens('abc123')
    expect(useAuthStore.getState().accessToken).toBe('abc123')
  })

  it('setUser updates user', () => {
    const user: User = {
      id: 1,
      username: 'test',
      displayName: 'Test',
      role: 'user',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
    }
    useAuthStore.getState().setUser(user)
    expect(useAuthStore.getState().user).toEqual(user)
  })

  it('updates the dismissed dashboard banner revision on the current user', () => {
    useAuthStore.setState({ user: { id: 1 } as User })

    useAuthStore.getState().setDismissedDashboardBannerRevision(8)

    expect(
      useAuthStore.getState().user?.dismissed_dashboard_banner_revision
    ).toBe(8)
  })

  it('logout clears token, user, and fl_tour_done from localStorage', () => {
    useAuthStore.setState({ accessToken: 'token', user: { id: 1 } as User })
    localStorage.setItem('fl_tour_done', 'true')

    useAuthStore.getState().logout()

    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
    expect(localStorage.getItem('fl_tour_done')).toBeNull()
  })
})
