import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient, ApiError } from '../api/client'
import { uploadImage } from '../api/s3Uploader'
import { isWithinLimit, MAX_BIO_LENGTH } from '../auth/requirements'
import type { FeedPost, FollowCategory, PostStatusResponse, ProfileDetails } from '../api/types'
import PostGrid from './PostGrid'
import Avatar from './Avatar'
import CharacterCounter from './CharacterCounter'

/** Relationship-category options shown once you follow someone (issue #392). */
const CATEGORY_OPTIONS: { value: FollowCategory; label: string }[] = [
  { value: 'following', label: 'Following' },
  { value: 'friend', label: 'Friend' },
  { value: 'family', label: 'Family' },
]

/** How often the bounded post-classification poll checks pending posts (#282). */
const STATUS_POLL_INTERVAL_MS = 3000
/** Poll budget: ~30s of checks after which reconciliation falls back to the
 * user's own Refresh (there is deliberately no standing timer in this app). */
const STATUS_POLL_MAX_ATTEMPTS = 10
/** At most this many pending posts are polled per round, keeping the worst
 * case (3 posts every 3s = 60 requests/min) inside the status endpoint's
 * 120/m per-user rate limit; older pending posts reconcile on refresh. */
const STATUS_POLL_MAX_POSTS = 3

interface ProfileViewProps {
  username: string
  /** Hides the follow/block actions, which don't apply to your own account. */
  isOwnProfile: boolean
  /** The signed-in user, passed to the grid so it can offer Delete on own posts. */
  currentUsername: string | null
}

/**
 * A user's profile body: stats, follow/block actions, and their post grid.
 * Mirrors iOS ProfileView / ProfileViewModel (optimistic follow/block,
 * paginated grid).
 *
 * Shared by the Profile tab (your own account, reached from the bottom bar per
 * issue #347) and the /profile/:username route (anyone else), so both render an
 * identical profile and the same in-place post actions.
 */
