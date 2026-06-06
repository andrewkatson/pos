// Client-side mirrors of the backend validation patterns in
// backend/user_system/constants.py. Keeping these in one place lets the live
// requirement hints and the form-validity checks share a single source of
// truth so they can never drift apart.
//
//   password    = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=_])(?=\S+$).{8,}$
//   alphanumeric = ^\w{10,500}$   (used for usernames)

export interface Requirement {
  label: string
  met: boolean
}

export function getPasswordRequirements(password: string): Requirement[] {
  return [
    { label: 'At least 8 characters', met: password.length >= 8 },
    { label: 'At least one number', met: /[0-9]/.test(password) },
    { label: 'At least one lowercase letter', met: /[a-z]/.test(password) },
    { label: 'At least one uppercase letter', met: /[A-Z]/.test(password) },
    {
      label: 'At least one special character (@#$%^&+=_)',
      met: /[@#$%^&+=_]/.test(password),
    },
    { label: 'No spaces', met: password.length > 0 && !/\s/.test(password) },
  ]
}

export function getUsernameRequirements(username: string): Requirement[] {
  const trimmed = username.trim()
  return [
    {
      label: 'Between 10 and 500 characters',
      met: trimmed.length >= 10 && trimmed.length <= 500,
    },
    { label: 'Letters, numbers, and underscores only', met: /^\w+$/.test(trimmed) },
  ]
}

export function allMet(requirements: Requirement[]): boolean {
  return requirements.every(r => r.met)
}
