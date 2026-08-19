import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// --- Module mocks (hoisted by vitest) ---

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => 'en',
}))

const { mockApiFetch } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
}))
vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

vi.mock('@/lib/mappers', () => ({
  mapUser: (data: Record<string, any>, current: any) => ({
    ...current,
    ...data,
  }),
}))

import { ConversationSection } from '@/components/settings/ConversationSection'
import { useAuthStore } from '@/store/auth'

const defaultUser = {
  id: 1,
  username: 'testuser',
  displayName: 'Test User',
  role: 'user' as const,
  conversation_max_duration: 1800,
  conversation_inactivity_timeout: 180,
  conversation_speech_pause: 0,
}

function savedBody() {
  return JSON.parse(mockApiFetch.mock.calls[0][1].body)
}

describe('ConversationSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ...defaultUser, conversation_speech_pause: 3000 }),
    })
    useAuthStore.setState({
      accessToken: 'test-token',
      user: { ...defaultUser },
    })
  })

  it('renders every end-of-turn pause option', () => {
    render(<ConversationSection />)

    expect(screen.getByText('conversationSpeechPause')).toBeDefined()
    expect(screen.getByText('speechPauseAuto')).toBeDefined()
    expect(screen.getByText('speechPauseSec1')).toBeDefined()
    expect(screen.getByText('speechPauseSec2')).toBeDefined()
    expect(screen.getByText('speechPauseSec3')).toBeDefined()
  })

  it('saves the selected pause', async () => {
    render(<ConversationSection />)

    fireEvent.click(screen.getByText('speechPauseSec3'))
    fireEvent.click(screen.getByText('saveConversation'))

    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledTimes(1))
    expect(savedBody().conversation_speech_pause).toBe(3000)
  })

  it('keeps the stored pause when another setting is saved', async () => {
    useAuthStore.setState({
      accessToken: 'test-token',
      user: { ...defaultUser, conversation_speech_pause: 2000 },
    })
    render(<ConversationSection />)

    fireEvent.click(screen.getByText('min15'))
    fireEvent.click(screen.getByText('saveConversation'))

    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledTimes(1))
    expect(savedBody()).toMatchObject({
      conversation_max_duration: 900,
      conversation_speech_pause: 2000,
    })
  })

  it('sends automatic back to the API when the learner picks it', async () => {
    useAuthStore.setState({
      accessToken: 'test-token',
      user: { ...defaultUser, conversation_speech_pause: 3000 },
    })
    render(<ConversationSection />)

    fireEvent.click(screen.getByText('speechPauseAuto'))
    fireEvent.click(screen.getByText('saveConversation'))

    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledTimes(1))
    expect(savedBody().conversation_speech_pause).toBe(0)
  })
})
