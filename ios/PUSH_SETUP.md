# iOS push setup (issues #342/#343)

The app registers for **APNs** and uploads its device token to
`POST /devices/register/` (`platform: ios`). Push is best-effort and never the
source of truth — without the capability below it simply fails to register and
the user still learns async outcomes via in-app reconciliation (#282).

## What's wired (code)

- `state/PushNotifications.swift` — requests `UNUserNotificationCenter`
  authorization, registers with APNs, hex-encodes the device token and uploads
  it via `Networking.registerDevice`, and routes a tapped notification (reading
  `post_identifier` from the payload's `data` map) to `PushRouter`.
- `state/PushRouter.swift` — the shared bus a tap writes to.
- `AppDelegate` in `Positive_Only_SocialApp.swift` (via
  `@UIApplicationDelegateAdaptor`) forwards the APNs callbacks.
- `HomeView` requests authorization on appear (post-login) and, on a tapped
  notification, jumps to the Profile tab and pushes the rejected post's detail.

## To enable it (Xcode + Apple Developer)

1. In the target's **Signing & Capabilities**, add the **Push Notifications**
   capability. Xcode creates the entitlements file with `aps-environment` and
   provisions an APNs-enabled profile. (No entitlements file is committed here so
   CI's unsigned simulator build keeps working; adding the capability is a
   signing/provisioning step.)
2. In the Apple Developer portal, create an **APNs Auth Key** (`.p8`) and note
   its Key ID and your Team ID. Give these to the backend (`APNS_AUTH_KEY*`,
   `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_TOPIC` = the app bundle id
   `com.katsonsoftware.goodvibesonly`; see the root README "Push notifications").
3. Development builds register **sandbox** tokens — set `APNS_USE_SANDBOX=true`
   on the backend for those.

## Notes

- Pushes are user-visible alerts, so no `remote-notification` background mode is
  required.
- A denied permission or a simulator (which has no APNs) just no-ops.
