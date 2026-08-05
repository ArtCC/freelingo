import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ElementType, HTMLAttributes, ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  fetchFreemium: vi.fn(),
  decrementFreemium: vi.fn(),
  dismissTooltip: vi.fn(),
  handleTextSelection: vi.fn(),
}))

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))
vi.mock('@/lib/api', () => ({ apiFetch: mocks.apiFetch }))
vi.mock('@/store/auth', () => ({
  useAuthStore: (selector: (state: object) => unknown) =>
    selector({
      user: {
        username: 'learner',
        displayName: 'Learner',
        avatarUrl: null,
        subscription_status: 'active',
      },
    }),
  isSubscribed: () => true,
  isFreemiumTrialActive: () => false,
}))
vi.mock('@/store/language', () => ({
  useLanguageStore: (selector: (state: object) => unknown) =>
    selector({ activeLanguage: { code: 'en-GB' } }),
}))
vi.mock('@/store/config', () => ({
  useConfigStore: (selector: (state: object) => unknown) =>
    selector({ stripeEnabled: false }),
}))
vi.mock('@/store/freemium', () => ({
  useFreemiumStore: (selector: (state: object) => unknown) =>
    selector({
      status: null,
      fetchStatus: mocks.fetchFreemium,
      decrement: mocks.decrementFreemium,
    }),
}))
vi.mock('@/components/billing/MaintenanceBanner', () => ({
  MaintenanceGate: ({ children }: { children: ReactNode }) => children,
}))
vi.mock('@/components/billing/PaywallBanner', () => ({
  PaywallBanner: () => null,
}))
vi.mock('@/components/billing/FreemiumQuotaBanner', () => ({
  FreemiumQuotaBanner: () => null,
}))
vi.mock('@/components/ui/AudioPlayer', () => ({ AudioPlayer: () => null }))
vi.mock('@/components/ui/confirm-dialog', () => ({
  ConfirmDialog: () => null,
}))
vi.mock('@/components/ui/WordTooltip', () => ({
  WordTooltip: () => null,
  useWordSave: () => ({
    selectedWord: null,
    tooltipPos: null,
    saveState: 'idle',
    handleTextSelection: mocks.handleTextSelection,
    handleSaveWord: vi.fn(),
    dismissTooltip: mocks.dismissTooltip,
  }),
}))
vi.mock('@/components/ui/page-loading', () => ({ PageLoading: () => null }))
vi.mock('@/components/TargetLanguageText', () => ({
  TargetLanguageText: ({
    children,
    as: Component = 'div',
    languageCode,
    reading,
    translation,
    ...props
  }: {
    children: ReactNode
    as?: ElementType
    languageCode?: string | null
    reading?: string | null
    translation?: string | null
  } & HTMLAttributes<HTMLElement>) => (
    <Component
      data-language-code={languageCode ?? undefined}
      data-reading={reading ?? undefined}
      data-translation={translation ?? undefined}
      {...props}
    >
      {children}
    </Component>
  ),
}))
vi.mock('@/components/AuthAvatarImage', () => ({
  AuthAvatarImage: () => null,
}))

import ChatPage from '@/app/(app)/chat/page'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function chatStreamResponse(events: Array<Record<string, unknown>>) {
  const encoder = new TextEncoder()
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const event of events) {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
          )
        }
        controller.close()
      },
    }),
    { status: 200 }
  )
}

function controlledChatStreamResponse() {
  const encoder = new TextEncoder()
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null
  const response = new Response(
    new ReadableStream<Uint8Array>({
      start(streamController) {
        controller = streamController
      },
    }),
    { status: 200 }
  )

  return {
    response,
    enqueue(event: Record<string, unknown>) {
      if (!controller) throw new Error('Chat stream is not initialized')
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
    },
    close() {
      if (!controller) throw new Error('Chat stream is not initialized')
      controller.close()
    },
  }
}

