'use client'

import Link from 'next/link'
import { BrainCircuit, Flame, Mic, Target, TrendingUp, Sparkles, ArrowRight, RotateCcw } from 'lucide-react'

const insights = [
  { label: 'Vocabulary', value: 82, note: 'Your strongest skill', icon: TrendingUp },
  { label: 'Listening', value: 68, note: 'Practice recommended', icon: Mic },
  { label: 'Pronunciation', value: 61, note: 'Focus area this week', icon: Target },
  { label: 'Fluency', value: 74, note: 'Improving steadily', icon: Sparkles },
]

const reviewWords = ['although', 'appointment', 'nevertheless', 'probably', 'schedule']

export default function CoachPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 dark:bg-slate-950 dark:text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <span className="juba-eyebrow"><BrainCircuit className="h-3.5 w-3.5" /> Your AI learning coach</span>
            <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-5xl">Learn smarter, not harder.</h1>
            <p className="mt-3 max-w-2xl text-slate-600 dark:text-slate-400">JUBA AI watches your progress, finds patterns in your mistakes and chooses the next activity for you.</p>
          </div>
          <Link href="/conversation" className="inline-flex items-center justify-center gap-2 rounded-2xl bg-amber-500 px-5 py-3 font-bold text-slate-950 shadow-lg shadow-amber-500/20 transition hover:bg-amber-400">Start a conversation <ArrowRight className="h-4 w-4" /></Link>
        </header>

        <section className="grid gap-4 lg:grid-cols-12">
          <div className="juba-card overflow-hidden p-6 sm:p-8 lg:col-span-7">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-amber-500 text-slate-950 shadow-lg"><BrainCircuit className="h-7 w-7" /></div>
              <div><p className="text-xs font-bold uppercase tracking-widest text-amber-600 dark:text-amber-400">Coach insight</p><h2 className="mt-1 text-xl font-extrabold">Your listening is the next opportunity.</h2><p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-400">You have practiced vocabulary consistently, but listening activity dropped over the last 3 days. A short session today will keep your weekly balance healthy.</p></div>
            </div>
            <div className="mt-7 rounded-2xl bg-slate-100 p-4 dark:bg-slate-900">
              <div className="flex items-center justify-between text-xs font-bold"><span>Recommended today</span><span className="text-amber-600 dark:text-amber-400">12 min</span></div>
              <div className="mt-3 flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className="h-full w-[68%] rounded-full bg-amber-500" /></div><span className="text-xs font-bold">68%</span></div>
              <Link href="/listening" className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-amber-700 dark:text-amber-400">Begin recommended session <ArrowRight className="h-4 w-4" /></Link>
            </div>
          </div>

          <div className="juba-card p-6 lg:col-span-5">
            <div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-slate-500">Weekly mission</p><h2 className="mt-1 text-xl font-extrabold">Speak for 30 minutes</h2></div><div className="rounded-xl bg-orange-100 p-2 text-orange-600 dark:bg-orange-950/40 dark:text-orange-400"><Flame className="h-5 w-5" /></div></div>
            <div className="mt-6 flex items-end gap-2"><span className="text-4xl font-black">18</span><span className="pb-1 text-sm text-slate-500">/ 30 min</span></div>
            <div className="mt-3 h-3 rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-3 w-[60%] rounded-full bg-gradient-to-r from-amber-500 to-orange-500" /></div>
            <p className="mt-3 text-xs text-slate-500">Two more short conversations will complete your mission.</p>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {insights.map(({ label, value, note, icon: Icon }) => <div key={label} className="juba-card p-5"><div className="flex items-center justify-between"><span className="text-sm font-bold">{label}</span><Icon className="h-4 w-4 text-amber-500" /></div><div className="mt-5 flex items-end justify-between"><span className="text-3xl font-black">{value}%</span><span className="text-[11px] text-slate-500">CEFR signal</span></div><p className="mt-2 text-xs text-slate-500">{note}</p></div>)}
        </section>

        <section className="juba-card p-6 sm:p-8">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><span className="text-xs font-bold uppercase tracking-widest text-amber-600 dark:text-amber-400">Smart review</span><h2 className="mt-1 text-2xl font-extrabold">Due when you need them.</h2><p className="mt-2 text-sm text-slate-500">Spaced repetition prioritizes words you are most likely to forget.</p></div><Link href="/flashcards" className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900">Review now <RotateCcw className="h-4 w-4" /></Link></div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{reviewWords.map((word, i) => <div key={word} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><p className="font-bold">{word}</p><p className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">{i < 2 ? 'Due today' : 'Due soon'}</p></div>)}</div>
        </section>
      </div>
    </main>
  )
}
