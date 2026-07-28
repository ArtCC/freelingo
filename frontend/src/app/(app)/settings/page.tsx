'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { apiFetch } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { useRouter } from 'next/navigation'
import {
  Bot,
  CreditCard,
  Globe2,
  MessageSquareText,
  Palette,
  User,
  Volume2,
} from 'lucide-react'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useLogout } from '@/hooks/useLogout'
import { ProfileSection } from '@/components/settings/ProfileSection'
import { ConversationSection } from '@/components/settings/ConversationSection'
import { VoiceSection } from '@/components/settings/VoiceSection'
import { UsageLimitsSection } from '@/components/settings/UsageLimitsSection'
import { AppearanceSection } from '@/components/settings/AppearanceSection'
import { BillingSection } from '@/components/settings/BillingSection'
import { ReviewSection } from '@/components/settings/ReviewSection'
import {
  SettingsActionCard,
  SettingsNav,
  SettingsPageHeader,
  SettingsPanel,
} from '@/components/settings/SettingsShell'

export default function SettingsPage() {
  const t = useTranslations('settings')
  const tCommon = useTranslations('common')
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const router = useRouter()
  const handleLogout = useLogout()

  const [logoutConfirm, setLogoutConfirm] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const navItems = [
    { href: '#account', label: t('sectionAccount'), icon: User },
    { href: '#preferences', label: t('sectionAppearance'), icon: Palette },
    { href: '#voice', label: t('sectionConversation'), icon: Volume2 },
    { href: '#plan', label: t('sectionUsageLimits'), icon: CreditCard },
    { href: '#community', label: t('sectionReview'), icon: MessageSquareText },
    { href: '#legal', label: t('sectionLegal'), icon: Globe2 },
  ]

  async function handleDeleteAccount() {
    setDeleting(true)
    try {
      await apiFetch('/api/auth/me', { method: 'DELETE' })
      logout()
      router.push('/login')
    } catch {
      setDeleting(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <SettingsPageHeader
        eyebrow={`${t('sectionAccount')} / ${t('title')}`}
        title={t('title')}
      />

      <SettingsNav items={navItems} />

      <div className="grid gap-3 md:grid-cols-2">
        <SettingsActionCard
          href="/settings/languages"
          label={t('languagesManage')}
          description={t('sectionLanguages')}
          icon={Globe2}
        />
        <SettingsActionCard
          href="/settings/memories"
          label={t('memoryManage')}
          description={t('sectionMemory')}
          icon={Bot}
        />
      </div>

      <div className="space-y-4">
        <SettingsPanel id="account" title={t('sectionAccount')}>
          <ProfileSection title={t('cardProfileAccess')} />

          <div className="border-fl-border bg-fl-surface border p-6">
            <div className="border-fl-border mb-4 flex items-center gap-2 border-b pb-4">
              <span className="text-fl-label text-fl-muted-2">●</span>
              <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
                {t('cardSessionSecurity')}
              </span>
            </div>
            <div className="space-y-2">
              <button
                onClick={() => setLogoutConfirm(true)}
                className="text-fl-label text-fl-muted-2 border-fl-border hover:text-fl-error hover:border-fl-error/40 w-full border py-3 font-mono tracking-widest uppercase transition-colors"
              >
                {tCommon('logout')}
              </button>

              {user?.role !== 'admin' && (
                <button
                  onClick={() => setDeleteConfirm(true)}
                  disabled={deleting}
                  className="text-fl-label text-fl-error border-fl-error/40 hover:border-fl-error/70 w-full border py-3 font-mono tracking-widest uppercase transition-colors disabled:opacity-40"
                >
                  {t('deleteAccount')}
                </button>
              )}
            </div>
          </div>
        </SettingsPanel>

        <SettingsPanel id="preferences" title={t('sectionAppearance')}>
          <AppearanceSection title={t('cardTheme')} />
        </SettingsPanel>

        <SettingsPanel id="voice" title={t('sectionConversation')}>
          <div className="grid gap-4 xl:grid-cols-2">
            <ConversationSection title={t('cardConversationTiming')} />
            <VoiceSection title={t('cardTutorVoice')} />
          </div>
        </SettingsPanel>

        <SettingsPanel id="plan" title={t('sectionUsageLimits')}>
          <div className="space-y-4">
            <BillingSection />
            <UsageLimitsSection title={t('cardCurrentUsage')} />
          </div>
        </SettingsPanel>

        <SettingsPanel id="community" title={t('sectionReview')}>
          <ReviewSection title={t('cardProductReview')} />
        </SettingsPanel>

        <SettingsPanel id="legal" title={t('sectionLegal')}>
          <div className="border-fl-border bg-fl-surface border p-6">
            <div className="border-fl-border mb-4 flex items-center gap-2 border-b pb-4">
              <span className="text-fl-label text-fl-muted-2">●</span>
              <span className="text-fl-label text-fl-muted-2 font-mono tracking-widest uppercase">
                {t('cardLegalDocuments')}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <a
                href="/terms?from=settings"
                className="text-fl-muted-2 hover:text-fl-fg font-mono text-xs tracking-widest uppercase transition-colors"
              >
                {t('termsOfService')}
              </a>
              <a
                href="/privacy?from=settings"
                className="text-fl-muted-2 hover:text-fl-fg font-mono text-xs tracking-widest uppercase transition-colors"
              >
                {t('privacyPolicy')}
              </a>
            </div>
          </div>
        </SettingsPanel>
      </div>

      <ConfirmDialog
        open={logoutConfirm}
        title={tCommon('logoutConfirmTitle')}
        message={tCommon('logoutConfirmMessage')}
        confirmLabel={tCommon('logout')}
        onConfirm={handleLogout}
        onCancel={() => setLogoutConfirm(false)}
      />

      <ConfirmDialog
        open={deleteConfirm}
        title={t('deleteAccountTitle')}
        message={t('deleteAccountMessage')}
        confirmLabel={t('deleteAccountConfirm')}
        danger
        onConfirm={handleDeleteAccount}
        onCancel={() => setDeleteConfirm(false)}
      />
    </div>
  )
}
