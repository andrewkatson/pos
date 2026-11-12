# Profiles

## Profile photos

A user's profile photo is stored on the user (`profile_image_url`) and served
next to their name in every list and detail payload as `author_profile_image_url`
with `author_profile_image_original_url` as the full-resolution fallback — the
same CloudFront-signed compressed-plus-original pairing post images use (see
[Serving post images](images.md#serving-post-images)), for the same reason (the compressed copy can
briefly lag; #252/#254). Only an **approved** photo is ever shown to anyone else.

An avatar is an image like any other, so it also carries a **BlurHash** (issue
#460, see [BlurHash placeholders](images.md#blurhash-placeholders-issue-387)): `profile_image_blurhash` on the user,
served as `author_profile_image_blurhash` next to the avatar URLs in every
list/detail payload and as `profile_image_blurhash` in profile details. All three
clients decode it into a blurred preview shown inside the avatar circle while the
photo loads — search results, follower/blocked lists, feed and comment bylines,
and the large profile header — instead of the flat placeholder. The worker
computes it best-effort when it **approves** a photo (a pending or rejected
upload is shown to nobody, so it needs none), it is always rewritten on approval
so a new photo can never inherit the old one's blur, and it is cleared when the
photo is removed. The hash is only serialized when the photo itself is — so a
requester the profile has blocked gets neither, and a leftover hash can never
blur in a picture that is no longer being served.

Setting a photo reuses the post upload path: the client uploads a re-encoded,
EXIF-stripped JPEG through the presigned-PUT flow (`POST /posts/upload-url/`,
which scopes the key to the uploading user), then calls `POST /profile/photo/`
with the returned URL. Because a profile photo is an image broadcast next to the
user's name across the whole network, it is **moderated exactly like a post
image** and off the request path (issue #282's async pipeline): the upload is
stored on the user as `pending_profile_image_url` with
`profile_image_status = "pending"` and classified by the same image cascade in a
worker (`classify_profile_photo`). On approval it becomes the live
`profile_image_url` and the previously approved photo is cleaned from S3; on
rejection it is dropped (its S3 object deleted) and the owner is told in-app via
`profile_image_status = "rejected"` and `profile_image_reason_code`, so they can
pick a different picture. A previously approved photo stays live and visible
while a new upload is under review, and a rejected upload never replaces it.
Profile photos are **not appealable** — unlike a post, the remedy is simply to
choose another image — so there is no appealable/final split or tombstone. The
owner's own profile-details response carries the pending/rejected state
(`profile_image_status`, `profile_image_reason_code`,
`pending_profile_image_url`); no one else ever sees it. `POST /profile/photo/remove/`
clears the photo entirely.

Reconciliation mirrors posts: `sweep_classifications` re-enqueues a photo stuck
in `pending` past the threshold, or — once its retry budget is spent — leaves it
pending (fail closed, never shown) and alerts an operator exactly once.

## Bios

A user can write a short free-text **bio** shown on their profile (issue #380).
It is stored on the user (`bio`, empty string when unset) and returned in the
profile-details payload (`GET /users/<username>/profile/`) — already moderated
on write, so it is safe to show. It is redacted (returned empty) for a
requester the profile has blocked, exactly like the stats and avatar there, so
a blocked user cannot read the blocker's bio by name. `POST /profile/bio/` with
`{"bio": "..."}` sets it; an empty or whitespace-only value clears it.

Unlike a profile photo, a bio is **plain text**, so it is moderated
**synchronously by the text classifier on write** — exactly like a username or a
comment — rather than through the async image pipeline. There is no
pending/approved lifecycle: a bio that fails the positivity check is rejected
with a `400` (carrying a `reason_code`) and **never stored**, leaving any
existing bio untouched. The remedy is simply to edit it, so a rejection is **not
appealable**. Bios are capped at `MAX_BIO_LENGTH` (500) characters, counted as
unicode code points like captions and comments.
