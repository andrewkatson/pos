import { useId, useState } from 'react'
import type { InterestOption, RejectedInterest } from '../api/types'
import {
  MAX_FREEFORM_INTEREST_LENGTH,
  MAX_FREEFORM_INTERESTS,
  parseFreeformInput,
} from '../api/interestVocabulary'
import { isWithinLimit } from '../auth/requirements'
import CharacterCounter from './CharacterCounter'
import './InterestPicker.css'

interface InterestPickerProps {
  /** The preset bucket vocabulary to render as chips. */
  options: InterestOption[]
  /** Currently-selected preset slugs. */
  selectedSlugs: string[]
  /** Toggle a preset bucket on/off. */
  onToggleSlug: (slug: string) => void
  /** Freeform terms the user has added, in order. */
  freeformTerms: string[]
  /** Add one or more freeform terms (a comma-separated entry is split). */
  onAddFreeform: (terms: string[]) => void
  /** Remove a freeform term. */
  onRemoveFreeform: (term: string) => void
  /** Freeform terms the server rejected on the last save, shown inline. */
  rejected?: RejectedInterest[]
  /** Disable all controls (e.g. while saving). */
  disabled?: boolean
}

/**
 * The positive-interest picker (issues #446/#35): preset buckets as toggleable
 * chips plus a freeform entry that accepts a single term or a comma-separated
 * list. Fully controlled — the parent owns the selection so the same component
 * serves the Settings dialog (prefilled, removable) and the registration form
 * (empty, add-only). Removal is first-class: tap a selected chip to deselect,
 * or ✕ a freeform pill to drop it.
 */
function InterestPicker({
  options,
  selectedSlugs,
  onToggleSlug,
  freeformTerms,
  onAddFreeform,
  onRemoveFreeform,
  rejected = [],
  disabled = false,
}: InterestPickerProps) {
  const [input, setInput] = useState('')
  const selected = new Set(selectedSlugs)
  // Per-instance ids (same approach as Modal): hard-coded ones would collide if
  // two pickers ever mount together, breaking the label / aria-describedby
  // association for assistive tech.
  const inputId = useId()
  const hintId = useId()

  const parsed = parseFreeformInput(input)
  // Gate on the backend's per-term limit like every other length-limited input
  // here (see NewPostTab's isWithinLimit use). Without this a too-long term is
  // accepted into the list only to be dropped server-side — and at registration
  // the rejection isn't surfaced at all, so it would vanish silently.
  const isEveryTermWithinLimit = parsed.every(t => isWithinLimit(t, MAX_FREEFORM_INTEREST_LENGTH))
  // Gate on the count cap too. The parent silently drops anything past it while
  // commitFreeform clears the input regardless, so without this the user's text
  // just disappears. Count only terms not already listed, matching the parent's
  // case-insensitive dedupe — re-typing an existing term shouldn't consume room.
  const alreadyListed = new Set(freeformTerms.map(t => t.toLowerCase()))
  const newTermCount = parsed.filter(t => !alreadyListed.has(t.toLowerCase())).length
  const hasRoom = freeformTerms.length + newTermCount <= MAX_FREEFORM_INTERESTS
  const canAdd = parsed.length > 0 && isEveryTermWithinLimit && hasRoom
  // Falls back to the raw input when nothing parses (e.g. only commas/spaces).
  const longestTerm = parsed.reduce((a, b) => (b.length > a.length ? b : a), parsed[0] ?? input)

  function commitFreeform() {
    // Guard here too, not just on the button: Enter reaches this directly.
    // A blocked commit keeps the input so the user can shorten it.
    if (!canAdd) return
    onAddFreeform(parsed)
    setInput('')
  }

  return (
    <div className="interest-picker">
      <fieldset className="interest-picker__group" disabled={disabled}>
        <legend className="interest-picker__legend">Pick what you find positive</legend>
        <div className="interest-chips" role="group" aria-label="Interest categories">
          {options.map(option => {
            const isSelected = selected.has(option.slug)
            return (
              <button
                key={option.slug}
                type="button"
                className={`interest-chip${isSelected ? ' interest-chip--selected' : ''}`}
                aria-pressed={isSelected}
                onClick={() => onToggleSlug(option.slug)}
              >
                {option.name}
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="interest-picker__group">
        <label className="interest-picker__legend" htmlFor={inputId}>
          Add your own
        </label>
        {freeformTerms.length > 0 && (
          <ul className="interest-freeform-list" aria-label="Your added interests">
            {freeformTerms.map(term => (
              <li key={term} className="interest-pill">
                <span className="interest-pill__text">{term}</span>
                <button
                  type="button"
                  className="interest-pill__remove"
                  aria-label={`Remove ${term}`}
                  disabled={disabled}
                  onClick={() => onRemoveFreeform(term)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="interest-freeform-entry">
          <input
            id={inputId}
            className="search-bar"
            type="text"
            placeholder="e.g. hiking, jazz, baking"
            value={input}
            disabled={disabled}
            aria-describedby={hintId}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault()
                commitFreeform()
              }
            }}
          />
          <button
            type="button"
            className="modal__confirm"
            disabled={disabled || !canAdd}
            onClick={commitFreeform}
          >
            Add
          </button>
        </div>
        <p id={hintId} className="interest-picker__hint">
          Separate multiple with commas. Each is checked to keep things positive.
        </p>
        {/* Inline guidance so the disabled Add button isn't a dead end (the
            counter plays that role for the length limit). */}
        {!hasRoom && (
          <p className="interest-picker__hint" role="status">
            {freeformTerms.length >= MAX_FREEFORM_INTERESTS
              ? `You've added the maximum of ${MAX_FREEFORM_INTERESTS} interests. Remove one to add another.`
              : `That's more than the ${MAX_FREEFORM_INTERESTS}-interest maximum. Remove one, or add fewer at once.`}
          </p>
        )}
        {input.length > 0 && (
          // The limit is per term, not per entry, so count the longest parsed
          // term — otherwise a comma-separated list of short terms would read as
          // over the limit while Add (correctly) stayed enabled.
          <CharacterCounter value={longestTerm} max={MAX_FREEFORM_INTEREST_LENGTH} />
        )}
        {rejected.length > 0 && (
          <ul className="interest-rejected" role="alert">
            {/* Keyed by position: the text alone isn't guaranteed unique (an
                elided over-length term can collide with another), and a
                duplicate key would make React's reconciliation unstable. */}
            {rejected.map((r, index) => (
              <li key={`${index}-${r.text}`}>
                “{r.text}” {r.reason ?? 'was not added'}.
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default InterestPicker
