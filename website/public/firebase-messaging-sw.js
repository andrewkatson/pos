/* Firebase Cloud Messaging service worker (issues #342/#343).
 *
 * Receives background push for FCM-for-web and routes a click to the rejected
 * post's deep link. A service worker cannot read the app's build-time env, so
 * the (public) Firebase config is passed in this worker's registration URL
 * query string (see src/push/webPush.ts) and parsed below.
 *
 * The compat SDK is loaded from gstatic and must match the `firebase` dependency
 * in package.json, which is pinned to an exact version (not a ^range) for that
 * reason — bump both together.
 */
importScripts('https://www.gstatic.com/firebasejs/12.17.0/firebase-app-compat.js')
importScripts('https://www.gstatic.com/firebasejs/12.17.0/firebase-messaging-compat.js')

function readConfig() {
  try {
    const raw = new URLSearchParams(self.location.search).get('config')
    return raw ? JSON.parse(raw) : null
  } catch (err) {
    return null
  }
}

const config = readConfig()
if (config && config.apiKey) {
  firebase.initializeApp(config)
  const messaging = firebase.messaging()

  // Fires for data-only messages. When the backend includes a `notification`
  // block, FCM auto-displays it and its webpush.fcm_options.link drives the
  // click; this handler is the fallback that still surfaces anything else.
  messaging.onBackgroundMessage((payload) => {
    const notification = payload.notification || {}
    const data = payload.data || {}
    // showNotification returns a Promise that can reject (permission revoked
    // after registration, a transient worker error). Swallow it explicitly, as
    // the foreground handler in src/push/webPush.ts does: leaving it unhandled
    // just prints noise, and background push is best-effort either way.
    self.registration
      .showNotification(notification.title || 'Good Vibes Only', {
        body: notification.body || '',
        data: { deep_link: data.deep_link },
      })
      .catch(() => {})
  })
}

// Restrict navigation to same-origin URLs so a malformed or external deep_link
// (a future push type, a backend bug) can't turn a tap into an open redirect /
// phishing navigation; anything else falls back to the app root.
function safeTarget(rawLink) {
  // A missing deep_link must fall back to '/', not become new URL(undefined)
  // -> "/undefined".
  if (!rawLink) return '/'
  try {
    const url = new URL(rawLink, self.location.origin)
    return url.origin === self.location.origin ? url.href : '/'
  } catch (err) {
    return '/'
  }
}

// Open (or focus) the rejected post when a notification is tapped.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const data = event.notification.data || {}
  const target = safeTarget(data.deep_link)
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          // Return the navigate -> focus chain so waitUntil actually awaits the
          // navigation before the SW is allowed to terminate; otherwise the
          // window can get focused without reliably landing on deep_link.
          if ('navigate' in client) {
            return client.navigate(target).then((navigated) => (navigated || client).focus())
          }
          return client.focus()
        }
      }
      return self.clients.openWindow ? self.clients.openWindow(target) : undefined
    }),
  )
})
