'use client'

import {
  Globe,
  Target,
  Compass,
  MessageSquare,
  TrendingUp,
  ArrowRight,
  Sparkles,
  BrainCircuit,
  BriefcaseBusiness,
  Plane,
  Trophy,
  FileText,
} from 'lucide-react'

interface LearningExperienceProps {
  t: (key: string) => string
}

export function LearningExperience({ t }: LearningExperienceProps) {
  const steps = [
    { num: '01', title: t('step1Title'), desc: t('step1Desc'), icon: Globe },
    { num: '02', title: t('step2Title'), desc: t('step2Desc'), icon: Target },
    { num: '03', title: t('step3Title'), desc: t('step3Desc'), icon: Compass },
    { num: '04', title: t('step4Title'), desc: t('step4Desc'), icon: MessageSquare },
    { num: '05', title: t('step5Title'), desc: t('step5Desc'), icon: TrendingUp },
  ]

  const scenarios = [
    { icon: Plane, label: 'Travel', desc: 'Airport, hotel & real-world conversations' },
    { icon: BriefcaseBusiness, label: 'Business', desc: 'Meetings, interviews & workplace English' },
    { icon: MessageSquare, label: 'Daily Life', desc: 'Natural conversations for everyday life' },
    { icon: Trophy, label: 'Exams', desc: 'Focused practice for CEFR & language exams' },
  ]

  const intelligence = [
    { icon: BrainCircuit, title: 'Adaptive AI Coach', desc: 'Your next activity changes with your progress, mistakes and goals.' },
    { icon: FileText, title: 'Learn From Anything', desc: 'Turn text, notes or imported content into lessons, vocabulary and quizzes.' },
    { icon: Trophy, title: 'Weekly Missions', desc: 'Small challenges create momentum without turning learning into a chore.' },
  ]

  return (
    <section className="py-20 sm:py-24 bg-neutral-50/50 dark:bg-neutral-900/40 border-y border-neutral-200/60 dark:border-neutral-800/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-14">
          <span className="text-amber-600 dark:text-amber-400 font-bold text-xs tracking-widest uppercase mb-2 block">
            THE METHODOLOGY
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
            {t('experienceTitle')}
          </h2>
          <p className="mt-4 text-base sm:text-lg text-neutral-600 dark:text-neutral-400">
            {t('experienceSubtitle')}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 relative">
          {steps.map((step, idx) => {
            const Icon = step.icon
            return (
              <div key={step.num} className="juba-card p-6 flex flex-col justify-between relative group">
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <span className="text-2xl font-extrabold text-amber-500/40 dark:text-amber-400/30 group-hover:text-amber-500 transition-colors">
                      {step.num}
                    </span>
                    <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                      <Icon className="w-5 h-5" />
                    </div>
                  </div>
                  <h3 className="font-bold text-base text-neutral-900 dark:text-white mb-2">{step.title}</h3>
                  <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">{step.desc}</p>
                </div>
                {idx < steps.length - 1 && (
                  <div className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-neutral-300 dark:text-neutral-700">
                    <ArrowRight className="w-5 h-5" />
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 juba-card p-7 sm:p-9 bg-white dark:bg-neutral-950 overflow-hidden relative">
            <div className="absolute -top-20 -right-20 h-56 w-56 rounded-full bg-amber-400/10 blur-3xl" />
            <div className="relative">
              <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs font-bold uppercase tracking-widest mb-4">
                <Sparkles className="w-4 h-4" /> Real-world practice
              </div>
              <h3 className="text-2xl sm:text-3xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
                Practice the language you actually need.
              </h3>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
                Choose a situation, speak naturally with JUBA AI, receive instant feedback and repeat the scenario until it feels effortless.
              </p>

              <div className="mt-7 grid grid-cols-2 gap-3">
                {scenarios.map(({ icon: Icon, label, desc }) => (
                  <div key={label} className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50/80 dark:bg-neutral-900/70 p-4 transition-transform hover:-translate-y-0.5">
                    <Icon className="w-5 h-5 text-amber-500 mb-3" />
                    <p className="font-bold text-sm text-neutral-900 dark:text-white">{label}</p>
                    <p className="mt-1 text-[11px] leading-relaxed text-neutral-500 dark:text-neutral-400">{desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-5 space-y-3">
            {intelligence.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="juba-card p-5 bg-white dark:bg-neutral-950 flex gap-4 items-start group">
                <div className="shrink-0 w-11 h-11 rounded-2xl bg-neutral-100 dark:bg-neutral-900 flex items-center justify-center text-amber-500 group-hover:bg-amber-500 group-hover:text-neutral-950 transition-colors">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-neutral-900 dark:text-white">{title}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-neutral-500 dark:text-neutral-400">{desc}</p>
                </div>
              </div>
            ))}
            <div className="rounded-2xl bg-neutral-900 dark:bg-white p-5 text-white dark:text-neutral-950 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-extrabold">Your learning, not a generic course.</p>
                <p className="mt-1 text-[11px] text-neutral-400 dark:text-neutral-600">Personalized from day one.</p>
              </div>
              <Sparkles className="w-6 h-6 shrink-0 text-amber-400 dark:text-amber-600" />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
