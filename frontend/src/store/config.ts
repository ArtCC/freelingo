import { create } from 'zustand'

interface ConfigStore {
  stripeEnabled: boolean
  stripeTrialDays: number
  freemiumTrialEnabled: boolean
  ttsProvider: string
  openaiTtsVoice: string
  maintenanceMode: boolean
  priceMonthly: number
  priceYearly: number
  totalPriceMonthly: number
  totalPriceYearly: number
  loaded: boolean
  load: () => Promise<void>
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  stripeEnabled: false,
  stripeTrialDays: 7,
  freemiumTrialEnabled: true,
  ttsProvider: 'local',
  openaiTtsVoice: 'nova',
  maintenanceMode: false,
  priceMonthly: 0.0,
  priceYearly: 0.0,
  totalPriceMonthly: 0.0,
  totalPriceYearly: 0.0,
  loaded: false,
  load: async () => {
    if (get().loaded) return
    try {
      const res = await fetch('/api/config')
      if (!res.ok) return
      const data = await res.json()
      set({
        stripeEnabled: data.stripe_enabled ?? false,
        stripeTrialDays: data.stripe_trial_days ?? 7,
        freemiumTrialEnabled: data.freemium_trial_enabled ?? true,
        ttsProvider: data.tts_provider ?? 'local',
        openaiTtsVoice: data.openai_tts_voice ?? 'nova',
        maintenanceMode: data.maintenance_mode ?? false,
        priceMonthly: data.price_monthly ?? 0.0,
        priceYearly: data.price_yearly ?? 0.0,
        totalPriceMonthly: data.total_price_monthly ?? 0.0,
        totalPriceYearly: data.total_price_yearly ?? 0.0,
        loaded: true,
      })
    } catch {
      // Non-fatal: keep defaults (stripe disabled)
      set({ loaded: true })
    }
  },
}))
