import { useCallback, useEffect, useRef, useState } from 'react'

export function useTransientToast(durationMs = 3500) {
  const [visible, setVisible] = useState(false)
  const [announcementId, setAnnouncementId] = useState(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const show = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setAnnouncementId((current) => current + 1)
    setVisible(true)
    timerRef.current = setTimeout(() => {
      setVisible(false)
      timerRef.current = null
    }, durationMs)
  }, [durationMs])

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    },
    []
  )

  return { visible, announcementId, show }
}
