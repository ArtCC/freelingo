'use client'

import {
  BookOpen,
  MessageSquare,
  Mic,
  Headphones,
  Layers,
  TrendingUp,
  Sparkles,
  Zap,
} from 'lucide-react'

interface BentoFeaturesProps {
  t: (key: string) => string
}

export function BentoFeatures({ t }: BentoFeaturesProps) {
  return (
    <section id="features" className="scroll-mt-24 py-20 bg-neutral-50/50 dark:bg-neutral-900/30">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold text-xs tracking-wider uppercase mb-3">
            <Sparkles className="h-3.5 w-3.5" />
            Comprehensive Platform
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
            {t('bentoTitle')}
          </h2>
          <p className="mt-4 text-base sm:text-lg text-neutral-600 dark:text-neutral-400">
            {t('bentoSubtitle')}
          </p>
        </div>

        {/* Asymmetric Bento Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {/* Card 1: AI Tutor (Large Span 2) */}
          <div className="juba-card md:col-span-2 p-8 flex flex-col justify-between relative overflow-hidden group bg-gradient-to-br from-amber-500/5 via-white to-orange-500/5 dark:from-amber-950/20 dark:via-neutral-900 dark:to-neutral-900">
            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
              <MessageSquare className="w-32 h-32 text-amber-500" />
            </div>
            <div>
              <div className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-6">
                <MessageSquare className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-neutral-900 dark:text-white mb-3">
                {t('feature2Title')}
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400 text-sm leading-relaxed max-w-md">
                {t('feature2Desc')}
              </p>
            </div>
            <div className="mt-8 pt-4 border-t border-neutral-100 dark:border-neutral-800 flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
              <Zap className="w-4 h-4" /> Real-time intelligent corrections
            </div>
          </div>

          {/* Card 2: Voice Conversation */}
          <div className="juba-card p-6 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-4">
                <Mic className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-neutral-900 dark:text-white mb-2">
                {t('feature3Title')}
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400 text-xs leading-relaxed">
                {t('feature3Desc')}
              </p>
            </div>
          </div>

          {/* Card 3: Learning Plan */}
          <div className="juba-card p-6 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-4">
                <BookOpen className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-neutral-900 dark:text-white mb-2">
                {t('feature1Title')}
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400 text-xs leading-relaxed">
                {t('feature1Desc')}
              </p>
            </div>
          </div>

          {/* Card 4: Listening */}
          <div className="juba-card p-6 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center mb-4">
                <Headphones className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-neutral-900 dark:text-white mb-2">
                {t('feature4Title')}
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400 text-xs leading-relaxed">
                {t('feature4Desc')}
              </p>
            </div>
          </div>

          {/* Card 5: Smart Flashcards */}
          <div className="juba-card p-6 flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-4">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-neutral-900 dark:text-white mb-2">
                {t('feature6Title')}
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400 text-xs leading-relaxed">
                {t('feature6Desc')}
              </p>
            </div>
          </div>

          {/* Card 6: Progress & Analytics (Span 2) */}
          <div className="juba-card md:col-span-2 p-8 flex flex-col justify-between relative overflow-hidden bg-gradient-to-tr from-white via-neutral-50 to-blue-50/20 dark:from-neutral-900 dark:to-neutral-900">
            <div>
              <div className="w-12 h-12 rounded-2xl bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center mb-6">
                <TrendingUp className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-neutral-900 dark:text-white mb-3">
                {t('feature8Title')}
              </h3>
              <p className="text-neutral-600 dark:text-neutral-400 text-sm leading-relaxed max-w-md">
                {t('feature8Desc')}
              </p>
            </div>
            <div className="mt-6 flex items-center gap-4 text-xs font-semibold text-neutral-500">
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500"></span> Streak tracker</div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500"></span> CEFR scores</div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500"></span> XP milestone</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
