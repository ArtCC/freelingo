import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'
import UnitCard from '@/components/plan/UnitCard'
import UnitDrawer from '@/components/plan/UnitDrawer'
import type { CurriculumUnit } from '@/data/curriculum'

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))

vi.mock('next/image', () => ({
  default: function MockImage(
    props: React.ImgHTMLAttributes<HTMLImageElement> & {
      unoptimized?: boolean
      priority?: boolean
    }
  ) {
    const { unoptimized, priority, ...imgProps } = props
    void unoptimized
    void priority
    return React.createElement('img', imgProps)
  },
}))

// next/navigation is already mocked in tests/setup.ts

// ── Helpers ────────────────────────────────────────────────────────────────

type UnitStatus = {
  completed: boolean
  active: boolean
  locked: boolean
  isLevelTest: boolean
}

const defaultStatus: UnitStatus = {
  completed: false,
  active: false,
  locked: false,
  isLevelTest: false,
}

function renderUnitCard(
  overrides: Partial<{
    title: string
    index: number
    lessonCount: number
    grammarCount: number
    competency: number
    status: Partial<UnitStatus>
    onClick: () => void
    onStartLesson: () => void
  }> = {}
) {
  const props = {
    title: overrides.title ?? 'Basic Greetings',
    index: overrides.index ?? 0,
    lessonCount: overrides.lessonCount ?? 5,
    grammarCount: overrides.grammarCount ?? 2,
    competency: overrides.competency ?? 0.6,
    status: { ...defaultStatus, ...overrides.status },
    onClick: overrides.onClick ?? vi.fn(),
    onStartLesson: overrides.onStartLesson,
  }
  const result = render(<UnitCard {...props} />)
  return { ...result, props }
}

// ── UnitCard tests ─────────────────────────────────────────────────────────

