# Images

## Serving post images

Post images live in two S3 buckets: clients upload the original to the source
bucket (`AWS_STORAGE_BUCKET_NAME`) and a Lambda mirrors a compressed copy to
`AWS_COMPRESSED_STORAGE_BUCKET_NAME` under the same key.

The compressed copy is also **resized**: the Lambda (`backend/tools/image_compressor.py`)
caps the long edge at 1440px (override with the Lambda's `MAX_DIMENSION_PX`
env var; smaller images are never upscaled) before stepping JPEG quality down
toward `TARGET_SIZE_KB`. Clients only ever show images at screen size, and a
full 12 MP camera photo (4032x3024) is slow to decode — on iOS it logged
`CVPixelBufferCreate returned err -6680` and fell back to software decoding.
Compressed copies written before the cap keep their full size until their
source object is rewritten (which re-triggers the Lambda). On top of that, the
iOS image views decode straight to the size they display at
(`VibesHelpers/ImageDownsampling.swift`), matching what Coil does on Android, so
even the full-resolution fallback never builds a full-size bitmap.

Both buckets are **private** (S3 Block Public Access + an Origin Access Control
bucket policy). Reads happen only through CloudFront, and the backend signs every
image URL it hands to a client, so an image is fetchable only with a valid,
time-limited signature — a bare object URL returns 403 (issues #332, #341).
Uploads are likewise never anonymous: clients PUT via short-lived presigned URLs
minted by `POST /posts/upload-url/` (issue #310), so no client ever holds AWS
credentials for either direction.

Because the two buckets hold the same object key, two CloudFront domains front
them (no URI rewriting needed):

- `CLOUDFRONT_IMAGES_DOMAIN` → distribution → compressed bucket. The serialized
  `image_url` is signed on this domain.
- `CLOUDFRONT_ORIGINALS_DOMAIN` → distribution → source bucket. The serialized
  `original_image_url` (the full-res fallback used while the async-compressed copy
  is still missing, #252/#254) is signed on this domain.

Signing lives in `backend/user_system/cloudfront.py` (`sign_compressed_url` /
`sign_original_url`), invoked from every post-serialization site in `views.py`. A
signed URL carries the object key as its path but **no bucket name**, and stays
valid for `CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS` (default 24h — comfortably longer
than a session, since clients embed these URLs in payloads they refetch on
mount/refresh, while still bounding a leaked URL). Server-side image access (the
classifier, `delete_image`, the orphan sweeper, `strip_image_metadata`) goes
through credentialed boto3 and is unaffected by the buckets being private.

If the CloudFront settings are unset — local dev, tests, or a not-yet-provisioned
deploy — signing degrades gracefully to the legacy unsigned URLs, so nothing
breaks; the read hole only actually closes once the infra below exists.

**Backend env vars:** `CLOUDFRONT_IMAGES_DOMAIN`, `CLOUDFRONT_ORIGINALS_DOMAIN`,
`CLOUDFRONT_KEY_PAIR_ID`, and the signing private key as either
`CLOUDFRONT_PRIVATE_KEY` (inline PEM) or `CLOUDFRONT_PRIVATE_KEY_PATH` (a mounted
file); optionally `CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS`.

**One-time AWS setup (not automated):**

1. Two CloudFront distributions with Origin Access Control to the compressed and
   source buckets, each on a custom domain (`images.smiling.social` /
   `originals.smiling.social`)
   with an ACM cert and DNS.
2. Turn on Block Public Access for both buckets and set a bucket policy allowing
   only the two OAC principals (removing any legacy public-read).
3. Create a CloudFront public key + key group (trusted signer) and attach it to
   both distributions; deliver the matching private key to the backend as
   `CLOUDFRONT_PRIVATE_KEY[_PATH]` and its id as `CLOUDFRONT_KEY_PAIR_ID`.

### BlurHash placeholders (issue #387)

Even with the `original_image_url` fallback, a grid tile is blank while its image
downloads — a grey/black square that flashes on every feed load. Each post
therefore carries a **BlurHash**: a ~30-character string
([woltapp/blurhash](https://github.com/woltapp/blurhash)) that encodes a tiny,
blurred version of the image. All three clients decode it locally and render the
blur in the tile *while the real image loads* (and leave it in place if the image
never loads), so a loading photo is a soft blur of itself instead of a flat box.

The BlurHash is stored on the post (`Post.image_blurhash`) and computed
best-effort by the async classification worker (`classify_post`), which already
has the image in hand — it downscales the image and encodes a 4x3 hash. It is
purely decorative: any failure (encode error, missing object, no credentials)
just leaves it null, and the clients fall back to their plain placeholder, so it
can never block a post from being published. It is skipped for final-rejected
posts (their image is deleted) and for text-only posts (which have no image), and
is serialized as `image_blurhash` alongside `image_url` in every listing/detail
payload. Older clients that don't know the field simply ignore it.

Profile photos carry a BlurHash of their own on exactly the same terms (issue
#460) — see [Profile photos](profiles.md#profile-photos).

Images published before this feature shipped have no hash and still flash a grey
tile. The `backfill_blurhash` management command (issues #438/#460) is the one-off
repair: it walks every post that has an `image_url` but a null `image_blurhash`,
and every user with an approved `profile_image_url` but a null
`profile_image_blurhash`, and runs the same encoder the worker uses. It is safe
to re-run — it only touches null hashes and never overwrites one the worker may
have set — and an image that can't be fetched/encoded is left null (still grey)
and examined at most once per run (so a broken object never loops the command); a
later run re-attempts it, letting a transient failure recover. Supports
`--dry-run`, `--limit`, `--batch-size`, and `--target posts|profiles|all`
(default `all`).

## Post image cleanup

Post images live in two S3 buckets: clients upload the original to the source
bucket (`AWS_STORAGE_BUCKET_NAME`) and a Lambda mirrors a compressed copy to
`AWS_COMPRESSED_STORAGE_BUCKET_NAME` under the same key. Profile photos live in
the same buckets under the same `{user_id}/` prefix and are cleaned up the same
way.

Every client strips image metadata before uploading. Each uploader (web
`s3Uploader.ts`, iOS `AWSManager.swift`, Android `ImageUploader.kt`) always
decodes the picked photo and re-encodes it as a fresh JPEG rather than sending
the original file, so no EXIF — most importantly the camera's GPS coordinates —
ever reaches the source bucket. Any orientation is baked into the pixels first
so the picture still displays upright. The compression Lambda likewise re-saves
without EXIF, so the compressed bucket is metadata-free too.

Images uploaded before clients stripped metadata can be cleaned in place with
the `strip_image_metadata` management command. It sweeps both buckets and
rewrites, losslessly (pixel data is copied verbatim, never re-encoded), any
JPEG that carries metadata: EXIF/XMP, IPTC, comments, and post-EOI trailers
are dropped, keeping only the EXIF Orientation tag so old photos — whose
pixels were never rotated upright by a client — still display correctly.
Already-clean objects are left untouched, so re-running it is cheap and safe.
Use `--dry-run` to preview. It needs the backend's AWS credentials with
`s3:ListBucket`, `s3:GetObject`, and `s3:PutObject` on both buckets, and
rewriting a source-bucket object re-triggers the compression Lambda (harmless
— it just refreshes the compressed copy).

Because the upload
happens before the backend ever sees the post, images can be left behind:
when a post is rejected outright by the classifier, deleted, or its appeal is
denied. Cleanup happens at two levels (see `backend/user_system/s3.py`):

- **Inline** — `delete_image` removes the key from both buckets the moment a
  post is deleted, fails the pre-filter, or is finally rejected by the
  classification worker. It is best-effort: failures are logged and never
  block the request (or the worker).
- **Sweeper** — the `cleanup_orphan_images` management command lists both
  buckets and deletes any object no live `Post` **and no user profile photo**
  references. Both a user's approved `profile_image_url` and any
  `pending_profile_image_url` still under review are treated as live, so the
  sweep never reclaims an avatar out from under a user or deletes an upload
  mid-review. A grace window (default 24h, `--grace-hours`) protects objects too
  new to have become a post yet and the brief window where the Lambda writes a
  compressed copy just after a rejection cleaned up the original. Run it with
  `--dry-run` to preview. It is scheduled as a daily systemd timer on the app
  host (`setup-django.sh`), not in CI, because it needs both the database and
  AWS credentials.

The backend's IAM credentials need `s3:DeleteObject` on both buckets for either
path to take effect, plus `s3:ListBucket` on both buckets for the sweeper to
enumerate them (without it `cleanup_orphan_images` fails with AccessDenied).
