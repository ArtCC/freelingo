import { describe, expect, it } from 'vitest'
import { annotateAnswer } from '@/lib/free-write-corrections'

const correction = (original: string, corrected: string) => ({
  original,
  corrected,
  explanation: '',
})

describe('annotateAnswer', () => {
  it('splits the answer around an exact match', () => {
    const segments = annotateAnswer('Ich bin mit auto gefahren.', [
      correction('mit auto', 'mit dem Auto'),
    ])
    expect(segments).toEqual([
      { type: 'plain', text: 'Ich bin ' },
      { type: 'fix', original: 'mit auto', corrected: 'mit dem Auto' },
      { type: 'plain', text: ' gefahren.' },
    ])
  })

  it('annotates multiple corrections in answer order', () => {
    const segments = annotateAnswer('Ich habe viele abenteuer gehabt. Ich bin mit auto gefahren.', [
      correction('mit auto', 'mit dem Auto'),
      correction('abenteuer', 'Abenteuer'),
    ])
    expect(segments.filter((s) => s.type === 'fix')).toEqual([
      { type: 'fix', original: 'abenteuer', corrected: 'Abenteuer' },
      { type: 'fix', original: 'mit auto', corrected: 'mit dem Auto' },
    ])
  })

  it('matches case-insensitively when the exact fragment is absent', () => {
    const segments = annotateAnswer('ich wohne in berlin', [
      correction('Ich wohne', 'Ich lebe'),
    ])
    expect(segments[0]).toEqual({
      type: 'fix',
      original: 'ich wohne',
      corrected: 'Ich lebe',
    })
  })

  it('matches after trimming whitespace from the original', () => {
    const segments = annotateAnswer('Das ist gut.', [correction(' gut ', 'sehr gut')])
    expect(segments.some((s) => s.type === 'fix')).toBe(true)
  })

  it('produces no fix segment for an unmatched correction', () => {
    const segments = annotateAnswer('Ich gehe nach Hause.', [
      correction('completely different text', 'whatever'),
    ])
    expect(segments).toEqual([{ type: 'plain', text: 'Ich gehe nach Hause.' }])
  })

  it('keeps the earlier match when corrections overlap', () => {
    const segments = annotateAnswer('mit auto gefahren', [
      correction('mit auto', 'mit dem Auto'),
      correction('auto gefahren', 'Auto gefahren'),
    ])
    expect(segments.filter((s) => s.type === 'fix')).toEqual([
      { type: 'fix', original: 'mit auto', corrected: 'mit dem Auto' },
    ])
  })

  it('skips corrections with an empty original or corrected value', () => {
    const segments = annotateAnswer('Ich gehe.', [
      correction('', 'something'),
      correction('Ich', ''),
    ])
    expect(segments).toEqual([{ type: 'plain', text: 'Ich gehe.' }])
  })

  it('covers matches at the start and end of the answer', () => {
    const segments = annotateAnswer('abc def', [
      correction('abc', 'ABC'),
      correction('def', 'DEF'),
    ])
    expect(segments).toEqual([
      { type: 'fix', original: 'abc', corrected: 'ABC' },
      { type: 'plain', text: ' ' },
      { type: 'fix', original: 'def', corrected: 'DEF' },
    ])
  })
})
