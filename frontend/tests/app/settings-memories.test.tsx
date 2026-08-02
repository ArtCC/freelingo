import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  fetchMemories: vi.fn(),
  createMemory: vi.fn(),
  deleteMemory: vi.fn(),
  clearMemories: vi.fn(),
}))

vi.mock('next-intl', () => ({
  useTranslations: () =>
    (key: string, values?: Record<string, string | number>) =>
      values?.content ? `${key}: ${values.content}` : key,
}))
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))
vi.mock('@/lib/memories', async () => {
  const actual = await vi.importActual<typeof import('@/lib/memories')>(
    '@/lib/memories'
  )
  return { ...actual, ...mocks }
})

import SettingsMemoriesPage from '@/app/(app)/settings/memories/page'

const memory = {
  id: 1,
  content: 'Likes hiking',
  source: 'chat',
  created_at: '2026-08-02T10:00:00',
}

describe('memory settings page', () => {
  beforeEach(() => {
    Object.values(mocks).forEach((mock) => mock.mockReset())
    mocks.fetchMemories.mockResolvedValue({ memories: [memory] })
  })

  it('loads memories with accessible deletion controls', async () => {
    render(<SettingsMemoriesPage />)
    expect(await screen.findByText('Likes hiking')).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: 'memoryDeleteLabel: Likes hiking',
      })
    ).toBeInTheDocument()
  })

  it('shows a retry state instead of an empty state after load failure', async () => {
    mocks.fetchMemories.mockRejectedValueOnce(new Error('offline'))
    render(<SettingsMemoriesPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'memoryLoadError'
    )
    expect(screen.queryByText('memoryEmpty')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'memoryAdd' })).toBeDisabled()
  })

  it('adds a manual memory after server confirmation', async () => {
    mocks.createMemory.mockResolvedValueOnce({
      ...memory,
      id: 2,
      content: 'Prefers examples',
      source: 'manual',
    })
    render(<SettingsMemoriesPage />)
    await screen.findByText('Likes hiking')
    fireEvent.change(screen.getByLabelText('memoryInputLabel'), {
      target: { value: '  Prefers examples  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'memoryAdd' }))
    await waitFor(() =>
      expect(mocks.createMemory).toHaveBeenCalledWith('Prefers examples')
    )
    expect(await screen.findByText('Prefers examples')).toBeInTheDocument()
  })

  it('keeps a memory visible when deletion fails', async () => {
    mocks.deleteMemory.mockRejectedValueOnce(new Error('failed'))
    render(<SettingsMemoriesPage />)
    fireEvent.click(
      await screen.findByRole('button', {
        name: 'memoryDeleteLabel: Likes hiking',
      })
    )
    expect(await screen.findByText('memoryDeleteError')).toBeInTheDocument()
    expect(screen.getByText('Likes hiking')).toBeInTheDocument()
  })

  it('clears the list only after server confirmation', async () => {
    mocks.clearMemories.mockResolvedValueOnce({ deleted: 1 })
    render(<SettingsMemoriesPage />)
    await screen.findByText('Likes hiking')
    fireEvent.click(screen.getByRole('button', { name: 'memoryClearAll' }))
    fireEvent.click(
      screen.getByRole('button', { name: 'memoryClearAllConfirm' })
    )
    expect(await screen.findByText('memoryEmpty')).toBeInTheDocument()
    expect(screen.queryByText('Likes hiking')).not.toBeInTheDocument()
  })
})
