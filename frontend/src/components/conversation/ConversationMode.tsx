'use client'

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useMicVAD } from '@ricky0123/vad-react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { useAuthStore } from '@/store/auth'
import { useConfigStore } from '@/store/config'
import { apiFetch } from '@/lib/api'
import { float32ToWav, createAudioQueue, type AudioQueue } from '@/lib/audio'
import { getLogger, silentLogger } from '@/lib/logger'
import { mapUser } from '@/lib/mappers'
import { splitYearlyCta, type BillingInterval } from '@/lib/billing-copy'
import {
  buildConversationWsUrl,
  type WsMessage,
  type ChatContextItem,
} from '@/lib/conversation-ws'
import StatusIndicator, { type ConvStatus } from './StatusIndicator'
import TranscriptBubble from './TranscriptBubble'
import SessionTimeoutBanner from './SessionTimeoutBanner'
import MicButton from './MicButton'
import { type QuotaStatus } from '@/types/api'
import {
  ReviewPrompt,
  getReviewPromptDismissal,
} from '@/components/reviews/ReviewPrompt'
import { shouldShowVoiceReviewPrompt } from '@/lib/review-prompt-triggers'

interface TranscriptEntry {
  id: number
  role: 'user' | 'assistant'
  text: string
}

function QuotaBar({
  label,
  used,
  limit,
  unlimited,
}: {
  label: string
  used: number
  limit: number
  unlimited: boolean
}) {
  const pct =
    unlimited || limit === 0
      ? null
      : Math.min(100, Math.round((used / limit) * 100))
  const exceeded = !unlimited && limit > 0 && used >= limit
  return (
    <div className="flex items-center gap-3">
      <span className="text-fl-hint text-fl-muted-4 w-36 shrink-0 font-mono tracking-widest uppercase">
        {label}
      </span>
      {unlimited ? (
        <span className="text-fl-hint text-fl-muted-2 font-mono">∞</span>
      ) : (
        <>
          <div className="bg-fl-surface-2 h-1 flex-1 overflow-hidden">
            <div
              className={`h-full transition-all ${exceeded ? 'bg-fl-error' : 'bg-fl-accent'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span
            className={`text-fl-hint font-mono tabular-nums ${exceeded ? 'text-fl-error' : 'text-fl-muted-2'}`}
          >
            {used}&thinsp;/&thinsp;{limit}
          </span>
        </>
      )}
    </div>
  )
}

function quotaPillSummary(quota: QuotaStatus): {
  text: string
  alert: boolean
} {
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
    const kUsed = Math.round((quota.tokens_this_month ?? 0) / 1000)
    const kLimit = Math.round((quota.tokens_monthly_limit ?? 0) / 1000)
    parts.push(`${kUsed}k/${kLimit}k tok`)
    if ((quota.tokens_this_month ?? 0) >= (quota.tokens_monthly_limit ?? 0))
      alert = true
  }

  return { text: parts.length ? parts.join(' · ') : '∞', alert }
}

function QuotaPill({
  quota,
  t,
}: {
  quota: QuotaStatus
  t: (k: string) => string
}) {
  const [open, setOpen] = useState(false)
  const { text, alert } = quotaPillSummary(quota)

  return (
    <div className="w-full">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`text-fl-hint flex w-full items-center justify-between border px-3 py-1.5 font-mono tracking-widest uppercase transition-colors ${
          alert
            ? 'border-fl-error/50 text-fl-error hover:border-fl-error'
            : 'border-fl-border text-fl-muted-3 hover:border-fl-border-2 hover:text-fl-muted-1'
        }`}
      >
        <span>● {text}</span>
        <span className="text-fl-muted-4">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="border-fl-border bg-fl-surface space-y-1.5 border border-t-0 px-4 py-3">
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
              used={quota.tokens_this_month ?? 0}
              limit={quota.tokens_monthly_limit ?? 0}
              unlimited={false}
            />
          )}
        </div>
      )}
    </div>
  )
}

function TrialPremiumCta() {
  const t = useTranslations('billing')
  const tConversation = useTranslations('conversation')
  const router = useRouter()
  const priceMonthly = useConfigStore((s) => s.priceMonthly)
  const priceYearly = useConfigStore((s) => s.priceYearly)
  const [loading, setLoading] = useState<BillingInterval | null>(null)
  const [error, setError] = useState<string | null>(null)
  const yearlyCta = splitYearlyCta(
    t('planYearly', { price: String(priceYearly) })
  )

  async function handleCheckout(interval: BillingInterval) {
    setLoading(interval)
    setError(null)
    try {
      const res = await apiFetch('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: interval }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? t('checkoutError'))
      }
      const { url } = await res.json()
      window.location.assign(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('checkoutError'))
      setLoading(null)
    }
  }

  return (
    <div className="border-fl-border bg-fl-surface mb-4 border p-5 text-center">
      <p className="text-fl-label text-fl-muted-2 mb-2 font-mono tracking-widest uppercase">
        {tConversation('trialCtaLabel')}
      </p>
      <h2 className="text-fl-fg mb-2 font-mono text-base font-bold">
        {tConversation('trialCtaTitle')}
      </h2>
      <p className="text-fl-muted-1 mb-5 font-mono text-xs leading-relaxed">
        {tConversation('trialCtaDesc')}
      </p>
      <div className="flex flex-col gap-3">
        <button
          onClick={() => handleCheckout('yearly')}
          disabled={loading !== null}
          className="bg-fl-accent text-fl-accent-fg hover:bg-fl-accent/90 w-full px-4 py-3 font-mono text-xs tracking-widest uppercase transition-colors disabled:opacity-50"
        >
          {loading === 'yearly' ? (
            '...'
          ) : (
            <span className="flex flex-col items-center gap-0.5 leading-relaxed">
              <span>{yearlyCta.main}</span>
              {yearlyCta.savings && (
                <span className="text-fl-accent-fg/80 text-[0.68rem]">
                  {yearlyCta.savings}
                </span>
              )}
            </span>
          )}
        </button>
        <button
          onClick={() => handleCheckout('monthly')}
          disabled={loading !== null}
          className="border-fl-border text-fl-muted-1 hover:text-fl-fg hover:border-fl-border-2 w-full border px-4 py-3 font-mono text-xs tracking-widest uppercase transition-colors disabled:opacity-50"
        >
          {loading === 'monthly'
            ? '...'
            : t('planMonthly', { price: String(priceMonthly) })}
        </button>
      </div>
      {error && (
        <p className="text-fl-hint mt-4 font-mono text-red-500">{error}</p>
      )}
      <button
        onClick={() => router.push('/plan')}
        className="text-fl-hint text-fl-muted-4 hover:text-fl-muted-2 mt-5 w-full font-mono tracking-widest uppercase transition-colors"
      >
        {t('paywallSkip')}
      </button>
    </div>
  )
}

function vadRedemptionMs(cefrLevel: string | null | undefined): number {
  if (!cefrLevel) return 1000
  if (cefrLevel === 'A1' || cefrLevel === 'A2') return 1300
  if (cefrLevel === 'B1' || cefrLevel === 'B2') return 1100
  return 900 // C1, C2
}

const ENABLE_CONVERSATION_AUDIO_DEBUG_LOGS = false
const ENABLE_CONVERSATION_BARGE_IN = false
const MIN_UTTERANCE_MS = 900
const MIN_UTTERANCE_RMS = 0.012
const INTERRUPTION_MIN_UTTERANCE_MS = 1200
const INTERRUPTION_RMS_THRESHOLD = 0.03
const BARGE_IN_STARTUP_GUARD_MS = 900
const VAD_MAX_RMS = 0.25
const convLogger = ENABLE_CONVERSATION_AUDIO_DEBUG_LOGS
  ? getLogger('conversation-audio')
  : silentLogger

export default function ConversationMode({
  initialContext,
  autoStart,
  cefrLevel,
  targetLanguage,
  voiceTrialToken,
  voiceTrialDurationSeconds,
  trialMode,
  freemiumVoiceRemaining,
  freemiumVoiceLimit,
  onClose,
}: {
  initialContext?: ChatContextItem[]
  autoStart?: boolean
  cefrLevel?: string | null
  targetLanguage?: string
  voiceTrialToken?: string
  voiceTrialDurationSeconds?: number
  trialMode?: boolean
  freemiumVoiceRemaining?: number
  freemiumVoiceLimit?: number
  onClose?: () => void
}) {
  const t = useTranslations('conversation')
  const tCommon = useTranslations('common')
  const accessToken = useAuthStore((s) => s.accessToken)
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)

  // ─── UI State ────────────────────────────────────────────────────────────
  const [status, setStatus] = useState<ConvStatus>('loading')
  const [sessionActive, setSessionActive] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [streamingText, setStreamingText] = useState<string | null>(null)
  const [warningSeconds, setWarningSeconds] = useState<number | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [userSpeaking, setUserSpeaking] = useState(false)
  const [assistantSpeaking, setAssistantSpeaking] = useState(false)
  const [memoryToast, setMemoryToast] = useState(false)
  const [quota, setQuota] = useState<QuotaStatus | null>(null)
  const [reviewPromptOpen, setReviewPromptOpen] = useState(false)

  // 6 random starters picked once per component mount, shown alphabetically
  const visibleStarters = useMemo(
    () =>
      (t.raw('starters') as string[])
        .sort(() => Math.random() - 0.5)
        .slice(0, 6)
        .sort((a, b) => a.localeCompare(b)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  // ─── Fetch quota on mount ─────────────────────────────────────────────────
  const refreshQuota = useCallback(() => {
    apiFetch('/api/auth/quota')
      .then((r) => (r.ok ? r.json() : null))
      .then((data: QuotaStatus | null) => data && setQuota(data))
      .catch(() => {})
  }, [])

  useEffect(() => {
    refreshQuota()
  }, [refreshQuota])

  // ─── Refs ─────────────────────────────────────────────────────────────────
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const audioQueueRef = useRef<AudioQueue | null>(null)
  const transcriptIdRef = useRef(0)
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)
  const activeTurnIdRef = useRef<number | null>(null)
  // Tracks whether the session ended cleanly so ws.onclose doesn't overwrite state
  const cleanEndRef = useRef(false)
  const mountedRef = useRef(true)
  const startAttemptRef = useRef(0)
  const assistantSpeakingRef = useRef(false)
  const assistantTurnActiveRef = useRef(false)
  const speechStartedAtRef = useRef<number | null>(null)
  const sessionActiveRef = useRef(false)
  const ttsChunkIndexRef = useRef(0)
  const lastAssistantAudioAtRef = useRef(0)
  const closeReasonRef = useRef<'manual' | 'route_unload' | 'unknown'>(
    'unknown'
  )
  const sessionStartedAtRef = useRef<number | null>(null)

  useEffect(() => {
    assistantSpeakingRef.current = assistantSpeaking
  }, [assistantSpeaking])

  useEffect(() => {
    sessionActiveRef.current = sessionActive
  }, [sessionActive])

  const isLikelySpeech = useCallback(
    (
      audio: Float32Array,
      minUtteranceMs = MIN_UTTERANCE_MS
    ): { isSpeech: boolean; rms: number; durationMs: number } => {
      const samples = audio.length
      if (samples === 0) {
        return { isSpeech: false, rms: 0, durationMs: 0 }
      }
      const startedAt = speechStartedAtRef.current
      const durationMs = (samples / 16000) * 1000
      if (!startedAt || durationMs < minUtteranceMs) {
        return { isSpeech: false, rms: 0, durationMs }
      }
      let energy = 0
      for (let i = 0; i < samples; i += 1) {
        const sample = audio[i]
        energy += sample * sample
      }
      const rms = Math.sqrt(energy / samples)
      const cappedRms = Number.isFinite(rms) ? Math.min(rms, VAD_MAX_RMS) : 0
      return {
        isSpeech: cappedRms >= MIN_UTTERANCE_RMS,
        rms: cappedRms,
        durationMs,
      }
    },
    []
  )

  // ─── VAD ──────────────────────────────────────────────────────────────────
  // MicVAD.new() loads the ONNX model but does NOT request mic permission yet.
  // getUserMedia() is called only when vad.start() is invoked (inside handleStart,
  // which runs during a user-gesture click).
  const vad = useMicVAD({
    baseAssetPath: '/vad/',
    onnxWASMBasePath: '/vad/',
    model: 'v5',
    startOnLoad: false,
    redemptionMs: vadRedemptionMs(cefrLevel),
    ortConfig: (ort) => {
      // Single-threaded ONNX — no SharedArrayBuffer / COOP headers required
      ort.env.wasm.numThreads = 1
    },
    onSpeechStart: () => {
      convLogger.info('vad speech start', {
        assistantSpeaking: assistantSpeakingRef.current,
      })
      speechStartedAtRef.current = performance.now()
      setUserSpeaking(true)
    },
    onSpeechEnd: (audio: Float32Array) => {
      const minUtteranceMs = assistantTurnActiveRef.current
        ? INTERRUPTION_MIN_UTTERANCE_MS
        : MIN_UTTERANCE_MS
      const speech = isLikelySpeech(audio, minUtteranceMs)
      const isSpeech = speech.isSpeech
      convLogger.info('vad speech end', {
        isSpeech,
        rms: speech.rms,
        durationMs: Math.round(speech.durationMs),
        sessionActive: sessionActiveRef.current,
        assistantSpeaking: assistantSpeakingRef.current,
        assistantTurnActive: assistantTurnActiveRef.current,
      })
      speechStartedAtRef.current = null
      if (!isSpeech) {
        setUserSpeaking(false)
        return
      }
      setUserSpeaking(false)

      // Ignore accidental detections when the session ended.
      if (!sessionActiveRef.current) {
        return
      }

      // Never interrupt the tutor turn. While the backend is generating or
      // sending chunked audio, any detected speech is ignored to avoid lost
      // responses from VAD false positives or accidental overlap.
      if (assistantTurnActiveRef.current) {
        convLogger.warn('ignored user speech while assistant turn is active', {
          rms: speech.rms,
          durationMs: Math.round(speech.durationMs),
          assistantSpeaking: assistantSpeakingRef.current,
        })
        return
      }

      // If the assistant is speaking, avoid false positive interruptions
      // from playback leakage / room noise. Kept as a defensive guard for any
      // state race before assistantTurnActiveRef is updated.
      if (
        assistantSpeakingRef.current &&
        speech.rms < INTERRUPTION_RMS_THRESHOLD
      ) {
        convLogger.warn('ignored speech while assistant was speaking', {
          rms: speech.rms,
          lastAssistantAudioMsAgo:
            performance.now() - lastAssistantAudioAtRef.current,
        })
        return
      }

      const sinceLastAssistantAudioMs =
        performance.now() - lastAssistantAudioAtRef.current
      const wasAssistantSpeaking = assistantSpeakingRef.current

      if (wasAssistantSpeaking && !ENABLE_CONVERSATION_BARGE_IN) {
        convLogger.warn('ignored user speech while assistant audio is active', {
          rms: speech.rms,
          durationMs: Math.round(speech.durationMs),
          sinceLastAssistantAudioMs: Math.round(sinceLastAssistantAudioMs),
        })
        return
      }

      if (
        wasAssistantSpeaking &&
        sinceLastAssistantAudioMs < BARGE_IN_STARTUP_GUARD_MS
      ) {
        convLogger.warn('ignored speech early in assistant playback window', {
          rms: speech.rms,
          sinceLastAssistantAudioMs: Math.round(sinceLastAssistantAudioMs),
        })
        return
      }

      if (wasAssistantSpeaking) {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          convLogger.info('sending interrupt at speech end', {
            rms: speech.rms,
            durationMs: Math.round(speech.durationMs),
            sinceLastAssistantAudioMs: Math.round(sinceLastAssistantAudioMs),
          })
          wsRef.current.send(JSON.stringify({ type: 'interrupt' }))
          setAssistantSpeaking(false)
        }
      }

      // Barge-in: cancel in-progress TTS playback only when assistant is speaking.
      if (assistantSpeakingRef.current && audioQueueRef.current) {
        convLogger.info('processing barge-in speech', {
          rms: speech.rms,
          sinceLastAssistantAudioMs: Math.round(sinceLastAssistantAudioMs),
        })
        audioQueueRef.current.cancel()
        setAssistantSpeaking(false)
      }

      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        const wav = float32ToWav(audio, 16000)
        convLogger.info('sent user utterance to backend', {
          bytes: wav.byteLength,
          assistantSpeaking: assistantSpeakingRef.current,
        })
        ws.send(wav)
      }
    },
  })

  const refreshCurrentUser = useCallback(async () => {
    try {
      const res = await apiFetch('/api/auth/me')
      if (!res.ok) return
      const data = await res.json()
      setUser(mapUser(data, useAuthStore.getState().user))
    } catch {
      // Non-fatal: the backend remains authoritative and the next /me refresh will sync state.
    }
  }, [setUser])

  // Transition from loading → ready when VAD finishes initialising
  useEffect(() => {
    if (vad.loading) return
    if (vad.errored) {
      const errMsg = typeof vad.errored === 'string' ? vad.errored : ''
      const isPermission =
        errMsg.includes('NotAllowedError') ||
        errMsg.includes('PermissionDeniedError')
      setErrorMsg(
        isPermission
          ? t('errorMic')
          : `${t('errorVadInit')}${errMsg ? ` — ${errMsg}` : ''}`
      )
      setStatus('error')
      return
    }
    if (status === 'loading') setStatus('ready')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vad.loading, vad.errored])

  const finalizeSession = useCallback(
    (reason: 'manual' | 'route_unload' | 'unknown' = 'unknown') => {
      closeReasonRef.current = reason
      if (!mountedRef.current) return
      activeTurnIdRef.current = null
      assistantTurnActiveRef.current = false
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'client_event',
            event: 'session_close_request',
            reason,
          })
        )
      }
      wsRef.current?.close()
      wsRef.current = null
      vad.pause()
      setAssistantSpeaking(false)
      setUserSpeaking(false)
      setStreamingText(null)
      audioQueueRef.current?.cancel()
      audioQueueRef.current = null
      if (audioCtxRef.current) {
        void audioCtxRef.current.close().catch(() => {})
        audioCtxRef.current = null
      }
      setSessionActive(false)
    },
    [vad]
  )

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
    if (
      pendingAutoStartRef.current &&
      !vad.loading &&
      !vad.errored &&
      !!accessToken &&
      !sessionActive
    ) {
      pendingAutoStartRef.current = false
      void handleStart()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vad.loading, vad.errored, accessToken])

  // ─── WebSocket ────────────────────────────────────────────────────────────
  const connectWs = useCallback(
    (token: string, context?: ChatContextItem[]) => {
      convLogger.info('opening conversation websocket')
      const url = buildConversationWsUrl()
      const ws = new WebSocket(url)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        const authPayload: Record<string, unknown> = { type: 'auth', token }
        const storedVoice =
          typeof window !== 'undefined'
            ? localStorage.getItem('tts_voice')
            : null
        if (storedVoice) authPayload.voice = storedVoice
        if (context?.length) authPayload.context = context
        if (targetLanguage) authPayload.target_language = targetLanguage
        if (voiceTrialToken) authPayload.voice_trial_token = voiceTrialToken
        ws.send(JSON.stringify(authPayload))
        sessionStartedAtRef.current = Date.now()
        convLogger.info('ws auth sent', {
          hasContext: !!context?.length,
          targetLanguage: targetLanguage ?? null,
        })
        setStatus('live')
      }

      const handleAudioChunk = (arrayBuffer: ArrayBuffer): void => {
        const chunkId = ++ttsChunkIndexRef.current
        convLogger.warn('playback chunk received', {
          chunkId,
          bytes: arrayBuffer.byteLength,
        })
        lastAssistantAudioAtRef.current = performance.now()
        assistantTurnActiveRef.current = true
        if (!audioQueueRef.current) {
          convLogger.warn('audio queue missing for playback')
          setAssistantSpeaking(false)
          return
        }
        setAssistantSpeaking(true)
        void audioQueueRef.current.enqueue(arrayBuffer).catch((error) => {
          convLogger.error('audio queue enqueue failed', {
            chunkId,
            error: error instanceof Error ? error.message : String(error),
          })
          setAssistantSpeaking(false)
        })
      }

      ws.onmessage = (event) => {
        // Binary → TTS audio chunk
        if (event.data instanceof ArrayBuffer) {
          handleAudioChunk(event.data)
          return
        }
        if (event.data instanceof Blob) {
          void event.data
            .arrayBuffer()
            .then((arrayBuffer) => handleAudioChunk(arrayBuffer))
            .catch(() => {})
          return
        }

        // Text → JSON control message
        try {
          const msg = JSON.parse(event.data as string) as WsMessage
          convLogger.debug('ws text message', { type: msg.type })
          if (msg.turn_id !== undefined) {
            activeTurnIdRef.current = msg.turn_id
          }

          switch (msg.type) {
            case 'transcript':
              if (msg.role === 'user') {
                // STT result — always final
                setTranscript((prev) => [
                  ...prev,
                  {
                    id: transcriptIdRef.current++,
                    role: 'user',
                    text: msg.text,
                  },
                ])
              } else {
                assistantTurnActiveRef.current = true
                // LLM token stream
                if (msg.final) {
                  setStreamingText(null)
                  setTranscript((prev) => [
                    ...prev,
                    {
                      id: transcriptIdRef.current++,
                      role: 'assistant',
                      text: msg.text,
                    },
                  ])
                } else {
                  setStreamingText(msg.text)
                }
              }
              break

            case 'turn_complete':
              assistantTurnActiveRef.current = false
              break

            case 'barge_in':
              convLogger.warn('barge_in message from backend')
              audioQueueRef.current?.cancel()
              setAssistantSpeaking(false)
              setStreamingText(null)
              break

            case 'session_warning':
              convLogger.debug('session warning', {
                remainingSeconds: msg.remaining_seconds,
              })
              setWarningSeconds(msg.remaining_seconds)
              break

            case 'status':
              setStatus('live')
              convLogger.debug('status update', { value: msg.value })
              if (msg.value === 'transcribing') {
                setAssistantSpeaking(false)
              } else if (msg.value === 'speaking') {
                setAssistantSpeaking(true)
              } else if (msg.value === 'thinking') {
                assistantTurnActiveRef.current = true
              } else if (msg.value === 'listening') {
                assistantTurnActiveRef.current = false
              }
              break

            case 'session_end':
              cleanEndRef.current = true
              assistantTurnActiveRef.current = false
              finalizeSession()
              convLogger.info('session end received', { reason: msg.reason })
              setStatus('ended')
              if (trialMode) void refreshCurrentUser()
              break

            case 'error':
              convLogger.error('ws error message', {
                code: msg.code,
                message: msg.message,
              })
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
                        : msg.code === 'no_active_plan'
                          ? tCommon('noActivePlan')
                          : (msg.message ?? t('errorConnection'))
              )
              setStatus('error')
              assistantTurnActiveRef.current = false
              ws.close()
              break

            case 'memory_updated':
              setMemoryToast(true)
              setTimeout(() => setMemoryToast(false), 3500)
              break
          }
        } catch {
          // Non-JSON (shouldn't happen for text frames) — ignore
        }
      }

      ws.onerror = () => {
        if (!cleanEndRef.current) {
          convLogger.error('ws onerror')
          setErrorMsg(`${t('errorConnection')} [onerror → ${url}]`)
          setStatus('error')
          finalizeSession()
        }
      }

      ws.onclose = (ev) => {
        convLogger.warn('ws closed', { code: ev.code, reason: ev.reason })
        if (!cleanEndRef.current) {
          if (ev.code === 1008) {
            setErrorMsg(t('errorUnauthorized'))
          } else if (ev.code !== 1000) {
            setErrorMsg(
              `${t('errorConnection')} [code ${ev.code}: ${ev.reason || 'no reason'} → ${url}]`
            )
          }
          setStatus('error')
          finalizeSession()
        }
        cleanEndRef.current = false
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      t,
      targetLanguage,
      voiceTrialToken,
      trialMode,
      refreshCurrentUser,
      finalizeSession,
    ]
  )

  // ─── Session lifecycle ────────────────────────────────────────────────────
  async function handleStart(topicContext?: ChatContextItem[]) {
    if (
      !accessToken ||
      vad.loading ||
      vad.errored ||
      sessionActive ||
      status === 'warming' ||
      status === 'connecting' ||
      status === 'live'
    )
      return

    const startAttempt = ++startAttemptRef.current

    // AudioContext MUST be created during a user-gesture (this click handler)
    const ctx = new AudioContext()
    audioCtxRef.current = ctx
    try {
      if (ctx.state === 'suspended') {
        await ctx.resume()
      }
    } catch (error) {
      convLogger.warn('audio context resume failed', { error })
    }
    audioQueueRef.current = createAudioQueue(ctx, () => {
      setAssistantSpeaking(false)
    })

    cleanEndRef.current = false
    setStatus('connecting')
    setSessionActive(true)
    setAssistantSpeaking(false)
    setTranscript([])
    setStreamingText(null)
    setWarningSeconds(null)
    setErrorMsg(null)
    setUserSpeaking(false)
    setAssistantSpeaking(false)
    activeTurnIdRef.current = null
    assistantTurnActiveRef.current = false
    sessionStartedAtRef.current = null
    refreshQuota()

    // Trigger model warmup on TTS/STT services and WAIT for them to be ready
    // before opening the WebSocket. Models are loaded lazily by the backend;
    // this ensures the first transcription/synthesis in the session is fast.
    setStatus('warming')

    // Start mic (requests permission if not already granted)
    vad.start().catch((e: unknown) => {
      if (!mountedRef.current || startAttemptRef.current !== startAttempt)
        return
      startAttemptRef.current++
      setErrorMsg(e instanceof Error ? e.message : t('errorMic'))
      setStatus('error')
      setSessionActive(false)
      audioCtxRef.current?.close()
      audioCtxRef.current = null
      audioQueueRef.current = null
    })

    const warmupResponsePromise = apiFetch('/api/conversation/warmup', {
      method: 'POST',
      ...(voiceTrialToken
        ? {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trial_token: voiceTrialToken }),
          }
        : {}),
    })
    const warmupTimeout = new Promise<Response>((_, reject) => {
      setTimeout(() => reject(new Error('warmup timeout')), 15_000)
    })
    let warmupResponse: Response
    try {
      warmupResponse = (await Promise.race([
        warmupResponsePromise,
        warmupTimeout,
      ])) as Response
    } catch {
      if (!mountedRef.current || startAttemptRef.current !== startAttempt) {
        ctx.close()
        return
      }
      setErrorMsg(`${t('errorConnection')} [warmup request failed]`)
      convLogger.error('warmup request failed')
      setStatus('error')
      setSessionActive(false)
      vad.pause()
      ctx.close()
      audioCtxRef.current = null
      audioQueueRef.current = null
      return
    }

    if (!warmupResponse.ok) {
      if (!mountedRef.current || startAttemptRef.current !== startAttempt) {
        ctx.close()
        return
      }
      setErrorMsg(`${t('errorConnection')} [warmup ${warmupResponse.status}]`)
      convLogger.error('warmup bad status', { status: warmupResponse.status })
      setStatus('error')
      setSessionActive(false)
      vad.pause()
      ctx.close()
      audioCtxRef.current = null
      audioQueueRef.current = null
      return
    }

    if (!mountedRef.current || startAttemptRef.current !== startAttempt) {
      ctx.close()
      return
    }
    const latestToken = useAuthStore.getState().accessToken
    if (!latestToken) {
      setErrorMsg(t('errorUnauthorized'))
      setStatus('error')
      setSessionActive(false)
      ctx.close()
      audioCtxRef.current = null
      audioQueueRef.current = null
      convLogger.error('no access token for websocket connect')
      return
    }
    connectWs(latestToken, topicContext ?? initialContext)
  }

  function handleStop() {
    const sessionDurationMs = sessionStartedAtRef.current
      ? Date.now() - sessionStartedAtRef.current
      : 0
    startAttemptRef.current++
    cleanEndRef.current = true
    finalizeSession('manual')
    sessionStartedAtRef.current = null
    setStatus('ended')
    if (trialMode) void refreshCurrentUser()
    if (
      shouldShowVoiceReviewPrompt(getReviewPromptDismissal(), sessionDurationMs)
    ) {
      setReviewPromptOpen(true)
    }
    // Allow a moment for the backend to record session seconds, then refresh
    setTimeout(() => refreshQuota(), 1500)
  }

  // Cleanup on unmount
  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    return () => {
      mountedRef.current = false
      startAttemptRef.current++
      cleanEndRef.current = true
      assistantTurnActiveRef.current = false
      closeReasonRef.current = 'route_unload'
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'client_event',
            event: 'session_close_request',
            reason: closeReasonRef.current,
          })
        )
      }
      wsRef.current?.close()
      vad.pause()
      audioQueueRef.current?.cancel()
      audioCtxRef.current?.close()
      sessionStartedAtRef.current = null
    }
  }, [])
  /* eslint-enable react-hooks/exhaustive-deps */

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="mx-auto flex h-[calc(100dvh-56px)] max-w-4xl flex-col overflow-hidden p-4 md:h-screen md:p-6">
      {/* Header */}
      <div className="border-fl-border mb-6 flex items-end justify-between border-b pb-4">
        <div>
          <p className="text-fl-label text-fl-muted-2 mb-1 font-mono tracking-widest uppercase">
            {t('subtitle')}
          </p>
          <h1 className="text-fl-fg font-mono text-2xl font-bold tracking-tight">
            {t('title')}
          </h1>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-fl-hint text-fl-muted-2 hover:text-fl-fg font-mono tracking-widest uppercase transition-colors"
          >
            ← {tCommon('back')}
          </button>
        )}
      </div>

      {trialMode && (
        <div className="border-fl-accent/40 bg-fl-surface text-fl-muted-1 mb-4 border px-4 py-3 text-center font-mono text-xs tracking-widest uppercase">
          {t('trialBanner', {
            minutes: Math.round((voiceTrialDurationSeconds ?? 300) / 60),
          })}
        </div>
      )}

      {/* Memory updated toast */}
      {memoryToast && (
        <div className="pointer-events-none fixed inset-x-0 top-16 z-50 flex justify-center">
          <div className="border-fl-border bg-fl-surface text-fl-muted-1 animate-in fade-in slide-in-from-top-2 pointer-events-auto border px-4 py-2 font-mono text-xs tracking-widest uppercase shadow-lg">
            {t('memoryUpdated')}
          </div>
        </div>
      )}

      {/* Transcript area */}
      <div className="mb-4 min-h-0 flex-1 space-y-3 overflow-y-auto px-2">
        {transcript.length === 0 && !streamingText && status === 'live' && (
          <p className="text-fl-label text-fl-muted-4 py-8 text-center font-mono">
            {t('tapToStart')}
          </p>
        )}
        {(() => {
          const lastUserIdx = transcript.reduce(
            (acc, e, j) => (e.role === 'user' ? j : acc),
            -1
          )
          return transcript.map((entry, i) => (
            <TranscriptBubble
              key={entry.id}
              role={entry.role}
              text={entry.text}
              speaking={
                entry.role === 'user' && userSpeaking && i === lastUserIdx
              }
              userAvatar={user?.avatar}
              userInitial={(user?.displayName || user?.username || '?')[0]}
              languageCode={targetLanguage}
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
            languageCode={targetLanguage}
          />
        )}
        <div ref={transcriptEndRef} />
      </div>

      {/* Status message */}
      {status === 'error' && errorMsg && (
        <div className="border-fl-error/40 bg-fl-surface text-fl-error mb-4 border px-4 py-3 font-mono text-xs">
          ✕ {errorMsg}
        </div>
      )}
      {status === 'ended' && (
        <div className="border-fl-border bg-fl-surface text-fl-muted-2 mb-4 border px-4 py-3 font-mono text-xs">
          {t('sessionEnded')}
        </div>
      )}
      {trialMode && status === 'ended' && <TrialPremiumCta />}

      {/* Conversation starters — shown when idle, hidden as soon as session starts */}
      {!trialMode &&
        !sessionActive &&
        (status === 'ready' || status === 'ended' || status === 'error') && (
          <div className="mb-4">
            <p className="text-fl-hint text-fl-muted-3 mb-3 text-center font-mono tracking-widest uppercase">
              {t('startersHint')}
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {visibleStarters.map((topic) => (
                <button
                  key={topic}
                  onClick={() =>
                    void handleStart([
                      {
                        role: 'user',
                        content: `I'd like to practice English by talking about ${topic}.`,
                      },
                    ])
                  }
                  className="text-fl-muted-1 border-fl-border hover:border-fl-border-2 hover:text-fl-fg border px-3 py-2 font-mono text-xs tracking-wide transition-colors"
                >
                  {topic}
                </button>
              ))}
            </div>
          </div>
        )}

      {/* Controls */}
      <div className="flex flex-col items-center gap-4 pb-2">
        {/* Timeout warning */}
        {warningSeconds !== null && (
          <div className="w-full">
            <SessionTimeoutBanner seconds={warningSeconds} />
          </div>
        )}
        {/* Quota pill — freemium gets a simplified voice counter, premium gets full quota bars */}
        {freemiumVoiceRemaining != null && freemiumVoiceLimit != null ? (
          <span
            className={`text-fl-label font-mono tracking-widest uppercase ${freemiumVoiceRemaining <= 0 ? 'text-red-500' : 'text-fl-muted-2'}`}
          >
            {t('freemiumVoiceRemaining', {
              remaining: freemiumVoiceRemaining,
              limit: freemiumVoiceLimit,
            })}
          </span>
        ) : quota && !trialMode ? (
          <QuotaPill quota={quota} t={t} />
        ) : null}
        <StatusIndicator
          status={status}
          userSpeaking={userSpeaking}
          assistantSpeaking={assistantSpeaking}
        />
        {!(trialMode && status === 'ended') && (
          <MicButton
            status={status}
            sessionActive={sessionActive}
            onStart={handleStart}
            onStop={handleStop}
          />
        )}
      </div>
      <ReviewPrompt
        open={reviewPromptOpen}
        onClose={() => setReviewPromptOpen(false)}
        onSubmitted={() => setReviewPromptOpen(false)}
      />
    </div>
  )
}
