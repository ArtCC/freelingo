import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminSystemPage from '@/app/(app)/admin/system/page'

const mockApiFetch = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', () => ({ apiFetch: mockApiFetch }))
vi.mock('next-intl', () => ({
  useLocale: () => 'es',
  useTranslations:
    () => (key: string, values?: Record<string, string | number>) => {
      if (key === 'dashboardBanner.completion') {
        return `${values?.complete}/${values?.total} complete`
      }
      return key
    },
}))
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) =>
    React.createElement('a', { href }, children),
}))
vi.mock('next/navigation', () => ({
  usePathname: () => '/admin/system',
}))

const locales = ['en', 'es', 'fr', 'pt', 'de', 'it', 'ru', 'nl', 'pl', 'ro']
const generatedTranslations = Object.fromEntries(
  locales.map((locale) => [
    locale,
    {
      title: `${locale} title`,
      subtitle: `${locale} subtitle`,
      description: `${locale} description`,
    },
  ])
)

describe('Admin system dashboard banner', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(null), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
  })

  it('translates local source content and saves editable translations', async () => {
    mockApiFetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ translations: generatedTranslations }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            source_locale: 'es',
            is_active: true,
            revision: 2,
            translations: generatedTranslations,
            created_at: '2026-08-06T09:00:00Z',
            updated_at: '2026-08-06T10:00:00Z',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      )

    render(<AdminSystemPage />)
    await screen.findByText('dashboardBanner.description')

    fireEvent.change(screen.getByLabelText('dashboardBanner.fieldTitle'), {
      target: { value: 'Aviso' },
    })
    fireEvent.change(screen.getByLabelText('dashboardBanner.fieldSubtitle'), {
      target: { value: 'Importante' },
    })
    fireEvent.change(
      screen.getByLabelText('dashboardBanner.fieldDescription'),
      {
        target: { value: 'Contenido' },
      }
    )
    fireEvent.click(screen.getByText('dashboardBanner.translate'))

    expect(await screen.findByDisplayValue('es title')).toBeInTheDocument()
    expect(mockApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/admin/dashboard-banner/translate',
      expect.objectContaining({
        body: JSON.stringify({
          source_locale: 'es',
          title: 'Aviso',
          subtitle: 'Importante',
          description: 'Contenido',
        }),
      })
    )

    fireEvent.change(screen.getByDisplayValue('es title'), {
      target: { value: 'Título corregido' },
    })
    fireEvent.click(screen.getByText('dashboardBanner.save'))

    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledTimes(3))
    const saveOptions = mockApiFetch.mock.calls[2][1]
    expect(JSON.parse(saveOptions.body).translations.es.title).toBe(
      'Título corregido'
    )
    expect(await screen.findByText('dashboardBanner.saveSuccess')).toBeVisible()
  })

  it('keeps source editor content when translation fails', async () => {
    mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 500 }))
    render(<AdminSystemPage />)
    await screen.findByText('dashboardBanner.description')

    const title = screen.getByLabelText('dashboardBanner.fieldTitle')
    fireEvent.change(title, { target: { value: 'Keep this' } })
    fireEvent.change(screen.getByLabelText('dashboardBanner.fieldSubtitle'), {
      target: { value: 'Subtitle' },
    })
    fireEvent.change(
      screen.getByLabelText('dashboardBanner.fieldDescription'),
      {
        target: { value: 'Description' },
      }
    )
    fireEvent.click(screen.getByText('dashboardBanner.translate'))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'dashboardBanner.translateError'
    )
    expect(title).toHaveValue('Keep this')
  })
})
