'use client'

import Link from 'next/link'
import { Upload, Link2, ImageIcon, FileText, Video, Sparkles, BookOpen, Layers, Headphones, BrainCircuit, ArrowRight } from 'lucide-react'

const outputs = [
  { icon: BookOpen, title: 'Interactive lesson', desc: 'A structured lesson matched to your CEFR level.' },
  { icon: Layers, title: 'Smart vocabulary', desc: 'Key words become spaced-repetition flashcards.' },
  { icon: BrainCircuit, title: 'Grammar insights', desc: 'Useful grammar is extracted and explained in context.' },
  { icon: Headphones, title: 'Listening practice', desc: 'Turn the source into listening and comprehension practice.' },
]

export default function LearnAnythingPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 dark:bg-slate-950 dark:text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="text-center"><span className="juba-eyebrow"><Sparkles className="h-3.5 w-3.5" /> Learn From Anything</span><h1 className="mt-5 text-4xl font-black tracking-tight sm:text-6xl">Bring your world. <span className="juba-gradient-text">JUBA builds the lesson.</span></h1><p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-400">Paste a link, upload a document, image or video, and transform real content into a personalized language-learning path.</p></div>

        <section className="juba-card mt-10 p-6 sm:p-10">
          <div className="rounded-3xl border-2 border-dashed border-slate-200 bg-slate-50/70 p-8 text-center dark:border-slate-800 dark:bg-slate-900/60 sm:p-14">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-500 text-slate-950 shadow-lg"><Upload className="h-7 w-7" /></div>
            <h2 className="mt-5 text-2xl font-extrabold">Drop content here</h2><p className="mt-2 text-sm text-slate-500">PDF, text, image, video, audio or a web link</p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">{[[Link2,'Web link'],[FileText,'PDF / Text'],[ImageIcon,'Image'],[Video,'Video']].map(([Icon,label]) => { const I = Icon as typeof Upload; return <button key={String(label)} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold shadow-sm transition hover:-translate-y-0.5 hover:border-amber-400 dark:border-slate-800 dark:bg-slate-950"><I className="h-4 w-4 text-amber-500" />{String(label)}</button> })}</div>
          </div>
        </section>

        <section className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{outputs.map(({icon:Icon,title,desc}) => <div key={title} className="juba-card p-6"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400"><Icon className="h-5 w-5" /></div><h3 className="mt-5 font-extrabold">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-500">{desc}</p></div>)}</section>

        <section className="mt-10 rounded-3xl bg-slate-900 p-7 text-white shadow-xl dark:bg-white dark:text-slate-950 sm:p-9"><div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center"><div><p className="text-xs font-bold uppercase tracking-widest text-amber-400 dark:text-amber-600">From content to confidence</p><h2 className="mt-2 text-2xl font-black">One source. A complete learning path.</h2><p className="mt-2 max-w-2xl text-sm text-slate-300 dark:text-slate-600">JUBA can turn one piece of content into a lesson, vocabulary review, grammar practice, listening activity and quiz.</p></div><Link href="/dashboard" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-400">Continue to learning <ArrowRight className="h-4 w-4" /></Link></div></section>
      </div>
    </main>
  )
}
