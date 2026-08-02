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

1. Already done: the target has the **Push Notifications** capability, and
   `Positive Only Social/Positive Only Social.entitlements` (`aps-environment`)
   is committed and wired up via `CODE_SIGN_ENTITLEMENTS` on both
   configurations. What still has to happen per-machine is provisioning — the
   signing team needs an APNs-enabled profile for the bundle id.
2. In the Apple Developer portal, create an **APNs Auth Key** (`.p8`) and note
   its Key ID and your Team ID. Give these to the backend (`APNS_AUTH_KEY*`,
   `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_TOPIC` = the app bundle id
   `com.katsonsoftware.goodvibesonly`; see the root README "Push notifications").
3. Development builds register **sandbox** tokens — set `APNS_USE_SANDBOX=true`
   on the backend for those.

## Notes

- The committed entitlements say `aps-environment: development`, and that is
  the value to leave in place. It is what Xcode's Push Notifications capability
  writes, and Xcode substitutes `production` when it re-signs against an App
  Store profile on export, so shipped builds talk to production APNs without
  the file changing. Hardcoding `production` instead would break Release builds
  installed on a device with a development profile, which is the only Release
  path this repo has — there is no fastlane, no `ExportOptions.plist`, and no
  archive workflow, so distribution is a manual Xcode archive-and-export. If
  that ever becomes automated with explicit entitlements, revisit this.
- CI is unaffected by the entitlements file because `ios-tests.yml` builds with
  `CODE_SIGNING_ALLOWED=NO`. Without it, an entitlements file makes xcodebuild
  run `ProcessProductPackaging` and emit `.xcent` plists, which needs signing
  assets the runners do not have. Simulator test bundles are never signed.
- Pushes are user-visible alerts, so no `remote-notification` background mode is
  required.
- A denied permission or a simulator (which has no APNs) just no-ops.
