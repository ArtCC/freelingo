import type { Metadata } from 'next'
import {
  Geist,
  Geist_Mono,
  Noto_Sans_JP,
  Noto_Sans_KR,
  Noto_Sans_SC,
} from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/ThemeProvider'
import { NextIntlClientProvider } from 'next-intl'
import { getLocale, getMessages } from 'next-intl/server'
import { CookieBanner } from '@/components/CookieBanner'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

const notoSansJP = Noto_Sans_JP({
  variable: '--font-noto-ja',
  subsets: ['latin'],
})

const notoSansKR = Noto_Sans_KR({
  variable: '--font-noto-ko',
  subsets: ['latin'],
})

const notoSansSC = Noto_Sans_SC({
  variable: '--font-noto-zh',
  subsets: ['latin'],
})

const themeScript = `(function(){try{var t='system';var s=localStorage.getItem('fl-theme');if(s){var p=JSON.parse(s);t=p&&p.state&&p.state.theme?p.state.theme:t}var l=t==='light'||(t==='system'&&window.matchMedia('(prefers-color-scheme: light)').matches);if(l){document.documentElement.setAttribute('data-theme','light')}else{document.documentElement.removeAttribute('data-theme')}}catch(e){}})();`

export const metadata: Metadata = {
  metadataBase: new URL('https://freelingo.app'),
  title: {
    default: 'FreeLingo',
    template: '%s | FreeLingo',
  },
  description:
    'FreeLingo is a self-hosted AI-powered language learning platform with voice conversation, flashcards, grammar lessons, and a personal AI tutor.',
  keywords: [
    'English learning',
    'AI language tutor',
    'self-hosted',
    'voice conversation',
    'flashcards',
    'CEFR',
    'language learning app',
    'learn English online',
  ],
  authors: [
    {
      name: 'Arturo Carretero Calvo',
      url: 'https://www.arturocarreterocalvo.com',
    },
  ],
  creator: 'Arturo Carretero Calvo',
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon.png', type: 'image/png' },
    ],
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://freelingo.app',
    siteName: 'FreeLingo',
    title: 'FreeLingo: AI-powered language learning',
    description:
      'Learn languages with an AI tutor, voice conversations, flashcards, and structured lessons. Self-hosted and privacy-friendly.',
    images: [
      {
        url: '/og-image-v2.png',
        width: 1200,
        height: 630,
        alt: 'FreeLingo: AI-powered language learning',
      },
    ],
  },
  twitter: {
    card: 'summary',
    title: 'FreeLingo: AI-powered language learning',
    description:
      'Learn languages with an AI tutor, voice conversations, flashcards, and structured lessons.',
    images: ['/logo.png'],
  },
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <html
      suppressHydrationWarning
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} ${notoSansJP.variable} ${notoSansKR.variable} ${notoSansSC.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){if(document.cookie.indexOf('LOCALE_DETECTED=')!==-1)return;var m=document.cookie.match(/(^| )NEXT_LOCALE=([^;]+)/);var cl=m?m[2]:null;var bl=(navigator.language||'').split('-')[0].toLowerCase();var s=['es','fr','pt','de','it','pl','nl','ro','ru'];document.cookie='LOCALE_DETECTED=1;path=/;max-age=31536000;SameSite=Lax';if(bl!=='en'&&s.indexOf(bl)!==-1&&cl!==bl){document.cookie='NEXT_LOCALE='+bl+';path=/;max-age=31536000;SameSite=Lax';location.reload()}})();`,
          }}
        />
        {process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID && (
          <script
            defer
            src="/umami/script.js"
            data-host-url="/umami"
            data-website-id={process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID}
          />
        )}
      </head>
      <body className="min-h-full bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ThemeProvider>{children}</ThemeProvider>
          <CookieBanner />
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
