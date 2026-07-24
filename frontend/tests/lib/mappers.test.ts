import { describe, it, expect } from 'vitest'
import { mapUser, mapUserLanguageInfo } from '@/lib/mappers'
import type { User } from '@/store/auth'

describe('mapUser', () => {
  const rawFull = {
    id: 1,
    username: 'john',
    display_name: 'John Doe',
    email: 'john@example.com',
    native_language: 'es',
    target_language: 'en',
    role: 'user' as const,
    conversation_max_duration: 300,
    conversation_inactivity_timeout: 30,
    avatar: 'https://example.com/avatar.png',
    is_verified: true,
    bio: 'Hello',
    learning_goals: ['travel', 'work'],
    subscription_status: 'active' as const,
    subscription_ends_at: '2025-12-31',
    trial_used: true,
    assessment_voice_trial_used: false,
    freemium_trial_ends_at: null,
    freemium_trial_used: false,
    cancel_at_period_end: false,
  }

  it('maps snake_case API response to camelCase User', () => {
    const user = mapUser(rawFull)

    expect(user).toEqual({
      id: 1,
      username: 'john',
      displayName: 'John Doe',
      email: 'john@example.com',
      native_language: 'es',
      target_language: 'en',
      role: 'user',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
      avatar: 'https://example.com/avatar.png',
      is_verified: true,
      bio: 'Hello',
      learning_goals: ['travel', 'work'],
      subscription_status: 'active',
      subscription_ends_at: '2025-12-31',
      trial_used: true,
      assessment_voice_trial_used: false,
      freemium_trial_ends_at: null,
      freemium_trial_used: false,
      ui_locale: null,
      cancel_at_period_end: false,
    })
  })

  it('falls back to current user for optional fields absent in PATCH response', () => {
    const current: User = {
      id: 1,
      username: 'john',
      displayName: 'John Doe',
      role: 'user',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
      avatar: 'old-avatar.png',
      is_verified: true,
      bio: 'old bio',
      learning_goals: ['travel'],
      subscription_status: 'trialing',
      subscription_ends_at: '2025-06-01',
      trial_used: true,
      freemium_trial_ends_at: '2026-07-15T00:00:00',
      freemium_trial_used: true,
    }

    const patchResponse = {
      id: 1,
      username: 'john',
      display_name: 'John Updated',
      role: 'user',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
    }

    const user = mapUser(patchResponse, current)

    expect(user.displayName).toBe('John Updated')
    expect(user.avatar).toBe('old-avatar.png')
    expect(user.bio).toBe('old bio')
    expect(user.learning_goals).toEqual(['travel'])
    expect(user.subscription_status).toBe('trialing')
    expect(user.subscription_ends_at).toBe('2025-06-01')
    expect(user.trial_used).toBe(true)
    expect(user.freemium_trial_ends_at).toBe('2026-07-15T00:00:00')
    expect(user.freemium_trial_used).toBe(true)
  })

  it('uses safe defaults when no current user and optional fields missing', () => {
    const minimal = {
      id: 2,
      username: 'jane',
      display_name: 'Jane',
      role: 'admin',
      conversation_max_duration: 600,
      conversation_inactivity_timeout: 60,
    }

    const user = mapUser(minimal)

    expect(user.avatar).toBeNull()
    expect(user.is_verified).toBe(true)
    expect(user.bio).toBeNull()
    expect(user.learning_goals).toBeNull()
    expect(user.subscription_status).toBe('none')
    expect(user.subscription_ends_at).toBeNull()
    expect(user.trial_used).toBe(false)
    expect(user.assessment_voice_trial_used).toBe(false)
    expect(user.freemium_trial_ends_at).toBeNull()
    expect(user.freemium_trial_used).toBe(false)
  })

  it('prefers API data over current user when both present', () => {
    const current: User = {
      id: 1,
      username: 'john',
      displayName: 'Old Name',
      role: 'user',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
      avatar: 'old.png',
      bio: 'old',
      learning_goals: ['old'],
      subscription_status: 'canceled',
      trial_used: true,
    }

    const apiData = {
      id: 1,
      username: 'john',
      display_name: 'New Name',
      role: 'admin',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
      avatar: 'new.png',
      bio: 'new bio',
      learning_goals: ['new'],
      subscription_status: 'active',
      trial_used: false,
    }

    const user = mapUser(apiData, current)

    expect(user.displayName).toBe('New Name')
    expect(user.role).toBe('admin')
    expect(user.avatar).toBe('new.png')
    expect(user.bio).toBe('new bio')
    expect(user.learning_goals).toEqual(['new'])
    expect(user.subscription_status).toBe('active')
    expect(user.trial_used).toBe(false)
  })

  it('preserves explicit null avatar from API response', () => {
    const current: User = {
      id: 1,
      username: 'john',
      displayName: 'John Doe',
      role: 'user',
      conversation_max_duration: 300,
      conversation_inactivity_timeout: 30,
      avatar: 'old.png',
    }

    const user = mapUser(
      {
        id: 1,
        username: 'john',
        display_name: 'John Doe',
        role: 'user',
        conversation_max_duration: 300,
        conversation_inactivity_timeout: 30,
        avatar: null,
      },
      current
    )

    expect(user.avatar).toBeNull()
  })
})

