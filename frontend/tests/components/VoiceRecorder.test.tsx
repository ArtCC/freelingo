import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import React from 'react'
import { VoiceRecorder as VoiceRecorderComponent } from '@/components/ui/VoiceRecorder'

const TEST_STUDY_PLAN_ID = 42

function VoiceRecorder(
  props: Omit<React.ComponentProps<typeof VoiceRecorderComponent>, 'studyPlanId'>
) {
  return (
    <VoiceRecorderComponent
      studyPlanId={TEST_STUDY_PLAN_ID}
      {...props}
    />
  )
}

const { mockApiFetch } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

vi.mock('@/lib/audio', () => ({
  float32ToWav: vi.fn(() => new ArrayBuffer(100)),
}))

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))

vi.mock('next/image', () => ({
  default: function MockImage(
    props: React.ImgHTMLAttributes<HTMLImageElement> & {
      unoptimized?: boolean
      priority?: boolean
    }
  ) {
    const { unoptimized, priority, ...imgProps } = props
    void unoptimized
    void priority
    return React.createElement('img', imgProps)
  },
}))

describe('VoiceRecorder', () => {
  let mockGetUserMedia: ReturnType<typeof vi.fn>
  let streamTrackStop: ReturnType<typeof vi.fn>

  let mockProcessor: {
    connect: ReturnType<typeof vi.fn>
    disconnect: ReturnType<typeof vi.fn>
    onaudioprocess:
      | ((e: {
          inputBuffer: { getChannelData: (c: number) => Float32Array }
        }) => void)
      | null
  }
  let mockAudioCtx: {
    close: ReturnType<typeof vi.fn>
  }
  let mockStartRendering: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()

    streamTrackStop = vi.fn()

    mockGetUserMedia = vi.fn().mockResolvedValue({
      getTracks: vi.fn(() => [{ stop: streamTrackStop }]),
    })

    mockProcessor = {
      connect: vi.fn(),
      disconnect: vi.fn(),
      onaudioprocess: null,
    }

    const ctx = {
      createMediaStreamSource: vi.fn(() => ({ connect: vi.fn() })),
      createScriptProcessor: vi.fn(() => mockProcessor),
      close: vi.fn(),
      sampleRate: 48000,
      destination: {},
    }
    mockAudioCtx = ctx

    // Must use regular function (not arrow) — arrow functions cannot be called with `new`
    vi.stubGlobal(
      'AudioContext',
      vi.fn(function MockAudioContext() {
        return ctx
      })
    )

    mockStartRendering = vi.fn().mockResolvedValue({
      getChannelData: () => new Float32Array(16000),
    })
    const offlineCtx = {
      createBuffer: vi.fn(() => ({
        getChannelData: vi.fn(() => new Float32Array(100)),
      })),
      createBufferSource: vi.fn(() => ({
        buffer: null,
        connect: vi.fn(),
        start: vi.fn(),
      })),
      startRendering: mockStartRendering,
      destination: {},
    }

    vi.stubGlobal(
      'OfflineAudioContext',
      vi.fn(function MockOfflineAudioContext() {
        return offlineCtx
      })
    )

    vi.stubGlobal('navigator', {
      mediaDevices: { getUserMedia: mockGetUserMedia },
    })

    mockApiFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ text: 'transcribed text' }),
    } as Response)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  async function waitForRecordingReady(timeout = 3000) {
    await waitFor(
      () => {
        expect(typeof mockProcessor.onaudioprocess).toBe('function')
      },
      { timeout }
    )
  }

  function fireAudioChunk(samples = [0.5]) {
    if (typeof mockProcessor.onaudioprocess === 'function') {
      mockProcessor.onaudioprocess({
        inputBuffer: { getChannelData: () => new Float32Array(samples) },
      })
    }
  }

  // ===== Idle state =====

  it('renders in idle state with record label', () => {
    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')
    expect(button.textContent).toContain('record')
  })

  it('has correct aria-label in idle state', () => {
    render(<VoiceRecorder onTranscription={vi.fn()} />)
    expect(screen.getByRole('button').getAttribute('aria-label')).toBe(
      'ariaRecord'
    )
  })

  it('applies custom className', () => {
    render(<VoiceRecorder onTranscription={vi.fn()} className="my-custom" />)
    expect(screen.getByRole('button').className).toContain('my-custom')
  })

  // ===== Disabled state =====

  it('renders disabled state correctly', () => {
    render(<VoiceRecorder onTranscription={vi.fn()} disabled />)
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button.className).toContain('cursor-not-allowed')
  })

  it('does not respond to clicks when disabled', () => {
    render(<VoiceRecorder onTranscription={vi.fn()} disabled />)
    fireEvent.click(screen.getByRole('button'))
    expect(mockGetUserMedia).not.toHaveBeenCalled()
  })

  // ===== Recording start =====

  it('transitions to recording state and calls getUserMedia with constraints', async () => {
    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)

    // setState('recording') runs synchronously before the await
    expect(button.textContent).toContain('stop')
    expect(button.getAttribute('aria-label')).toBe('ariaStop')
    expect(mockGetUserMedia).toHaveBeenCalledWith({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
  })

  it('creates AudioContext and sets up processor after getUserMedia resolves', async () => {
    render(<VoiceRecorder onTranscription={vi.fn()} />)
    fireEvent.click(screen.getByRole('button'))

    await waitForRecordingReady()

    expect(typeof mockProcessor.onaudioprocess).toBe('function')
    expect(mockProcessor.connect).toHaveBeenCalled()
  })

  it('captures audio chunks and sends them to STT on stop', async () => {
    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()

    fireAudioChunk([0.1, 0.2])
    fireAudioChunk([0.3, 0.4])

    fireEvent.click(button)

    await waitFor(() => {
      expect(onTranscription).toHaveBeenCalledWith('transcribed text')
    })
    expect(button.textContent).toContain('record')
  })

  // ===== Stop & transcription flow =====

  it('sends audio and study plan context to /api/stt', async () => {
    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/api/stt',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
        })
      )
    })

    const request = mockApiFetch.mock.calls[0][1] as RequestInit
    const formData = request.body as FormData
    expect(formData.get('study_plan_id')).toBe(String(TEST_STUDY_PLAN_ID))
    expect(formData.get('audio')).toBeInstanceOf(Blob)
  })

  it('keeps the recording context when props change before upload', async () => {
    const originalHandler = vi.fn()
    const replacementHandler = vi.fn()
    const { rerender } = render(
      <VoiceRecorderComponent
        studyPlanId={42}
        onTranscription={originalHandler}
      />
    )
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    rerender(
      <VoiceRecorderComponent
        studyPlanId={99}
        onTranscription={replacementHandler}
      />
    )
    fireEvent.click(button)

    await waitFor(() => expect(originalHandler).toHaveBeenCalled())
    const request = mockApiFetch.mock.calls[0][1] as RequestInit
    const formData = request.body as FormData
    expect(formData.get('study_plan_id')).toBe('42')
    expect(replacementHandler).not.toHaveBeenCalled()
  })

  it('stays busy until an async transcription handler completes', async () => {
    let resolveHandler: () => void
    const onTranscription = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveHandler = resolve
        })
    )
    render(<VoiceRecorder onTranscription={onTranscription} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(() => expect(onTranscription).toHaveBeenCalled())
    expect(button.textContent).toContain('processing')
    await act(async () => resolveHandler!())
    await waitFor(() => expect(button.textContent).toContain('record'))
  })

  it('cleans up audio resources on stop', async () => {
    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(() => {
      expect(onTranscription).toHaveBeenCalled()
    })

    expect(streamTrackStop).toHaveBeenCalled()
    expect(mockAudioCtx.close).toHaveBeenCalled()
    expect(mockProcessor.disconnect).toHaveBeenCalled()
  })

  // ===== Auto-stop =====

  it('auto-stops after maxSeconds', async () => {
    vi.useFakeTimers()

    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} maxSeconds={3} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(button.textContent).toContain('stop')

    fireAudioChunk()

    // Advance past auto-stop timeout
    await act(() => vi.advanceTimersByTimeAsync(3001))
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(onTranscription).toHaveBeenCalledWith('transcribed text')
    expect(button.textContent).toContain('record')

    vi.useRealTimers()
  })

  // ===== Transcribing state =====

  it('shows processing label while transcribing', async () => {
    let resolveApi: (value: Response) => void
    mockApiFetch.mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveApi = resolve
      })
    )

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(() => {
      expect(button.textContent).toContain('processing')
    })

    resolveApi!({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ text: 'done' }),
    } as Response)

    await waitFor(() => {
      expect(button.textContent).toContain('record')
    })
  })

  it('does not start recording when transcribing', async () => {
    let resolveApi: (value: Response) => void
    mockApiFetch.mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveApi = resolve
      })
    )

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(() => {
      expect(button.textContent).toContain('processing')
    })

    const callsBefore = mockGetUserMedia.mock.calls.length
    fireEvent.click(button)
    expect(mockGetUserMedia).toHaveBeenCalledTimes(callsBefore)

    await act(async () => {
      resolveApi!({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ text: 'done' }),
      } as Response)
    })
  })

  // ===== Error: microphone permission denied =====

  it('shows error when getUserMedia rejects', async () => {
    mockGetUserMedia.mockRejectedValue(
      new DOMException('Permission denied', 'NotAllowedError')
    )

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)

    await waitFor(() => {
      expect(button.textContent).toContain('error')
    })
  })

  it('recovers from getUserMedia error after timeout', async () => {
    vi.useFakeTimers()

    mockGetUserMedia.mockRejectedValue(
      new DOMException('Permission denied', 'NotAllowedError')
    )

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)

    // Advance time to let the rejected promise propagate and React re-render
    await act(() => vi.advanceTimersByTimeAsync(10))

    expect(button.textContent).toContain('error')

    // Advance past the 2s error recovery timeout
    await act(() => vi.advanceTimersByTimeAsync(2001))
    expect(button.textContent).toContain('record')

    vi.useRealTimers()
  })

  // ===== Error: STT API failure =====

  it('shows error when STT API response is not ok', async () => {
    mockApiFetch.mockResolvedValue({ ok: false, status: 500 } as Response)

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(
      () => {
        expect(button.textContent).toContain('error')
      },
      { timeout: 4000 }
    )
  })

  it('shows error when STT API rejects', async () => {
    mockApiFetch.mockRejectedValue(new Error('Network error'))

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)

    await waitFor(
      () => {
        expect(button.textContent).toContain('error')
      },
      { timeout: 4000 }
    )
  })

  it('recovers from STT error after timeout', async () => {
    vi.useFakeTimers()

    mockApiFetch.mockRejectedValue(new Error('fail'))

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(10))
    fireAudioChunk()
    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(10))

    expect(button.textContent).toContain('error')

    await act(() => vi.advanceTimersByTimeAsync(2001))
    expect(button.textContent).toContain('record')

    vi.useRealTimers()
  })

  // ===== Error: empty audio chunks =====

  it('shows error when no audio chunks were captured', async () => {
    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()

    fireEvent.click(button)

    expect(button.textContent).toContain('error')
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  // ===== Error state interaction =====

  it('does not start recording when in error state', async () => {
    mockApiFetch.mockRejectedValue(new Error('fail'))

    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await waitForRecordingReady()
    fireAudioChunk()
    fireEvent.click(button)
    await waitFor(
      () => {
        expect(button.textContent).toContain('error')
      },
      { timeout: 4000 }
    )

    const mediaCallsCount = mockGetUserMedia.mock.calls.length
    fireEvent.click(button)
    expect(mockGetUserMedia).toHaveBeenCalledTimes(mediaCallsCount)
  })

  // ===== Resampling (sampleRate != 16000) =====

  it('resamples audio via OfflineAudioContext when input rate != 16000', async () => {
    vi.useFakeTimers()

    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(0))

    fireAudioChunk([0.1, 0.2, 0.3])

    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(mockStartRendering).toHaveBeenCalled()

    await act(() => vi.advanceTimersByTimeAsync(100))

    expect(onTranscription).toHaveBeenCalledWith('transcribed text')

    vi.useRealTimers()
  })

  // ===== Unmount =====

  it('does not throw when unmounted during recording', () => {
    const { unmount } = render(<VoiceRecorder onTranscription={vi.fn()} />)
    fireEvent.click(screen.getByRole('button'))
    expect(() => unmount()).not.toThrow()
  })

  it('stops a microphone stream that resolves after unmount', async () => {
    let resolveStream: (stream: MediaStream) => void
    const lateTrackStop = vi.fn()
    mockGetUserMedia.mockReturnValue(
      new Promise<MediaStream>((resolve) => {
        resolveStream = resolve
      })
    )
    const { unmount } = render(<VoiceRecorder onTranscription={vi.fn()} />)

    fireEvent.click(screen.getByRole('button'))
    unmount()
    await act(async () => {
      resolveStream!({
        getTracks: () => [{ stop: lateTrackStop }],
      } as unknown as MediaStream)
    })

    expect(lateTrackStop).toHaveBeenCalledOnce()
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  it('cancels recording while microphone permission is pending', async () => {
    let resolveStream: (stream: MediaStream) => void
    const lateTrackStop = vi.fn()
    mockGetUserMedia.mockReturnValue(
      new Promise<MediaStream>((resolve) => {
        resolveStream = resolve
      })
    )
    render(<VoiceRecorder onTranscription={vi.fn()} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    fireEvent.click(button)
    expect(button.textContent).toContain('record')
    await act(async () => {
      resolveStream!({
        getTracks: () => [{ stop: lateTrackStop }],
      } as unknown as MediaStream)
    })

    expect(lateTrackStop).toHaveBeenCalledOnce()
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  // ===== maxSeconds prop =====

  it('uses custom maxSeconds for auto-stop', async () => {
    vi.useFakeTimers()

    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} maxSeconds={1} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(button.textContent).toContain('stop')

    fireAudioChunk()

    await act(() => vi.advanceTimersByTimeAsync(1001))
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(onTranscription).toHaveBeenCalled()

    vi.useRealTimers()
  })

  it('defaults to 5 seconds maxSeconds', async () => {
    vi.useFakeTimers()

    const onTranscription = vi.fn()
    render(<VoiceRecorder onTranscription={onTranscription} />)
    const button = screen.getByRole('button')

    fireEvent.click(button)
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(button.textContent).toContain('stop')

    fireAudioChunk()

    // At 4s, still recording
    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(button.textContent).toContain('stop')

    // At 5s+, auto-stop fires
    await act(() => vi.advanceTimersByTimeAsync(1001))
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(onTranscription).toHaveBeenCalled()

    vi.useRealTimers()
  })
})
