/**
 * Routes that must render for a visitor who is not — and may not be able to be
 * — signed in.
 *
 * These are the pages an app store, a search engine, or a locked-out user
 * reaches directly: Apple's required Support URL and the two legal URLs. The
 * catch is that a stale session in storage makes startup do authenticated work
 * (remember-me rotation, push registration), and a suspended or unverified
 * account fails that work with `account_banned` / `email_not_verified` — whose
 * handlers in `main.tsx` bounce the tab to /login. That would throw exactly the
 * people the support page exists for off the support page, so on these paths
 * the dead session is cleared in place and the page stays put.
 *
 * /delete-account is deliberately *not* here: it has to sign the visitor in
 * before it can delete anything, so it handles those same errors itself with a
 * message rather than silently continuing.
 */
export const PUBLIC_PATHS = ['/support', '/privacy-policy', '/terms-of-service'] as const

/** True when `pathname` is one of the signed-out-reachable pages above. */
export function isPublicPath(pathname: string): boolean {
  const normalized =
    pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname
  return (PUBLIC_PATHS as readonly string[]).includes(normalized)
}
