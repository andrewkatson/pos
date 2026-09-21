import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import ProfilePage from './ProfilePage'
import type { ProfileDetails, PublicProfileDetails } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getProfile: vi.fn(),
    getPostsForUser: vi.fn(),
    getPublicProfile: vi.fn(),
    getPublicPostsForUser: vi.fn(),
    followUser: vi.fn(),
    unfollowUser: vi.fn(),
    setFollowCategory: vi.fn(),
    toggleBlock: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
    setBio: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

import { apiClient } from '../api/client'
const mockGetProfile = vi.mocked(apiClient.getProfile)
const mockGetPosts = vi.mocked(apiClient.getPostsForUser)
const mockGetPublicProfile = vi.mocked(apiClient.getPublicProfile)
const mockGetPublicPosts = vi.mocked(apiClient.getPublicPostsForUser)
const mockFollow = vi.mocked(apiClient.followUser)
const mockUnfollow = vi.mocked(apiClient.unfollowUser)
const mockSetCategory = vi.mocked(apiClient.setFollowCategory)
const mockLikePost = vi.mocked(apiClient.likePost)
const mockUnlikePost = vi.mocked(apiClient.unlikePost)
const mockReportPost = vi.mocked(apiClient.reportPost)
const mockRetractReport = vi.mocked(apiClient.retractReportPost)

const baseProfile: ProfileDetails = {
  username: 'bob',
  post_count: 2,
  follower_count: 10,
  following_count: 5,
  is_following: false,
  is_blocked: false,
  identity_is_verified: true,
  is_adult: true,
  membership_number: 7,
  bio: 'Explorer of small joys.',
}

function renderProfile() {
  return render(
    <MemoryRouter initialEntries={['/profile/bob']}>
      <Routes>
        <Route path="/profile/:username" element={<ProfilePage />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(apiClient.isAuthenticated).mockReturnValue(true)
  mockGetProfile.mockReset().mockResolvedValue(baseProfile)
  mockGetPosts.mockReset().mockResolvedValue([])
  mockGetPublicProfile.mockReset()
  mockGetPublicPosts.mockReset()
  mockFollow.mockReset().mockResolvedValue({ message: 'ok' })
  mockUnfollow.mockReset().mockResolvedValue({ message: 'ok' })
  mockSetCategory.mockReset().mockResolvedValue({ message: 'ok' })
  mockLikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockUnlikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockReportPost.mockReset().mockResolvedValue({ message: 'ok' })
  mockRetractReport.mockReset().mockResolvedValue({ message: 'ok' })
})

test('renders profile stats and follow button', async () => {
  renderProfile()
  expect(await screen.findByText('10')).toBeInTheDocument() // followers
  expect(screen.getByRole('button', { name: 'Follow' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Block' })).toBeInTheDocument()
})

test("shows the other member's public join number (#198)", async () => {
  renderProfile()
  expect(await screen.findByText('🎉 Member #7')).toBeInTheDocument()
})

test("shows another member's bio but no edit control (#380)", async () => {
  renderProfile()
  expect(await screen.findByText('Explorer of small joys.')).toBeInTheDocument()
  // Bio editing is only offered on your own profile.
  expect(screen.queryByRole('button', { name: 'Edit bio' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add bio' })).not.toBeInTheDocument()
})

test('following a user calls the API and updates the button', async () => {
  renderProfile()
  const followBtn = await screen.findByRole('button', { name: 'Follow' })
  await userEvent.click(followBtn)
  await waitFor(() => expect(mockFollow).toHaveBeenCalledWith('bob'))
  expect(screen.getByRole('button', { name: 'Following' })).toBeInTheDocument()
})

test('the relationship-category control appears only once following (#392)', async () => {
  renderProfile()
  await screen.findByRole('button', { name: 'Follow' })
  // Not following yet: no category control.
  expect(screen.queryByLabelText('Relationship with bob')).not.toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Follow' }))
  const categorySelect = await screen.findByLabelText('Relationship with bob')
  await userEvent.selectOptions(categorySelect, 'family')

  await waitFor(() => expect(mockSetCategory).toHaveBeenCalledWith('bob', 'family'))
})

test('a followed profile pre-selects its saved category (#392)', async () => {
  mockGetProfile.mockResolvedValue({ ...baseProfile, is_following: true, follow_category: 'friend' })
  renderProfile()

  const categorySelect = await screen.findByLabelText('Relationship with bob')
  expect(categorySelect).toHaveValue('friend')
})

test('shows empty state when the user has no posts', async () => {
  renderProfile()
  expect(await screen.findByText("bob hasn't posted anything yet.")).toBeInTheDocument()
})

test('renders the post grid and opens a post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()
  await userEvent.click(await screen.findByRole('button', { name: 'Post by bob' }))
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('refresh reloads both the profile details and the posts', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()
  await screen.findByRole('button', { name: 'Post by bob' })
  expect(mockGetPosts).toHaveBeenCalledTimes(1)
  expect(mockGetProfile).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  // Both the posts and the profile details (follow/block/counts) reload, so the
  // follow state can't go stale on refresh.
  await waitFor(() => expect(mockGetPosts).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(mockGetProfile).toHaveBeenCalledTimes(2))
  expect(mockGetPosts).toHaveBeenLastCalledWith('bob', 0)
  expect(mockGetProfile).toHaveBeenLastCalledWith('bob')
})

test('offers a retry when the profile fails to load', async () => {
  // A missing user and a transient network error are indistinguishable here, so
  // the view offers a way out rather than a dead end.
  mockGetProfile.mockRejectedValueOnce(new Error('boom'))
  renderProfile()

  expect(await screen.findByText("Couldn't load bob's profile.")).toBeInTheDocument()

  // Retrying succeeds and the profile renders.
  mockGetProfile.mockResolvedValue(baseProfile)
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('10')).toBeInTheDocument()
  expect(screen.queryByText("Couldn't load bob's profile.")).not.toBeInTheDocument()
})

// ---- In-place post actions on the grid (issue #267) ----

test('likes a post straight from the grid and reflects the new count', async () => {
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'bob',
      caption: 'hi',
      post_likes: 3,
      is_liked: false,
    },
  ])
  renderProfile()

  const like = await screen.findByRole('button', { name: 'Like post' })
  expect(screen.getByText('3')).toBeInTheDocument()
  await userEvent.click(like)

  await waitFor(() => expect(mockLikePost).toHaveBeenCalledWith('p1'))
  // Optimistic: the control flips and the count climbs without a refetch.
  expect(await screen.findByRole('button', { name: 'Unlike post' })).toBeInTheDocument()
  expect(screen.getByText('4')).toBeInTheDocument()
})

test('reverts the like when the request fails', async () => {
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'bob',
      caption: 'hi',
      post_likes: 3,
      is_liked: false,
    },
  ])
  mockLikePost.mockRejectedValue(new Error('nope'))
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Like post' }))

  // Back to the pre-click state, with the failure surfaced.
  expect(await screen.findByRole('alert')).toHaveTextContent('nope')
  expect(screen.getByRole('button', { name: 'Like post' })).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('reports a post from the grid', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by bob' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Report' }))
  await userEvent.type(screen.getByLabelText('Reason for reporting'), 'mean')
  await userEvent.click(screen.getByRole('button', { name: 'Submit Report' }))

  await waitFor(() => expect(mockReportPost).toHaveBeenCalledWith('p1', 'mean'))
  // The row now shows the reported flag.
  expect(await screen.findByLabelText('You reported this post')).toBeInTheDocument()
})

