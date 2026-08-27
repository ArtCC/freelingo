'use client'

import Link from 'next/link'
import { Globe2, Trophy, Flame, Mic, BookOpen, Headphones, ArrowRight, LockKeyhole } from 'lucide-react'

const challenges = [
  { icon: Mic, title: 'Speak for 30 minutes', progress: 18, total: 30, xp: 500, text: 'Build real speaking confidence this week.' },
  { icon: BookOpen, title: 'Learn 50 useful words', progress: 32, total: 50, xp: 350, text: 'Expand the vocabulary you can actually use.' },
  { icon: Headphones, title: 'Complete 3 listening sessions', progress: 1, total: 3, xp: 300, text: 'Train your ear with authentic language.' },
]

export default function ChallengesPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 dark:bg-slate-950 dark:text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><span className="juba-eyebrow"><Globe2 className="h-3.5 w-3.5" /> Global challenge</span><h1 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">Turn practice into momentum.</h1><p className="mt-3 max-w-2xl text-slate-600 dark:text-slate-400">Weekly missions keep your learning consistent. Compete with yourself or join the global community.</p></div><div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"><Trophy className="h-5 w-5 text-amber-500" /><span className="text-sm font-bold">+1,150 XP available</span></div></div>

        <div className="mt-8 grid gap-4 lg:grid-cols-3">{challenges.map(({icon:Icon,title,progress,total,xp,text}) => <article key={title} className="juba-card p-6"><div className="flex items-center justify-between"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400"><Icon className="h-5 w-5" /></div><span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-extrabold text-amber-700 dark:text-amber-400">+{xp} XP</span></div><h2 className="mt-6 text-lg font-extrabold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{text}</p><div className="mt-6 flex items-center justify-between text-xs font-bold"><span>{progress} / {total}</span><span>{Math.round(progress / total * 100)}%</span></div><div className="mt-2 h-2.5 rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-2.5 rounded-full bg-amber-500" style={{width:`${Math.min(progress/total*100,100)}%`}} /></div><Link href="/dashboard" className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-amber-700 dark:text-amber-400">Continue mission <ArrowRight className="h-4 w-4" /></Link></article>)}</div>

        <section className="juba-card mt-8 overflow-hidden"><div className="flex flex-col gap-5 bg-gradient-to-r from-slate-900 to-slate-800 p-7 text-white dark:from-slate-100 dark:to-white dark:text-slate-950 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2 text-amber-400 dark:text-amber-600"><Flame className="h-5 w-5" /><span className="text-sm font-extrabold">14 day streak</span></div><h2 className="mt-2 text-2xl font-black">Consistency beats intensity.</h2><p className="mt-2 text-sm text-slate-300 dark:text-slate-600">Keep your streak alive with even a 5-minute session today.</p></div><div className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-xs font-bold dark:border-slate-200 dark:bg-slate-50"><LockKeyhole className="h-4 w-4" /> Privacy-first leaderboard</div></div></section>
      </div>
    </main>
  )
}
