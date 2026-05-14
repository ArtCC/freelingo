'use client'

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useMicVAD } from '@ricky0123/vad-react'
import { useTranslations } from 'next-intl'
import { useAuthStore } from '@/store/auth'
import { apiFetch } from '@/lib/api'
import { float32ToWav, createConvStreamPlayer, type ConvStreamPlayer } from '@/lib/audio'
import { buildConversationWsUrl, type WsMessage, type ChatContextItem } from '@/lib/conversation-ws'
import StatusIndicator, { type ConvStatus } from './StatusIndicator'
import TranscriptBubble from './TranscriptBubble'
import SessionTimeoutBanner from './SessionTimeoutBanner'
import MicButton from './MicButton'

interface TranscriptEntry {
  id: number
  role: 'user' | 'assistant'
  text: string
}

interface QuotaStatus {
  sessions_this_week: number
  sessions_limit: number
  sessions_unlimited: boolean
  minutes_today: number
  minutes_limit: number
  time_unlimited: boolean
  tokens_this_month: number
  tokens_monthly_limit: number
  tokens_unlimited: boolean
}

function QuotaBar({ label, used, limit, unlimited }: { label: string; used: number; limit: number; unlimited: boolean }) {
  const pct = unlimited || limit === 0 ? null : Math.min(100, Math.round((used / limit) * 100))
  const exceeded = !unlimited && limit > 0 && used >= limit
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-fl-hint tracking-widest text-fl-muted-4 uppercase w-36 shrink-0">{label}</span>
      {unlimited ? (
        <span className="font-mono text-fl-hint text-fl-muted-2">∞</span>
      ) : (
        <>
          <div className="flex-1 h-1 bg-fl-surface-2 overflow-hidden">
            <div
              className={`h-full transition-all ${exceeded ? 'bg-fl-error' : 'bg-fl-accent'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className={`font-mono text-fl-hint tabular-nums ${exceeded ? 'text-fl-error' : 'text-fl-muted-2'}`}>
            {used}&thinsp;/&thinsp;{limit}
          </span>
        </>
      )}
    </div>
  )
}

function quotaPillSummary(quota: QuotaStatus): { text: string; alert: boolean } {
  const parts: string[] = []
  let alert = false

  if (!quota.sessions_unlimited) {
    parts.push(`${quota.sessions_this_week}/${quota.sessions_limit} ses`)
    if (quota.sessions_this_week >= quota.sessions_limit) alert = true
  }

  if (!quota.time_unlimited) {
    parts.push(`${quota.minutes_today}/${quota.minutes_limit} min`)
    if (quota.minutes_today >= quota.minutes_limit) alert = true
  }

  if (!quota.tokens_unlimited) {
    const kUsed = Math.round(quota.tokens_this_month / 1000)
    const kLimit = Math.round(quota.tokens_monthly_limit / 1000)
    parts.push(`${kUsed}k/${kLimit}k tok`)
    if (quota.tokens_this_month >= quota.tokens_monthly_limit) alert = true
  }

  return { text: parts.length ? parts.join(' · ') : '∞', alert }
}

const CONVERSATION_STARTERS = [
  'Art & creativity',
  'Books & reading',
  'Childhood memories',
  'City vs. countryside',
  'Cooking & recipes',
  'Dreams & ambitions',
  'Family & relationships',
  'Fashion & style',
  'Favourite films',
  'Festivals & traditions',
  'Food from around the world',
  'Health & wellbeing',
  'Hobbies & crafts',
  'Language learning',
  'Learning new skills',
  'Money & budgeting',
  'Music & concerts',
  'Pets & animals',
  'Public transport',
  'Science & space',
  'Shopping habits',
  'Social media',
  'Sports & fitness',
  'Technology & gadgets',
  'The environment',
  'Travel destinations',
  'TV shows & series',
  'Weekend plans',
  'Work & career goals',
  'Working from home',
] as const

function QuotaPill({ quota, t }: { quota: QuotaStatus; t: (k: string) => string }) {
  const [open, setOpen] = useState(false)
  const { text, alert } = quotaPillSummary(quota)

  return (
    <div className="w-full">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`w-full flex items-center justify-between px-3 py-1.5 border font-mono text-fl-hint tracking-widest uppercase transition-colors ${alert
          ? 'border-fl-error/50 text-fl-error hover:border-fl-error'
          : 'border-fl-border text-fl-muted-3 hover:border-fl-border-2 hover:text-fl-muted-1'
          }`}
      >
        <span>● {text}</span>
        <span className="text-fl-muted-4">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="border border-t-0 border-fl-border bg-fl-surface px-4 py-3 space-y-1.5">
          <QuotaBar
            label={t('quotaSessions')}
            used={quota.sessions_this_week}
            limit={quota.sessions_limit}
            unlimited={quota.sessions_unlimited}
          />
          <QuotaBar
            label={t('quotaMinutes')}
            used={quota.minutes_today}
            limit={quota.minutes_limit}
            unlimited={quota.time_unlimited}
          />
          {!quota.tokens_unlimited && (
            <QuotaBar
              label={t('quotaTokens')}
              used={quota.tokens_this_month}
              limit={quota.tokens_monthly_limit}
              unlimited={false}
            />
          )}
        </div>
      )}
    </div>
  )
}

export default function ConversationMode({
  initialContext,
  autoStart,
  onClose,
}: {
  initialContext?: ChatContextItem[]
  autoStart?: boolean
  onClose?: () => void
}) {
  const t = useTranslations('conversation')
  const tCommon = useTranslations('common')
  const accessToken = useAuthStore((s) => s.accessToken)
  const user = useAuthStore((s) => s.user)

  // ─── UI State ────────────────────────────────────────────────────────────
  const [status, setStatus] = useState<ConvStatus>('loading')
  const [sessionActive, setSessionActive] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [streamingText, setStreamingText] = useState<string | null>(null)
  const [warningSeconds, setWarningSeconds] = useState<number | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [userSpeaking, setUserSpeaking] = useState(false)
  const [assistantSpeaking, setAssistantSpeaking] = useState(false)
  const [quota, setQuota] = useState<QuotaStatus | null>(null)

  // 6 random starters picked once per component mount, shown alphabetically
  const visibleStarters = useMemo(
    () =>
      ([...CONVERSATION_STARTERS] as string[])
        .sort(() => Math.random() - 0.5)
        .slice(0, 6)
        .sort((a, b) => a.localeCompare(b)),
    [],
  )

  // ─── Fetch quota on mount ─────────────────────────────────────────────────
  const refreshQuota = useCallback(() => {
    apiFetch('/api/auth/quota')
      .then((r) => (r.ok ? r.json() : null))
      .then((data: QuotaStatus | null) => data && setQuota(data))
      .catch(() => { })
  }, [])

  useEffect(() => { refreshQuota() }, [refreshQuota])

  // ─── Refs ─────────────────────────────────────────────────────────────────
  const wsRef = useRef<WebSocket | null>(null)
  const convPlayerRef = useRef<ConvStreamPlayer | null>(null)
  const transcriptIdRef = useRef(0)
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)
  // Tracks whether the session ended cleanly so ws.onclose doesn't overwrite state
  const cleanEndRef = useRef(false)

  // ─── VAD ──────────────────────────────────────────────────────────────────
  // MicVAD.new() loads the ONNX model but does NOT request mic permission yet.
  // getUserMedia() is called only when vad.start() is invoked (inside handleStart,
  // which runs during a user-gesture click).
  const vad = useMicVAD({
    baseAssetPath: '/vad/',
    onnxWASMBasePath: '/vad/',
    model: 'v5',
    startOnLoad: false,
    ortConfig: (ort) => {
      // Single-threaded ONNX — no SharedArrayBuffer / COOP headers required
      ort.env.wasm.numThreads = 1
    },
    onSpeechStart: () => {
      // Barge-in: immediately cancel any in-progress TTS playback
      if (convPlayerRef.current) {
        convPlayerRef.current.cancel()
        setAssistantSpeaking(false)
      }
      setUserSpeaking(true)
    },
    onSpeechEnd: (audio: Float32Array) => {
      setUserSpeaking(false)
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        const wav = float32ToWav(audio, 16000)
        ws.send(wav)
      }
    },
  })

  // Transition from loading → ready when VAD finishes initialising
  useEffect(() => {
    if (vad.loading) return
    if (vad.errored) {
      const errMsg = typeof vad.errored === 'string' ? vad.errored : ''
      const isPermission =
        errMsg.includes('NotAllowedError') || errMsg.includes('PermissionDeniedError')
      setErrorMsg(isPermission ? t('errorMic') : `${t('errorVadInit')}${errMsg ? ` — ${errMsg}` : ''}`)
      setStatus('error')
      return
    }
    if (status === 'loading') setStatus('ready')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vad.loading, vad.errored])

  // Auto-scroll transcript to bottom
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript, streamingText])

  // ─── Auto-start when opened as overlay from chat ────────────────────────
  const pendingAutoStartRef = useRef(false)

  useEffect(() => {
    if (autoStart && !sessionActive) {
      pendingAutoStartRef.current = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart])

  useEffect(() => {
    if (pendingAutoStartRef.current && !vad.loading && !vad.errored && !!accessToken && !sessionActive) {
      pendingAutoStartRef.current = false
      void handleStart()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vad.loading, vad.errored, accessToken])

  // ─── WebSocket ────────────────────────────────────────────────────────────
  const connectWs = useCallback(
    (token: string, context?: ChatContextItem[]) => {
      const url = buildConversationWsUrl()
      const ws = new WebSocket(url)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        const authPayload: Record<string, unknown> = { type: 'auth', token }
        if (context?.length) authPayload.context = context
        ws.send(JSON.stringify(authPayload))
        setStatus('live')
      }

      ws.onmessage = async (event) => {
        // Binary → raw MP3 chunk; forward to the streaming player
        if (event.data instanceof ArrayBuffer) {
          convPlayerRef.current?.appendChunk(event.data)
          return
        }

        // Text → JSON control message
        try {
          const msg = JSON.parse(event.data as string) as WsMessage
          switch (msg.type) {
            case 'tts_stream_start':
              setAssistantSpeaking(true)
              convPlayerRef.current?.start(() => setAssistantSpeaking(false))
              break

            case 'tts_stream_end':
              convPlayerRef.current?.end()
              break

            case 'transcript':
              if (msg.role === 'user') {
                // STT result — always final
                setTranscript((prev) => [
                  ...prev,
                  { id: transcriptIdRef.current++, role: 'user', text: msg.text },
                ])
              } else {
                // LLM token stream
                if (msg.final) {
                  setStreamingText(null)
                  setTranscript((prev) => [
                    ...prev,
                    { id: transcriptIdRef.current++, role: 'assistant', text: msg.text },
                  ])
                  setAssistantSpeaking(false)
                } else {
                  setStreamingText(msg.text)
                }
              }
              break

            case 'barge_in':
              convPlayerRef.current?.cancel()
              setAssistantSpeaking(false)
              setStreamingText(null)
              break

            case 'session_warning':
              setWarningSeconds(msg.remaining_seconds)
              break

            case 'session_end':
              cleanEndRef.current = true
              setStatus('ended')
              setSessionActive(false)
              vad.pause()
              ws.close(1000, 'session_end')
              break

            case 'error':
              cleanEndRef.current = true
              setErrorMsg(
                msg.code === 'services_disabled'
                  ? t('errorServicesDisabled')
                  : msg.code === 'quota_exceeded_sessions'
                    ? t('quotaExceededSessions')
                    : msg.code === 'quota_exceeded_time'
                      ? t('quotaExceededTime')
                      : msg.code === 'quota_exceeded_tokens'
                        ? t('quotaExceededTokens')
                        : (msg.message ?? t('errorConnection')),
              )
              setStatus('error')
              ws.close()
              break
          }
        } catch {
          // Non-JSON (shouldn't happen for text frames) — ignore
        }
      }

      ws.onerror = () => {
        if (!cleanEndRef.current) {
          setErrorMsg(`${t('errorConnection')} [onerror → ${url}]`)
          setStatus('error')
          setSessionActive(false)
        }
      }

      ws.onclose = (ev) => {
        if (!cleanEndRef.current) {
          if (ev.code === 1008) {
            setErrorMsg(t('errorUnauthorized'))
          } else if (ev.code !== 1000) {
            setErrorMsg(`${t('errorConnection')} [code ${ev.code}: ${ev.reason || 'no reason'} → ${url}]`)
          }
          setStatus('error')
          setSessionActive(false)
        }
        cleanEndRef.current = false
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  )

  // ─── Session lifecycle ────────────────────────────────────────────────────
  async function handleStart(topicContext?: ChatContextItem[]) {
    if (!accessToken || vad.loading || vad.errored) return

    // Unlock audio for this page during the user-gesture context.
    // On iOS Safari and browsers with strict autoplay policies, audio.play() and
    // new AudioContext().resume() are only allowed synchronously during a user
    // gesture.  Playing a 1-sample silent buffer here marks the page as
    // "user has interacted" so subsequent play() calls in event handlers succeed.
    try {
      const unlockCtx = new AudioContext()
      const silentBuf = unlockCtx.createBuffer(1, 1, 22050)
      const src = unlockCtx.createBufferSource()
      src.buffer = silentBuf
      src.connect(unlockCtx.destination)
      src.start(0)
      // Close after a short delay so the gesture context is fully registered
      setTimeout(() => unlockCtx.close().catch(() => undefined), 500)
    } catch {
      // Some environments don't support AudioContext — proceed without unlock
    }

    // Create the streaming TTS player (must be during user gesture so autoplay
    // is unlocked; the player itself defers HTMLAudioElement creation to start())
    convPlayerRef.current = createConvStreamPlayer()

    cleanEndRef.current = false
    setStatus('connecting')
    setSessionActive(true)
    setTranscript([])
    setStreamingText(null)
    setWarningSeconds(null)
    setErrorMsg(null)
    setUserSpeaking(false)
    setAssistantSpeaking(false)
    refreshQuota()

    // Trigger model warmup on TTS/STT services and WAIT for them to be ready
    // before opening the WebSocket. Models are loaded lazily by the backend;
    // this ensures the first transcription/synthesis in the session is fast.
    // Runs in parallel with VAD mic permission request.
    setStatus('warming')
    const warmupPromise = apiFetch('/api/conversation/warmup', { method: 'POST' }).catch(() => undefined)

    // Start mic (requests permission if not already granted)
    vad.start().catch((e: unknown) => {
      setErrorMsg(e instanceof Error ? e.message : t('errorMic'))
      setStatus('error')
      setSessionActive(false)
    })

    await warmupPromise
    connectWs(accessToken, topicContext ?? initialContext)
  }

  function handleStop() {
    cleanEndRef.current = true
    wsRef.current?.close(1000, 'user_stopped')
    wsRef.current = null
    vad.pause()
    convPlayerRef.current?.cancel()
    convPlayerRef.current = null
    setSessionActive(false)
    setStatus('ended')
    // Allow a moment for the backend to record session seconds, then refresh
    setTimeout(() => refreshQuota(), 1500)
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanEndRef.current = true
      wsRef.current?.close()
      convPlayerRef.current?.cancel()
    }
  }, [])

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full min-h-[calc(100vh-56px)] md:min-h-screen p-4 md:p-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6 pb-4 border-b border-fl-border flex items-end justify-between">
        <div>
          <p className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase mb-1">
            {t('subtitle')}
          </p>
          <h1 className="font-mono text-2xl font-bold tracking-tight text-fl-fg">{t('title')}</h1>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="font-mono text-fl-hint tracking-widest text-fl-muted-2 hover:text-fl-fg uppercase transition-colors"
          >
            ← {tCommon('back')}
          </button>
        )}
      </div>

      {/* Timeout warning */}
      {warningSeconds !== null && <SessionTimeoutBanner seconds={warningSeconds} />}

      {/* Transcript area */}
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 min-h-[120px] px-2">
        {transcript.length === 0 && !streamingText && status === 'live' && (
          <p className="font-mono text-fl-label text-fl-muted-4 text-center py-8">
            {t('tapToStart')}
          </p>
        )}
        {(() => {
          const lastUserIdx = transcript.reduce((acc, e, j) => e.role === 'user' ? j : acc, -1)
          return transcript.map((entry, i) => (
            <TranscriptBubble
              key={entry.id}
              role={entry.role}
              text={entry.text}
              speaking={entry.role === 'user' && userSpeaking && i === lastUserIdx}
              userAvatar={user?.avatar}
              userInitial={(user?.displayName || user?.username || '?')[0]}
            />
          ))
        })()}
        {streamingText !== null && (
          <TranscriptBubble
            role="assistant"
            text={streamingText}
            streaming
            speaking={assistantSpeaking}
            userAvatar={user?.avatar}
            userInitial={(user?.displayName || user?.username || '?')[0]}
          />
        )}
        <div ref={transcriptEndRef} />
      </div>

      {/* Status message */}
      {status === 'error' && errorMsg && (
        <div className="mb-4 border border-fl-error/40 bg-fl-surface px-4 py-3 font-mono text-xs text-fl-error">
          ✕ {errorMsg}
        </div>
      )}
      {status === 'ended' && (
        <div className="mb-4 border border-fl-border bg-fl-surface px-4 py-3 font-mono text-xs text-fl-muted-2">
          — {t('sessionEnded')}
        </div>
      )}

      {/* Conversation starters — shown when idle, hidden as soon as session starts */}
      {!sessionActive && (status === 'ready' || status === 'ended' || status === 'error') && (
        <div className="mb-4">
          <p className="font-mono text-fl-hint tracking-widest text-fl-muted-3 uppercase text-center mb-3">
            {t('startersHint')}
          </p>
          <div className="flex flex-wrap gap-2 justify-center">
            {visibleStarters.map((topic) => (
              <button
                key={topic}
                onClick={() => void handleStart([{ role: 'user', content: `I'd like to practice English by talking about ${topic}.` }])}
                className="font-mono text-xs tracking-wide text-fl-muted-1 border border-fl-border px-3 py-2 hover:border-fl-border-2 hover:text-fl-fg transition-colors"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-col items-center gap-4 pb-2">
        {/* Quota pill */}
        {quota && <QuotaPill quota={quota} t={t} />}
        <StatusIndicator
          status={status}
          userSpeaking={userSpeaking}
          assistantSpeaking={assistantSpeaking}
        />
        <MicButton
          status={status}
          sessionActive={sessionActive}
          onStart={handleStart}
          onStop={handleStop}
        />
      </div>
    </div>
  )
}
