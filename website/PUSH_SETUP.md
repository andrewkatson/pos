# Web push setup (issues #342/#343)

The website receives push via **FCM-for-web** (Firebase Cloud Messaging JS SDK).
Push is best-effort and never the source of truth — when it isn't configured the
app still works and simply doesn't register a device (the user learns async
outcomes via in-app reconciliation, #282).

## What's wired

- `src/push/firebaseConfig.ts` — reads the public Firebase Web config from
  `VITE_FIREBASE_*` build-time env vars; `isPushConfigured()` gates everything.
- `src/push/webPush.ts` — `registerForPush()`: requests notification permission,
  obtains an FCM token, and uploads it via `POST /devices/register/`
  (`platform: web`). Called from `LoginPage` after login (prompts) and from
  `main.tsx` on a restored session (refresh only, no prompt).
- `public/firebase-messaging-sw.js` — the messaging service worker, served at
  the stable root path `/firebase-messaging-sw.js`. It receives the (public)
  Firebase config through its registration URL's query string (a worker can't
  read `import.meta.env`) and routes a notification tap to the rejected post's
  `deep_link`.

## To enable it on a deploy

1. Create a Firebase project and add a **Web app**; enable Cloud Messaging.
2. In Cloud Messaging → Web configuration, generate a **Web Push certificate**
   (VAPID key pair) and copy the public key.
3. Export these in the deploy environment before running `deploy-web.sh` (they
   are public client identifiers, not secrets):

   ```bash
   export VITE_FIREBASE_API_KEY=...
   export VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
   export VITE_FIREBASE_PROJECT_ID=<project>
   export VITE_FIREBASE_MESSAGING_SENDER_ID=...
   export VITE_FIREBASE_APP_ID=...
   export VITE_FIREBASE_VAPID_KEY=<public VAPID key>
   ```

4. The backend must have the **same** Firebase project's service-account JSON in
   `FCM_CREDENTIALS` (see the root README "Push notifications" section) so its
   sends reach these tokens.

## Notes

- Keep the compat SDK version in `public/firebase-messaging-sw.js` in step with
  the `firebase` version in `package.json`.
- The service worker is deployed with `no-cache` (see `deploy-web.sh`), so an
  updated worker is picked up on the next visit.
