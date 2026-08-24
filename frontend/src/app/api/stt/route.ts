/**
 * STT proxy — forwards multipart audio to the backend and returns the transcription.
 *
 * A dedicated Route Handler is needed to correctly forward FormData (multipart/form-data)
 * without the generic next.config.ts rewrite interfering with the Content-Type boundary.
 */

import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000'

export async function POST(request: NextRequest): Promise<NextResponse> {
  const formData = await request.formData()

  const headers = new Headers()

  const auth = request.headers.get('Authorization')
  if (auth) headers.set('Authorization', auth)

  const cookie = request.headers.get('Cookie')
  if (cookie) headers.set('Cookie', cookie)

  // Do NOT set Content-Type — fetch sets it automatically with the correct multipart boundary.
  const backendRes = await fetch(`${BACKEND_URL}/api/stt`, {
    method: 'POST',
    headers,
    body: formData,
    signal: request.signal,
  })

  if (!backendRes.ok) {
    const errorText = await backendRes.text()
    return new NextResponse(errorText, { status: backendRes.status })
  }

  const data = await backendRes.json()
  return NextResponse.json(data)
}