describe('UnitCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Status states ──────────────────────────────────────────────────────

  it('renders completed unit with checkmark icon', () => {
    renderUnitCard({ status: { completed: true }, competency: 1 })
    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('renders active unit with pulsing dot icon', () => {
    renderUnitCard({ status: { active: true } })
    const dot = screen.getByText('●')
    expect(dot).toBeInTheDocument()
    expect(dot.className).toContain('animate-pulse')
  })

  it('renders locked unit with empty circle icon and opacity', () => {
    const { container } = renderUnitCard({ status: { locked: true } })
    expect(screen.getByText('○')).toBeInTheDocument()
    // outer wrapper should have opacity-40
    const outer = container.firstChild as HTMLElement
    expect(outer.className).toContain('opacity-40')
  })

  it('renders level-test unit with special icon and badge', () => {
    renderUnitCard({ status: { isLevelTest: true } })
    expect(screen.getByText('⊞')).toBeInTheDocument()
    expect(screen.getByText('levelTestLabel')).toBeInTheDocument()
  })

  it('renders default state (none of the flags) with hollow dot', () => {
    renderUnitCard()
    expect(screen.getByText('◦')).toBeInTheDocument()
  })

  // ── Card content ───────────────────────────────────────────────────────

  it('renders padded unit index', () => {
    renderUnitCard({ index: 3 })
    expect(screen.getByText('04')).toBeInTheDocument()
  })

  it('renders the unit title', () => {
    renderUnitCard({ title: 'Past Tenses' })
    expect(screen.getByText('Past Tenses')).toBeInTheDocument()
  })

  it('renders lesson count translation key', () => {
    renderUnitCard({ lessonCount: 5 })
    expect(screen.getByText('nLessons')).toBeInTheDocument()
  })

  it('renders grammar count when grammarCount > 0', () => {
    renderUnitCard({ grammarCount: 3 })
    expect(screen.getByText('nGrammar')).toBeInTheDocument()
  })

  it('does not render grammar count when grammarCount is 0', () => {
    renderUnitCard({ grammarCount: 0 })
    expect(screen.queryByText('nGrammar')).toBeNull()
  })

  // ── Progress bar ───────────────────────────────────────────────────────

  it('renders progress bar for non-locked units', () => {
    const { container } = renderUnitCard({ competency: 0.42 })
    expect(screen.getByText('42%')).toBeInTheDocument()
    const bar = container.querySelector('.bg-fl-fg.h-px') as HTMLElement
    expect(bar).toBeInTheDocument()
    expect(bar.style.width).toBe('42%')
  })

  it('renders 0% progress bar when competency is 0', () => {
    const { container } = renderUnitCard({ competency: 0 })
    expect(screen.getByText('0%')).toBeInTheDocument()
    const bar = container.querySelector('.bg-fl-fg.h-px') as HTMLElement
    expect(bar.style.width).toBe('0%')
  })

  it('renders 100% progress bar when competency is 1', () => {
    const { container } = renderUnitCard({
      competency: 1,
      status: { completed: true },
    })
    expect(screen.getByText('100%')).toBeInTheDocument()
    const bar = container.querySelector('.bg-fl-fg.h-px') as HTMLElement
    expect(bar.style.width).toBe('100%')
  })

  it('does not render progress bar for locked units', () => {
    const { container } = renderUnitCard({ status: { locked: true } })
    expect(container.querySelector('.bg-fl-fg.h-px')).toBeNull()
    expect(screen.queryByText(/%$/)).toBeNull()
  })

  // ── Click interaction ──────────────────────────────────────────────────

  it('calls onClick when card header is clicked', () => {
    const onClick = vi.fn()
    renderUnitCard({ onClick })
    const button = screen.getByLabelText('unitAriaLabel')
    fireEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not call onClick when locked unit is clicked (button disabled)', () => {
    const onClick = vi.fn()
    renderUnitCard({ onClick, status: { locked: true } })
    const button = screen.getByLabelText('unitAriaLabel')
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  // ── Start lesson button ────────────────────────────────────────────────

  it('shows start button when active and onStartLesson is provided', () => {
    const onStartLesson = vi.fn()
    renderUnitCard({ status: { active: true }, onStartLesson })
    expect(screen.getByText(/start/)).toBeInTheDocument()
  })

  it('calls onStartLesson when start button is clicked', () => {
    const onStartLesson = vi.fn()
    renderUnitCard({ status: { active: true }, onStartLesson })
    fireEvent.click(screen.getByText(/start/))
    expect(onStartLesson).toHaveBeenCalledTimes(1)
  })

  it('does not show start button when active but onStartLesson is not provided', () => {
    renderUnitCard({ status: { active: true } })
    expect(screen.queryByText(/start/)).toBeNull()
  })

  it('does not show start button when not active (even with onStartLesson)', () => {
    renderUnitCard({ onStartLesson: vi.fn() })
    expect(screen.queryByText(/start/)).toBeNull()
  })

  it('does not show start button when locked (even with onStartLesson)', () => {
    renderUnitCard({ status: { locked: true }, onStartLesson: vi.fn() })
    expect(screen.queryByText(/start/)).toBeNull()
  })
})

// ── UnitDrawer tests ───────────────────────────────────────────────────────

const mockUnit: CurriculumUnit = {
  id: 'unit-a1-1',
  level: 'A1',
  unit_number: 1,
  title: 'Greetings & Introductions',
  default_weeks: 2,
  grammar_points: ['presente de indicativo', 'verbos ser/estar'],
  vocabulary_set_ids: ['v1', 'v2'],
  lesson_types: ['grammar', 'vocabulary', 'reading'],
  prerequisite_unit: undefined,
  competency_checklist: ['Can greet people', 'Can introduce oneself'],
}

const mockUnitNoGrammar: CurriculumUnit = {
  ...mockUnit,
  grammar_points: [],
}

const mockLessons = [
  {
    id: 1,
    title: 'Verb Conjugation',
    lesson_type: 'grammar',
    week: 1,
    day: 1,
    completed: true,
    action: 'review' as const,
  },
  {
    id: 2,
    title: 'Common Phrases',
    lesson_type: 'vocabulary',
    week: 1,
    day: 2,
    completed: false,
    action: 'continue' as const,
  },
  {
    id: 3,
    title: 'Reading Comprehension',
    lesson_type: 'reading',
    week: 2,
    day: 1,
    completed: false,
    action: 'start' as const,
  },
]

const mockLessonsWithNullId = [
  {
    id: null,
    title: 'Pending Content',
    lesson_type: 'review',
    week: 3,
    day: 1,
    completed: false,
  },
  {
    id: 4,
    title: 'Final Test',
    lesson_type: 'review',
    week: 3,
    day: 2,
    completed: false,
    action: 'start' as const,
  },
]

function renderUnitDrawer(
  overrides: Partial<{
    unit: CurriculumUnit
    lessons: Array<{
      id: number | null
      title: string
      lesson_type: string
      week: number
      day: number
      completed: boolean
      action?: 'start' | 'continue' | 'review'
    }>
    onClose: () => void
    onStartLesson: (lessonId: number) => void
  }> = {}
) {
  const props = {
    unit: overrides.unit ?? mockUnit,
    lessons: overrides.lessons ?? mockLessons,
    onClose: overrides.onClose ?? vi.fn(),
    onStartLesson: overrides.onStartLesson ?? vi.fn(),
  }
  const result = render(<UnitDrawer {...props} />)
  return { ...result, props }
}

describe('UnitDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Header ─────────────────────────────────────────────────────────────

  it('renders unit level and label in header', () => {
    renderUnitDrawer()
    expect(screen.getByText(/A1/)).toBeInTheDocument()
    expect(screen.getByText(/unitLabel/)).toBeInTheDocument()
  })

  it('renders unit title in header', () => {
    renderUnitDrawer()
    expect(screen.getByText('Greetings & Introductions')).toBeInTheDocument()
  })

  // ── Grammar points ─────────────────────────────────────────────────────

  it('renders grammar points section when grammar_points is non-empty', () => {
    renderUnitDrawer()
    expect(screen.getByText('grammarCovered')).toBeInTheDocument()
    expect(screen.getByText('presente de indicativo')).toBeInTheDocument()
    expect(screen.getByText('verbos ser/estar')).toBeInTheDocument()
  })

  it('does not render grammar section when grammar_points is empty', () => {
    renderUnitDrawer({ unit: mockUnitNoGrammar })
    expect(screen.queryByText('grammarCovered')).toBeNull()
  })

  // ── Lessons list ───────────────────────────────────────────────────────

  it('renders all lesson titles', () => {
    renderUnitDrawer()
    expect(screen.getByText('Verb Conjugation')).toBeInTheDocument()
    expect(screen.getByText('Common Phrases')).toBeInTheDocument()
    expect(screen.getByText('Reading Comprehension')).toBeInTheDocument()
  })

  it('shows completed lessons with checkmark and strikethrough', () => {
    renderUnitDrawer()
    // completed lesson
    expect(screen.getByText('Verb Conjugation').className).toContain(
      'line-through'
    )
    // the ✓ icon next to it
    const checkmarks = screen.getAllByText('✓')
    expect(checkmarks.length).toBeGreaterThanOrEqual(1)
  })

  it('shows incomplete lessons with empty circle', () => {
    renderUnitDrawer()
    const circles = screen.getAllByText('○')
    // 2 incomplete lessons (id:2 and id:3)
    expect(circles.length).toBe(2)
  })

  it('renders lesson type label for each lesson', () => {
    renderUnitDrawer()
    expect(screen.getByText(/lessonTypes\.grammar/)).toBeInTheDocument()
    expect(screen.getByText(/lessonTypes\.vocabulary/)).toBeInTheDocument()
    expect(screen.getByText(/lessonTypes\.reading/)).toBeInTheDocument()
  })

  it('renders week/day info for each lesson', () => {
    renderUnitDrawer()
    const weekDayEls = screen.getAllByText(/weekDay/)
    expect(weekDayEls.length).toBe(3)
  })

  it('shows empty state when lessons array is empty', () => {
    renderUnitDrawer({ lessons: [] })
    expect(screen.getByText('noLessons')).toBeInTheDocument()
  })

  // ── Lesson action buttons ──────────────────────────────────────────────

  it('renders the action matching each available lesson state', () => {
    renderUnitDrawer()
    expect(screen.getByText('reviewLesson')).toBeInTheDocument()
    expect(screen.getByText('continueLesson')).toBeInTheDocument()
    expect(screen.getByText('start')).toBeInTheDocument()
  })

  it('does not render start button when lesson id is null', () => {
    renderUnitDrawer({ lessons: mockLessonsWithNullId })
    expect(screen.getAllByText('start')).toHaveLength(1)
  })

  it('calls onStartLesson with correct lesson id when start is clicked', () => {
    const onStartLesson = vi.fn()
    renderUnitDrawer({ onStartLesson })
    fireEvent.click(screen.getByText('continueLesson'))
    expect(onStartLesson).toHaveBeenCalledTimes(1)
    expect(onStartLesson).toHaveBeenCalledWith(2)
  })

  it('opens a completed lesson for review', () => {
    const onStartLesson = vi.fn()
    renderUnitDrawer({ onStartLesson })
    fireEvent.click(screen.getByText('reviewLesson'))
    expect(onStartLesson).toHaveBeenCalledWith(1)
  })

  // ── Close interactions ─────────────────────────────────────────────────

  it('closes on X button click', () => {
    const onClose = vi.fn()
    renderUnitDrawer({ onClose })
    fireEvent.click(screen.getByText('✕'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on bottom close button click', () => {
    const onClose = vi.fn()
    renderUnitDrawer({ onClose })
    // There are 2 elements with text 'close': X button's aria-label and bottom button
    const closeButtons = screen.getAllByText('close')
    // The bottom button is the one that is a visible button (the X is ✕)
    const bottomButton = closeButtons.find((btn) => btn.tagName === 'BUTTON')
    fireEvent.click(bottomButton!)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on Escape key press', () => {
    const onClose = vi.fn()
    renderUnitDrawer({ onClose })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not close on non-Escape key press', () => {
    const onClose = vi.fn()
    renderUnitDrawer({ onClose })
    fireEvent.keyDown(document, { key: 'Enter' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('closes on outside click (mousedown on backdrop)', () => {
    const onClose = vi.fn()
    const { container } = renderUnitDrawer({ onClose })
    // Click the backdrop (parent of the drawer content)
    const backdrop = container.firstChild as HTMLElement
    fireEvent.mouseDown(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not close when clicking inside drawer content', () => {
    const onClose = vi.fn()
    renderUnitDrawer({ onClose })
    // Click inside the drawer (e.g., on a lesson title)
    fireEvent.mouseDown(screen.getByText('Verb Conjugation'))
    expect(onClose).not.toHaveBeenCalled()
  })
})
