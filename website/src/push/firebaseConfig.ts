// Firebase Web config for FCM-for-web push (issues #342/#343).
//
// These are public client identifiers (not secrets), injected at build time as
// VITE_FIREBASE_* env vars — the same mechanism as VITE_API_BASE_URL (see
// website/deploy-web.sh). When any required value is unset — local dev, tests,
// or a deploy where push has not been provisioned yet — push registration is a
// no-op, mirroring the backend's "unconfigured provider = no-op" behavior. Push
// is a nudge, never the source of truth (#282 reconciliation is), so silently
// doing nothing is the correct degradation.

export interface FirebaseWebConfig {
  apiKey: string
  authDomain: string
  projectId: string
  messagingSenderId: string
  appId: string
}

function readEnv(key: string): string {
  const env = typeof import.meta !== 'undefined' ? import.meta.env : undefined
  const value = env?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

export const firebaseConfig: FirebaseWebConfig = {
  apiKey: readEnv('VITE_FIREBASE_API_KEY'),
  authDomain: readEnv('VITE_FIREBASE_AUTH_DOMAIN'),
  projectId: readEnv('VITE_FIREBASE_PROJECT_ID'),
  messagingSenderId: readEnv('VITE_FIREBASE_MESSAGING_SENDER_ID'),
  appId: readEnv('VITE_FIREBASE_APP_ID'),
}

// The Web Push VAPID public key, from the Firebase console (Cloud Messaging →
// Web configuration → "Web Push certificates"). getToken requires it for web.
export const firebaseVapidKey = readEnv('VITE_FIREBASE_VAPID_KEY')

/** True only when every value push needs is present. */
export function isPushConfigured(): boolean {
  return Boolean(
    firebaseConfig.apiKey &&
      firebaseConfig.projectId &&
      firebaseConfig.messagingSenderId &&
      firebaseConfig.appId &&
      firebaseVapidKey,
  )
}
