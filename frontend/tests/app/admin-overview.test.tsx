import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
  usePathname: () => '/admin',
}))

const { mockApiFetch } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

import AdminOverviewPage from '@/app/(app)/admin/page'
import { useConfigStore } from '@/store/config'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('AdminOverviewPage', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    useConfigStore.setState({ maintenanceMode: false, stripeEnabled: true })
  })

  it('loads and renders admin overview stats', async () => {
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({
        users_total: 12,
        users_active: 10,
        users_inactive: 2,
        subscriptions_active: 4,
        subscriptions_trialing: 3,
        subscriptions_past_due: 1,
        feedback_total: 9,
        feedback_pending: 5,
        feedback_bug_pending: 2,
      })
    )

    render(<AdminOverviewPage />)

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/api/admin/stats')
    )
    expect(screen.getByText('12')).toBeDefined()
    expect(screen.getByText('10')).toBeDefined()
    expect(screen.getByText('4 / 3')).toBeDefined()
    expect(screen.getByText('5')).toBeDefined()
    expect(screen.getByText('pendingBugs')).toBeDefined()
    expect(screen.getByText('pastDueSubscriptions')).toBeDefined()
  })

  it('shows a translated error when stats fail to load', async () => {
    mockApiFetch.mockResolvedValueOnce(jsonResponse({}, 500))

    render(<AdminOverviewPage />)

    await waitFor(() =>
      expect(screen.getByText('adminStatsError')).toBeDefined()
    )
  })

  it('hides subscription metrics and alerts when Stripe is disabled', async () => {
    useConfigStore.setState({ stripeEnabled: false })
    mockApiFetch.mockResolvedValueOnce(
      jsonResponse({
        users_total: 12,
        users_active: 10,
        subscriptions_active: 4,
        subscriptions_trialing: 3,
        subscriptions_past_due: 1,
        feedback_pending: 5,
        feedback_bug_pending: 2,
        reviews_pending: 1,
      })
    )

    render(<AdminOverviewPage />)

    await waitFor(() => expect(screen.getByText('12')).toBeDefined())
    expect(screen.queryByText('paidAccess')).toBeNull()
    expect(screen.queryByText('4 / 3')).toBeNull()
    expect(screen.queryByText('pastDueSubscriptions')).toBeNull()
  })
})
