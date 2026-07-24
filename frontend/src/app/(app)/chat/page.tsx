'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { useTranslations } from 'next-intl'
import { apiFetch } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { useLanguageStore } from '@/store/language'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { AudioPlayer } from '@/components/ui/AudioPlayer'
import { MaintenanceGate } from '@/components/billing/MaintenanceBanner'
import { PaywallBanner } from '@/components/billing/PaywallBanner'
import { FreemiumQuotaBanner } from '@/components/billing/FreemiumQuotaBanner'
import { useFreemiumStore } from '@/store/freemium'
import { useConfigStore } from '@/store/config'
import { isSubscribed, isFreemiumTrialActive } from '@/store/auth'
import { WordTooltip, useWordSave } from '@/components/ui/WordTooltip'
import { PageLoading } from '@/components/ui/page-loading'
import { TargetLanguageText } from '@/components/TargetLanguageText'
import { AuthAvatarImage } from '@/components/AuthAvatarImage'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Conversation {
  id: number
  title: string
  source: string
  created_at: string
  updated_at: string
}

export default function ChatPage() {
  const t = useTranslations('chat')
  const tCommon = useTranslations('common')
  const tLang = useTranslations('targetLanguages')
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const activeLanguage = useLanguageStore((s) => s.activeLanguage)
  const {
    selectedWord,
    tooltipPos,
    saveState,
    handleTextSelection,
    handleSaveWord,
    dismissTooltip,
  } = useWordSave()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sendingWarn, setSendingWarn] = useState(false)
  const sendingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [error, setError] = useState('')
  const [loadingConvs, setLoadingConvs] = useState(true)
  const [convLoadError, setConvLoadError] = useState(false)
  const [loadingMsgs, setLoadingMsgs] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [deletePending, setDeletePending] = useState<number | null>(null)
  const [memoryToast, setMemoryToast] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const targetLanguageCode = activeLanguage?.code ?? 'en-GB'

  const stripeEnabled = useConfigStore((s) => s.stripeEnabled)
  const freemiumStatus = useFreemiumStore((s) => s.status)
  const fetchFreemium = useFreemiumStore((s) => s.fetchStatus)
  const decrementFreemium = useFreemiumStore((s) => s.decrement)
  const freemiumExhausted =
    stripeEnabled &&
    !isSubscribed(user, stripeEnabled) &&
    !isFreemiumTrialActive(user, stripeEnabled) &&
    freemiumStatus &&
    freemiumStatus.chat_remaining <= 0

  useEffect(() => {
    if (stripeEnabled && !isSubscribed(user, stripeEnabled)) {
      fetchFreemium()
    }
  }, [stripeEnabled, user, fetchFreemium])

  const scrollBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollBottom()
  }, [messages, scrollBottom])

  // Open sidebar by default only on desktop
  useEffect(() => {
    setSidebarOpen(window.innerWidth >= 768)
  }, [])

  // Warn if LLM takes longer than 60 s
  useEffect(() => {
    if (sending) {
      setSendingWarn(false)
      sendingTimerRef.current = setTimeout(() => setSendingWarn(true), 60_000)
    } else {
      if (sendingTimerRef.current) clearTimeout(sendingTimerRef.current)
      setSendingWarn(false)
    }
    return () => {
      if (sendingTimerRef.current) clearTimeout(sendingTimerRef.current)
    }
  }, [sending])

  const loadConversations = useCallback(async () => {
    try {
      const res = await apiFetch('/api/chat/conversations')
      if (res.ok) {
        const data: Conversation[] = await res.json()
        setConversations(data)
        return data
      }
    } catch {
      /* ignore */
    }
    return null
  }, [])

  // Load conversations on mount, auto-select the most recent
  useEffect(() => {
    async function init() {
      setConvLoadError(false)
      setLoadingConvs(true)
      const data = await loadConversations()
      if (data === null) {
        setConvLoadError(true)
        setLoadingConvs(false)
        return
      }
      if (data.length > 0) {
        selectConversation(data[0].id)
      } else {
        setActiveId(null)
        setMessages([])
      }
      setLoadingConvs(false)
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLanguage?.code])

  async function selectConversation(id: number) {
    dismissTooltip()
    setActiveId(id)
    setMessages([])
    setError('')
    setLoadingMsgs(true)
    try {
      const res = await apiFetch(`/api/chat/conversations/${id}/messages`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data.messages || [])
      }
    } catch {
      /* ignore */
    } finally {
      setLoadingMsgs(false)
    }
  }

  async function newChat() {
    // Don't create — let the first message auto-create the conversation
    dismissTooltip()
    setActiveId(null)
    setMessages([])
    setError('')
    inputRef.current?.focus()
  }

  function continueInVoice() {
    const context = messages
      .filter((m) => m.content.trim().length > 0)
      .slice(-20)
    // Only pass the message context — no conversation_id.
    // The voice session will create its own new conversation record so the
    // original text chat stays clean and the two appear as separate entries
    // in the sidebar (the voice one gets the 🎤 icon).
    sessionStorage.setItem(
      'voice_context',
      JSON.stringify({
        messages: context,
      })
    )
    router.push('/conversation')
  }

  async function deleteConversation(id: number) {
    await apiFetch(`/api/chat/conversations/${id}`, { method: 'DELETE' })
    setDeletePending(null)
    const updated = await loadConversations()
    if (updated === null) {
      setConvLoadError(true)
      return
    }
    if (activeId === id) {
      if (updated.length > 0) {
        selectConversation(updated[0].id)
      } else {
        setActiveId(null)
        setMessages([])
      }
    }
  }

  async function sendMessage() {
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
    setError('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setSending(true)

    try {
      const res = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: activeId }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Error ${res.status}`)
      }

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let assistantContent = ''
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.conversation_id && !activeId) {
              setActiveId(data.conversation_id)
              // Refresh sidebar with the new conversation
              loadConversations().then((list) => list && setConversations(list))
            }
            if (data.token) {
              assistantContent += data.token
              setMessages((prev) => {
                const copy = [...prev]
                copy[copy.length - 1] = {
                  role: 'assistant',
                  content: assistantContent,
                }
                return copy
              })
            }
            if (data.error) setError(data.error)
            if (data.done) {
              if (
                !isSubscribed(user, stripeEnabled) &&
                !isFreemiumTrialActive(user, stripeEnabled)
              ) {
                decrementFreemium('chat_remaining')
              }
              loadConversations().then((list) => list && setConversations(list))
            }
            if (data.memory_updated) {
              setMemoryToast(true)
              setTimeout(() => setMemoryToast(false), 3500)
            }
          } catch {
            /* skip malformed */
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorMessage'))
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  return (
    <MaintenanceGate>
      <div className="flex h-full min-h-0 w-full overflow-hidden">
        {/* Memory updated toast */}
        {memoryToast && (
          <div className="pointer-events-none fixed inset-x-0 top-16 z-50 flex justify-center">
            <div className="border-fl-border bg-fl-surface text-fl-muted-1 animate-in fade-in slide-in-from-top-2 pointer-events-auto border px-4 py-2 font-mono text-xs tracking-widest uppercase shadow-lg">
              {t('memoryUpdated')}
            </div>
          </div>
        )}
        {/* Sidebar backdrop — mobile only */}
        {sidebarOpen && (
          <div
            className="fixed inset-x-0 top-14 bottom-0 z-10 bg-black/40 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="border-fl-border bg-fl-bg fixed top-14 bottom-0 left-0 z-20 flex w-56 shrink-0 flex-col overflow-hidden border-r md:relative md:top-auto md:bottom-auto md:left-auto md:z-auto">
            <div className="border-fl-border flex items-center justify-between border-b px-4 py-3">
              <span className="text-fl-hint text-fl-muted-2 font-mono tracking-widest uppercase">
                {t('conversations')}
              </span>
              <button
                onClick={newChat}
                className="text-fl-label text-fl-muted-1 hover:text-fl-fg font-mono tracking-widest uppercase transition-colors"
                title={t('newConversation')}
              >
                + {t('newConversation')}
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loadingConvs ? (
                <PageLoading fullScreen={false} className="block px-4 py-4" />
              ) : convLoadError ? (
                <div className="flex flex-col items-center gap-3 px-4 py-6">
                  <p className="text-fl-error font-mono text-xs">
                    {tCommon('error')}
                  </p>
                  <button
                    onClick={() => {
                      setConvLoadError(false)
                      setLoadingConvs(true)
                      loadConversations()
                        .then((data) => {
                          if (data === null) {
                            setConvLoadError(true)
                          } else if (data.length > 0) {
                            selectConversation(data[0].id)
                          }
                        })
                        .finally(() => setLoadingConvs(false))
                    }}
                    className="border-fl-border text-fl-label text-fl-muted-1 hover:text-fl-fg hover:border-fl-border-2 border px-4 py-2 font-mono tracking-widest uppercase transition-colors"
                  >
                    {tCommon('retry')}
                  </button>
                </div>
              ) : conversations.length === 0 ? (
                <p className="text-fl-label text-fl-muted-4 px-4 py-4 font-mono">
                  {t('noConversation')}
                </p>
              ) : (
                conversations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => selectConversation(c.id)}
                    className={`group border-fl-surface-2 flex cursor-pointer items-center justify-between border-b px-4 py-3 transition-colors ${
                      activeId === c.id
                        ? 'bg-fl-surface-2 border-l-fl-fg border-l-2'
                        : 'hover:bg-fl-surface border-l-2 border-l-transparent'
                    }`}
                  >
                    <span
                      className={`text-fl-label truncate pr-1 font-mono leading-tight ${activeId === c.id ? 'text-fl-fg' : 'text-fl-muted-1'}`}
                    >
                      {c.source === 'voice' && (
                        <span
                          className="text-fl-muted-3 mr-1.5"
                          title="Voice session"
                        >
                          🎤
                        </span>
                      )}
                      {c.title}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeletePending(c.id)
                      }}
                      className="text-fl-label text-fl-error-fg hover:text-fl-error shrink-0 font-mono opacity-0 transition-all group-hover:opacity-100"
                      title="Delete"
                    >
                      ✕
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>
        )}

        {/* Main chat area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Header */}
          <div className="border-fl-border bg-fl-bg flex shrink-0 items-center gap-2 border-b px-5 py-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-fl-label text-fl-muted-2 hover:text-fl-fg mr-1 font-mono tracking-widest transition-colors"
              title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
            >
              {sidebarOpen ? '◂' : '▸'}
            </button>
            <span className="text-fl-label text-fl-muted-3">●</span>
            <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
              {activeId
                ? (conversations.find((c) => c.id === activeId)?.title ??
                  t('title'))
                : t('newConversation')}
            </span>
            {sending ? (
              <div className="ml-auto flex flex-col items-end gap-0.5">
                <span className="text-fl-hint text-fl-muted-3 animate-pulse font-mono tracking-widest uppercase">
                  {t('thinking')}
                </span>
                {sendingWarn && (
                  <span className="text-fl-hint font-mono tracking-widest text-amber-500 uppercase">
                    {t('takingLonger')}
                  </span>
                )}
              </div>
            ) : messages.length > 0 ? (
              <button
                onClick={continueInVoice}
                className="text-fl-hint text-fl-muted-2 hover:text-fl-fg ml-auto font-mono tracking-widest uppercase transition-colors"
              >
                {t('continueInVoice')}
              </button>
            ) : null}
          </div>

          <FreemiumQuotaBanner feature="chat" />

          {/* Messages */}
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4">
            {loadingMsgs ? (
              <div className="flex h-full items-center justify-center">
                <PageLoading fullScreen={false} />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <p className="text-fl-label text-fl-muted-3 font-mono tracking-widest uppercase">
                  {t('title')}
                </p>
                <p className="text-fl-muted-2 max-w-xs font-mono text-xs leading-relaxed">
                  {t('subtitle', {
                    language: activeLanguage
                      ? tLang(activeLanguage.code)
                      : tLang('en-GB'),
                  })}
                </p>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex items-end gap-2 ${msg.role === 'user' ? 'ml-auto max-w-[75%] flex-row-reverse' : 'flex-row'}`}
                >
                  {/* Avatar */}
                  <div className="border-fl-border mb-0.5 h-7 w-7 flex-shrink-0 overflow-hidden rounded-full border">
                    {msg.role === 'assistant' ? (
                      <Image
                        src="/logo_head.png"
                        alt="Tutor"
                        width={28}
                        height={28}
                        className="h-full w-full object-cover"
                      />
                    ) : user?.avatar ? (
                      <AuthAvatarImage
                        avatar={user.avatar}
                        alt=""
                        width={28}
                        height={28}
                        className="h-full w-full object-cover"
                        fallback={
                          <div className="bg-fl-surface-2 flex h-full w-full items-center justify-center">
                            <span className="text-fl-hint text-fl-muted-1 font-mono select-none">
                              {(user?.displayName ||
                                user?.username ||
                                '?')[0].toUpperCase()}
                            </span>
                          </div>
                        }
                      />
                    ) : (
                      <div className="bg-fl-surface-2 flex h-full w-full items-center justify-center">
                        <span className="text-fl-hint text-fl-muted-1 font-mono select-none">
                          {(user?.displayName ||
                            user?.username ||
                            '?')[0].toUpperCase()}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className={`max-w-[75%] min-w-[10rem] text-left`}>
                    <TargetLanguageText
                      as="div"
                      languageCode={targetLanguageCode}
                      className={`word-selectable border px-4 py-3 text-left ${
                        msg.role === 'user'
                          ? 'bg-fl-accent text-fl-accent-fg border-fl-accent'
                          : 'bg-fl-surface text-fl-fg-2 border-fl-border'
                      }`}
                      onPointerUp={
                        msg.role === 'assistant'
                          ? () => handleTextSelection(msg.content)
                          : undefined
                      }
                    >
                      {msg.content ||
                        (sending && i === messages.length - 1 ? (
                          <span className="text-fl-muted-2 animate-pulse">
                            ▌
                          </span>
                        ) : null)}
                    </TargetLanguageText>
                    {msg.role === 'assistant' &&
                      msg.content &&
                      !(sending && i === messages.length - 1) && (
                        <div className="mt-1">
                          <AudioPlayer text={msg.content} size="sm" />
                        </div>
                      )}
                  </div>
                </div>
              ))
            )}
            {error && (
              <div className="text-fl-label text-fl-error-fg border-fl-error/30 border px-4 py-2 font-mono">
                ✕{' '}
                {error === 'No active study plan found'
                  ? tCommon('noActivePlan')
                  : t('errorMessage')}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-fl-border bg-fl-bg shrink-0 border-t px-4 py-4">
            {freemiumExhausted ? (
              <PaywallBanner feature="chat" compact />
            ) : (
              <>
                <div className="flex gap-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) =>
                      e.key === 'Enter' && !e.shiftKey && sendMessage()
                    }
                    disabled={sending || loadingMsgs}
                    placeholder={t('placeholder')}
                    className="bg-fl-surface border-fl-border text-fl-fg placeholder:text-fl-border-2 focus:border-fl-border-2 flex-1 border px-4 py-3 font-mono text-sm transition-colors focus:outline-none disabled:opacity-40"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={sending || !input.trim() || loadingMsgs}
                    className="bg-fl-accent text-fl-accent-fg text-fl-label hover:bg-fl-accent/90 px-5 font-mono font-bold tracking-widest uppercase transition-colors disabled:opacity-30"
                  >
                    {sending ? '...' : t('send')}
                  </button>
                </div>
                <p className="text-fl-hint text-fl-border-2 mt-2 font-mono tracking-wide">
                  {t('enterToSend')}
                </p>
              </>
            )}
          </div>
        </div>

        <ConfirmDialog
          open={deletePending !== null}
          title={t('deleteTitle')}
          message={t('deleteMessage')}
          confirmLabel={t('deleteConfirm')}
          danger
          onConfirm={() =>
            deletePending !== null && deleteConversation(deletePending)
          }
          onCancel={() => setDeletePending(null)}
        />

        {/* Word-save tooltip */}
        {selectedWord && (
          <WordTooltip
            word={selectedWord}
            pos={tooltipPos}
            saveState={saveState}
            onSave={() => handleSaveWord()}
            onDismiss={dismissTooltip}
            labels={{
              saveWord: tCommon('saveWord'),
              wordSaved: tCommon('wordSaved'),
              wordSaveError: tCommon('wordSaveError'),
            }}
          />
        )}
      </div>
    </MaintenanceGate>
  )
}
