/**
 * End-of-turn silence handling for voice conversation.
 *
 * The VAD closes an utterance after `redemptionMs` of silence. Learners hesitate
 * mid-sentence while searching for a word, so the window has to tolerate pauses
 * that are normal at their level. Users who need more room than the automatic
 * value can pick their own in Settings.
 */

export const SPEECH_PAUSE_AUTO = 0

export const SPEECH_PAUSE_OPTIONS = [
  SPEECH_PAUSE_AUTO,
  1000,
  2000,
  3000,
] as const

export type SpeechPause = (typeof SPEECH_PAUSE_OPTIONS)[number]

const AUTO_REDEMPTION_MS: Record<string, number> = {
  A1: 1800,
  A2: 1800,
  B1: 1500,
  B2: 1500,
  C1: 1200,
  C2: 1200,
}

const AUTO_REDEMPTION_FALLBACK_MS = 1500

export function autoRedemptionMs(cefrLevel: string | null | undefined): number {
  if (!cefrLevel) return AUTO_REDEMPTION_FALLBACK_MS
  return AUTO_REDEMPTION_MS[cefrLevel] ?? AUTO_REDEMPTION_FALLBACK_MS
}

export function isSpeechPause(value: number | null | undefined): boolean {
  return SPEECH_PAUSE_OPTIONS.includes(value as SpeechPause)
}

/**
 * Resolve the silence window that ends a spoken turn.
 *
 * @param speechPause - User setting in milliseconds; 0 (or an unknown value) means automatic.
 * @param cefrLevel   - Level the automatic value is derived from.
 */
export function resolveVadRedemptionMs(
  speechPause: number | null | undefined,
  cefrLevel: string | null | undefined
): number {
  if (speechPause && isSpeechPause(speechPause)) return speechPause
  return autoRedemptionMs(cefrLevel)
}
