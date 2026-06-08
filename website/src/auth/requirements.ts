// Client-side mirrors of the backend validation patterns in
// backend/user_system/constants.py. Keeping these in one place lets the live
// requirement hints and the form-validity checks share a single source of
// truth so they can never drift apart.
//
//   password    = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=_])(?=\S+$).{8,}$
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
      label: 'At least one special character (@#$%^&+=_)',
      didMeetRequirement: /[@#$%^&+=_]/.test(password),
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
