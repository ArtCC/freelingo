import { create } from 'zustand'
import { apiFetch } from '@/lib/api'

interface FreemiumStatus {
  trial_active: boolean
  trial_ends_at: string | null
  chat_remaining: number
  chat_limit: number
  lessons_remaining: number
  lessons_limit: number
  listening_remaining: number
  listening_limit: number
  reading_remaining: number
  reading_limit: number
  voice_remaining_seconds: number
  voice_limit_seconds: number
}

interface FreemiumStore {
  status: FreemiumStatus | null
  loaded: boolean
  lastFetch: number
  fetchStatus: () => Promise<void>
  /** Optimistically decrement a numeric quota counter on the client. */
  decrement: (feature: NumericFreemiumKey) => void
}

type NumericFreemiumKey =
  | 'chat_remaining'
  | 'lessons_remaining'
  | 'listening_remaining'
  | 'reading_remaining'

export const useFreemiumStore = create<FreemiumStore>((set, get) => ({
  status: null,
  loaded: false,
  lastFetch: 0,
  fetchStatus: async () => {
    const now = Date.now()
    // Cache for 60 seconds
    if (get().loaded && now - get().lastFetch < 60_000) return
    try {
      const res = await apiFetch('/api/freemium/status')
      if (!res.ok) return
      const data: FreemiumStatus = await res.json()
      set({ status: data, loaded: true, lastFetch: now })
    } catch {
      // Non-fatal
    }
  },
  decrement: (feature: NumericFreemiumKey) => {
    const current = get().status
    if (!current) return
    set({
      status: {
        ...current,
        [feature]: Math.max(0, current[feature] - 1),
      },
    })
  },
}))
