// Whether the signed-in user has accepted the current privacy policy (issue #620).
//
// The backend records the version each member last accepted
// (`policies_accepted_version`, read from GET /me/), so the re-accept prompt only
// shows when that is missing or older than the POLICY_VERSION this build
// bundles. The answer is cached in memory for the session: a page load or a new
// sign-in (persistSession and clearSession both reset it) asks the backend
// again. PrivacyPolicyReacceptGate drives the check and shows the prompt.
//
//   unknown  → nobody has asked the backend yet for this session
//   checking → GET /me/ is in flight
//   accepted → nothing to ask (on record, or accepted in this session)
//   needed   → show the prompt (nothing current on record, or the check failed)

import { POLICY_VERSION } from '../privacyPolicy'

export type PrivacyPolicyStatus = 'unknown' | 'checking' | 'accepted' | 'needed'

type Listener = () => void

let status: PrivacyPolicyStatus = 'unknown'
// Bumped by every reset, so a check that was in flight for a previous session
// can't settle the status of the next one.
let generation = 0
const listeners = new Set<Listener>()

function setStatus(next: PrivacyPolicyStatus): void {
  if (status === next) return
  status = next
  listeners.forEach(listener => listener())
}

/**
 * Whether an accepted version on record covers the version this build shows.
 * Versions are `YYYY-MM-DD` dates, so they compare as strings; a member who
 * agreed to a newer copy on another, more up-to-date client is not asked to
 * agree to this build's older one.
 */
export function isPolicyVersionCurrent(acceptedVersion: string | null | undefined): boolean {
  return typeof acceptedVersion === 'string' && acceptedVersion >= POLICY_VERSION
}

export function getPrivacyPolicyStatus(): PrivacyPolicyStatus {
  return status
}

export function hasAcceptedPrivacyPolicy(): boolean {
  return status === 'accepted'
}

/**
 * Starts asking the backend, if nobody has yet this session. Returns a token for
 * finishPrivacyPolicyCheck, or null when a check is already running or settled.
 */
export function beginPrivacyPolicyCheck(): number | null {
  if (status !== 'unknown') return null
  setStatus('checking')
  return generation
}

/**
 * Settles a check begun by beginPrivacyPolicyCheck with the version on record
 * (null when there is none), or `undefined` when the request failed — which asks,
 * since it's the safe answer. Ignored if the session changed in the meantime.
 */
export function finishPrivacyPolicyCheck(
  check: number,
  acceptedVersion: string | null | undefined,
): void {
  if (check !== generation || status !== 'checking') return
  setStatus(isPolicyVersionCurrent(acceptedVersion) ? 'accepted' : 'needed')
}

/** Records that the user accepted the policy for the rest of this session. */
export function markPrivacyPolicyAccepted(): void {
  setStatus('accepted')
}

/** Forgets the answer. Called whenever a session starts or ends. */
export function resetPrivacyPolicyAcceptance(): void {
  generation += 1
  setStatus('unknown')
}

/** useSyncExternalStore-compatible subscription. */
export function subscribeToPrivacyPolicyAcceptance(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
