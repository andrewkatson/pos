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
    const script = document.createElement('script')

    // Every failure has to leave things exactly as it found them, or Google
    // sign-in is dead for the rest of the session. Two things must be undone:
    //
    //  - the cached promise, so a later attempt isn't handed the rejected one
    //    (a blocked first load should not be permanent); and
    //  - the script element, because a tag that has already fired load or error
    //    never fires either again. Reusing one would leave the retry's promise
    //    unsettled forever — a button that hangs rather than reports, which is
    //    worse than the failure it was retrying.
    const fail = (message: string) => {
      loadPromise = null
      script.remove()
      reject(new Error(message))
    }

    script.addEventListener(
      'load',
      () => {
        if (window.google?.id) {
          resolve(window.google)
        } else {
          // Loaded but installed nothing usable, which is no better than not
          // loading at all — and just as retryable.
          fail('Google Identity Services loaded without an id API')
        }
      },
      { once: true },
    )
    script.addEventListener('error', () => fail('Could not load Google Identity Services'), {
      once: true,
    })

    // Always a fresh element. Concurrent callers are deduplicated by
    // `loadPromise` above, which is what stops a second tag being appended
    // while one is in flight; adopting a pre-existing tag from the DOM would
    // reintroduce the already-fired-its-events hang described above.
    script.src = GOOGLE_IDENTITY_SCRIPT_URL
    script.async = true
    script.defer = true
    document.head.appendChild(script)
  })

  return loadPromise
}

/** Test seam: forget any cached load so each test starts from a clean slate. */
export function resetGoogleIdentityServicesForTests(): void {
  loadPromise = null
}
