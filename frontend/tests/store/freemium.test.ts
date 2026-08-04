import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiFetchMock = vi.fn()

vi.mock('@/lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

import { useFreemiumStore } from '@/store/freemium'

const status = {
  trial_active: false,
  trial_ends_at: null,
  chat_remaining: 3,
  chat_limit: 3,
  lessons_remaining: 2,
  lessons_limit: 3,
  listening_remaining: 2,
  listening_limit: 2,
  reading_remaining: 2,
  reading_limit: 2,
  voice_remaining_seconds: 900,
  voice_limit_seconds: 900,
}

describe('freemium store', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    useFreemiumStore.setState({ status: null, loaded: false, lastFetch: 0 })
  })

  it('uses the cached status during the cache window', async () => {
    useFreemiumStore.setState({ status, loaded: true, lastFetch: Date.now() })

    await useFreemiumStore.getState().fetchStatus()

    expect(apiFetchMock).not.toHaveBeenCalled()
  })

  it('refreshes the status when forced', async () => {
    const refreshed = { ...status, lessons_remaining: 1 }
    useFreemiumStore.setState({ status, loaded: true, lastFetch: Date.now() })
    apiFetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(refreshed),
    })

    await useFreemiumStore.getState().fetchStatus(true)

    expect(apiFetchMock).toHaveBeenCalledWith('/api/freemium/status')
    expect(useFreemiumStore.getState().status).toEqual(refreshed)
  })
})