test('offers retract report when the post is already reported', async () => {
  // The listing endpoint carries is_reported/report_reason, so the grid knows
  // to offer retraction without opening the post first (issues #267, #176).
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'bob',
      caption: 'hi',
      is_reported: true,
      report_reason: 'was mean',
    },
  ])
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by bob' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Retract Report' }))
  // The original reason is shown back to the user before they confirm.
  expect(screen.getByLabelText('Your report reason')).toHaveValue('was mean')
  await userEvent.click(screen.getByRole('button', { name: 'Retract Report' }))

  await waitFor(() => expect(mockRetractReport).toHaveBeenCalledWith('p1'))
  await waitFor(() =>
    expect(screen.queryByLabelText('You reported this post')).not.toBeInTheDocument(),
  )
})

test('does not offer delete on another user post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by bob' }))
  expect(screen.queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument()
})

// ---- Sharing a profile (issue #510) ----

afterEach(() => {
  vi.unstubAllGlobals()
})

test('the profile options menu shares the profile link, copying it without an OS share sheet', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  // No navigator.share in jsdom, so shareLink() falls back to the clipboard.
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  renderProfile()
  await screen.findByText('10')

  await userEvent.click(screen.getByRole('button', { name: 'Profile options' }))
  const menu = screen.getByRole('menu', { name: 'Profile options' })
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Share' }))

  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/profile/bob`),
  )
  // The fallback tells the user the link is now on their clipboard.
  expect(await screen.findByRole('dialog', { name: 'Link copied' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'OK' }))
  expect(screen.queryByRole('dialog', { name: 'Link copied' })).not.toBeInTheDocument()
})

test('the profile options menu hands the link to the OS share sheet when there is one', async () => {
  const share = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { share })
  renderProfile()
  await screen.findByText('10')

  await userEvent.click(screen.getByRole('button', { name: 'Profile options' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Share' }))

  await waitFor(() =>
    expect(share).toHaveBeenCalledWith({ url: `${window.location.origin}/profile/bob` }),
  )
  // The share sheet did the telling; no "Link copied" prompt.
  expect(screen.queryByRole('dialog', { name: 'Link copied' })).not.toBeInTheDocument()
})

test('reports when the link could not be shared at all', async () => {
  // Neither a share sheet nor a clipboard: the only honest outcome is an error.
  vi.stubGlobal('navigator', {})
  renderProfile()
  await screen.findByText('10')

  await userEvent.click(screen.getByRole('button', { name: 'Profile options' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Share' }))

  expect(await screen.findByText('Could not share this profile.')).toBeInTheDocument()
})

// ---- Signed out: a shared profile link opened by someone with no account (issue #510) ----

const publicProfile: PublicProfileDetails = {
  username: 'bob',
  post_count: 1,
  follower_count: 10,
  following_count: 5,
  identity_is_verified: true,
  membership_number: 7,
  bio: 'Explorer of small joys.',
}

function renderSignedOut() {
  vi.mocked(apiClient.isAuthenticated).mockReturnValue(false)
  return render(
    <MemoryRouter initialEntries={['/profile/bob']}>
      <Routes>
        <Route path="/profile/:username" element={<ProfilePage />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/" element={<div>Landing page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('a signed-out visitor reads the profile through the public endpoints', async () => {
  mockGetPublicProfile.mockResolvedValue(publicProfile)
  mockGetPublicPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderSignedOut()

  // The header renders from the public payload...
  expect(await screen.findByText('10')).toBeInTheDocument()
  expect(screen.getByText('Explorer of small joys.')).toBeInTheDocument()
  expect(screen.getByText('🎉 Member #7')).toBeInTheDocument()
  // ...the grid too, and a tile still opens the post.
  await userEvent.click(await screen.findByRole('button', { name: 'Post by bob' }))
  expect(screen.getByText('Post page')).toBeInTheDocument()

  // Nothing went through the authenticated endpoints.
  expect(mockGetProfile).not.toHaveBeenCalled()
  expect(mockGetPosts).not.toHaveBeenCalled()
  expect(mockGetPublicProfile).toHaveBeenCalledWith('bob')
  expect(mockGetPublicPosts).toHaveBeenCalledWith('bob', 0)
})

test('a signed-out visitor sees a prompt to log in instead of Follow / Block', async () => {
  mockGetPublicProfile.mockResolvedValue(publicProfile)
  mockGetPublicPosts.mockResolvedValue([])
  renderSignedOut()
  await screen.findByText('10')

  expect(screen.queryByRole('button', { name: 'Follow' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Block' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Log in' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'join' })).toBeInTheDocument()
})

test('a signed-out grid has no in-place actions', async () => {
  mockGetPublicProfile.mockResolvedValue(publicProfile)
  mockGetPublicPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderSignedOut()
  await screen.findByRole('button', { name: 'Post by bob' })

  // Liking, saving, reporting and deleting all need a session.
  expect(screen.queryByRole('button', { name: 'Like post' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Save post' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Options for post by bob' })).not.toBeInTheDocument()
})

test('a signed-out visitor can still share the profile', async () => {
  mockGetPublicProfile.mockResolvedValue(publicProfile)
  mockGetPublicPosts.mockResolvedValue([])
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  renderSignedOut()
  await screen.findByText('10')

  await userEvent.click(screen.getByRole('button', { name: 'Profile options' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Share' }))

  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/profile/bob`),
  )
})

test('a signed-out visitor is told a profile that fails to load may not be public', async () => {
  // A shadow-banned account or a verified minor's 404s like a missing user, so
  // the recipient gets a hint that logging in may reveal it.
  mockGetPublicProfile.mockRejectedValue(new Error('not found'))
  mockGetPublicPosts.mockResolvedValue([])
  renderSignedOut()

  expect(await screen.findByText("Couldn't load bob's profile.")).toBeInTheDocument()
  expect(screen.getByText(/This profile may not be public/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
})

test('Back on a cold-opened shared link goes to the landing page rather than nowhere', async () => {
  mockGetPublicProfile.mockResolvedValue(publicProfile)
  mockGetPublicPosts.mockResolvedValue([])
  // A shared link opened in a fresh tab has a single-entry history.
  vi.spyOn(window.history, 'length', 'get').mockReturnValue(1)
  renderSignedOut()
  await screen.findByText('10')

  await userEvent.click(screen.getByRole('button', { name: '← Back' }))

  expect(screen.getByText('Landing page')).toBeInTheDocument()
})
