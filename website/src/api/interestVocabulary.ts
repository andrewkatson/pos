// The curated positive-interest bucket vocabulary and limits (issues #446/#35),
// mirroring backend/user_system/constants.py (INTEREST_CATEGORY_CHOICES and the
// MAX_FREEFORM_* limits). The backend's GET /interests/options/ is the source of
// truth at runtime; this local copy backs the in-memory StatefulStubbedAPI and
// the picker's client-side freeform validation.
import type { InterestOption } from './types'

export const INTEREST_OPTIONS: InterestOption[] = [
  { slug: 'nature', name: 'Nature' },
  { slug: 'animals', name: 'Animals' },
  { slug: 'sports', name: 'Sports' },
  { slug: 'art', name: 'Art' },
  { slug: 'music', name: 'Music' },
  { slug: 'food', name: 'Food' },
  { slug: 'travel', name: 'Travel' },
  { slug: 'science', name: 'Science' },
  { slug: 'technology', name: 'Technology' },
  { slug: 'fitness', name: 'Fitness' },
  { slug: 'family', name: 'Family' },
  { slug: 'friends', name: 'Friends' },
  { slug: 'humor', name: 'Humor' },
  { slug: 'gratitude', name: 'Gratitude' },
  { slug: 'kindness', name: 'Kindness' },
  { slug: 'community', name: 'Community' },
  { slug: 'learning', name: 'Learning' },
  { slug: 'achievement', name: 'Achievement' },
  { slug: 'faith', name: 'Faith' },
  { slug: 'wellness', name: 'Wellness' },
  { slug: 'outdoors', name: 'Outdoors' },
  { slug: 'books', name: 'Books' },
  { slug: 'gaming', name: 'Gaming' },
  { slug: 'photography', name: 'Photography' },
]

export const INTEREST_SLUGS: ReadonlySet<string> = new Set(INTEREST_OPTIONS.map((o) => o.slug))

/** A user keeps at most this many freeform interest terms. */
export const MAX_FREEFORM_INTERESTS = 20
/** Max length (code points) of a single freeform interest term. */
export const MAX_FREEFORM_INTEREST_LENGTH = 100
/** How much of a rejected (over-length) term the backend echoes back, so the
 * stub can bound it the same way. Well above the length limit, so an elided
 * term still reads as clearly too long. */
export const REJECTED_TEXT_ECHO_LIMIT = MAX_FREEFORM_INTEREST_LENGTH * 2

/** Split a freeform entry (which may be a comma-separated list) into trimmed,
 * non-empty terms, deduped case-insensitively, preserving order. */
export function parseFreeformInput(raw: string): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const piece of raw.split(',')) {
    const term = piece.trim()
    if (!term) continue
    const key = term.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(term)
  }
  return out
}

/** Deterministic keyword mapper mirroring the backend's TESTING categorizer:
 * a bucket matches when its slug appears as a word in the text. Used by the
 * stub to map a freeform term to buckets. */
export function matchInterestSlugs(text: string): string[] {
  const words = new Set((text.toLowerCase().match(/[a-z0-9]+/g) ?? []))
  return INTEREST_OPTIONS.map((o) => o.slug).filter((slug) => words.has(slug))
}
