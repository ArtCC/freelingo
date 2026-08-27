'use client'

import { Globe, Target, Compass, MessageSquare, TrendingUp, ArrowRight } from 'lucide-react'

interface LearningExperienceProps {
  t: (key: string) => string
}

export function LearningExperience({ t }: LearningExperienceProps) {
  const steps = [
    {
      num: '01',
      title: t('step1Title'),
      desc: t('step1Desc'),
      icon: Globe,
    },
    {
      num: '02',
      title: t('step2Title'),
      desc: t('step2Desc'),
      icon: Target,
    },
    {
      num: '03',
      title: t('step3Title'),
      desc: t('step3Desc'),
      icon: Compass,
    },
    {
      num: '04',
      title: t('step4Title'),
      desc: t('step4Desc'),
      icon: MessageSquare,
    },
    {
      num: '05',
      title: t('step5Title'),
      desc: t('step5Desc'),
      icon: TrendingUp,
    },
  ]

  return (
    <section className="py-20 bg-neutral-50/50 dark:bg-neutral-900/40 border-y border-neutral-200/60 dark:border-neutral-800/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
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

        {/* Timeline Grid */}
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
                  <h3 className="font-bold text-base text-neutral-900 dark:text-white mb-2">
                    {step.title}
                  </h3>
                  <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
                    {step.desc}
                  </p>
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
      </div>
    </section>
  )
}
