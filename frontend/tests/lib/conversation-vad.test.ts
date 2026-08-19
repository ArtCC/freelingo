import { describe, it, expect } from 'vitest'
import {
  SPEECH_PAUSE_AUTO,
  SPEECH_PAUSE_OPTIONS,
  autoRedemptionMs,
  isSpeechPause,
  resolveVadRedemptionMs,
} from '@/lib/conversation-vad'

describe('autoRedemptionMs', () => {
  it('gives beginners the longest automatic pause', () => {
    expect(autoRedemptionMs('A1')).toBe(1800)
    expect(autoRedemptionMs('A2')).toBe(1800)
  })

  it('shortens the automatic pause as the level rises', () => {
    expect(autoRedemptionMs('B1')).toBe(1500)
    expect(autoRedemptionMs('B2')).toBe(1500)
    expect(autoRedemptionMs('C1')).toBe(1200)
    expect(autoRedemptionMs('C2')).toBe(1200)
  })

  it('falls back when the level is missing or unknown', () => {
    expect(autoRedemptionMs(null)).toBe(1500)
    expect(autoRedemptionMs(undefined)).toBe(1500)
    expect(autoRedemptionMs('')).toBe(1500)
    expect(autoRedemptionMs('X9')).toBe(1500)
  })

  it('gives every level more room than the previous window', () => {
    const previous: Record<string, number> = {
      A1: 1300,
      A2: 1300,
      B1: 1100,
      B2: 1100,
      C1: 900,
      C2: 900,
    }
    for (const [level, before] of Object.entries(previous)) {
      expect(autoRedemptionMs(level)).toBeGreaterThan(before)
    }
  })
})

describe('isSpeechPause', () => {
  it('accepts the offered values', () => {
    for (const option of SPEECH_PAUSE_OPTIONS) {
      expect(isSpeechPause(option)).toBe(true)
    }
  })

  it('rejects anything else', () => {
    expect(isSpeechPause(1500)).toBe(false)
    expect(isSpeechPause(null)).toBe(false)
    expect(isSpeechPause(undefined)).toBe(false)
  })
})

describe('resolveVadRedemptionMs', () => {
  it('uses the value the learner chose', () => {
    expect(resolveVadRedemptionMs(1000, 'A1')).toBe(1000)
    expect(resolveVadRedemptionMs(3000, 'C2')).toBe(3000)
  })

  it('derives the value from the level when set to automatic', () => {
    expect(resolveVadRedemptionMs(SPEECH_PAUSE_AUTO, 'A2')).toBe(1800)
    expect(resolveVadRedemptionMs(SPEECH_PAUSE_AUTO, 'C1')).toBe(1200)
  })

  it('falls back to automatic without a stored setting', () => {
    expect(resolveVadRedemptionMs(null, 'B1')).toBe(1500)
    expect(resolveVadRedemptionMs(undefined, 'A1')).toBe(1800)
  })

  it('ignores a stored value that is not offered any more', () => {
    expect(resolveVadRedemptionMs(700, 'A1')).toBe(1800)
  })
})
