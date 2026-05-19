'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { apiFetch } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { useProgressStore } from '@/store/progress'
import OnboardingTour from '@/components/tour/OnboardingTour'
import WhatsNew from '@/components/whats-new/WhatsNew'

interface TodayLessonItem {
  id: number | null
  title: string
  lesson_type: string
  week: number
  day: number
  objectives: string[]
  estimated_minutes: number
}

export default function DashboardPage() {
  const t = useTranslations('dashboard')
  const tNav = useTranslations('nav')
  const tPlan = useTranslations('plan')
  const user = useAuthStore((s) => s.user)
  const { streak, xp, skills, todayLessons, completedToday, setProgress, setTodayLessons } =
    useProgressStore()
  const [loading, setLoading] = useState(true)
  const [hasPlan, setHasPlan] = useState(false)
  const [cefrLevel, setCefrLevel] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [progRes, planRes] = await Promise.all([
        apiFetch('/api/progress/summary'),
        apiFetch('/api/study-plan/today'),
      ])
      if (progRes.ok) {
        const prog = await progRes.json()
        setProgress({ streak: prog.current_streak ?? 0, xp: prog.total_xp ?? 0, skills: prog.skills ?? {} })
      }
      if (planRes.ok) {
        const plan = await planRes.json()
        setCefrLevel(plan.cefr_level ?? null)
        setTodayLessons(plan.lessons.map((l: TodayLessonItem) => ({
          id: l.id, title: l.title, lessonType: l.lesson_type,
          week: l.week, day: l.day, objectives: l.objectives || [],
          estimatedMinutes: l.estimated_minutes || 25,
        })))
        setHasPlan(plan.lessons.length > 0)
      }
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [setProgress, setTodayLessons])

  useEffect(() => { loadData() }, [loadData])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="font-mono text-xs tracking-widest text-fl-muted-2 uppercase animate-pulse">{t('loadingProgress')}</span>
      </div>
    )
  }

  const skillEntries = Object.entries(skills)

  return (
    <>
      <OnboardingTour />
      <WhatsNew />
      <div className="p-6 max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8 pb-4 border-b border-fl-border">
          <p className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase mb-1">{t('welcomeBack')}</p>
          <h1 className="font-mono text-2xl font-bold tracking-tight text-fl-fg">
            {user?.displayName || user?.username}
          </h1>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-fl-border mb-8">
          {[
            { label: t('streak'), value: `${streak}d`, accent: streak > 0 },
            { label: t('xp'), value: xp, accent: false },
            { label: t('level'), value: cefrLevel ?? '—', accent: false },
            { label: t('skills'), value: skillEntries.length, accent: false },
          ].map((stat) => (
            <div key={stat.label} className="bg-fl-surface px-5 py-5">
              <p className="font-mono text-fl-hint tracking-widest text-fl-muted-2 uppercase mb-2">{stat.label}</p>
              <p className={`font-mono text-3xl font-bold tracking-tight ${stat.accent ? 'text-fl-accent' : 'text-fl-fg'}`}>{stat.value}</p>
            </div>
          ))}
        </div>

        <div className="grid sm:grid-cols-2 gap-px bg-fl-border mb-8">
          {/* Skills */}
          <div className="bg-fl-surface p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-fl-label text-fl-muted-2">●</span>
              <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">{t('skills')}</span>
            </div>
            {skillEntries.length > 0 ? (
              <div className="space-y-3">
                {skillEntries.map(([skill, value]) => (
                  <div key={skill}>
                    <div className="flex justify-between mb-1">
                      <span className="font-mono text-fl-label tracking-widest text-fl-muted-1 uppercase">{tPlan(`lessonTypes.${skill}`)}</span>
                      <span className="font-mono text-fl-label text-fl-muted-2">{Math.round((value as number) * 100)}%</span>
                    </div>
                    <div className="h-px bg-fl-border w-full">
                      <div className="h-px bg-fl-accent" style={{ width: `${(value as number) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="font-mono text-xs text-fl-muted-2">{t('noSkills')}</p>
            )}
          </div>

          {/* Today's lessons */}
          <div className="bg-fl-surface p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-fl-label text-fl-muted-2">●</span>
              <span className="font-mono text-fl-label tracking-widest text-fl-muted-2 uppercase">{t('today')}</span>
            </div>
            {todayLessons.length > 0 ? (
              <div className="space-y-2">
                {todayLessons.map((lesson, i) => (
                  <div key={i} className="flex items-center justify-between border border-fl-border px-4 py-3">
                    <div>
                      <p className="font-mono text-xs text-fl-fg">{lesson.title}</p>
                      <p className="font-mono text-fl-label text-fl-muted-2 uppercase tracking-wider mt-0.5">
                        {tPlan(`lessonTypes.${lesson.lessonType}`)} · {lesson.estimatedMinutes}min
                      </p>
                    </div>
                    {lesson.id && completedToday.includes(lesson.id) ? (
                      <span className="font-mono text-fl-label text-fl-muted-2 uppercase tracking-widest">✓ {t('lessonDone')}</span>
                    ) : lesson.id ? (
                      <Link href={`/lesson/${lesson.id}`}>
                        <button className="font-mono text-fl-label tracking-widest text-fl-bg bg-fl-fg px-3 py-1 uppercase hover:bg-fl-accent/90 transition-colors">
                          {t('startLesson')}
                        </button>
                      </Link>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="font-mono text-xs text-fl-muted-2">
                  {hasPlan ? t('allCaughtUp') : t('startWithAssessment')}
                </p>
                <Link href="/assessment">
                  <button className="font-mono text-fl-label tracking-widest text-fl-bg bg-fl-fg px-4 py-2 uppercase hover:bg-fl-accent/90 transition-colors">
                    {t('takeAssessmentArrow')}
                  </button>
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Quick actions */}
        <div className="flex gap-2 flex-wrap">
          {hasPlan && (
            <Link href="/plan">
              <button className="font-mono text-fl-label tracking-widest text-fl-bg bg-fl-fg px-4 py-2 uppercase hover:bg-fl-accent/90 transition-colors">
                {t('goToMyPlan')}
              </button>
            </Link>
          )}
          <Link href="/flashcards">
            <button className="font-mono text-fl-label tracking-widest text-fl-fg border border-fl-border px-4 py-2 uppercase hover:border-fl-border-2 transition-colors">
              {tNav('flashcards')}
            </button>
          </Link>
          <Link href="/chat">
            <button className="font-mono text-fl-label tracking-widest text-fl-fg border border-fl-border px-4 py-2 uppercase hover:border-fl-border-2 transition-colors">
              {tNav('tutor')}
            </button>
          </Link>
          <Link href="/assessment">
            <button className="font-mono text-fl-label tracking-widest text-fl-fg border border-fl-border px-4 py-2 uppercase hover:border-fl-border-2 transition-colors">
              {tNav('assessment')}
            </button>
          </Link>
        </div>
      </div>
    </>
  )
}
