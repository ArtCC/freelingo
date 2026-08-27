'use client'

import Link from 'next/link'
import { ContactButton } from '@/components/ui/contact-button'

interface LandingFooterProps {
  t: (key: string) => string
}

export function LandingFooter({ t }: LandingFooterProps) {
  return (
    <footer className="border-t border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 pt-16 pb-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-10 mb-12">
          {/* Brand Column */}
          <div className="md:col-span-2">
            <Link href="/" className="flex items-center gap-3 mb-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500 text-white font-bold text-lg shadow-md shadow-amber-500/20">
                J
              </div>
              <span className="font-sans text-xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
                JUBA <span className="text-amber-600 dark:text-amber-400">LISAN</span>
              </span>
            </Link>
            <p className="text-neutral-600 dark:text-neutral-400 text-sm max-w-sm leading-relaxed mb-6">
              {t('footerTagline')}
            </p>
            <p className="text-xs text-neutral-400">
              © {new Date().getFullYear()} JUBA LISAN Inc. All rights reserved.
            </p>
          </div>

          {/* Product Links */}
          <div>
            <h4 className="font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wider mb-4">
              {t('footerProduct')}
            </h4>
            <ul className="space-y-2.5 text-sm">
              <li>
                <a href="#features" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  {t('navFeatures')}
                </a>
              </li>
              <li>
                <a href="#demo" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  AI Voice Demo
                </a>
              </li>
              <li>
                <a href="#languages" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  Supported Languages
                </a>
              </li>
              <li>
                <a href="#pricing" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  {t('navPricing')}
                </a>
              </li>
            </ul>
          </div>

          {/* Resources & Support */}
          <div>
            <h4 className="font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wider mb-4">
              {t('footerResources')}
            </h4>
            <ul className="space-y-2.5 text-sm">
              <li>
                <a href="#faq" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  {t('navFAQ')}
                </a>
              </li>
              <li>
                <a href="https://github.com/ArtCC/freelingo" target="_blank" rel="noopener noreferrer" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  {t('github')}
                </a>
              </li>
              <li className="pt-1">
                <ContactButton />
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wider mb-4">
              {t('footerLegal')}
            </h4>
            <ul className="space-y-2.5 text-sm">
              <li>
                <Link href="/privacy?from=landing" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  {t('privacy')}
                </Link>
              </li>
              <li>
                <Link href="/terms?from=landing" className="text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors">
                  {t('terms')}
                </Link>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  )
}
