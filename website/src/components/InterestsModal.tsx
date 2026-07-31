import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { InterestOption, RejectedInterest } from '../api/types'
import { MAX_FREEFORM_INTERESTS } from '../api/interestVocabulary'
import Modal from './Modal'
import InterestPicker from './InterestPicker'

interface InterestsModalProps {
  onClose: () => void
  /** Called after a successful save with the confirmation message. */
  onSaved: (message: string) => void
}

/**
 * The Settings "Interests" dialog (issues #446/#35). Prefills the picker from
 * the user's current selection so preset buckets show selected and freeform
 * terms show as removable pills, then saves the full remaining set — so
 * deselecting a bucket or deleting a term removes it (the endpoint's
 * full-replace semantics). Template: TwoFactorAuthModals' ChangePasswordModal.
 */
function InterestsModal({ onClose, onSaved }: InterestsModalProps) {
  const [options, setOptions] = useState<InterestOption[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [freeform, setFreeform] = useState<string[]>([])
  const [rejected, setRejected] = useState<RejectedInterest[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Saving is a full replace, so it must never run on state we failed to load:
  // the empty defaults would wipe every stored interest. Save stays disabled
  // until the current selection is actually in hand.
  const [hasLoaded, setHasLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    // The preset vocabulary is public reference data, so it is best-effort —
    // the same way RegisterPage treats it. Failing to fetch it must not take
    // the dialog down with it: with the selection loaded the user can still
    // remove freeform terms and save. Only the chips would be missing.
    apiClient
      .getInterestOptions()
      .then(opts => {
        if (!cancelled) setOptions(opts.options)
      })
      .catch(() => {
        // Non-fatal; the preset section simply renders empty (see below).
      })
    // The current selection is what Save replaces, so this is the call that
    // gates saving — a full replace built on state we never loaded would wipe
    // everything the user has stored.
    apiClient
      .getInterests()
      .then(current => {
        if (cancelled) return
        setSelected(current.categories)
        setFreeform(current.freeform)
        setHasLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your interests. Please try again.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function toggleSlug(slug: string) {
    setSelected(prev => (prev.includes(slug) ? prev.filter(s => s !== slug) : [...prev, slug]))
  }

  function addFreeform(terms: string[]) {
    setFreeform(prev => {
      const seen = new Set(prev.map(t => t.toLowerCase()))
      const next = [...prev]
      for (const term of terms) {
        const key = term.toLowerCase()
        if (!seen.has(key) && next.length < MAX_FREEFORM_INTERESTS) {
          seen.add(key)
          next.push(term)
        }
      }
      return next
    })
  }

  function removeFreeform(term: string) {
    setFreeform(prev => prev.filter(t => t !== term))
  }

  async function handleSave() {
    // Guarded here too, not just on the button: a full replace built from
    // never-loaded state would clear everything the user has stored.
    if (!hasLoaded) return
    setIsSaving(true)
    setError(null)
    setRejected([])
    try {
      const result = await apiClient.setInterests({ categories: selected, freeform })
      // Reflect server truth: some freeform terms may have been rejected, and
      // the stored buckets are the union of picks and whatever the accepted
      // terms mapped to. Re-seed both from the response, exactly as the initial
      // load does — otherwise a dialog left open after a partial rejection
      // would show different chips than the same dialog reopened.
      setFreeform(result.freeform.accepted)
      setSelected(result.categories)
      if (result.freeform.rejected.length > 0) {
        // Keep the dialog open so the user sees which terms were dropped.
        setRejected(result.freeform.rejected)
        setIsSaving(false)
        return
      }
      onSaved('Your interests have been updated.')
    } catch {
      setError('Could not save your interests. Please try again.')
      setIsSaving(false)
    }
  }

  return (
    <Modal
      title="Your Interests"
      body="Pick topics you enjoy to see more of them in your feed. You can remove any at any time."
    >
      {isLoading ? (
        <p className="interest-picker__hint">Loading…</p>
      ) : (
        <>
          {error && (
            <div className="auth-error" role="alert">
              <p>{error}</p>
            </div>
          )}
          {/* Say why the preset chips are missing rather than leaving an
              unexplained empty section; the rest of the dialog still works. */}
          {hasLoaded && options.length === 0 && (
            <p className="interest-picker__hint" role="status">
              Topic suggestions couldn’t be loaded. You can still add your own below.
            </p>
          )}
          <InterestPicker
            options={options}
            selectedSlugs={selected}
            onToggleSlug={toggleSlug}
            freeformTerms={freeform}
            onAddFreeform={addFreeform}
            onRemoveFreeform={removeFreeform}
            rejected={rejected}
            disabled={isSaving}
          />
        </>
      )}
      <div className="modal__actions">
        <button type="button" className="modal__cancel" onClick={onClose} disabled={isSaving}>
          Cancel
        </button>
        <button
          type="button"
          className="modal__confirm"
          onClick={handleSave}
          disabled={isLoading || isSaving || !hasLoaded}
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </Modal>
  )
}

export default InterestsModal
