import { getRequestConfig } from 'next-intl/server'
import { cookies, headers } from 'next/headers'
import { SUPPORTED_LOCALES, type Locale } from '@/lib/locales'

function resolveLocale(raw: string | undefined): Locale {
  if (raw && (SUPPORTED_LOCALES as readonly string[]).includes(raw)) {
    return raw as Locale
  }
  return 'en'
}

export default getRequestConfig(async () => {
  const headerStore = await headers()
  const cookieStore = await cookies()

  // x-next-locale is injected by the middleware on every request (including the
  // very first one, before the NEXT_LOCALE cookie has been written to the client)
  const locale = resolveLocale(
    headerStore.get('x-next-locale') ?? cookieStore.get('NEXT_LOCALE')?.value
  )

  let messages
  try {
    messages = (await import(`../../../messages/${locale}.json`)).default
  } catch {
    // Fallback to English if locale file is missing
    const defaultLocale = 'en'
    messages = (await import(`../../../messages/${defaultLocale}.json`)).default
  }

  return {
    locale,
    messages,
  }
})
