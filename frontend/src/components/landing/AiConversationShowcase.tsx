'use client'

import { Mic, Volume2, Sparkles, User, Bot, Circle } from 'lucide-react'

interface AiConversationShowcaseProps {
  t: (key: string) => string
}

export function AiConversationShowcase({ t }: AiConversationShowcaseProps) {
  return (
    <section id="demo" className="scroll-mt-24 py-20 bg-neutral-900 text-white relative overflow-hidden">
      {/* Background radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/20 text-amber-400 font-semibold text-xs tracking-wider uppercase mb-3">
            <Sparkles className="h-3.5 w-3.5" />
            Live Interactive AI Demo
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            {t('showcaseTitle')}
          </h2>
          <p className="mt-4 text-base sm:text-lg text-neutral-400">
            {t('showcaseSubtitle')}
          </p>
        </div>

        {/* AI Conversation Mockup Window */}
        <div className="max-w-3xl mx-auto rounded-3xl bg-neutral-950/80 border border-neutral-800 shadow-2xl overflow-hidden backdrop-blur-xl">
          {/* Header Bar */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-900/50">
            <div className="flex items-center gap-3">
              <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 text-white font-bold">
                <Bot className="w-5 h-5" />
                <span className="absolute -bottom-0.5 -right-0.5 flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="font-bold text-sm text-white">JUBA AI Tutor</h4>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                    B2 CEFR Level
                  </span>
                </div>
                <p className="text-xs text-neutral-400 flex items-center gap-1.5 mt-0.5">
                  <Circle className="w-2 h-2 fill-emerald-500 text-emerald-500 animate-pulse" />
                  {t('showcaseSpeaking')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-flex text-xs px-3 py-1 rounded-full bg-neutral-800 text-neutral-300 font-medium border border-neutral-700">
                {t('showcaseMicActive')}
              </span>
            </div>
          </div>

          {/* Chat Body */}
          <div className="p-6 sm:p-8 space-y-6">
            {/* User Message */}
            <div className="flex items-start gap-3 justify-end">
              <div className="max-w-md bg-amber-500 text-neutral-950 rounded-2xl rounded-tr-none px-5 py-3.5 shadow-lg">
                <p className="text-sm font-medium">
                  "{t('showcaseUserMsg')}"
                </p>
              </div>
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-neutral-800 text-neutral-300">
                <User className="w-4 h-4" />
              </div>
            </div>

            {/* AI Tutor Message */}
            <div className="flex items-start gap-3 justify-start">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 text-white shadow-md">
                <Bot className="w-4 h-4" />
              </div>
              <div className="max-w-md bg-neutral-900 border border-neutral-800 text-neutral-100 rounded-2xl rounded-tl-none px-5 py-4 shadow-lg space-y-3">
                <p className="text-sm leading-relaxed">
                  "{t('showcaseAiMsg')}"
                </p>

                {/* Simulated Audio Waveform */}
                <div className="flex items-center gap-3 pt-2 border-t border-neutral-800/80 text-xs text-amber-400">
                  <Volume2 className="w-4 h-4 shrink-0 animate-bounce" />
                  <div className="flex items-center gap-1 h-4 flex-1">
                    <span className="w-1 bg-amber-500 h-2 rounded-full animate-pulse"></span>
                    <span className="w-1 bg-amber-500 h-4 rounded-full animate-pulse delay-75"></span>
                    <span className="w-1 bg-amber-500 h-3 rounded-full animate-pulse delay-150"></span>
                    <span className="w-1 bg-amber-500 h-4 rounded-full animate-pulse delay-100"></span>
                    <span className="w-1 bg-amber-500 h-2 rounded-full animate-pulse"></span>
                    <span className="w-1 bg-amber-500 h-3 rounded-full animate-pulse delay-200"></span>
                  </div>
                  <span className="text-[10px] text-neutral-400 font-mono">00:04</span>
                </div>
              </div>
            </div>
          </div>

          {/* Simulated Input Bar */}
          <div className="p-4 sm:p-6 border-t border-neutral-800 bg-neutral-900/40 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 text-neutral-400 text-sm flex-1">
              <Mic className="w-5 h-5 text-amber-400 animate-pulse" />
              <span>Listening to your voice... (VAD enabled)</span>
            </div>
            <button className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-neutral-950 font-bold text-xs px-4 py-2.5 rounded-xl transition-all shadow-md">
              <Mic className="w-4 h-4" />
              Hold to speak
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
