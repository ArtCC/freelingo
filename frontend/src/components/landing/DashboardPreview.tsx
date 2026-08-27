'use client'

import { Flame, Award, BookOpen, Target, CheckCircle2, ArrowRight, Sparkles } from 'lucide-react'

interface DashboardPreviewProps {
  t: (key: string) => string
}

export function DashboardPreview({ t }: DashboardPreviewProps) {
  return (
    <section className="py-20 bg-neutral-900 text-white overflow-hidden relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/20 text-amber-400 font-semibold text-xs tracking-wider uppercase mb-3">
            <Sparkles className="h-3.5 w-3.5" />
            Intuitive Learning Hub
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            {t('dashboardPreviewTitle')}
          </h2>
          <p className="mt-4 text-base sm:text-lg text-neutral-400">
            {t('dashboardPreviewSubtitle')}
          </p>
        </div>

        {/* Mockup Dashboard Box */}
        <div className="max-w-5xl mx-auto rounded-3xl bg-neutral-950 border border-neutral-800 p-6 sm:p-8 shadow-2xl relative">
          {/* Top Metrics Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-orange-500/10 text-orange-400 flex items-center justify-center shrink-0">
                <Flame className="w-5 h-5 fill-orange-500" />
              </div>
              <div>
                <p className="text-xs text-neutral-400">{t('dashboardStreak')}</p>
                <p className="text-xl font-bold text-white">14 Days</p>
              </div>
            </div>

            <div className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
                <Award className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs text-neutral-400">{t('dashboardXp')}</p>
                <p className="text-xl font-bold text-white">2,450 XP</p>
              </div>
            </div>

            <div className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs text-neutral-400">{t('dashboardMasteredWords')}</p>
                <p className="text-xl font-bold text-white">420 Words</p>
              </div>
            </div>

            <div className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center shrink-0">
                <Target className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs text-neutral-400">{t('dashboardCurrentUnit')}</p>
                <p className="text-xl font-bold text-white">Unit 4 (B2)</p>
              </div>
            </div>
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Today's Practice Lessons */}
            <div className="lg:col-span-2 bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-6">
                <h4 className="font-bold text-base text-white flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                  Today's Practice Lessons
                </h4>
                <span className="text-xs text-amber-400 font-semibold bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
                  2 / 3 Completed
                </span>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-4 rounded-xl bg-neutral-900 border border-neutral-800">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <div>
                      <h5 className="text-sm font-semibold text-white">Business Vocabulary & Phrases</h5>
                      <p className="text-xs text-neutral-400">Mastered 15 new key expressions</p>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md">
                    +50 XP
                  </span>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl bg-neutral-900 border border-neutral-800">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <div>
                      <h5 className="text-sm font-semibold text-white">Advanced Conditional Sentences</h5>
                      <p className="text-xs text-neutral-400">Grammar exercise & quiz completed</p>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md">
                    +40 XP
                  </span>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl bg-neutral-900 border border-amber-500/40">
                  <div className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full border-2 border-amber-500 animate-pulse"></div>
                    <div>
                      <h5 className="text-sm font-semibold text-white">Interactive Voice Conversation</h5>
                      <p className="text-xs text-neutral-400">10 mins practice with JUBA AI Tutor</p>
                    </div>
                  </div>
                  <button className="flex items-center gap-1.5 text-xs font-bold text-neutral-950 bg-amber-500 hover:bg-amber-600 px-3 py-1.5 rounded-lg transition-colors">
                    Start <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Skill Level Radar / Breakdown */}
            <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 flex flex-col justify-between">
              <div>
                <h4 className="font-bold text-base text-white mb-6">Competency Levels</h4>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1.5">
                      <span className="text-neutral-300">Speaking & Voice</span>
                      <span className="text-amber-400">82%</span>
                    </div>
                    <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                      <div className="h-full bg-amber-500 rounded-full" style={{ width: '82%' }}></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1.5">
                      <span className="text-neutral-300">Listening Comprehension</span>
                      <span className="text-blue-400">90%</span>
                    </div>
                    <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: '90%' }}></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1.5">
                      <span className="text-neutral-300">Grammar Accuracy</span>
                      <span className="text-emerald-400">76%</span>
                    </div>
                    <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: '76%' }}></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1.5">
                      <span className="text-neutral-300">Vocabulary Retention</span>
                      <span className="text-purple-400">88%</span>
                    </div>
                    <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                      <div className="h-full bg-purple-500 rounded-full" style={{ width: '88%' }}></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-neutral-800 text-center">
                <p className="text-xs text-neutral-400">CEFR Level Placement: <strong className="text-amber-400">Upper Intermediate (B2)</strong></p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
