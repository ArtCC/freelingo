import { apiFetch } from '@/lib/api'
import type {
  ClearMemoriesResponse,
  Memory,
  MemoryListResponse,
} from '@/types/api'

export class MemoryApiError extends Error {
  constructor(public readonly status: number) {
    super(`memories_api_error_${status}`)
  }
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) throw new MemoryApiError(response.status)
  return response.json() as Promise<T>
}

export async function fetchMemories(): Promise<MemoryListResponse> {
  return parseOrThrow(await apiFetch('/api/memories'))
}

export async function createMemory(content: string): Promise<Memory> {
  const response = await apiFetch('/api/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: content.trim() }),
  })
  return parseOrThrow<Memory>(response)
}

export async function deleteMemory(id: number): Promise<void> {
  const response = await apiFetch(`/api/memories/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new MemoryApiError(response.status)
}

export async function clearMemories(): Promise<ClearMemoriesResponse> {
  const response = await apiFetch('/api/memories', { method: 'DELETE' })
  return parseOrThrow<ClearMemoriesResponse>(response)
}