describe('mapUserLanguageInfo', () => {
  it('maps full API response with plan and progress', () => {
    const raw = {
      target_language: 'es-ES',
      is_active: true,
      plan: {
        id: 1,
        cefr_level: 'B1',
        progress_day: 42,
        total_days: 48,
        completion_pct: 87.5,
      },
      progress: {
        total_xp: 12500,
        current_streak: 23,
        lessons_completed: 38,
      },
    }

    const result = mapUserLanguageInfo(raw)

    expect(result).toEqual({
      target_language: 'es-ES',
      is_active: true,
      plan: {
        id: 1,
        cefr_level: 'B1',
        progress_day: 42,
        total_days: 48,
        completion_pct: 87.5,
      },
      progress: {
        total_xp: 12500,
        current_streak: 23,
        lessons_completed: 38,
      },
    })
  })

  it('maps null plan to null', () => {
    const raw = {
      target_language: 'it-IT',
      is_active: false,
      plan: null,
      progress: null,
    }

    const result = mapUserLanguageInfo(raw)

    expect(result).toEqual({
      target_language: 'it-IT',
      is_active: false,
      plan: null,
      progress: null,
    })
  })

  it('maps null cefr_level to null', () => {
    const raw = {
      target_language: 'pt-PT',
      is_active: true,
      plan: {
        id: 3,
        cefr_level: null,
        progress_day: 0,
        total_days: 60,
        completion_pct: 0,
      },
      progress: null,
    }

    const result = mapUserLanguageInfo(raw)

    expect(result.plan).toBeDefined()
    expect(result.plan!.cefr_level).toBeNull()
    expect(result.progress).toBeNull()
  })

  it('maps missing plan to null', () => {
    const raw = {
      target_language: 'en-US',
      is_active: false,
    }

    const result = mapUserLanguageInfo(raw)

    expect(result.plan).toBeNull()
    expect(result.progress).toBeNull()
  })

  it('maps plan with progress but null cefr_level', () => {
    const raw = {
      target_language: 'en-GB',
      is_active: true,
      plan: {
        id: 2,
        cefr_level: null,
        progress_day: 10,
        total_days: 60,
        completion_pct: 16.7,
      },
      progress: {
        total_xp: 500,
        current_streak: 3,
        lessons_completed: 4,
      },
    }

    const result = mapUserLanguageInfo(raw)

    expect(result.plan).toEqual({
      id: 2,
      cefr_level: null,
      progress_day: 10,
      total_days: 60,
      completion_pct: 16.7,
    })
    expect(result.progress).toEqual({
      total_xp: 500,
      current_streak: 3,
      lessons_completed: 4,
    })
  })
})
