# Push notifications

Native push notifications tell a user about two things:

- **Post moderation** (issues #342 / #343). Because async classification
  decides a rejection *after* `make_post` has already returned `201`, the author
  is told out-of-band. Alongside the rejection email, the worker fires a
  **best-effort native push notification** so the pop-up reaches the user even
  with the app closed.
- **Social activity** (issue #444): a new post from someone you follow, a
  comment on your post or a reply to your comment, and a like on your post or
  comment. See [Activity notifications](#activity-notifications-issue-444).

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
- **Preferences (Settings toggles).** Every push type is listed in
  `PUSH_TYPE_TREE` as `(type, label, parent)`, a tree in display order with
  each parent before its children (issue #444):

  - `all` — "Push notifications", the master switch.
    - `post_rejected` — "Post moderation".
    - `new_post` — "New posts", with one child per relationship source:
      `new_post_following`, `new_post_friend`, `new_post_family`.
    - `new_comment` — "Comments and replies", with `new_comment_following`,
      `_friend`, `_family` and `_other`.
    - `new_like` — "Likes", with `new_like_following`, `_friend`, `_family` and
      `_other`.

  The source is the [relationship category](audience-and-relationships.md)
  the *recipient* gave the person who acted, on the recipient's own follow
  edge — "From people I follow", "From friends", "From family" — or "From
  everyone else" (`other`) when the recipient does not follow them. New posts
  only ever reach followers, so they have no `other` source.

  A user turns a type off in the app's Settings → **Notifications**: `GET/POST
  /notifications/preferences/` reads/writes them, returning one `{type, label,
  parent, enabled}` row per type, and `send_push` skips a push unless its type
  **and every ancestor** are on — so the master switch silences everything and
  a kind's switch silences its sources. Each row's `enabled` is the user's own
  setting for that row, so turning a parent back on restores the children as
  they were. Preferences default to enabled (a `NotificationPreference` row
  exists only once toggled). The clients render a toggle per returned row
  generically, indenting it under its `parent` and hiding it while any ancestor
  is off (a row whose parent is missing shows at the top level) — so a **new
  push type shows up in every client's Settings with no client change**, just a
  new `PUSH_TYPE_TREE` entry and a `send_push` call that passes its type. (This
  is separate from the OS-level notification switch, which the user can also
  flip.)
- **Send path.** `user_system.push.send_push(user, payload, notification_type)`
  fans out to all of
  a user's tokens, called by `classify_post` on a resolved rejection and by the
  activity jobs in `user_system.notifications` — off the request path, on the
  same durable queue, best-effort. The payload's `data` map carries the
  `post_identifier`, a `type` (`post_rejected`, `new_post`, `new_comment` or
  `new_like` — the kind, not the per-source preference type), and a `deep_link`
  (`<FRONTEND_BASE_URL>/post/<id>`); a rejection also says whether it is
  `appealable`. Every kind opens its post on tap: the rejected post and its
  appeal UI, the new post, or the post a comment or like landed on. Clients
  route only the types they know to a post, so a future kind is ignored rather
  than misrouted. **All `data` values are strings**
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

## Activity notifications (issue #444)

Who is told about what:

- **New post** — when a post is approved (the one-time pending → visible
  transition in `classify_post`, so once per post and never for a post that is
  rejected), each follower of the author who can see it, by the type for the
  category on their follow edge. Audience applies as it does in the feed: a
  friends-only post reaches only followers the author labeled friend or family.
- **Comment** — a top-level comment notifies the post's author ("commented on
  your post"). A reply notifies the thread's first commenter ("replied to your
  comment") and, when that is someone else, the post's author too ("replied to
  a comment on your post"). A comment hidden pending appeal notifies nobody.
- **Like** — a like on a post notifies its author, a like on a comment the
  comment's author. Only the first like by a given person on a given post or
  comment within 24 hours notifies, so like/unlike/like does not repeat it.

Nobody is told about their own activity, and every push requires the recipient
to be able to see the content right now — the same rules as feeds and comment
lists (hidden content, the author's privacy and audience, the comment's own
audience, age bands) — and nobody is told about a shadow-banned actor, or across
a block in either direction. The views and the worker only *enqueue* a job
(`notifications.notify_*`, inline when there is no Redis queue, otherwise after
the commit); the job re-reads the content when it runs, so a like withdrawn or
a comment hidden in the meantime sends nothing. These jobs carry no retry
budget: a missed push is harmless.

The jobs run on their own `notifications` queue (`PUSH_QUEUE_NAME`), drained by
the same `classification_worker`, which always takes from the classification
queue first, so notification work never queues ahead of moderation. A new post
is announced in batches of 50 followers, one job per batch. A full batch
enqueues the next one before it sends, so a batch that dies (say, a timeout
behind a slow provider) loses only its own followers. A batch loads blocks,
the post's audience, preferences and device tokens for all of its followers in
one query each, so its database cost does not grow with the batch, and
followers with no registered device are skipped without a send.

The title names who acted (for example "sam liked your comment") and the body
quotes up to 100 characters of the caption or comment. On Android, activity
arrives on its own "Activity" notification channel, separate from "Post
moderation", so it can be muted in the system settings without silencing
rejections. The FCM payload names the channel
(`android.notification.channel_id`), because a message that arrives while the
app is in the background is shown by the system without reaching the app's
code. The app registers both channels at launch so they exist before the first
such message.

**Secrets** (all optional — an unconfigured provider is a logged no-op, so
local dev, tests, and a not-yet-provisioned deploy send nothing and still import
cleanly; set them like the `EMAIL_*` / `CLOUDFRONT_*` credentials):

- **APNs (iOS):** `APNS_AUTH_KEY` (the `.p8` PEM inline) or `APNS_AUTH_KEY_PATH`
  (a mounted file), plus `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_TOPIC` (the app
  bundle id), and `APNS_USE_SANDBOX=true` for development app builds.
- **FCM (Android + web):** `FCM_CREDENTIALS` (the service-account JSON inline)
  or `FCM_CREDENTIALS_PATH` (a mounted file).
