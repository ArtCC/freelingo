import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import LessonPage from '@/app/(app)/lesson/[id]/page'

const { mockApiFetch } = vi.hoisted(() => ({
  mockApiFetch: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  apiFetch: mockApiFetch,
}))

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => 'en',
}))

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '1' }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/lesson/1',
  useSearchParams: () => new URLSearchParams(),
}))

function mockSelection(word: string) {
  const rect = { left: 10, top: 20, width: 30, height: 10 }
  const selection = {
    isCollapsed: false,
    rangeCount: 1,
    toString: () => word,
    getRangeAt: () => ({ getBoundingClientRect: () => rect }),
    removeAllRanges: vi.fn(),
  }
  vi.spyOn(window, 'getSelection').mockReturnValue(
    selection as unknown as Selection
  )
}

const lesson = {
  id: 1,
  study_plan_id: 42,
  title: 'Lesson one',
  lesson_type: 'writing',
  cefr_level: 'B1',
  content: {},
  is_completed: false,
}

const exercises = [
  {
    id: 10,
    exercise_type: 'free_write',
    question: 'Primera pregunta',
    options: null,
    correct_answer: 'respuesta',
    explanation: null,
    native_explanation: null,
    user_answer: null,
    score: null,
    feedback: null,
    native_hint: null,
  },
  {
    id: 11,
    exercise_type: 'free_write',
    question: 'Segunda pregunta',
    options: null,
    correct_answer: 'respuesta dos',
    explanation: null,
    native_explanation: null,
    user_answer: null,
    score: null,
    feedback: null,
    native_hint: null,
  },
]

function mockApiFetchImplementation(url: string) {
  if (url === '/api/lessons/1') {
    return Promise.resolve(
      new Response(JSON.stringify({ lesson, exercises }), { status: 200 })
    )
  }
  if (url === '/api/study-plan/today') {
    return Promise.resolve(
      new Response(
        JSON.stringify({ progress_day: 1, total_days: 30, lessons: [] }),
        { status: 200 }
      )
    )
  }
  if (url.startsWith('/api/grammar')) {
    return Promise.resolve(
      new Response(JSON.stringify({ topics: [] }), { status: 200 })
    )
  }
  if (url === '/api/lessons/exercises/10/answer') {
    return Promise.resolve(
      new Response(JSON.stringify({ score: 1, feedback: 'Great job' }), {
        status: 200,
      })
    )
  }
  return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
}

async function selectWordInQuestion(word: string, questionText: string) {
  const question = await screen.findByText(questionText)
  mockSelection(word)
  fireEvent.pointerUp(question)
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

async function submitCurrentAnswer(answer: string) {
  const textarea = screen.getByPlaceholderText('yourAnswer')
  fireEvent.change(textarea, { target: { value: answer } })
  fireEvent.click(screen.getByRole('button', { name: 'submitAnswer' }))
  await waitFor(() => {
    expect(
      mockApiFetch.mock.calls.some(
        ([calledUrl]) => calledUrl === '/api/lessons/exercises/10/answer'
      )
    ).toBe(true)
  })
  await screen.findByText('Great job')
}

describe('Lesson page word tooltip', () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockImplementation(mockApiFetchImplementation)
  })

  it('keeps the word tooltip open when the exercises array is replaced without navigation', async () => {
    render(<LessonPage />)

    await selectWordInQuestion('pregunta', 'Primera pregunta')
    expect(screen.getByText('saveWord')).toBeInTheDocument()

    // Submitting the answer replaces the current exercise item in `exercises`
    // without changing `currentExercise` — this must not close the tooltip.
    await submitCurrentAnswer('respuesta')

    expect(screen.getByText('saveWord')).toBeInTheDocument()
  })

  it('dismisses the word tooltip when navigating to the next exercise', async () => {
    render(<LessonPage />)

    await selectWordInQuestion('pregunta', 'Primera pregunta')
    expect(screen.getByText('saveWord')).toBeInTheDocument()

    await submitCurrentAnswer('respuesta')

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText('Segunda pregunta')

    expect(screen.queryByText('saveWord')).not.toBeInTheDocument()
  })
})
