import type { ReactNode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FlashcardsPage from '@/app/(app)/flashcards/page'

const { mockApiFetch } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))

vi.mock('@/store/language', () => ({
  useLanguageStore: (selector: (state: object) => unknown) =>
    selector({ activeLanguage: { code: 'it-IT' } }),
}))

vi.mock('@/components/ui/AudioPlayer', () => ({
  AudioPlayer: () => null,
}))

vi.mock('@/components/ui/VoiceRecorder', () => ({
  VoiceRecorder: () => null,
}))

vi.mock('@/components/ui/page-loading', () => ({
  PageLoading: () => <div>loading</div>,
}))

vi.mock('@/components/TargetLanguageText', () => ({
  TargetLanguageText: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}))

describe('Flashcards review', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('prevents concurrent reviews while one update is pending', async () => {
    let resolveReview: (response: Response) => void
    const pendingReview = new Promise<Response>((resolve) => {
      resolveReview = resolve
    })
    mockApiFetch.mockImplementation((url: string) => {
      if (url === '/api/flashcards/due') {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              due: [
                {
                  id: 7,
                  study_plan_id: 42,
                  word: 'ciao',
                  definition: 'hola',
                  example_sentence: 'Ciao a tutti.',
                  translation: 'hola',
                  ease_factor: 2.5,
                  interval: 0,
                  repetitions: 0,
                },
              ],
              total: 1,
            }),
            { status: 200 }
          )
        )
      }
      return pendingReview
    })
    render(<FlashcardsPage />)

    const word = await screen.findByText('ciao')
    fireEvent.click(word)
    const goodButton = await screen.findByRole('button', { name: 'good' })
    fireEvent.click(goodButton)
    fireEvent.click(goodButton)

    await waitFor(() => {
      const reviewCalls = mockApiFetch.mock.calls.filter(([url]) =>
        String(url).endsWith('/review')
      )
      expect(reviewCalls).toHaveLength(1)
    })
    expect(goodButton).toBeDisabled()

    await act(async () => {
      resolveReview!(new Response(null, { status: 200 }))
    })
    await waitFor(() => {
      const dueCalls = mockApiFetch.mock.calls.filter(
        ([url]) => url === '/api/flashcards/due'
      )
      expect(dueCalls).toHaveLength(2)
    })
  })
})
