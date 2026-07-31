import { useId, useState } from 'react'
import type { InterestOption, RejectedInterest } from '../api/types'
import { MAX_FREEFORM_INTEREST_LENGTH, parseFreeformInput } from '../api/interestVocabulary'
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

  function commitFreeform() {
    const terms = parseFreeformInput(input)
    if (terms.length > 0) onAddFreeform(terms)
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
            disabled={disabled || parseFreeformInput(input).length === 0}
            onClick={commitFreeform}
          >
            Add
          </button>
        </div>
        <p id={hintId} className="interest-picker__hint">
          Separate multiple with commas. Each is checked to keep things positive.
        </p>
        {input.length > 0 && <CharacterCounter value={input} max={MAX_FREEFORM_INTEREST_LENGTH} />}
        {rejected.length > 0 && (
          <ul className="interest-rejected" role="alert">
            {rejected.map(r => (
              <li key={r.text}>
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
