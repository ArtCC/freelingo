export interface FreeWriteCorrection {
  original: string
  corrected: string
  explanation: string
}

export type AnswerSegment =
  | { type: 'plain'; text: string }
  | { type: 'fix'; original: string; corrected: string }

interface Occurrence {
  start: number
  end: number
  wholeWord: boolean
}

interface Candidate extends Occurrence {
  correction: number
}

const WORD_CHAR = /[\p{L}\p{N}]/u

function isWordChar(char: string | undefined): boolean {
  return char !== undefined && WORD_CHAR.test(char)
}

// A match is "whole word" when the fragment does not continue a word on
// either side of the answer. Sides where the fragment itself starts/ends with
// punctuation or whitespace are not constrained.
function isWholeWord(
  answer: string,
  needle: string,
  start: number,
  end: number
): boolean {
  const startsWithWord = isWordChar(needle[0])
  const endsWithWord = isWordChar(needle[needle.length - 1])
  return (
    (!startsWithWord || !isWordChar(answer[start - 1])) &&
    (!endsWithWord || !isWordChar(answer[end]))
  )
}

function allIndexes(haystack: string, needle: string): number[] {
  const indexes: number[] = []
  let index = haystack.indexOf(needle)
  while (index !== -1) {
    indexes.push(index)
    index = haystack.indexOf(needle, index + 1)
  }
  return indexes
}

// Every occurrence of the fragment in the answer. Tries the fragment as-is,
// then trimmed; within each, an exact match before a case-insensitive one. The
// first variant with any hits wins so the segments keep the answer's spelling.
function findOccurrences(answer: string, original: string): Occurrence[] {
  const lowerAnswer = answer.toLowerCase()
  const variants = [original, original.trim()].filter(
    (candidate, index, all) => candidate && all.indexOf(candidate) === index
  )
  for (const candidate of variants) {
    for (const [haystack, needle] of [
      [answer, candidate],
      [lowerAnswer, candidate.toLowerCase()],
    ]) {
      const indexes = allIndexes(haystack, needle)
      if (indexes.length === 0) continue
      return indexes.map((start) => {
        const end = start + needle.length
        return {
          start,
          end,
          wholeWord: isWholeWord(answer, needle, start, end),
        }
      })
    }
  }
  return []
}

// Locates each correction's `original` fragment in the submitted answer and
// splits the answer into plain/fix segments. Each correction is assigned one
// non-overlapping occurrence: repeated identical fragments consume successive
// occurrences, whole-word matches are preferred over matches inside a longer
// word, and when two fragments start at the same position the longer one wins.
// Corrections whose fragment cannot be placed yield no segment — they are
// still shown in the corrections list below the answer.
export function annotateAnswer(
  answer: string,
  corrections: FreeWriteCorrection[]
): AnswerSegment[] {
  const candidates: Candidate[] = corrections.flatMap((correction, index) =>
    correction.original && correction.corrected
      ? findOccurrences(answer, correction.original).map((occurrence) => ({
          ...occurrence,
          correction: index,
        }))
      : []
  )
  candidates.sort(
    (a, b) =>
      a.start - b.start ||
      b.end - b.start - (a.end - a.start) ||
      a.correction - b.correction
  )

  const matches: Array<{ start: number; end: number; corrected: string }> = []
  const placed = new Set<number>()
  const overlaps = (start: number, end: number) =>
    matches.some((match) => start < match.end && end > match.start)
  for (const wholeWordOnly of [true, false]) {
    for (const candidate of candidates) {
      if (placed.has(candidate.correction)) continue
      if (wholeWordOnly && !candidate.wholeWord) continue
      if (overlaps(candidate.start, candidate.end)) continue
      placed.add(candidate.correction)
      matches.push({
        start: candidate.start,
        end: candidate.end,
        corrected: corrections[candidate.correction].corrected,
      })
    }
  }
  matches.sort((a, b) => a.start - b.start)

  const segments: AnswerSegment[] = []
  let cursor = 0
  for (const match of matches) {
    if (match.start > cursor) {
      segments.push({ type: 'plain', text: answer.slice(cursor, match.start) })
    }
    segments.push({
      type: 'fix',
      original: answer.slice(match.start, match.end),
      corrected: match.corrected,
    })
    cursor = match.end
  }
  if (cursor < answer.length) {
    segments.push({ type: 'plain', text: answer.slice(cursor) })
  }
  return segments
}
