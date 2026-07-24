/**
 * /conversation — Voice conversation page.
 *
 * ConversationMode uses @ricky0123/vad-react (ONNX/WASM) and the Web Audio
 * API, neither of which are compatible with SSR. It is loaded client-side only
 * via `dynamic({ ssr: false })`.
 */
'use client'

import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import type { ChatContextItem } from '@/lib/conversation-ws'
import { PageLoading } from '@/components/ui/page-loading'
import { FreemiumQuotaBanner } from '@/components/billing/FreemiumQuotaBanner'
import { PaywallBanner } from '@/components/billing/PaywallBanner'
import { MaintenanceGate } from '@/components/billing/MaintenanceBanner'
import { apiFetch } from '@/lib/api'
import { useLanguageStore } from '@/store/language'
import { useConfigStore } from '@/store/config'
import { useAuthStore, isSubscribed, isFreemiumTrialActive } from '@/store/auth'
import { useFreemiumStore } from '@/store/freemium'

function ConversationLoading() {
  return <PageLoading minHeight="min-h-[calc(100vh-56px)] md:min-h-screen" />
}

const ConversationMode = dynamic(
  () => import('@/components/conversation/ConversationMode'),
  {
    ssr: false,
    loading: ConversationLoading,
  }
)

export default function ConversationPage() {
  const activeLanguage = useLanguageStore((s) => s.activeLanguage)
  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const user = useAuthStore((s) => s.user)
  const fetchFreemium = useFreemiumStore((s) => s.fetchStatus)
  const freemiumStatus = useFreemiumStore((s) => s.status)
  const freemiumExhausted =
    stripeEnabled &&
    !isSubscribed(user, stripeEnabled) &&
    !isFreemiumTrialActive(user, stripeEnabled) &&
    freemiumStatus &&
    freemiumStatus.voice_remaining_seconds <= 0

  const freemiumVoiceRemaining = freemiumStatus
    ? Math.ceil(freemiumStatus.voice_remaining_seconds / 60)
    : undefined
  const freemiumVoiceLimit = freemiumStatus
    ? Math.ceil(freemiumStatus.voice_limit_seconds / 60)
    : undefined
  const showFreemiumVoicePill =
    stripeEnabled &&
    !isSubscribed(user, stripeEnabled) &&
    !isFreemiumTrialActive(user, stripeEnabled) &&
    freemiumStatus &&
    freemiumStatus.voice_limit_seconds > 0

  const [initialContext, setInitialContext] = useState<
    ChatContextItem[] | undefined
  >(undefined)
  const [autoStart, setAutoStart] = useState(false)
  const [cefrLevel, setCefrLevel] = useState<string | null>(null)
  const [planReady, setPlanReady] = useState(false)
  const [voiceTrial, setVoiceTrial] = useState<{
    token: string
    durationSeconds: number
    cefrLevel?: string
    targetLanguage?: string
  } | null>(null)

  useEffect(() => {
    if (stripeEnabled && !isSubscribed(user, stripeEnabled)) {
      fetchFreemium()
    }
  }, [stripeEnabled, user, fetchFreemium])

  useEffect(() => {
    const raw = sessionStorage.getItem('voice_context')
    if (raw) {
      sessionStorage.removeItem('voice_context')
      try {
        const parsed = JSON.parse(raw) as unknown
        if (
          typeof parsed === 'object' &&
          parsed !== null &&
          'messages' in (parsed as Record<string, unknown>)
        ) {
          const pkg = parsed as { messages: unknown }
          if (Array.isArray(pkg.messages)) {
            setInitialContext(pkg.messages as ChatContextItem[])
          }
          setAutoStart(true)
        } else if (Array.isArray(parsed)) {
          setInitialContext(parsed as ChatContextItem[])
          setAutoStart(true)
        }
      } catch {
        // malformed — ignore
      }
    }
    const trialRaw = sessionStorage.getItem('assessment_voice_trial')
    if (trialRaw) {
      sessionStorage.removeItem('assessment_voice_trial')
      try {
        const parsed = JSON.parse(trialRaw) as {
          token?: unknown
          durationSeconds?: unknown
          cefrLevel?: unknown
          targetLanguage?: unknown
        }
        if (typeof parsed.token === 'string' && parsed.token.length > 0) {
          setVoiceTrial({
            token: parsed.token,
            durationSeconds:
              typeof parsed.durationSeconds === 'number'
                ? parsed.durationSeconds
                : 300,
            cefrLevel:
              typeof parsed.cefrLevel === 'string'
                ? parsed.cefrLevel
                : undefined,
            targetLanguage:
              typeof parsed.targetLanguage === 'string'
                ? parsed.targetLanguage
                : undefined,
          })
          setInitialContext([
            {
              role: 'user',
              content:
                'I just completed the placement assessment. Please start a short, friendly voice conversation adapted to my level.',
            },
          ])
          setAutoStart(true)
        }
      } catch {
        // malformed — ignore
      }
    }
    setPlanReady(false)
    apiFetch('/api/study-plan/today')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.cefr_level) setCefrLevel(data.cefr_level)
      })
      .catch(() => {
        /* sin plan — usa default 1500ms */
      })
      .finally(() => setPlanReady(true))
  }, [activeLanguage?.code])

  if (!planReady) return null

  return (
    <MaintenanceGate>
      {voiceTrial ? (
        <ConversationMode
          initialContext={initialContext}
          autoStart={autoStart}
          cefrLevel={voiceTrial.cefrLevel ?? cefrLevel}
          targetLanguage={voiceTrial.targetLanguage ?? activeLanguage?.code}
          voiceTrialToken={voiceTrial.token}
          voiceTrialDurationSeconds={voiceTrial.durationSeconds}
          trialMode
        />
      ) : freemiumExhausted ? (
        <>
          <FreemiumQuotaBanner feature="voice" className="mb-4" />
          <PaywallBanner feature="voice" compact />
        </>
      ) : (
        <ConversationMode
          initialContext={initialContext}
          autoStart={autoStart}
          cefrLevel={cefrLevel}
          targetLanguage={activeLanguage?.code}
          freemiumVoiceRemaining={
            showFreemiumVoicePill ? freemiumVoiceRemaining : undefined
          }
          freemiumVoiceLimit={
            showFreemiumVoicePill ? freemiumVoiceLimit : undefined
          }
        />
      )}
    </MaintenanceGate>
  )
}
