'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { ContactFormModal } from '@/components/ui/contact-form-modal'

export function ContactButton() {
  const t = useTranslations('landing')
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-fl-hint text-fl-muted-3 hover:text-fl-muted-1 font-mono tracking-widest uppercase transition-colors text-left w-full"
      >
        {t('contact')}
      </button>
      <ContactFormModal open={open} onClose={() => setOpen(false)} />
    </>
  )
}
