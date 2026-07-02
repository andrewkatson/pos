// Client-side mirrors of the backend validation patterns in
// backend/user_system/constants.py. Keeping these in one place lets the live
// requirement hints and the form-validity checks share a single source of
// truth so they can never drift apart.
//
//   password    = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*-)(?=\S+$).{8,}$
//   alphanumeric = ^\w{10,500}$   (used for usernames)

export interface Requirement {
  label: string
  didMeetRequirement: boolean
}

export function getPasswordRequirements(password: string): Requirement[] {
  return [
    { label: 'At least 8 characters', didMeetRequirement: password.length >= 8 },
    { label: 'At least one number', didMeetRequirement: /[0-9]/.test(password) },
    { label: 'At least one lowercase letter', didMeetRequirement: /[a-z]/.test(password) },
    { label: 'At least one uppercase letter', didMeetRequirement: /[A-Z]/.test(password) },
    {
      label: 'At least one dash (-)',
      didMeetRequirement: /-/.test(password),
    },
    {
      label: 'Adding other special characters (like !) is suggested',
      didMeetRequirement: true,
    },
    { label: 'No spaces', didMeetRequirement: password.length > 0 && !/\s/.test(password) },
  ]
}

export function getUsernameRequirements(username: string): Requirement[] {
  const trimmed = username.trim()
  return [
    {
      label: 'Between 10 and 500 characters',
      didMeetRequirement: trimmed.length >= 10 && trimmed.length <= 500,
    },
    {
      label: 'Letters, numbers, and underscores only',
      // Unicode-aware to mirror Python's \w (which matches Unicode word
      // characters for str patterns), unlike JavaScript's ASCII-only \w.
      didMeetRequirement: /^[\p{L}\p{N}_]+$/u.test(trimmed),
    },
  ]
}

export function allMet(requirements: Requirement[]): boolean {
  return requirements.every(r => r.didMeetRequirement)
}

// Maximum lengths for user-authored text, mirroring MAX_CAPTION_LENGTH /
// MAX_COMMENT_LENGTH in backend/user_system/constants.py.
export const MAX_CAPTION_LENGTH = 125
export const MAX_COMMENT_LENGTH = 500

// The fraction of the limit at which the counter starts warning the user that
// they are getting close (mirrored across iOS and Android).
export const NEAR_LIMIT_FRACTION = 0.9

// Counts unicode code points rather than UTF-16 code units, so the count
// matches Python's len() on the backend (which is what the server enforces).
// e.g. "💚" is one code point here, like it is one character server-side, even
// though "💚".length is 2 in JavaScript.
export function characterCount(text: string): number {
  return [...text].length
}

export function isWithinLimit(text: string, max: number): boolean {
  return characterCount(text) <= max
}
