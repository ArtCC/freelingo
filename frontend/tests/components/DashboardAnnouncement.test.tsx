import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardAnnouncement } from '@/components/dashboard/DashboardAnnouncement'
import { useAuthStore, type User } from '@/store/auth'
import { useConfigStore } from '@/store/config'

const mockApiFetch = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', () => ({ apiFetch: mockApiFetch }))
vi.mock('next-intl', () => ({
  useLocale: () => 'es',
  useTranslations: () => (key: string) => {
    if (key === 'announcementDismiss') return 'Cerrar anuncio'
    if (key === 'announcementDismissError') return 'No se pudo cerrar'
    return key
  },
}))

const user = {
  id: 1,
  username: 'learner',
  displayName: 'Learner',
  role: 'user',
  conversation_max_duration: 300,
  conversation_inactivity_timeout: 30,
  dismissed_dashboard_banner_revision: null,
} satisfies User

describe('DashboardAnnouncement', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    useAuthStore.setState({ user })
    useConfigStore.setState({
      dashboardBanner: {
        revision: 7,
        translations: {
          en: { title: 'News', subtitle: 'Today', description: 'English' },
          es: {
            title: 'Novedades',
            subtitle: 'Hoy',
            description: '<strong>Texto sin HTML</strong>',
          },
        },
      },
    })
  })

  it('uses the current locale and hides after the exact revision is dismissed', async () => {
    mockApiFetch.mockResolvedValue(new Response(null, { status: 204 }))
    render(<DashboardAnnouncement />)

    expect(screen.getByText('Novedades')).toBeInTheDocument()
    expect(
      screen.getByText('<strong>Texto sin HTML</strong>')
    ).toBeInTheDocument()
    expect(document.querySelector('strong')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar anuncio' }))

    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/api/dashboard-banner/dismiss',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ revision: 7 }),
        })
      )
    )
    await waitFor(() =>
      expect(screen.queryByText('Novedades')).not.toBeInTheDocument()
    )
    expect(
      useAuthStore.getState().user?.dismissed_dashboard_banner_revision
    ).toBe(7)
  })

  it('remains visible and reports a compact error when dismissal fails', async () => {
    mockApiFetch.mockResolvedValue(new Response(null, { status: 500 }))
    render(<DashboardAnnouncement />)

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar anuncio' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo cerrar'
    )
    expect(screen.getByText('Novedades')).toBeInTheDocument()
    expect(
      useAuthStore.getState().user?.dismissed_dashboard_banner_revision
    ).toBeNull()
  })

  it('does not render when the user dismissed the current revision', () => {
    useAuthStore.setState({
      user: { ...user, dismissed_dashboard_banner_revision: 7 },
    })

    render(<DashboardAnnouncement />)

    expect(screen.queryByText('Novedades')).not.toBeInTheDocument()
  })
})
