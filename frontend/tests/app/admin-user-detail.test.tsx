import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'

vi.mock('next-intl', () => ({
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

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '7' }),
  usePathname: () => '/admin/users/7',
}))

const { mockApiFetch } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

import AdminUserStatsPage from '@/app/(app)/admin/users/[id]/page'
import { useConfigStore } from '@/store/config'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const user = {
  id: 7,
  username: 'ada',
  display_name: 'Ada',
  email: 'ada@example.com',
  role: 'user',
  native_language: 'en',
  is_active: true,
  is_verified: true,
  subscription_status: 'active',
  subscription_ends_at: '2027-01-01T00:00:00Z',
  stripe_customer_id: 'cus_test',
  conversation_weekly_sessions: 5,
  conversation_daily_minutes: 10,
  conversation_weekly_minutes: 30,
  monthly_tokens_limit: 1000,
}

const stats = {
  user_id: 7,
  current_cefr: 'A1',
  current_unit: null,
  plan_duration_weeks: null,
  completion_test_score: null,
  xp_total: 100,
  streak_current: 2,
  active_days: 3,
  lessons_completed: 4,
  exercises_correct: 8,
  exercises_total: 10,
  chat_messages_sent: 6,
  tokens_total: 20,
  tokens_chat: 12,
  tokens_conversation: 8,
  per_language: [],
}

describe('AdminUserStatsPage subscription visibility', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockImplementation(async (url: string) => {
      if (url === '/api/admin/users/7') return jsonResponse(user)
      if (url === '/api/admin/users/7/stats') return jsonResponse(stats)
      if (url === '/api/admin/users/7/quota') return jsonResponse({})
      return jsonResponse({}, 404)
    })
  })

  it('hides subscription status and controls when Stripe is disabled', async () => {
    useConfigStore.setState({ stripeEnabled: false })

    render(<AdminUserStatsPage />)

    await waitFor(() => expect(screen.getAllByText('Ada').length).toBeGreaterThan(0))
    expect(screen.queryByText('tabSubscription')).toBeNull()
    expect(screen.queryByText('statusActive')).toBeNull()
    expect(screen.queryByText('subscriptionOverride')).toBeNull()
  })

  it('keeps subscription status and controls when Stripe is enabled', async () => {
    useConfigStore.setState({ stripeEnabled: true })

    render(<AdminUserStatsPage />)

    const subscriptionTab = await screen.findByRole('button', {
      name: 'tabSubscription',
    })
    expect(screen.getByText('statusActive')).toBeDefined()
    fireEvent.click(subscriptionTab)
    expect(screen.getByText('subscriptionOverride')).toBeDefined()
    expect(screen.getByText('cus_test')).toBeDefined()
  })
})
