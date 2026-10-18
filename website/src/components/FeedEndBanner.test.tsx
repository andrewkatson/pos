import { act, render, screen } from '@testing-library/react'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import FeedEndBanner from './FeedEndBanner'

// jsdom has no IntersectionObserver; this stand-in lets a test decide when the
// banner "scrolls into view".
let observerCallback: IntersectionObserverCallback | null = null
const disconnect = vi.fn()

class FakeIntersectionObserver {
  constructor(callback: IntersectionObserverCallback) {
    observerCallback = callback
  }
  observe() {}
  unobserve() {}
  disconnect = disconnect
}

function scrollBannerIntoView() {
  act(() => {
    observerCallback?.(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    )
  })
}

function setPageHeight(scrollHeight: number) {
  Object.defineProperty(document.documentElement, 'scrollHeight', {
    configurable: true,
    value: scrollHeight,
  })
}

function stubReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({ matches: reduce && query.includes('reduce') })),
  )
}

beforeEach(() => {
  observerCallback = null
  disconnect.mockReset()
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)
  stubReducedMotion(false)
  // A page taller than jsdom's 768px window: the viewer scrolled to get here.
  setPageHeight(5000)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

test('announces that the viewer finished, with the given message', () => {
  render(<FeedEndBanner message="You've seen every post in your feed." />)
  const banner = screen.getByRole('status')
  expect(banner).toHaveTextContent('You finished!')
  expect(banner).toHaveTextContent("You've seen every post in your feed.")
})

test('throws confetti when the banner scrolls into view at the end of a long list', () => {
  render(<FeedEndBanner message="done" />)
  expect(screen.queryByTestId('confetti')).not.toBeInTheDocument()

  scrollBannerIntoView()

  const confetti = screen.getByTestId('confetti')
  expect(confetti).toHaveAttribute('aria-hidden', 'true')
  expect(confetti.children.length).toBeGreaterThan(0)
  // One celebration per banner: it stops watching once seen.
  expect(disconnect).toHaveBeenCalled()
})

test('clears the confetti once it has fallen', () => {
  vi.useFakeTimers()
  render(<FeedEndBanner message="done" />)
  scrollBannerIntoView()
  expect(screen.getByTestId('confetti')).toBeInTheDocument()

  act(() => {
    vi.advanceTimersByTime(10_000)
  })
  expect(screen.queryByTestId('confetti')).not.toBeInTheDocument()
  // The banner itself stays.
  expect(screen.getByRole('status')).toBeInTheDocument()
})

test('a list that fits on one screen shows the banner without confetti', () => {
  setPageHeight(window.innerHeight)
  render(<FeedEndBanner message="done" />)
  scrollBannerIntoView()
  expect(screen.getByRole('status')).toBeInTheDocument()
  expect(screen.queryByTestId('confetti')).not.toBeInTheDocument()
})

test('skips the confetti under prefers-reduced-motion', () => {
  stubReducedMotion(true)
  render(<FeedEndBanner message="done" />)
  scrollBannerIntoView()
  expect(screen.getByRole('status')).toBeInTheDocument()
  expect(screen.queryByTestId('confetti')).not.toBeInTheDocument()
})

test('does nothing until the banner is actually on screen', () => {
  render(<FeedEndBanner message="done" />)
  act(() => {
    observerCallback?.(
      [{ isIntersecting: false } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    )
  })
  expect(screen.queryByTestId('confetti')).not.toBeInTheDocument()
  expect(disconnect).not.toHaveBeenCalled()
})
