// Google Identity Services (issue #10).
//
// GIS is loaded from Google's own CDN rather than bundled: Google requires the
// script to be served from accounts.google.com (it is versioned and revoked
// there), and there is no npm package that would be correct to pin instead.
// It is loaded lazily, on the pages that actually show the button, so the rest
// of the app never pays for it.
//
// The button hands back a *credential*: a Google ID token, which is posted
// straight to the backend. Nothing here decides who anyone is — that is
// backend/user_system/google_auth.py's job.

export const GOOGLE_IDENTITY_SCRIPT_URL = 'https://accounts.google.com/gsi/client'

/** The web OAuth client ID, or '' when Google sign-in is not configured.
 *
 * Read on each call rather than captured at module load so tests can stub the
 * env var; Vite inlines import.meta.env at build time, so a real build still
 * folds this to a constant.
 */
export function googleClientId(): string {
  const configured =
    typeof import.meta !== 'undefined'
      ? (import.meta.env?.VITE_GOOGLE_CLIENT_ID as string | undefined)
      : undefined
  return (configured ?? '').trim()
}

/**
 * Whether to offer Google sign-in at all.
 *
 * Unset means the feature is a silent no-op, matching how push is configured
 * (src/push/firebaseConfig.ts): a build without a client ID simply shows no
 * Google button rather than rendering one that could only ever fail.
 */
export function isGoogleSignInConfigured(): boolean {
  return googleClientId().length > 0
}

/** The slice of the GIS API this app uses. */
export interface GoogleCredentialResponse {
  credential: string
}

export interface GoogleIdentityServices {
  id: {
    initialize(config: {
      client_id: string
      callback: (response: GoogleCredentialResponse) => void
      auto_select?: boolean
      cancel_on_tap_outside?: boolean
      use_fedcm_for_prompt?: boolean
    }): void
    renderButton(
      parent: HTMLElement,
      options: {
        type?: 'standard' | 'icon'
        theme?: 'outline' | 'filled_blue' | 'filled_black'
        size?: 'small' | 'medium' | 'large'
        text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
        shape?: 'rectangular' | 'pill' | 'circle' | 'square'
        width?: number
        logo_alignment?: 'left' | 'center'
      },
    ): void
    disableAutoSelect(): void
  }
}

declare global {
  interface Window {
    google?: GoogleIdentityServices
  }
}

// One shared in-flight promise: several components can ask for GIS at once (the
// login page mounts one button, a route change mounts another), and each must
// get the same script rather than appending another <script> tag.
let loadPromise: Promise<GoogleIdentityServices> | null = null

/** Load the GIS script, resolving with the `google` global it installs. */
export function loadGoogleIdentityServices(): Promise<GoogleIdentityServices> {
  if (window.google?.id) {
    return Promise.resolve(window.google)
  }
  if (loadPromise) {
    return loadPromise
  }

  loadPromise = new Promise<GoogleIdentityServices>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${GOOGLE_IDENTITY_SCRIPT_URL}"]`,
    )
    const script = existing ?? document.createElement('script')

    const onLoad = () => {
      if (window.google?.id) {
        resolve(window.google)
      } else {
        // The script loaded but installed nothing usable — treat it as a
        // failure rather than resolving with an object we can't call.
        reject(new Error('Google Identity Services loaded without an id API'))
      }
    }
    const onError = () => {
      // Let a later attempt retry: a blocked or offline first load should not
      // permanently disable the button for the rest of the session.
      loadPromise = null
      reject(new Error('Could not load Google Identity Services'))
    }

    script.addEventListener('load', onLoad, { once: true })
    script.addEventListener('error', onError, { once: true })

    if (!existing) {
      script.src = GOOGLE_IDENTITY_SCRIPT_URL
      script.async = true
      script.defer = true
      document.head.appendChild(script)
    }
  })

  return loadPromise
}

/** Test seam: forget any cached load so each test starts from a clean slate. */
export function resetGoogleIdentityServicesForTests(): void {
  loadPromise = null
}
