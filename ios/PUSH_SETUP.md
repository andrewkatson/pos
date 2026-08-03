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

1. Already done: the target has the **Push Notifications** capability, and the
   entitlements file carrying `aps-environment` is committed at
   `ios/Positive Only Social/Positive Only Social/Positive Only Social.entitlements`.
   It is wired up on both configurations as
   `CODE_SIGN_ENTITLEMENTS = "Positive Only Social/Positive Only Social.entitlements"`
   — that build setting is resolved relative to the `.xcodeproj`, which is why it
   has one fewer path component than the repo path above. What still has to happen
   per-machine is provisioning — the signing team needs an APNs-enabled profile for
   the bundle id.
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
- CI overrides the entitlements away with `CODE_SIGN_ENTITLEMENTS=""` in
  `ios-tests.yml`, so `aps-environment` — which a real build would need a
  matching provisioning profile for — never reaches what the runner builds.
  Signing itself stays on, which matters: `CODE_SIGNING_ALLOWED=NO` was tried
  and broke every test job, because an unsigned app carries no
  application-identifier and the iOS Keychain then fails every call with
  `errSecMissingEntitlement` (-34018). The build still succeeds when that
  happens, so the build job passing is not evidence the tests will run.
- Pushes are user-visible alerts, so no `remote-notification` background mode is
  required.
- A denied permission or a simulator (which has no APNs) just no-ops.
