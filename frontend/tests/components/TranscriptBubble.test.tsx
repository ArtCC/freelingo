import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TranscriptBubble from '@/components/conversation/TranscriptBubble'

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))

describe('TranscriptBubble', () => {
  it('marks the text as selectable and fires onPointerUp when set', () => {
    const onPointerUp = vi.fn()
    render(
      <TranscriptBubble
        role="assistant"
        text="Hola"
        onPointerUp={onPointerUp}
      />
    )

    const bubble = screen.getByText('Hola')
    expect(bubble.className).toContain('word-selectable')
    expect(bubble.className).toContain('cursor-text')
    expect(bubble.className).toContain('select-text')

    fireEvent.pointerUp(bubble)
    expect(onPointerUp).toHaveBeenCalledTimes(1)
  })

  it('renders without the selectable classes when onPointerUp is not set', () => {
    render(<TranscriptBubble role="user" text="Hello" />)

    const bubble = screen.getByText('Hello')
    expect(bubble.className).not.toContain('word-selectable')
  })
})