function ProfileView({ username, isOwnProfile, currentUsername }: ProfileViewProps) {
  const navigate = useNavigate()
  // Track mount state so async loads that resolve after navigating away don't
  // set state on an unmounted view.
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [profile, setProfile] = useState<ProfileDetails | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [isFollowing, setIsFollowing] = useState(false)
  const [followCategory, setFollowCategory] = useState<FollowCategory>('following')
  const [isBlocked, setIsBlocked] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Own profile-photo controls (issue #7). Uploading reuses the post image
  // pipeline (compress + EXIF-strip + presigned PUT) then hands the URL to
  // setProfilePhoto; the photo is classified asynchronously, so we reload the
  // profile afterwards to reflect the new pending/approved state.
  const [photoBusy, setPhotoBusy] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Own bio editing (issue #380). Unlike the photo, a bio is plain text
  // moderated synchronously on the server, so a rejection comes back inline as
  // an error and there is no pending/approved state to poll.
  const [bioEditing, setBioEditing] = useState(false)
  const [bioDraft, setBioDraft] = useState('')
  const [bioBusy, setBioBusy] = useState(false)
  const [bioError, setBioError] = useState<string | null>(null)

  const [posts, setPosts] = useState<FeedPost[]>([])
  const [page, setPage] = useState(0)
  const [canLoadMore, setCanLoadMore] = useState(true)
  // Start loading so the spinner shows on mount without a synchronous setState
  // inside the fetch effect.
  const [isLoadingPosts, setIsLoadingPosts] = useState(true)

  // Reconciling async classification (#282): a bounded number of status polls
  // after a pending post is seen, plus a dismissible notice for rejections.
  // Only your own posts ever carry a status — everyone else's pending/hidden
  // posts are filtered out server-side — so this is gated on isOwnProfile.
  const pollAttempts = useRef(0)
  const [pollTick, setPollTick] = useState(0)
  const [reviewNotice, setReviewNotice] = useState<string | null>(null)

  const loadProfile = useCallback(async () => {
    try {
      const details = await apiClient.getProfile(username)
      if (!isMounted.current) return
      setProfile(details)
      setIsFollowing(details.is_following)
      setFollowCategory(details.follow_category ?? 'following')
      setIsBlocked(details.is_blocked)
      setLoadFailed(false)
    } catch {
      // Could be a missing user or a transient network/server error — we can't
      // tell them apart, so offer a retry rather than a dead end. The Profile
      // tab has no other way back from this, since it can't be navigated away
      // from and re-entered like the pushed profile route can.
      if (isMounted.current) setLoadFailed(true)
    }
  }, [username])

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect (React flags that as cascading renders),
  // matching how the post load below is kicked off.
  useEffect(() => {
    void Promise.resolve().then(() => loadProfile())
  }, [loadProfile])

  const loadPosts = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      try {
        const newPosts = await apiClient.getPostsForUser(username, pageToLoad)
        if (!isMounted.current) return
        if (replace) {
          setPosts(newPosts)
          setCanLoadMore(newPosts.length > 0)
          setPage(newPosts.length > 0 ? 1 : 0)
        } else if (newPosts.length === 0) {
          setCanLoadMore(false)
        } else {
          setPosts(prev => [...prev, ...newPosts])
          setPage(prev => prev + 1)
        }
      } catch {
        if (isMounted.current) setCanLoadMore(false)
      } finally {
        if (isMounted.current) setIsLoadingPosts(false)
      }
    },
    [username],
  )

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect (React flags that as cascading renders).
  useEffect(() => {
    void Promise.resolve().then(() => loadPosts(0, true))
  }, [loadPosts])

  // Short bounded poll while any of your posts is pending classification
  // (#282). Runs only while this view is mounted, stops as soon as nothing is
  // pending or the budget is spent; the ordinary mount/Refresh reload is the
  // backstop after that.
  useEffect(() => {
    if (!isOwnProfile) return
    // The grid is newest-first, so this polls the most recent pending posts.
    const pendingPosts = posts.filter(p => p.status === 'pending').slice(0, STATUS_POLL_MAX_POSTS)
    if (pendingPosts.length === 0 || pollAttempts.current >= STATUS_POLL_MAX_ATTEMPTS) return
    const id = setTimeout(async () => {
      pollAttempts.current += 1
      try {
        const results = await Promise.allSettled(
          pendingPosts.map(p => apiClient.getPostStatus(p.post_identifier)),
        )
        if (!isMounted.current) return
        const statuses = results
          .filter((r): r is PromiseFulfilledResult<PostStatusResponse> => r.status === 'fulfilled')
          .map(r => r.value)
        const resolved = statuses.filter(s => s.status !== 'pending')
        if (resolved.length > 0) {
          const rejection = resolved.find(
            s => s.status === 'rejected' || s.status === 'rejected_final',
          )
          if (rejection) {
            setReviewNotice(
              rejection.message ?? 'One of your recent posts did not pass automated review.',
            )
          }
          // Reload from the server so the grid reflects the resolved state
          // (approved posts lose the badge; final rejections drop out).
          void loadPosts(0, true)
        } else {
          // Nothing resolved yet: re-arm the timer by bumping the tick.
          setPollTick(t => t + 1)
        }
      } catch {
        // A failed poll round just ends this cycle; Refresh remains available.
      }
    }, STATUS_POLL_INTERVAL_MS)
    return () => clearTimeout(id)
  }, [isOwnProfile, posts, pollTick, loadPosts])

  // Manual refresh reloads both the posts and the profile details
  // (follow/block/counts) so the whole view stays in sync — not just the grid.
  function refresh() {
    setIsLoadingPosts(true)
    // A manual refresh grants a fresh reconcile-poll budget (#282).
    pollAttempts.current = 0
    apiClient
      .getProfile(username)
      .then(details => {
        if (!isMounted.current) return
        setProfile(details)
        setIsFollowing(details.is_following)
        setFollowCategory(details.follow_category ?? 'following')
        setIsBlocked(details.is_blocked)
      })
      .catch(() => {
        // Deliberately not loadProfile(): a failed manual refresh keeps the
        // already-loaded profile on screen rather than replacing it with the
        // retry prompt, since the user still has working data in front of them.
      })
    void loadPosts(0, true)
  }

  // Deleting from the grid drops the post locally and decrements the stat, so
  // the count doesn't contradict the grid until the next refresh (issue #267).
  function handlePostDeleted(postIdentifier: string) {
    setPosts(prev => prev.filter(post => post.post_identifier !== postIdentifier))
    setProfile(p => (p ? { ...p, post_count: Math.max(0, p.post_count - 1) } : p))
  }

  async function handlePhotoSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Clear the input so picking the same file again still fires onChange.
    event.target.value = ''
    if (!file || photoBusy) return
    setPhotoBusy(true)
    setErrorMessage(null)
    try {
      const imageUrl = await uploadImage(file)
      await apiClient.setProfilePhoto({ image_url: imageUrl })
      if (!isMounted.current) return
      // Reload so the header shows the new photo / review state. On async
      // backends it reads back as 'pending'; the eager (no-Redis) path and the
      // stub have already approved it.
      await loadProfile()
    } catch {
      if (isMounted.current) {
        setErrorMessage('Could not update your profile photo. Please try again.')
      }
    } finally {
      if (isMounted.current) setPhotoBusy(false)
    }
  }

  async function handleRemovePhoto() {
    if (photoBusy) return
    setPhotoBusy(true)
    setErrorMessage(null)
    try {
      await apiClient.removeProfilePhoto()
      if (!isMounted.current) return
      await loadProfile()
    } catch {
      if (isMounted.current) {
        setErrorMessage('Could not remove your profile photo. Please try again.')
      }
    } finally {
      if (isMounted.current) setPhotoBusy(false)
    }
  }

  function startEditingBio() {
    setBioDraft(profile?.bio ?? '')
    setBioError(null)
    setBioEditing(true)
  }

  function cancelEditingBio() {
    setBioEditing(false)
    setBioError(null)
  }

  async function handleSaveBio() {
    if (bioBusy) return
    // Guard on the same code-point limit the counter shows and the server
    // enforces; an empty draft is allowed and clears the bio.
    if (!isWithinLimit(bioDraft, MAX_BIO_LENGTH)) return
    setBioBusy(true)
    setBioError(null)
    try {
      const { bio } = await apiClient.setBio({ bio: bioDraft })
      if (!isMounted.current) return
      setProfile(p => (p ? { ...p, bio } : p))
      setBioEditing(false)
    } catch (err) {
      if (!isMounted.current) return
      // A moderation rejection (or length error) comes back as a 400 with a
      // human-readable message; show it inline so the user can edit and retry.
      setBioError(
        err instanceof ApiError && err.status === 400
          ? err.message
          : 'Could not update your bio. Please try again.',
      )
    } finally {
      if (isMounted.current) setBioBusy(false)
    }
  }

  async function toggleFollow() {
    if (isBusy) return
    setIsBusy(true)
    const wasFollowing = isFollowing
    try {
      if (wasFollowing) {
        await apiClient.unfollowUser(username)
        setIsFollowing(false)
        // Clear the relationship category so in-memory state matches the API
        // contract (follow_category is null when not following) and doesn't go
        // stale for any later UI that reads it.
        setFollowCategory('following')
        setProfile(p =>
          p ? { ...p, follow_category: null, follower_count: Math.max(0, p.follower_count - 1) } : p,
        )
      } else {
        await apiClient.followUser(username)
        setIsFollowing(true)
        setFollowCategory('following')
        setProfile(p => (p ? { ...p, follow_category: 'following', follower_count: p.follower_count + 1 } : p))
      }
    } catch {
      /* state is only updated after a successful call, so nothing to revert */
    } finally {
      setIsBusy(false)
    }
  }

  async function changeCategory(next: FollowCategory) {
    if (isBusy || next === followCategory) return
    setIsBusy(true)
    const previous = followCategory
    // Optimistic: reflect the choice immediately, revert if the call fails.
    setFollowCategory(next)
    try {
      await apiClient.setFollowCategory(username, next)
      setProfile(p => (p ? { ...p, follow_category: next } : p))
    } catch {
      setFollowCategory(previous)
    } finally {
      setIsBusy(false)
    }
  }

  async function toggleBlock() {
    if (isBusy) return
    setIsBusy(true)
    const wasFollowing = isFollowing
    try {
      await apiClient.toggleBlock(username)
      const nowBlocked = !isBlocked
      setIsBlocked(nowBlocked)
      // Blocking severs the follow relationship on the backend; reflect that in
      // the follow button and the follower count so the stats stay consistent.
      if (nowBlocked && wasFollowing) {
        setIsFollowing(false)
        // Blocking severs the follow, so clear the category too (matches the
        // API contract: follow_category is null when not following).
        setFollowCategory('following')
        setProfile(p =>
          p ? { ...p, follow_category: null, follower_count: Math.max(0, p.follower_count - 1) } : p,
        )
      }
    } catch {
      /* state is only updated after a successful call, so nothing to revert */
    } finally {
      setIsBusy(false)
    }
  }

  if (loadFailed) {
    return (
      <div className="profile-load-failed">
        <p className="muted">Couldn't load {username}'s profile.</p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setLoadFailed(false)
            setIsLoadingPosts(true)
            void loadProfile()
            void loadPosts(0, true)
          }}
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <>
      {errorMessage && (
        <div className="auth-error" role="alert">
          <p>{errorMessage}</p>
          <button
            type="button"
            className="auth-error__dismiss"
            aria-label="Dismiss error"
            onClick={() => setErrorMessage(null)}
          >
            ✕
          </button>
        </div>
      )}

      <div className="profile-header">
        <div className="profile-identity">
          <Avatar
            // The owner previews their own not-yet-approved upload immediately;
            // everyone else (and the owner once approved) sees the live photo.
            src={
              (isOwnProfile && profile?.pending_profile_image_url) ||
              profile?.profile_image_url
            }
            // Fall back to the previously approved photo, not the pending URL, so
            // if a pending preview fails to load the owner still sees their live
            // avatar (the approved photo stays visible while a new one is under
            // review) rather than dropping to the placeholder.
            originalSrc={profile?.profile_image_original_url}
            username={username}
            size="lg"
          />
          <div>
            <div className="profile-identity__name">{username}</div>
            {isOwnProfile && (
              <div className="profile-photo-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  disabled={photoBusy}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {profile?.profile_image_url || profile?.pending_profile_image_url
                    ? 'Change photo'
                    : 'Add photo'}
                </button>
                {(profile?.profile_image_url || profile?.pending_profile_image_url) && (
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={photoBusy}
                    onClick={() => void handleRemovePhoto()}
                  >
                    Remove
                  </button>
                )}
                {photoBusy && <span className="spinner" aria-label="Working" />}
                {!photoBusy && profile?.profile_image_status === 'pending' && (
                  <span className="profile-photo-status">
                    Your new photo is being reviewed.
                  </span>
                )}
                {!photoBusy && profile?.profile_image_status === 'rejected' && (
                  <span className="profile-photo-status">
                    Your last photo wasn't approved — try another.
                  </span>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={handlePhotoSelected}
                />
              </div>
            )}
          </div>
        </div>

        <div className="profile-stats">
          <div>
            <span className="profile-stat__count">{profile?.post_count ?? posts.length}</span>
            <span className="profile-stat__label">Posts</span>
          </div>
          {/* Only your own follow lists are viewable, so the counts are a
              tap-through on your own profile and plain stats on anyone else's
              (issue #8). */}
          {isOwnProfile ? (
            <button
              type="button"
              className="profile-stat profile-stat--action"
              onClick={() => navigate('/followers')}
            >
              <span className="profile-stat__count">{profile?.follower_count ?? 0}</span>
              <span className="profile-stat__label">Followers</span>
            </button>
          ) : (
            <div>
              <span className="profile-stat__count">{profile?.follower_count ?? 0}</span>
              <span className="profile-stat__label">Followers</span>
            </div>
          )}
          {isOwnProfile ? (
            <button
              type="button"
              className="profile-stat profile-stat--action"
              onClick={() => navigate('/following')}
            >
              <span className="profile-stat__count">{profile?.following_count ?? 0}</span>
              <span className="profile-stat__label">Following</span>
            </button>
          ) : (
            <div>
              <span className="profile-stat__count">{profile?.following_count ?? 0}</span>
              <span className="profile-stat__label">Following</span>
            </div>
          )}
        </div>

        {profile?.membership_number != null && (
          <p className="profile-membership" title="Join number — position in line since launch">
            🎉 Member #{profile.membership_number.toLocaleString()}
          </p>
        )}

        {/* Bio (issue #380): shown to everyone when set; the owner can edit it
            inline. Editing state is only ever offered on your own profile. */}
        <div className="profile-bio">
          {bioEditing ? (
            <div className="profile-bio__edit">
              <label className="auth-label" htmlFor="profile-bio-input">
                Your bio
              </label>
              <textarea
                id="profile-bio-input"
                className="text-area"
                rows={4}
                value={bioDraft}
                placeholder="Tell people a little about yourself"
                disabled={bioBusy}
                onChange={e => setBioDraft(e.target.value)}
              />
              <CharacterCounter value={bioDraft} max={MAX_BIO_LENGTH} />
              {bioError && (
                <p className="auth-error" role="alert">
                  {bioError}
                </p>
              )}
              <div className="profile-bio__actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={bioBusy || !isWithinLimit(bioDraft, MAX_BIO_LENGTH)}
                  onClick={() => void handleSaveBio()}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="btn btn-outline"
                  disabled={bioBusy}
                  onClick={cancelEditingBio}
                >
                  Cancel
                </button>
                {bioBusy && <span className="spinner" aria-label="Saving" />}
              </div>
            </div>
          ) : (
            <>
              {profile?.bio ? (
                <p className="profile-bio__text">{profile.bio}</p>
              ) : (
                isOwnProfile && <p className="profile-bio__empty muted">You haven't added a bio yet.</p>
              )}
              {isOwnProfile && profile && (
                <button type="button" className="btn btn-outline" onClick={startEditingBio}>
                  {profile.bio ? 'Edit bio' : 'Add bio'}
                </button>
              )}
            </>
          )}
        </div>

        {!isOwnProfile && (
          <div className="profile-actions">
            <button
              type="button"
              className={`btn ${isFollowing ? 'btn-outline' : 'btn-primary'}`}
              disabled={isBusy}
              onClick={toggleFollow}
            >
              {isFollowing ? 'Following' : 'Follow'}
            </button>
            {isFollowing && (
              <label className="profile-category">
                <span className="visually-hidden">Relationship category</span>
                <select
                  className="select-input"
                  aria-label={`Relationship with ${username}`}
                  value={followCategory}
                  disabled={isBusy}
                  onChange={e => void changeCategory(e.target.value as FollowCategory)}
                >
                  {CATEGORY_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              type="button"
              className={`btn ${isBlocked ? 'btn-danger--filled' : 'btn-danger'}`}
              disabled={isBusy}
              onClick={toggleBlock}
            >
              {isBlocked ? 'Unblock' : 'Block'}
            </button>
          </div>
        )}
      </div>

      <button
        type="button"
        className="refresh-button"
        aria-label="Refresh"
        disabled={isLoadingPosts}
        onClick={refresh}
      >
        <span aria-hidden="true">↻</span> Refresh
      </button>

      {reviewNotice && (
        <div className="auth-error" role="alert">
          <p>{reviewNotice}</p>
          <button
            type="button"
            className="auth-error__dismiss"
            aria-label="Dismiss notice"
            onClick={() => setReviewNotice(null)}
          >
            ✕
          </button>
        </div>
      )}

      {posts.length === 0 && !isLoadingPosts ? (
        <p className="muted">
          {isOwnProfile ? "You haven't posted anything yet." : `${username} hasn't posted anything yet.`}
        </p>
      ) : (
        <PostGrid
          posts={posts}
          currentUsername={currentUsername}
          onPostDeleted={handlePostDeleted}
          onError={setErrorMessage}
        />
      )}

      {isLoadingPosts && (
        <div className="center-spinner">
          <span className="spinner" />
        </div>
      )}
      {canLoadMore && !isLoadingPosts && posts.length > 0 && (
        <button
          type="button"
          className="load-more"
          onClick={() => {
            setIsLoadingPosts(true)
            void loadPosts(page, false)
          }}
        >
          Load more
        </button>
      )}
    </>
  )
}

export default ProfileView
