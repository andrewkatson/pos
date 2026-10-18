import { useEffect, useRef, useState, type CSSProperties } from 'react'

interface FeedEndBannerProps {
  /** What the viewer just finished, e.g. "You've seen every post in your feed." */
  message: string
}

/** How long the confetti stays on screen before it is removed, in ms. Covers
 * the longest piece's delay plus fall (see `confettiPieces`). */
const CONFETTI_DURATION_MS = 4200

const CONFETTI_COLORS = ['#5ba4dc', '#f7c948', '#ff7eb6', '#7ee081', '#b28dff', '#ff9f5a']
const CONFETTI_PIECE_COUNT = 72

interface ConfettiPiece {
  left: number
  delay: number
  duration: number
  drift: number
  spin: number
  color: string
  round: boolean
}

/** Spread derived from the index rather than Math.random, so render stays pure
 * and the overlay is stable between renders. Multipliers coprime with 100 walk
 * every column without bunching. */
function confettiPieces(): ConfettiPiece[] {
  return Array.from({ length: CONFETTI_PIECE_COUNT }, (_, i) => ({
    left: (i * 37) % 100,
    delay: ((i * 53) % 40) / 40,
    duration: 2.2 + ((i * 29) % 10) / 10,
    drift: ((i * 71) % 17) * 6 - 48,
    spin: 360 + ((i * 43) % 5) * 180,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    round: i % 4 === 0,
  }))
}

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/** Whether the page is taller than the window, i.e. the viewer had to scroll to
 * reach the end of the list. */
function pageOverflowsWindow(): boolean {
  return document.documentElement.scrollHeight > window.innerHeight
}

/**
 * The "you finished!" banner at the bottom of a feed or profile once every post
 * has been loaded (issue #528), with a burst of confetti across the screen the
 * first time it scrolls into view.
 *
 * The confetti only plays when the list was longer than the window — a profile
 * with a handful of posts that fits on one screen just shows the banner, so
 * opening it doesn't throw confetti every time — and never under
 * prefers-reduced-motion. It plays once per mount; the owner unmounts the
 * banner whenever the list reloads, so finishing it again celebrates again.
 */
function FeedEndBanner({ message }: FeedEndBannerProps) {
  const bannerRef = useRef<HTMLDivElement>(null)
  const [celebrating, setCelebrating] = useState(false)
  const [pieces] = useState(confettiPieces)

  useEffect(() => {
    const banner = bannerRef.current
    if (!banner || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return
      // Seen once is enough, whether or not it earned confetti.
      observer.disconnect()
      if (pageOverflowsWindow() && !prefersReducedMotion()) setCelebrating(true)
    })
    observer.observe(banner)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!celebrating) return
    const timer = window.setTimeout(() => setCelebrating(false), CONFETTI_DURATION_MS)
    return () => window.clearTimeout(timer)
  }, [celebrating])

  return (
    <>
      <div ref={bannerRef} className="feed-end" role="status">
        <span className="feed-end__icon" aria-hidden="true">
          🎉
        </span>
        <p className="feed-end__title">You finished!</p>
        <p className="feed-end__message">{message}</p>
      </div>
      {celebrating && (
        <div className="confetti" aria-hidden="true" data-testid="confetti">
          {pieces.map((piece, i) => (
            <span
              key={i}
              className={`confetti__piece${piece.round ? ' confetti__piece--round' : ''}`}
              style={
                {
                  left: `${piece.left}%`,
                  background: piece.color,
                  animationDelay: `${piece.delay}s`,
                  animationDuration: `${piece.duration}s`,
                  '--confetti-drift': `${piece.drift}px`,
                  '--confetti-spin': `${piece.spin}deg`,
                } as CSSProperties
              }
            />
          ))}
        </div>
      )}
    </>
  )
}

export default FeedEndBanner
