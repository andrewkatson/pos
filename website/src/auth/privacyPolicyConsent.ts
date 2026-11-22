// Whether the signed-in user has accepted the current privacy policy (issue #620).
//
// For now this is unconditional: nothing records which version of the policy a
// user accepted, so every signed-in session is asked again — once per page load,
// and again on every sign-in (persistSession and clearSession both reset it).
// The flag lives in memory on purpose, so a reload counts as "opening the app"
// and re-prompts. When the backend starts recording
// an acceptance timestamp, this is the one place that decides whether the
// PrivacyPolicyReacceptGate shows.

type Listener = () => void

let accepted = false
const listeners = new Set<Listener>()

function notify(): void {
  listeners.forEach(listener => listener())
}

export function hasAcceptedPrivacyPolicy(): boolean {
  return accepted
}

/** Records that the user accepted the policy for the rest of this session. */
export function markPrivacyPolicyAccepted(): void {
  if (accepted) return
  accepted = true
  notify()
}

/** Forgets the acceptance. Called whenever a session starts or ends. */
export function resetPrivacyPolicyAcceptance(): void {
  if (!accepted) return
  accepted = false
  notify()
}

/** useSyncExternalStore-compatible subscription. */
export function subscribeToPrivacyPolicyAcceptance(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
