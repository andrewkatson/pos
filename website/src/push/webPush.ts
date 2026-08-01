// FCM-for-web push registration (issues #342/#343).
//
// After login (and on a restored session) we ask for notification permission,
// obtain an FCM registration token, and upload it to POST /devices/register/ so
// the backend can best-effort notify the user when a post is rejected off the
// request path (#282). Everything here is best-effort and guarded: an
// unconfigured Firebase project, an unsupported browser, a denied permission,
// or a network error all just leave the user relying on in-app reconciliation,
// exactly as the design intends. Nothing here ever throws to its caller.

import { apiClient } from '../api/client'
import { firebaseConfig, firebaseVapidKey, isPushConfigured } from './firebaseConfig'

// Served from website/public/ at a stable root scope (see deploy-web.sh).
const SERVICE_WORKER_URL = '/firebase-messaging-sw.js'

let inFlight: Promise<void> | null = null
// The active foreground-message subscription. registerForPush can run more than
// once (login + session restore), so we keep a single subscription and replace
// it rather than stacking a new onMessage handler — and duplicate banners — each
// time.
let foregroundUnsubscribe: (() => void) | null = null

interface RegisterOptions {
  /** Request notification permission if the user hasn't decided yet. Set on the
   * explicit post-login call; left false on a passive session restore so a
   * returning user isn't prompted on every page load. */
  promptIfNeeded?: boolean
}

/**
 * Register (or refresh) this browser for push. De-duplicated so the login and
 * session-restore call sites can both fire without racing, and fully
 * best-effort: any failure is swallowed.
 */
export function registerForPush(options: RegisterOptions = {}): Promise<void> {
  if (inFlight) return inFlight
  inFlight = doRegister(options).finally(() => {
    inFlight = null
  })
  return inFlight
}

async function doRegister({ promptIfNeeded = false }: RegisterOptions): Promise<void> {
  try {
    // Only for a signed-in user, and only when push is actually configured.
    if (!apiClient.isAuthenticated() || !isPushConfigured()) return
    if (typeof window === 'undefined' || typeof navigator === 'undefined') return
    if (!('serviceWorker' in navigator) || !('Notification' in window) || !('PushManager' in window)) {
      return
    }

    // A denied permission is sticky until the user resets it; never re-prompt.
    if (Notification.permission === 'denied') return
    if (Notification.permission !== 'granted') {
      if (!promptIfNeeded) return
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') return
    }

    // Import the SDK lazily so the guards above (and the whole non-push app) pay
    // nothing for Firebase when push is off or unsupported.
    const { isSupported, getMessaging, getToken, onMessage } = await import('firebase/messaging')
    // Check messaging support BEFORE registering the worker, so a browser that
    // has Service Workers but not FCM never gets a root-scope worker installed
    // for nothing.
    if (!(await isSupported())) return

    // The worker can't read import.meta.env, so pass the (public) Firebase
    // config in the registration URL's query string for it to initialize with.
    const swUrl = `${SERVICE_WORKER_URL}?config=${encodeURIComponent(JSON.stringify(firebaseConfig))}`
    const registration = await navigator.serviceWorker.register(swUrl)

    const { initializeApp, getApps } = await import('firebase/app')
    const app = getApps()[0] ?? initializeApp(firebaseConfig)
    const messaging = getMessaging(app)

    const token = await getToken(messaging, {
      vapidKey: firebaseVapidKey,
      serviceWorkerRegistration: registration,
    })
    if (!token) return
    await apiClient.registerDevice({ platform: 'web', token })

    // A foreground message doesn't raise a system notification on its own, so
    // surface one ourselves; the service worker's notificationclick handler
    // deep-links it to the rejected post. Replace any prior subscription so
    // repeated registerForPush calls can't stack duplicate handlers.
    foregroundUnsubscribe?.()
    foregroundUnsubscribe = onMessage(messaging, (payload) => {
      const title = payload.notification?.title ?? 'Good Vibes Only'
      const body = payload.notification?.body ?? ''
      const deepLink = payload.data?.deep_link
      // showNotification returns a Promise; swallow a rejection explicitly (a
      // bare `void` still surfaces an unhandled rejection) — this module is
      // best-effort and must never throw.
      registration.showNotification(title, { body, data: { deep_link: deepLink } }).catch(() => {})
    })
  } catch {
    // Best-effort: push is a nudge, never the source of truth (#282).
  }
}
