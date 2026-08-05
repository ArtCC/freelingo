function parseEvent<T>(event: string): T | null {
  const payload = event
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!payload) return null
  try {
    return JSON.parse(payload) as T
  } catch {
    return null
  }
}

export async function* readSseData<T>(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<T> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += done
        ? decoder.decode()
        : decoder.decode(value, { stream: true })
      const trailingCr = !done && buffer.endsWith('\r')
      const completeBuffer = trailingCr ? buffer.slice(0, -1) : buffer
      buffer =
        completeBuffer.replace(/\r\n|\r/g, '\n') + (trailingCr ? '\r' : '')

      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''
      for (const event of events) {
        const data = parseEvent<T>(event)
        if (data !== null) yield data
      }
      if (done) break
    }

    if (buffer.trim()) {
      const remaining = parseEvent<T>(buffer)
      if (remaining === null) throw new Error('Incomplete SSE event')
      yield remaining
    }
  } finally {
    reader.releaseLock()
  }
}
