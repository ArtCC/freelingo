import type { User } from '@/store/auth'
import type { UserLanguageInfo } from '@/store/language'

/**
 * Map a raw API response (snake_case) to the front-end User shape.
 *
 * @param data    - Raw JSON from /api/auth/me or any PATCH /api/auth/me response.
 * @param current - Existing store user; used as fallback for optional fields that
 *                  may be absent in partial PATCH responses.
 */

export function mapUser(
  data: Record<string, any>,
  current?: User | null
): User {
  return {
    id: data.id,
    username: data.username,
    displayName: data.display_name,
    email: data.email,
    native_language: data.native_language,
    target_language: data.target_language,
    ui_locale: data.ui_locale ?? current?.ui_locale ?? null,
    role: data.role,
    conversation_max_duration: data.conversation_max_duration,
    conversation_inactivity_timeout: data.conversation_inactivity_timeout,
    avatar: 'avatar' in data ? data.avatar : (current?.avatar ?? null),
    is_verified: data.is_verified ?? current?.is_verified ?? true,
    bio: data.bio ?? current?.bio ?? null,
    learning_goals: data.learning_goals ?? current?.learning_goals ?? null,
    subscription_status:
      data.subscription_status ?? current?.subscription_status ?? 'none',
    subscription_ends_at:
      data.subscription_ends_at ?? current?.subscription_ends_at ?? null,
    cancel_at_period_end:
      data.cancel_at_period_end ?? current?.cancel_at_period_end ?? false,
    trial_used: data.trial_used ?? current?.trial_used ?? false,
    assessment_voice_trial_used:
      data.assessment_voice_trial_used ??
      current?.assessment_voice_trial_used ??
      false,
    freemium_trial_ends_at:
      data.freemium_trial_ends_at ?? current?.freemium_trial_ends_at ?? null,
    freemium_trial_used:
      data.freemium_trial_used ?? current?.freemium_trial_used ?? false,
    dismissed_dashboard_banner_revision:
      data.dismissed_dashboard_banner_revision ??
      current?.dismissed_dashboard_banner_revision ??
      null,
  }
}

export function mapUserLanguageInfo(
  data: Record<string, any>
): UserLanguageInfo {
  return {
    target_language: data.target_language,
    is_active: data.is_active,
    plan: data.plan
      ? {
          id: data.plan.id,
          cefr_level: data.plan.cefr_level ?? null,
          progress_day: data.plan.progress_day,
          total_days: data.plan.total_days,
          completion_pct: data.plan.completion_pct,
        }
      : null,
    progress: data.progress
      ? {
          total_xp: data.progress.total_xp,
          current_streak: data.progress.current_streak,
          lessons_completed: data.progress.lessons_completed,
        }
      : null,
  }
}
