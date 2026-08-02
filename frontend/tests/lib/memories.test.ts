import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockApiFetch } = vi.hoisted(() => ({ mockApiFetch: vi.fn() }))
vi.mock('@/lib/api', () => ({ apiFetch: mockApiFetch }))

import {
  MemoryApiError,
  clearMemories,
  createMemory,
  deleteMemory,
  fetchMemories,
} from '@/lib/memories'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('memories API client', () => {
  beforeEach(() => mockApiFetch.mockReset())

  it('loads global memories', async () => {
    const data = { memories: [{ id: 1, content: 'Likes tea' }] }
    mockApiFetch.mockResolvedValueOnce(jsonResponse(data))
    await expect(fetchMemories()).resolves.toEqual(data)
    expect(mockApiFetch).toHaveBeenCalledWith('/api/memories')
  })

  it('creates a trimmed manual memory', async () => {
    mockApiFetch.mockResolvedValueOnce(jsonResponse({ id: 2 }, 201))
    await createMemory('  Prefers examples  ')
    expect(mockApiFetch).toHaveBeenCalledWith('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: 'Prefers examples' }),
    })
  })

  it('deletes one memory and clears all memories', async () => {
    mockApiFetch
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(jsonResponse({ deleted: 1 }))
    await deleteMemory(12)
    await clearMemories()
    expect(mockApiFetch).toHaveBeenNthCalledWith(1, '/api/memories/12', {
      method: 'DELETE',
    })
    expect(mockApiFetch).toHaveBeenNthCalledWith(2, '/api/memories', {
      method: 'DELETE',
    })
  })

  it('rejects non-successful responses with their status', async () => {
    mockApiFetch.mockResolvedValueOnce(jsonResponse({}, 409))
    await expect(createMemory('Duplicate')).rejects.toEqual(
      expect.objectContaining<Partial<MemoryApiError>>({ status: 409 })
    )
  })
})
