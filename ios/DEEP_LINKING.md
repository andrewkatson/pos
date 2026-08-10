# iOS Universal Links (issue #382)

A shared `https://smiling.social/post/<id>` link opens the app instead of Safari
when the app is installed. If it isn't, the link opens the public web page
(issue #381) — so nothing about this is load-bearing: a failed association just
means links keep opening the browser.

## What's wired (code)

- `Positive Only Social.entitlements` carries
  `com.apple.developer.associated-domains` = `applinks:smiling.social` and
  `applinks:www.smiling.social`.
- `VibesHelpers/ShareURL.swift` — `ShareURL.parse(_:)` turns an incoming URL
  into a `SharedPostLink` (post id plus the optional `#comment-<id>` fragment),
  or nil when the URL is not one of ours. It is the exact inverse of the
  `ShareURL.post` / `ShareURL.comment` builders the share sheet uses, and is
  unit tested in `Positive_Only_SocialTests_ShareURL`.
- `Positive_Only_SocialApp.swift` — `.onOpenURL` parses the URL and hands the
  post id to `PushRouter`, the same bus a tapped push notification writes to.
  That is deliberate: the post detail lives inside `HomeView`, which only exists
  once logged in, so a link opened while signed out parks there and routes as
  soon as the user logs in rather than pushing an authenticated screen out of
  the Welcome flow.
- `https://smiling.social/.well-known/apple-app-site-association` is served from
  `website/public/.well-known/`, published by `website/deploy-web.sh` with an
  explicit `application/json` content type (the file has no extension, so a
  plain `s3 sync` would guess `binary/octet-stream` and iOS would reject it).

Only `/post/*` is claimed. Every other route belongs to the website, and
claiming them would hijack links the app has no screen for.

## To enable it (Apple Developer portal)

1. Enable the **Associated Domains** capability on the App ID
   `com.katsonsoftware.goodvibesonly`, then regenerate and re-download the
   provisioning profiles. Without this the entitlement is present in the source
   but signing fails, or the association is silently ignored.
2. Deploy the website so the AASA file is live at
   `https://smiling.social/.well-known/apple-app-site-association` over https,
   with no redirect, as `application/json`. Apple's CDN fetches it — allow time
   for it to pick up a change.
3. Install the app (a fresh install or an update triggers the association
   check) and tap a shared link from another app, e.g. Messages.

Verify with `https://app-site-association.cdn-apple.com/a/v1/smiling.social`,
which shows what Apple's CDN currently has cached for the domain.

## Notes

- The `appIDs` entry is `<Team ID>.<bundle id>` — `7L9M852R4K` and
  `com.katsonsoftware.goodvibesonly`, both already in `project.pbxproj`. Change
  either and the AASA file has to change with it.
- CI overrides entitlements away with `CODE_SIGN_ENTITLEMENTS=""`
  (`ios-tests.yml`), so the associated-domains key never reaches what the runner
  builds — same as `aps-environment`, see `PUSH_SETUP.md`.
- A `#comment-<id>` fragment is parsed and carried on `SharedPostLink`, and the
  post opens. Scrolling to that specific comment is web-only today; the parsed
  id is there for whoever wires it up.