describe('chat memory stream', () => {
  let chatEvents: Array<Record<string, unknown>>

  beforeEach(() => {
    mocks.apiFetch.mockReset()
    mocks.fetchFreemium.mockReset()
    mocks.decrementFreemium.mockReset()
    mocks.dismissTooltip.mockReset()
    mocks.handleTextSelection.mockReset()
    Element.prototype.scrollIntoView = vi.fn()
    chatEvents = [
      { conversation_id: 7 },
      { token: 'Partial response.' },
      { response_reset: true },
      { token: 'Complete normal response.' },
      { done: true },
    ]
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/chat') {
        return Promise.resolve(chatStreamResponse(chatEvents))
      }
      return Promise.resolve(jsonResponse([]))
    })
  })

  it('replaces a partial incompatible-tools response with the complete fallback', async () => {
    const stream = controlledChatStreamResponse()
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/chat') return Promise.resolve(stream.response)
      return Promise.resolve(jsonResponse([]))
    })
    render(<ChatPage />)

    const input = await screen.findByPlaceholderText('placeholder')
    fireEvent.change(input, { target: { value: 'Hello' } })
    fireEvent.click(screen.getByRole('button', { name: 'send' }))

    await act(async () => {
      stream.enqueue({ conversation_id: 7 })
      stream.enqueue({ token: 'Partial response.' })
    })
    expect(await screen.findByText('Partial response.')).toBeInTheDocument()

    await act(async () => {
      stream.enqueue({ response_reset: true })
    })
    await waitFor(() =>
      expect(screen.queryByText('Partial response.')).not.toBeInTheDocument()
    )

    await act(async () => {
      stream.enqueue({ token: 'Complete normal response.' })
      stream.enqueue({ done: true })
      stream.close()
    })
    expect(
      await screen.findByText('Complete normal response.')
    ).toBeInTheDocument()
    expect(screen.queryByText('Partial response.')).not.toBeInTheDocument()
    expect(screen.queryByText('memorySavedToast')).not.toBeInTheDocument()
    expect(mocks.dismissTooltip).toHaveBeenCalled()
    await waitFor(() =>
      expect(mocks.apiFetch).toHaveBeenCalledWith(
        '/api/chat',
        expect.anything()
      )
    )
  })

  it('enables assistant word selection only after streaming completes', async () => {
    const stream = controlledChatStreamResponse()
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/chat') return Promise.resolve(stream.response)
      return Promise.resolve(jsonResponse([]))
    })
    render(<ChatPage />)

    const input = await screen.findByPlaceholderText('placeholder')
    fireEvent.change(input, { target: { value: 'Hello' } })
    fireEvent.click(screen.getByRole('button', { name: 'send' }))

    await act(async () => {
      stream.enqueue({ conversation_id: 7 })
      stream.enqueue({ token: 'Streaming response.' })
    })
    const response = await screen.findByText('Streaming response.')
    fireEvent.pointerUp(response)
    expect(mocks.handleTextSelection).not.toHaveBeenCalled()

    await act(async () => {
      stream.enqueue({ done: true })
      stream.close()
    })
    await waitFor(() => expect(input).not.toBeDisabled())
    fireEvent.pointerUp(response)
    expect(mocks.handleTextSelection).toHaveBeenCalledWith(
      'Streaming response.'
    )
  })

  it('shows the toast only after the backend confirms a saved memory', async () => {
    chatEvents = [
      { conversation_id: 7 },
      { token: 'Normal response.' },
      { memory_updated: true },
      { done: true },
    ]
    render(<ChatPage />)

    const input = await screen.findByPlaceholderText('placeholder')
    fireEvent.change(input, { target: { value: 'Remember this' } })
    fireEvent.click(screen.getByRole('button', { name: 'send' }))

    expect(await screen.findByText('Normal response.')).toBeInTheDocument()
    expect(await screen.findByText('memorySavedToast')).toBeInTheDocument()
  })

  it('keeps the confirmed memory toast when a later stream error arrives', async () => {
    chatEvents = [
      { conversation_id: 7 },
      { memory_updated: true },
      { error: 'Something went wrong.' },
    ]
    render(<ChatPage />)

    const input = await screen.findByPlaceholderText('placeholder')
    fireEvent.change(input, { target: { value: 'Remember this' } })
    fireEvent.click(screen.getByRole('button', { name: 'send' }))

    expect(await screen.findByText('memorySavedToast')).toBeInTheDocument()
    expect(await screen.findByText(/errorMessage/)).toBeInTheDocument()
  })
})
