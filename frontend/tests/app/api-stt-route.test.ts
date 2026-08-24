import type { NextRequest } from 'next/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { POST } from '@/app/api/stt/route'

describe('STT API route', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('forwards multipart plan context and the request cancellation signal', async () => {
    const backendFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: 'ciao' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', backendFetch)
    const controller = new AbortController()
    const formData = new FormData()
    formData.append('audio', new Blob(['audio']), 'recording.wav')
    formData.append('study_plan_id', '42')
    const request = {
      formData: vi.fn().mockResolvedValue(formData),
      headers: new Headers({
        Authorization: 'Bearer token',
        Cookie: 'refresh_token=cookie',
      }),
      signal: controller.signal,
    } as unknown as NextRequest

    const response = await POST(request)

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ text: 'ciao' })
    expect(backendFetch).toHaveBeenCalledWith(
      'http://backend:8000/api/stt',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
        signal: request.signal,
      })
    )
    const forwardedHeaders = backendFetch.mock.calls[0][1].headers as Headers
    expect(forwardedHeaders.get('Authorization')).toBe('Bearer token')
    expect(forwardedHeaders.get('Cookie')).toBe('refresh_token=cookie')
  })
})
