import { getCurrentUsername } from '../api/session'

/**
 * Where tapping a username should go.
 *
 * Your own name routes to the Profile tab (`/home`, which opens on Profile)
 * rather than the /profile/:username route, so you land on the profile that is
 * part of the app shell — with the bottom bar and the search field — instead of
 * a pushed, back-stacked copy of it (issue #347). Everyone else routes to their
 * own profile page as before.
 */
export function profilePathFor(username: string): string {
  if (username === getCurrentUsername()) {
    return '/home'
  }
  return `/profile/${encodeURIComponent(username)}`
}
