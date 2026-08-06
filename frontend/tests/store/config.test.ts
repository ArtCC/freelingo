import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useConfigStore } from '@/store/config'

describe('useConfigStore', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    useConfigStore.setState({
      stripeEnabled: false,
      stripeTrialDays: 7,
      freemiumTrialEnabled: true,
      ttsProvider: 'local',
      openaiTtsVoice: 'nova',
      maintenanceMode: false,
      dashboardBanner: null,
      loaded: false,
    })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.unstubAllGlobals()
  })

  it('loads config from /api/config', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          stripe_enabled: true,
          stripe_trial_days: 14,
          tts_provider: 'openai',
          openai_tts_voice: 'alloy',
          maintenance_mode: true,
          freemium_trial_enabled: false,
          dashboard_banner: {
            revision: 3,
            translations: {
              en: { title: 'News', subtitle: 'Today', description: 'Details' },
            },
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )

    await useConfigStore.getState().load()

    expect(useConfigStore.getState().stripeEnabled).toBe(true)
    expect(useConfigStore.getState().stripeTrialDays).toBe(14)
    expect(useConfigStore.getState().ttsProvider).toBe('openai')
    expect(useConfigStore.getState().openaiTtsVoice).toBe('alloy')
    expect(useConfigStore.getState().maintenanceMode).toBe(true)
    expect(useConfigStore.getState().freemiumTrialEnabled).toBe(false)
    expect(useConfigStore.getState().dashboardBanner?.revision).toBe(3)
    expect(useConfigStore.getState().loaded).toBe(true)
  })

  it('does not fetch twice (idempotency)', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ stripe_enabled: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await useConfigStore.getState().load()
    await useConfigStore.getState().load()

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('keeps defaults when fetch fails', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('network error'))

    await useConfigStore.getState().load()

    expect(useConfigStore.getState().stripeEnabled).toBe(false)
    expect(useConfigStore.getState().ttsProvider).toBe('local')
    expect(useConfigStore.getState().loaded).toBe(true)
  })

  it('does not mark loaded when response is not ok (allows retry)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('error', { status: 500 })
    )

    await useConfigStore.getState().load()

    expect(useConfigStore.getState().stripeEnabled).toBe(false)
    expect(useConfigStore.getState().loaded).toBe(false)
  })

  it('uses defaults for missing fields in response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await useConfigStore.getState().load()

    expect(useConfigStore.getState().stripeEnabled).toBe(false)
    expect(useConfigStore.getState().stripeTrialDays).toBe(7)
    expect(useConfigStore.getState().ttsProvider).toBe('local')
    expect(useConfigStore.getState().openaiTtsVoice).toBe('nova')
    expect(useConfigStore.getState().maintenanceMode).toBe(false)
    expect(useConfigStore.getState().freemiumTrialEnabled).toBe(true)
    expect(useConfigStore.getState().dashboardBanner).toBeNull()
  })
})
