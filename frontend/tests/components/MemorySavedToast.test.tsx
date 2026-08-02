import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemorySavedToast } from '@/components/memory/MemorySavedToast'
import { useTransientToast } from '@/hooks/useTransientToast'

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))
function ToastHarness() {
  const toast = useTransientToast(1000)
  return (
    <>
      <button onClick={toast.show}>show</button>
      <MemorySavedToast
        visible={toast.visible}
        announcementId={toast.announcementId}
      />
    </>
  )
}

describe('MemorySavedToast', () => {
  afterEach(() => vi.useRealTimers())

  it('announces the saved memory as a polite status', () => {
    render(<MemorySavedToast visible announcementId={1} />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByText('memorySavedToast')).toBeInTheDocument()
  })

  it('restarts its timer when another memory is saved', () => {
    vi.useFakeTimers()
    render(<ToastHarness />)
    const trigger = screen.getByRole('button', { name: 'show' })
    fireEvent.click(trigger)
    act(() => vi.advanceTimersByTime(800))
    fireEvent.click(trigger)
    act(() => vi.advanceTimersByTime(800))
    expect(screen.getByRole('status')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(200))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
