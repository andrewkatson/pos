// Sharing posts and comments (issues #34, #381). The share action hands off a
// link to the website's /post/:postId route, which renders for signed-out
// recipients too — a shared post is readable without an account as long as it
// is public. Deep-linking the same URL into the mobile apps is tracked
// separately (#382).

/**
 * The absolute URL for a post's detail page, rooted at the current deployment's
 * origin (so a link shared from smiling.social points back to smiling.social,
 * and a link shared from a preview/localhost stays self-consistent).
 */
export function postShareUrl(postIdentifier: string): string {
  return `${window.location.origin}/post/${postIdentifier}`
}

/**
 * The URL for a specific comment: the post page plus a `#comment-<id>` fragment.
 * The detail page resolves the fragment by scrolling to (and marking out) that
 * comment within its thread — see `sharedCommentId`.
 */
export function commentShareUrl(postIdentifier: string, commentIdentifier: string): string {
  return `${postShareUrl(postIdentifier)}#comment-${commentIdentifier}`
}

/**
 * The inverse of `commentShareUrl`: the comment id a location hash points at,
 * or null when the hash is absent or is not a comment link.
 *
 * The id must look like a UUID. The value is used to build a DOM id and to
 * match against rendered comments, so anything else is ignored rather than
 * trusted — a hash is attacker-supplied whenever a link is.
 */
export function sharedCommentId(hash: string): string | null {
  const match = /^#comment-([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$/.exec(hash)
  return match ? match[1] : null
}

/**
 * How a share attempt resolved, so callers can tailor their feedback:
 * - `shared`  — handed off to the OS share sheet (or the user dismissed it);
 * - `copied`  — no share sheet, so the link was copied to the clipboard instead;
 * - `failed`  — neither path worked (e.g. clipboard blocked).
 */
export type ShareResult = 'shared' | 'copied' | 'failed'

/**
 * Shares a URL using the Web Share API when the browser offers it (typically
 * mobile), otherwise copies it to the clipboard. A user cancelling the native
 * sheet throws `AbortError`; that is a deliberate no-op, not a failure, so it
 * still resolves to `shared`.
 */
export async function shareLink(url: string): Promise<ShareResult> {
  const nav = typeof navigator !== 'undefined' ? navigator : undefined

  if (nav && typeof nav.share === 'function') {
    try {
      await nav.share({ url })
      return 'shared'
    } catch (err) {
      // The user dismissing the share sheet is not an error worth surfacing.
      // Read `name` off the thrown value directly rather than testing
      // `instanceof DOMException`: the rejection isn't guaranteed to be a
      // same-realm DOMException (cross-realm, or a non-DOM throw), so an
      // `instanceof` check can miss a genuine cancel and wrongly fall through
      // to the clipboard.
      if (
        typeof err === 'object' &&
        err !== null &&
        (err as { name?: unknown }).name === 'AbortError'
      ) {
        return 'shared'
      }
      // Otherwise fall through and try the clipboard as a backstop.
    }
  }

  if (nav?.clipboard && typeof nav.clipboard.writeText === 'function') {
    try {
      await nav.clipboard.writeText(url)
      return 'copied'
    } catch {
      return 'failed'
    }
  }

  return 'failed'
}
