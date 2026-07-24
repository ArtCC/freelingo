import { create } from 'zustand'

import { useConfigStore } from '@/store/config'

export type SubscriptionStatus =
  | 'none'
  | 'incomplete'
  | 'incomplete_expired'
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'canceled'
  | 'unpaid'
  | 'paused'

export interface User {
  id: number
  username: string
  displayName: string
  email?: string
  native_language?: string
  target_language?: string
  ui_locale?: string | null
  role: 'admin' | 'user'
  conversation_max_duration: number
  conversation_inactivity_timeout: number
  avatar?: string | null
  is_verified?: boolean
  bio?: string | null
  learning_goals?: string[] | null
  subscription_status?: SubscriptionStatus
  subscription_ends_at?: string | null
  cancel_at_period_end?: boolean
  trial_used?: boolean
  assessment_voice_trial_used?: boolean
  freemium_trial_ends_at?: string | null
  freemium_trial_used?: boolean
}

/** Returns true when the user has an active/trialing subscription, or when Stripe is disabled (self-hosted). */
export function isSubscribed(
  user: User | null,
  stripeEnabled: boolean
): boolean {
  if (!stripeEnabled) return true
  if (!user) return false
  return (
    user.subscription_status === 'active' ||
    user.subscription_status === 'trialing'
  )
}

export function needsPaymentRecovery(user: User | null): boolean {
  return (
    user?.subscription_status === 'past_due' ||
    user?.subscription_status === 'unpaid' ||
    user?.subscription_status === 'paused'
  )
}

export function isFreemiumTrialActive(
  user: User | null,
  stripeEnabled: boolean
): boolean {
  if (!stripeEnabled) return false
  if (!useConfigStore.getState().freemiumTrialEnabled) return false
  if (!user?.freemium_trial_ends_at) return false
  return new Date(user.freemium_trial_ends_at) > new Date()
}

interface AuthStore {
  accessToken: string | null
  user: User | null
  setTokens: (access: string) => void
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  accessToken: null,
  user: null,
  setTokens: (access: string) => set({ accessToken: access }),
  setUser: (user: User) => set({ user }),
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('fl_tour_done')
    }
    set({ accessToken: null, user: null })
  },
}))
