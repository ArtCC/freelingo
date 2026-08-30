export interface FreeWriteCorrection {
  original: string
  corrected: string
  explanation: string
}

export type AnswerSegment =
  | { type: 'plain'; text: string }
  | { type: 'fix'; original: string; corrected: string }

function findMatch(
  answer: string,
  original: string
): { start: number; end: number } | null {
  for (const candidate of [original, original.trim()]) {
    if (!candidate) continue
    let index = answer.indexOf(candidate)
    if (index === -1) {
      index = answer.toLowerCase().indexOf(candidate.toLowerCase())
    }
    if (index !== -1) return { start: index, end: index + candidate.length }
  }
  return null
}

// Locates each correction's `original` fragment in the submitted answer and
// splits the answer into plain/fix segments. Corrections whose fragment cannot
// be found (or that overlap an earlier match) yield no segment — they are
// still shown in the corrections list below the answer.
export function annotateAnswer(
  answer: string,
  corrections: FreeWriteCorrection[]
): AnswerSegment[] {
  const matches: Array<{ start: number; end: number; corrected: string }> = []
  for (const correction of corrections) {
    if (!correction.original || !correction.corrected) continue
    const match = findMatch(answer, correction.original)
    if (match) matches.push({ ...match, corrected: correction.corrected })
  }
  matches.sort((a, b) => a.start - b.start)

  const segments: AnswerSegment[] = []
  let cursor = 0
  for (const match of matches) {
    if (match.start < cursor) continue
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
