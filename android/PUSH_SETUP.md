# Android push setup (issues #342/#343)

The app receives push via **FCM** and uploads its token to
`POST /devices/register/` (`platform: android`). Push is best-effort and never
the source of truth — when it isn't configured the app builds and runs normally
and simply registers no device (the user learns async outcomes via in-app
reconciliation, #282).

## What's wired (code)

- `fcm/FcmConfig.kt` — reads the Firebase project identifiers from `BuildConfig`
  (populated from Gradle properties) and gates everything on `isConfigured`.
- `fcm/PushRegistrar.kt` — initializes a `FirebaseApp` **from those identifiers**
  (no `google-services.json` / plugin needed), fetches the FCM token and uploads
  it, and re-uploads on rotation.
- `fcm/PosFirebaseMessagingService.kt` — `onNewToken` (rotation) and
  `onMessageReceived` (foreground notification whose tap carries `post_identifier`).
- `fcm/PushNavigator.kt` + `NavGraph` — a tapped notification deep-links to the
  rejected post's detail. `MainActivity` requests `POST_NOTIFICATIONS` (Android
  13+) and reads the tap intent's extras.

## Why no `google-services.json` / plugin

Applying the `com.google.gms.google-services` plugin **requires** a
`google-services.json` at build time, which would break CI (there isn't one in
the repo). Instead the app builds `FirebaseOptions` by hand from `BuildConfig`,
so the Firebase dependency compiles and CI stays green without any secret file.

## To enable it on a build

Pass the (public) Firebase identifiers as Gradle properties — via `-P` or
`~/.gradle/gradle.properties` / a CI secret — from the Firebase console
(Project settings → your Android app, applicationId
`io.github.andrewkatson.positiveonlysocial`):

```properties
FCM_PROJECT_ID=your-project-id
FCM_APPLICATION_ID=1:1234567890:android:abcdef      # the "App ID"
FCM_API_KEY=AIza...                                 # the Android API key
FCM_SENDER_ID=1234567890                            # the "Project number"
```

The backend must use the **same** Firebase project's service-account JSON in
`FCM_CREDENTIALS` (root README "Push notifications") so its sends reach these
tokens.

> If you later prefer the standard `google-services.json` flow, add the
> `com.google.gms.google-services` plugin + the JSON and drop the manual
> `FirebaseOptions` init in `PushRegistrar`.
