import { describe, expect, it } from 'vitest'
import { readSseData } from '@/lib/sse'

function streamFrom(chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

describe('readSseData', () => {
  it('reassembles JSON events split across network chunks', async () => {
    const stream = streamFrom([
      'data: {"token":"Hel',
      'lo"}\n\ndata: {"memory_',
      'updated":true}\n\n',
    ])
    const events = []
    for await (const event of readSseData<Record<string, unknown>>(stream)) {
      events.push(event)
    }
    expect(events).toEqual([
      { token: 'Hello' },
      { memory_updated: true },
    ])
  })

  it('supports CRLF and CR framing while ignoring malformed events', async () => {
    const stream = streamFrom([
      'data: not-json\r',
      '\n\r\ndata: {"done":true}\r\r',
    ])
    const events = []
    for await (const event of readSseData<Record<string, unknown>>(stream)) {
      events.push(event)
    }
    expect(events).toEqual([{ done: true }])
  })

  it('rejects a truncated final event', async () => {
    const stream = streamFrom(['data: {"memory_updated":tru'])

    await expect(async () => {
      for await (const event of readSseData(stream)) void event
    }).rejects.toThrow('Incomplete SSE event')
  })
})
