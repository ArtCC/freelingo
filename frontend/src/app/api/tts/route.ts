/**
 * TTS proxy — forwards the request to the backend and streams back binary MP3.
 *
 * A dedicated Route Handler is needed because the generic next.config.ts rewrite
 * would return the response as text/event-stream, breaking binary audio data.
 *
 * The response body is streamed directly without buffering so that:
 *  - OpenAI TTS audio starts playing in the browser as soon as the first bytes
 *    arrive from the API (progressive streaming).
 *  - The LRU cache on the backend is still populated on the first request, so
 *    subsequent requests for the same text are served instantly.
 */

import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000'

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body = await request.text()

  const headers = new Headers()
  headers.set('Content-Type', 'application/json')

  const auth = request.headers.get('Authorization')
  if (auth) headers.set('Authorization', auth)

  const cookie = request.headers.get('Cookie')
  if (cookie) headers.set('Cookie', cookie)

  const backendRes = await fetch(`${BACKEND_URL}/api/tts`, {
    method: 'POST',
    headers,
    body,
  })

  if (!backendRes.ok) {
    const errorText = await backendRes.text()
    return new NextResponse(errorText, { status: backendRes.status })
  }

  // Pass the ReadableStream straight through — no ArrayBuffer buffering.
  // This lets MediaSource-capable browsers start decoding and playing audio
  // as soon as the first chunk of the TTS response arrives.
  return new NextResponse(backendRes.body, {
    status: 200,
    headers: { 'Content-Type': 'audio/mpeg' },
  })
}
