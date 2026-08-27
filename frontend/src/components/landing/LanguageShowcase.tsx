'use client'

import { Globe2, Sparkles } from 'lucide-react'

interface LanguageShowcaseProps {
  t: (key: string) => string
}

const LANGUAGES = [
  { code: 'en-US', name: 'English (US)', flag: '🇺🇸', greeting: 'Hello!' },
  { code: 'en-GB', name: 'English (UK)', flag: '🇬🇧', greeting: 'Hello!' },
  { code: 'es-ES', name: 'Spanish', flag: '🇪🇸', greeting: '¡Hola!' },
  { code: 'fr-FR', name: 'French', flag: '🇫🇷', greeting: 'Bonjour !' },
  { code: 'de-DE', name: 'German', flag: '🇩🇪', greeting: 'Hallo!' },
  { code: 'it-IT', name: 'Italian', flag: '🇮🇹', greeting: 'Ciao!' },
  { code: 'pt-PT', name: 'Portuguese', flag: '🇵🇹', greeting: 'Olá!' },
  { code: 'ja-JP', name: 'Japanese', flag: '🇯🇵', greeting: 'こんにちは！' },
  { code: 'ko-KR', name: 'Korean', flag: '🇰🇷', greeting: '안녕하세요!' },
  { code: 'zh-CN', name: 'Chinese', flag: '🇨🇳', greeting: '你好！' },
]

export function LanguageShowcase({ t }: LanguageShowcaseProps) {
  return (
    <section id="languages" className="scroll-mt-24 py-20 bg-white dark:bg-neutral-950">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold text-xs tracking-wider uppercase mb-3">
            <Globe2 className="h-3.5 w-3.5" />
            Global Learning Support
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
            {t('languagesTitle')}
          </h2>
          <p className="mt-4 text-base sm:text-lg text-neutral-600 dark:text-neutral-400">
            {t('languagesSubtitle')}
          </p>
        </div>

        {/* Language Grid Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {LANGUAGES.map((lang) => (
            <div
              key={lang.code}
              className="juba-card p-5 flex flex-col items-center justify-center text-center group hover:border-amber-500/50 hover:shadow-lg transition-all"
            >
              <span className="text-3xl mb-2 group-hover:scale-110 transition-transform">
                {lang.flag}
              </span>
              <h4 className="font-bold text-sm text-neutral-900 dark:text-white">
                {lang.name}
              </h4>
              <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mt-1">
                "{lang.greeting}"
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
