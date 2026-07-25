// Sharing posts and comments (issue #34). Scope A is an in-app share/copy-link
// action; the URL points at the website's existing /post/:postId route. Making
// that route publicly viewable and deep-linking it into the mobile apps is a
// tracked follow-up (Scope B), so a shared link currently opens the site and
// prompts login for signed-out recipients.

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
 * Nothing consumes the fragment yet, but it is forward-compatible with scrolling
 * to the comment once the detail page honors it, and it is harmless today.
 */
export function commentShareUrl(postIdentifier: string, commentIdentifier: string): string {
  return `${postShareUrl(postIdentifier)}#comment-${commentIdentifier}`
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
      if (err instanceof DOMException && err.name === 'AbortError') return 'shared'
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
