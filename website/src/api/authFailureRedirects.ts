import { apiClient } from './client'
import { clearSession } from './session'
import { isPublicPath } from '../publicPaths'

/**
 * The bits of `window.location` these handlers need, injected so the wiring can
 * be tested without a real document.
 */
export interface LocationLike {
  pathname: () => string
  assign: (url: string) => void
}

/**
 * Install the global "this session is no longer usable" handlers.
 *
 * A restored session that turns out to be suspended or unverified is dead: the
 * endpoints it would call all refuse it. Dropping it and landing on /login,
 * which explains why, is right nearly everywhere — but not on the pages that
 * are meant to be read signed out. A suspended user opening the support page to
 * find out how to appeal, or an App Store reviewer opening it with a stale
 * session in the tab, must not be redirected to a login screen they cannot get
 * past. On those paths the session is still cleared; the page just stays.
 */
export function installAuthFailureHandlers(location: LocationLike): void {
  apiClient.setOnAccountBanned(() => {
    clearSession()
    if (isPublicPath(location.pathname())) return
    location.assign('/login?suspended=1')
  })

  apiClient.setOnEmailNotVerified(() => {
    clearSession()
    if (isPublicPath(location.pathname())) return
    location.assign('/login?verify_email=1')
  })
}
