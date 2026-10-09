# Push notifications

Because async classification decides a rejection *after* `make_post` has
already returned `201`, the author is told out-of-band. Alongside the rejection
email, the worker fires a **best-effort native push notification** (issues #342
/ #343) so the pop-up reaches the user even with the app closed.

Push is a **nudge, never the source of truth.** Permissions get denied and
tokens go stale, so a user who never receives the push must still see the
correct outcome via in-app reconciliation (the authoritative `GET
posts/<id>/status/` path in [Post classification](post-classification.md)). Push and email never carry state; they only
bring the user back to look.

- **Device tokens.** Each client, after the OS grants notification permission,
  uploads its provider token to authenticated `POST /devices/register/`
  (`{platform, token}`, `platform ∈ {ios, android, web}`, `token` at most
  `MAX_DEVICE_TOKEN_LENGTH` = 1024 chars — bounded so it stays within the
  `(platform, token)` unique index) and re-uploads on rotation. A `DeviceToken`
  row is keyed by `(platform, token)`, so re-registering an existing token
  repoints it at the current user rather than duplicating (a device can change
  accounts).
- **Per-type preferences (Settings toggles).** Every push type is listed in
  `PUSH_TYPE_CHOICES` (currently just `post_rejected`, "Post moderation"; more
  are planned). A user can turn a type off in the app's Settings →
  **Notifications**: `GET/POST /notifications/preferences/` reads/writes them,
  returning one `{type, label, enabled}` row per known type, and `send_push`
  skips a type a user has disabled before contacting any provider. Preferences
  default to enabled (a `NotificationPreference` row exists only once toggled),
  and the clients render a toggle per returned row generically — so a **new push
  type shows up in every client's Settings with no client change**, just a new
  `PUSH_TYPE_CHOICES` entry and a `send_push` call that passes its type. (This is
  separate from the OS-level notification switch, which the user can also flip.)
- **Send path.** `user_system.push.send_push(user, payload, notification_type)`
  fans out to all of
  a user's tokens, called by `classify_post` on a resolved rejection — off the
  request path, on the same durable queue, best-effort. The payload's `data`
  map carries the `post_identifier`, a `type` (`post_rejected`), whether it is
  `appealable`, and a `deep_link` (`<FRONTEND_BASE_URL>/post/<id>`) so the client
  can open the rejected post and its appeal UI. **All `data` values are strings**
  — FCM's data map only carries strings, so the shape is identical across
  providers (both APNs and FCM deliver it under a `data` key) and clients parse
  `appealable` as `"true"`/`"false"` rather than a boolean.
- **Providers.** iOS delivers through **APNs** directly (token-based `.p8`
  auth); Android and web both go through **FCM** (web uses FCM-for-web, so it
  registers with `platform: web` and needs no separate Web Push/VAPID path).
- **Dead-token pruning.** When a provider reports a token as gone (`410` /
  `Unregistered` on APNs, `404` / `NOT_FOUND` / `UNREGISTERED` on FCM), the send
  path deletes that `DeviceToken` row so we neither leak rows nor keep paying to
  send to it.

**Secrets** (all optional — an unconfigured provider is a logged no-op, so
local dev, tests, and a not-yet-provisioned deploy send nothing and still import
cleanly; set them like the `EMAIL_*` / `CLOUDFRONT_*` credentials):

- **APNs (iOS):** `APNS_AUTH_KEY` (the `.p8` PEM inline) or `APNS_AUTH_KEY_PATH`
  (a mounted file), plus `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_TOPIC` (the app
  bundle id), and `APNS_USE_SANDBOX=true` for development app builds.
- **FCM (Android + web):** `FCM_CREDENTIALS` (the service-account JSON inline)
  or `FCM_CREDENTIALS_PATH` (a mounted file).
