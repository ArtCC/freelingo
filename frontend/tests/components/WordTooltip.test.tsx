import { act, render, renderHook, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WordTooltip, useWordSave } from '@/components/ui/WordTooltip'

const mockApiFetch = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', () => ({ apiFetch: mockApiFetch }))

const labels = {
  saveWord: 'Save',
  wordSaved: 'Saved',
  wordAlreadySaved: 'Already saved',
  wordSaveError: 'Something went wrong',
}

function mockSelection(word: string) {
  const rect = { left: 10, top: 20, width: 30, height: 10 }
  const selection = {
    isCollapsed: false,
    rangeCount: 1,
    toString: () => word,
    getRangeAt: () => ({ getBoundingClientRect: () => rect }),
    removeAllRanges: vi.fn(),
  }
  vi.spyOn(window, 'getSelection').mockReturnValue(
    selection as unknown as Selection
  )
}

describe('WordTooltip component', () => {
  it('renders the save button in idle state', () => {
    render(
      <WordTooltip
        word="perro"
        pos={{ x: 0, y: 0 }}
        saveState="idle"
        onSave={() => {}}
        onDismiss={() => {}}
        labels={labels}
      />
    )
    expect(screen.getByText('Save')).toBeInTheDocument()
  })

  it('renders wordSaved with green styling in saved state', () => {
    render(
      <WordTooltip
        word="perro"
        pos={{ x: 0, y: 0 }}
        saveState="saved"
        onSave={() => {}}
        onDismiss={() => {}}
        labels={labels}
      />
    )
    const label = screen.getByText(/Saved/)
    expect(label.className).toContain('text-green-400')
  })

  it('renders wordAlreadySaved with muted styling in exists state', () => {
    render(
      <WordTooltip
        word="perro"
        pos={{ x: 0, y: 0 }}
        saveState="exists"
        onSave={() => {}}
        onDismiss={() => {}}
        labels={labels}
      />
    )
    const label = screen.getByText(/Already saved/)
    expect(label.className).toContain('text-fl-muted-2')
    expect(label.className).not.toContain('text-green-400')
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
  })

  it('does not render the exists label outside the exists state', () => {
    render(
      <WordTooltip
        word="perro"
        pos={{ x: 0, y: 0 }}
        saveState="idle"
        onSave={() => {}}
        onDismiss={() => {}}
        labels={labels}
      />
    )
    expect(screen.queryByText(/Already saved/)).not.toBeInTheDocument()
  })

  it('renders wordSaveError in error state', () => {
    render(
      <WordTooltip
        word="perro"
        pos={{ x: 0, y: 0 }}
        saveState="error"
        onSave={() => {}}
        onDismiss={() => {}}
        labels={labels}
      />
    )
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })
})

describe('useWordSave', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sets saveState to saved when already_saved is false', async () => {
    mockSelection('perro')
    const { result } = renderHook(() => useWordSave())

    await act(async () => {
      result.current.handleTextSelection('El perro corre')
      await new Promise((r) => setTimeout(r, 0))
    })
    expect(result.current.selectedWord).toBe('perro')

    mockApiFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ already_saved: false }), { status: 200 })
    )

    await act(async () => {
      await result.current.handleSaveWord()
    })

    expect(result.current.saveState).toBe('saved')
  })

  it('sets saveState to exists when already_saved is true', async () => {
    mockSelection('perro')
    const { result } = renderHook(() => useWordSave())

    await act(async () => {
      result.current.handleTextSelection('El perro corre')
      await new Promise((r) => setTimeout(r, 0))
    })

    mockApiFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ already_saved: true }), { status: 200 })
    )

    await act(async () => {
      await result.current.handleSaveWord()
    })

    expect(result.current.saveState).toBe('exists')
  })

  it('auto-dismisses back to idle 1500ms after already_saved resolves', async () => {
    vi.useFakeTimers()
    mockSelection('perro')
    const { result } = renderHook(() => useWordSave())

    act(() => {
      result.current.handleTextSelection('El perro corre')
    })
    act(() => {
      vi.advanceTimersByTime(0)
    })

    mockApiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ already_saved: true }),
    })

    await act(async () => {
      await result.current.handleSaveWord()
    })
    expect(result.current.saveState).toBe('exists')

    act(() => {
      vi.advanceTimersByTime(1500)
    })

    expect(result.current.selectedWord).toBeNull()
    expect(result.current.saveState).toBe('idle')
  })

  it('sets saveState to error when the request fails', async () => {
    mockSelection('perro')
    const { result } = renderHook(() => useWordSave())

    await act(async () => {
      result.current.handleTextSelection('El perro corre')
      await new Promise((r) => setTimeout(r, 0))
    })

    mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 500 }))

    await act(async () => {
      await result.current.handleSaveWord()
    })

    expect(result.current.saveState).toBe('error')
  })
})
