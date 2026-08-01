import { ApiError, INVALID_TWO_FACTOR_CHALLENGE } from './client'
import { STUB_TOTP_CODE, StatefulStubbedAPI } from './StatefulStubbedAPI'
import { isTwoFactorRequired } from './types'
import type { RegisterRequest } from './types'

function register(api: StatefulStubbedAPI, username: string) {
  const body: RegisterRequest = {
    username,
    email: `${username}@example.com`,
    password: 'password123',
  }
  return api.register(body)
}

test('register authenticates the new user', async () => {
  const api = new StatefulStubbedAPI()

  const result = await register(api, 'ada')

  expect(result.username).toBe('ada')
  expect(api.isAuthenticated()).toBe(true)
  expect(api.getToken()).toBe(result.session_management_token)
})

test('registering with an adult date of birth marks the profile verified and adult', async () => {
  const api = new StatefulStubbedAPI()

  await api.register({
    username: 'grace',
    email: 'grace@example.com',
    password: 'password123',
    date_of_birth: '1990-01-01',
  })

  const profile = await api.getProfile('grace')
  expect(profile.identity_is_verified).toBe(true)
  expect(profile.is_adult).toBe(true)
})

test('registering with a minor date of birth verifies identity but is not adult', async () => {
  const api = new StatefulStubbedAPI()
  const thisYear = new Date().getFullYear()

  await api.register({
    username: 'kid',
    email: 'kid@example.com',
    password: 'password123',
    date_of_birth: `${thisYear - 10}-01-01`,
  })

  const profile = await api.getProfile('kid')
  expect(profile.identity_is_verified).toBe(true)
  expect(profile.is_adult).toBe(false)
})

test('register assigns sequential membership numbers in join order (#198)', async () => {
  const api = new StatefulStubbedAPI()

  const first = await register(api, 'ada')
  const second = await register(api, 'grace')
  const third = await register(api, 'katherine')

  expect(first.membership_number).toBe(1)
  expect(second.membership_number).toBe(2)
  expect(third.membership_number).toBe(3)
})

test('getProfile exposes the member join number to anyone (#198)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await register(api, 'grace')

  // A different signed-in user can still see grace's number.
  const graceProfile = await api.getProfile('grace')
  expect(graceProfile.membership_number).toBe(2)
})

test('register rejects duplicate usernames', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  await expect(register(api, 'ada')).rejects.toThrow('User already exists')
})

test('login fails with the wrong password', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  await expect(
    api.login({ username_or_email: 'ada', password: 'wrong' }),
  ).rejects.toThrow('Invalid username or password')
})

test('authenticated calls require a session', async () => {
  const api = new StatefulStubbedAPI()

  await expect(api.getFeed(0)).rejects.toBeInstanceOf(ApiError)
})

test('a created post shows up in another user feed and can be liked', async () => {
  const api = new StatefulStubbedAPI()

  await register(api, 'author')
  const created = await api.createPost({
    image_url: 'https://example.com/a.jpg',
    caption: 'a sunny day',
  })

  await register(api, 'viewer')
  const feed = await api.getFeed(0)
  expect(feed.map((p) => p.post_identifier)).toContain(created.post_identifier)
  expect(feed[0].author_username).toBe('author')

  await api.likePost(created.post_identifier)
  const details = await api.getPostDetails(created.post_identifier)
  expect(details.post_likes).toBe(1)
})

test('a text-only post round-trips with a null image_url (#307)', async () => {
  const api = new StatefulStubbedAPI()

  await register(api, 'author')
  const created = await api.createPost({ caption: 'words only' })

  await register(api, 'viewer')
  const feed = await api.getFeed(0)
  const post = feed.find((p) => p.post_identifier === created.post_identifier)
  expect(post).toBeDefined()
  expect(post?.image_url).toBeNull()

  const details = await api.getPostDetails(created.post_identifier)
  expect(details.image_url).toBeNull()
  expect(details.caption).toBe('words only')
})

test('you cannot like your own post', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const created = await api.createPost({
    image_url: 'https://example.com/a.jpg',
    caption: 'hello',
  })

  await expect(api.likePost(created.post_identifier)).rejects.toThrow('Cannot like own post')
})

test('the positivity stub rejects negative captions', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')

  await expect(
    api.createPost({ image_url: 'https://example.com/a.jpg', caption: 'a negative thought' }),
  ).rejects.toThrow('Text is not positive')
})

test('comment then reply builds a thread', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({
    image_url: 'https://example.com/a.jpg',
    caption: 'nice',
  })

  const comment = await api.commentOnPost(post.post_identifier, 'love this')
  await api.replyToCommentThread(
    post.post_identifier,
    comment.comment_thread_identifier,
    'agreed',
  )

  const threads = await api.getCommentsForPost(post.post_identifier, 0)
  expect(threads).toHaveLength(1)

  const comments = await api.getCommentsForThread(comment.comment_thread_identifier, 0)
  expect(comments.map((c) => c.body)).toEqual(['love this', 'agreed'])
})

test('follow then followed-feed surfaces the followed user posts', async () => {
  const api = new StatefulStubbedAPI()

  await register(api, 'author')
  const post = await api.createPost({
    image_url: 'https://example.com/a.jpg',
    caption: 'good vibes',
  })

  await register(api, 'follower')
  expect(await api.getFollowedFeed(0)).toEqual([])

  await api.followUser('author')
  const followed = await api.getFollowedFeed(0)
  expect(followed.map((p) => p.post_identifier)).toEqual([post.post_identifier])
})

test('blocking a user hides their profile stats and severs following', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  await api.createPost({ image_url: 'https://example.com/a.jpg', caption: 'hi' })

  await register(api, 'viewer')
  await api.followUser('author')
  await api.toggleBlock('author')

  const profile = await api.getProfile('author')
  expect(profile.is_blocked).toBe(true)
  expect(profile.is_following).toBe(false)
})

test('getBlockedUsers lists blocks sorted by username and empties after unblock', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'zed')
  await register(api, 'amy')

  await register(api, 'viewer')
  expect(await api.getBlockedUsers()).toEqual([])

  await api.toggleBlock('zed')
  await api.toggleBlock('amy')
  expect((await api.getBlockedUsers()).map((u) => u.username)).toEqual(['amy', 'zed'])

  // Toggling again unblocks.
  await api.toggleBlock('amy')
  expect((await api.getBlockedUsers()).map((u) => u.username)).toEqual(['zed'])
})

test('getFollowing lists the viewer\'s own follows sorted by username', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'zed')
  await register(api, 'amy')

  await register(api, 'viewer')
  expect(await api.getFollowing()).toEqual([])

  await api.followUser('zed')
  await api.followUser('amy')
  expect((await api.getFollowing()).map((u) => u.username)).toEqual(['amy', 'zed'])

  await api.unfollowUser('amy')
  expect((await api.getFollowing()).map((u) => u.username)).toEqual(['zed'])
})

test('getFollowers lists only the viewer\'s own followers, not their follows', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'viewer')

  // amy and zed each follow the viewer.
  await register(api, 'amy')
  await api.followUser('viewer')
  await register(api, 'zed')
  await api.followUser('viewer')

  const login = await api.login({ username_or_email: 'viewer', password: 'password123' })
  if (isTwoFactorRequired(login)) throw new Error('expected a session, not a challenge')

  expect((await api.getFollowers()).map((u) => u.username)).toEqual(['amy', 'zed'])
  // The viewer follows nobody — followers and following are distinct directions.
  expect(await api.getFollowing()).toEqual([])
})

test('logout clears the session token', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  await api.logout()

  expect(api.isAuthenticated()).toBe(false)
  await expect(api.getFeed(0)).rejects.toThrow()
})

test('password reset flow updates the password', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  await api.requestReset({ username_or_email: 'ada' })
  const verify = await api.verifyReset({
    username_or_email: 'ada',
    verification_token: 'stub_verification_token_ada',
  })
  await api.resetPassword({
    username: 'ada',
    email: 'ada@example.com',
    password: 'newpassword1',
    reset_token: verify.reset_token,
  })

  const login = await api.login({
    username_or_email: 'ada',
    password: 'newpassword1',
  })
  if (isTwoFactorRequired(login)) throw new Error('expected a session, not a challenge')
  expect(login.username).toBe('ada')
})

test('getCurrentUser returns the signed-in account’s own username and email', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  expect(await api.getCurrentUser()).toEqual({ username: 'ada', email: 'ada@example.com' })
})

test('changePassword enforces the current password and strength, then updates it', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  // Wrong current password is rejected.
  await expect(
    api.changePassword({ password: 'wrongpass1', new_password: 'NewPassword1' }),
  ).rejects.toThrow()

  // A weak new password is rejected, mirroring the backend strength policy, so
  // the stub can't mask a client that forgot to validate.
  await expect(
    api.changePassword({ password: 'password123', new_password: 'weak' }),
  ).rejects.toThrow()

  await api.changePassword({ password: 'password123', new_password: 'NewPassword1' })

  // Reusing the (now current) password is rejected.
  await expect(
    api.changePassword({ password: 'NewPassword1', new_password: 'NewPassword1' }),
  ).rejects.toThrow()

  // The old password no longer logs in; the new one does.
  await expect(api.login({ username_or_email: 'ada', password: 'password123' })).rejects.toThrow()
  const login = await api.login({ username_or_email: 'ada', password: 'NewPassword1' })
  if (isTwoFactorRequired(login)) throw new Error('expected a session, not a challenge')
  expect(login.username).toBe('ada')
})

// --- Appeals -----------------------------------------------------------------

async function makeReportHiddenPost(api: StatefulStubbedAPI) {
  await register(api, 'author')
  const post = await api.createPost({
    image_url: 'https://example.com/a.jpg',
    caption: 'flagged caption',
  })
  // Report past the stub hide threshold (one report per distinct user).
  for (let i = 0; i < 6; i += 1) {
    await register(api, `reporter${i}`)
    await api.reportPost(post.post_identifier, 'bad')
  }
  await api.login({ username_or_email: 'author', password: 'password123' })
  return post
}

test('getHiddenPosts is empty when nothing is hidden', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  await api.createPost({ image_url: 'https://example.com/a.jpg', caption: 'fine' })

  expect(await api.getHiddenPosts(0)).toEqual([])
})

test('a report-hidden post appears in getHiddenPosts with its reason', async () => {
  const api = new StatefulStubbedAPI()
  const post = await makeReportHiddenPost(api)

  const hidden = await api.getHiddenPosts(0)
  expect(hidden).toHaveLength(1)
  expect(hidden[0].post_identifier).toBe(post.post_identifier)
  expect(hidden[0].hidden_reason).toBe('reports')
  expect(hidden[0].has_appeal).toBe(false)
})

test('appealing a hidden post records a pending appeal and flips has_appeal', async () => {
  const api = new StatefulStubbedAPI()
  const post = await makeReportHiddenPost(api)

  const result = await api.submitAppeal({
    target_type: 'post',
    target_identifier: post.post_identifier,
    reason: 'please reconsider',
  })
  expect(result.appeal_identifier).toBeTruthy()

  const appeals = await api.getMyAppeals(0)
  expect(appeals).toHaveLength(1)
  expect(appeals[0].status).toBe('pending')
  expect(appeals[0].reason).toBe('please reconsider')

  const hidden = await api.getHiddenPosts(0)
  expect(hidden[0].has_appeal).toBe(true)
})

test('cannot appeal a post that is not hidden', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ image_url: 'https://example.com/a.jpg', caption: 'fine' })

  await expect(
    api.submitAppeal({ target_type: 'post', target_identifier: post.post_identifier, reason: 'x' }),
  ).rejects.toThrow('No appealable item with that identifier')
})

test('cannot appeal the same item twice', async () => {
  const api = new StatefulStubbedAPI()
  const post = await makeReportHiddenPost(api)
  await api.submitAppeal({ target_type: 'post', target_identifier: post.post_identifier, reason: 'a' })

  await expect(
    api.submitAppeal({ target_type: 'post', target_identifier: post.post_identifier, reason: 'b' }),
  ).rejects.toThrow('already been appealed')
})

test('rejects an invalid appeal target type', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')

  await expect(
    // 'ban' is not appealable in-app; cast past the type to exercise the guard.
    api.submitAppeal({ target_type: 'ban' as never, target_identifier: '1', reason: 'x' }),
  ).rejects.toThrow('Invalid target_type')
})

// ---------------------------------------------------------------------------
// Two-factor authentication
// ---------------------------------------------------------------------------

async function enableTwoFactor(api: StatefulStubbedAPI) {
  await api.setupTotp()
  return api.confirmTotp({ password: 'password123', totp_code: STUB_TOTP_CODE })
}

test('totp setup returns a secret and provisioning uri', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  const setup = await api.setupTotp()

  expect(setup.totp_secret.length).toBeGreaterThan(0)
  expect(setup.otpauth_uri.startsWith('otpauth://totp/')).toBe(true)
})

test('confirming with the stub code enables 2fa and returns recovery codes', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  const confirm = await enableTwoFactor(api)

  expect(confirm.totp_enabled).toBe(true)
  expect(confirm.recovery_codes).toHaveLength(10)
})

test('confirming with a wrong code fails and 2fa stays off', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await api.setupTotp()

  await expect(
    api.confirmTotp({ password: 'password123', totp_code: '000000' }),
  ).rejects.toThrow('Invalid two-factor code')

  // Login still single-step.
  const login = await api.login({ username_or_email: 'ada', password: 'password123' })
  expect('session_management_token' in login).toBe(true)
})

test('login for an enrolled account returns a challenge, and the code exchanges it', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await enableTwoFactor(api)
  await api.logout()

  const login = await api.login({ username_or_email: 'ada', password: 'password123' })
  if (!('two_factor_required' in login)) {
    throw new Error('expected a two-factor challenge')
  }
  expect(api.isAuthenticated()).toBe(false)

  const session = await api.loginWithTwoFactor({
    challenge_token: login.challenge_token,
    totp_code: STUB_TOTP_CODE,
  })
  expect(session.username).toBe('ada')
  expect(api.isAuthenticated()).toBe(true)

  // The challenge is single-use.
  await expect(
    api.loginWithTwoFactor({ challenge_token: login.challenge_token, totp_code: STUB_TOTP_CODE }),
  ).rejects.toThrow(INVALID_TWO_FACTOR_CHALLENGE)
})

test('recovery codes work once each', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  const confirm = await enableTwoFactor(api)
  const recoveryCode = confirm.recovery_codes[0]
  await api.logout()

  const first = await api.login({ username_or_email: 'ada', password: 'password123' })
  if (!('two_factor_required' in first)) throw new Error('expected challenge')
  await api.loginWithTwoFactor({ challenge_token: first.challenge_token, recovery_code: recoveryCode })
  await api.logout()

  const second = await api.login({ username_or_email: 'ada', password: 'password123' })
  if (!('two_factor_required' in second)) throw new Error('expected challenge')
  await expect(
    api.loginWithTwoFactor({ challenge_token: second.challenge_token, recovery_code: recoveryCode }),
  ).rejects.toThrow('Invalid two-factor code')
})

test('remember_me is carried through the two-factor step', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await enableTwoFactor(api)
  await api.logout()

  const login = await api.login({
    username_or_email: 'ada',
    password: 'password123',
    remember_me: true,
  })
  if (!('two_factor_required' in login)) throw new Error('expected challenge')

  const session = await api.loginWithTwoFactor({
    challenge_token: login.challenge_token,
    totp_code: STUB_TOTP_CODE,
  })
  expect(session.series_identifier).toBeDefined()
  expect(session.login_cookie_token).toBeDefined()
})

test('disabling requires the password and a valid code, then login is single-step', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await enableTwoFactor(api)

  await expect(
    api.disableTotp({ password: 'wrong', totp_code: STUB_TOTP_CODE }),
  ).rejects.toThrow('Invalid password')

  const result = await api.disableTotp({ password: 'password123', totp_code: STUB_TOTP_CODE })
  expect(result.totp_enabled).toBe(false)

  await api.logout()
  const login = await api.login({ username_or_email: 'ada', password: 'password123' })
  expect('session_management_token' in login).toBe(true)
})

// --- Async classification (#282) --------------------------------------------

test('createPost reports pending and getPostStatus resolves to approved (#282)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')

  const created = await api.createPost({ caption: 'a lovely day' })
  expect(created.status).toBe('pending')
  expect(created.hidden).toBe(true)
  expect(created.hidden_reason).toBe('pending_classification')

  // The stub classifies instantly (like the backend's eager dev mode), so the
  // status endpoint already reports the outcome.
  const status = await api.getPostStatus(created.post_identifier)
  expect(status.status).toBe('approved')
  expect(status.hidden).toBe(false)
  expect(status.appealable).toBe(false)
})

test('a borderline caption resolves to an appealable rejection (#282)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')

  const created = await api.createPost({ caption: 'a borderline take' })
  const status = await api.getPostStatus(created.post_identifier)
  expect(status.status).toBe('rejected')
  expect(status.hidden).toBe(true)
  expect(status.hidden_reason).toBe('classifier')
  expect(status.appealable).toBe(true)

  // It shows on the appeals screen and can be appealed.
  const hidden = await api.getHiddenPosts(0)
  expect(hidden.map((p) => p.post_identifier)).toContain(created.post_identifier)

  // It is invisible to other users but present (with status) in the author's grid.
  await register(api, 'viewer')
  const feed = await api.getFeed(0)
  expect(feed.map((p) => p.post_identifier)).not.toContain(created.post_identifier)
  expect(await api.getPostsForUser('author', 0)).toEqual([])

  await api.login({ username_or_email: 'author', password: 'password123' })
  const own = await api.getPostsForUser('author', 0)
  const ownPost = own.find((p) => p.post_identifier === created.post_identifier)
  expect(ownPost?.status).toBe('rejected')
  expect(ownPost?.appealable).toBe(true)
})

test('getPostStatus only answers for your own posts (#282)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const created = await api.createPost({ caption: 'mine' })

  await register(api, 'other')
  await expect(api.getPostStatus(created.post_identifier)).rejects.toThrow(
    'No post with that identifier',
  )
})

// --- Relationship categories & post audience (issue #392) --------------------

async function loginAs(api: StatefulStubbedAPI, username: string) {
  const result = await api.login({ username_or_email: username, password: 'password123' })
  if (isTwoFactorRequired(result)) throw new Error('expected a session, not a challenge')
  return result
}

test('follow defaults to the following category and can be set explicitly', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'target')

  await register(api, 'plain')
  await api.followUser('target')
  expect((await api.getProfile('target')).follow_category).toBe('following')

  await register(api, 'familyfollower')
  const res = await api.followUser('target', 'family')
  expect(res.follow_category).toBe('family')
  expect((await api.getProfile('target')).follow_category).toBe('family')
})

test('setFollowCategory re-categorizes an existing follow and requires one', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'target')
  await register(api, 'viewer')

  await expect(api.setFollowCategory('target', 'friend')).rejects.toThrow('Not following user')

  await api.followUser('target')
  await api.setFollowCategory('target', 'friend')
  expect((await api.getProfile('target')).follow_category).toBe('friend')
})

test('profile reports a null category when not following', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'target')
  await register(api, 'viewer')

  const profile = await api.getProfile('target')
  expect(profile.is_following).toBe(false)
  expect(profile.follow_category).toBeNull()
})

test('a family-only post reaches only family-labeled viewers', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'viewer')
  await register(api, 'author')
  // The author labels the viewer, then posts to family only.
  await api.followUser('viewer', 'friend')
  const post = await api.createPost({ caption: 'family only', audience: 'family' })

  // A friend is too far out for a family-only post.
  await loginAs(api, 'viewer')
  await expect(api.getPostDetails(post.post_identifier)).rejects.toThrow(
    'No post with that identifier',
  )

  // Promote the viewer to family and it becomes visible.
  await loginAs(api, 'author')
  await api.setFollowCategory('viewer', 'family')
  await loginAs(api, 'viewer')
  const details = await api.getPostDetails(post.post_identifier)
  expect(details.audience).toBe('family')
})

test('a friends post reaches friends and family but not plain followers', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'plain')
  await register(api, 'author')
  await api.followUser('plain', 'following')
  const post = await api.createPost({ caption: 'for friends', audience: 'friends' })

  await loginAs(api, 'plain')
  await expect(api.getPostDetails(post.post_identifier)).rejects.toThrow(
    'No post with that identifier',
  )
})

test('the author always sees their own restricted post', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ caption: 'private', audience: 'family' })
  const details = await api.getPostDetails(post.post_identifier)
  expect(details.audience).toBe('family')
})

test('the followed feed can be filtered to an exact group', async () => {
  const api = new StatefulStubbedAPI()
  // Two authors, each with a public post.
  await register(api, 'fam')
  const famPost = await api.createPost({ image_url: 'https://example.com/f.jpg', caption: 'fam post' })
  await register(api, 'fri')
  const friPost = await api.createPost({ image_url: 'https://example.com/r.jpg', caption: 'fri post' })

  await register(api, 'viewer')
  await api.followUser('fam', 'family')
  await api.followUser('fri', 'friend')

  const all = (await api.getFollowedFeed(0)).map((p) => p.post_identifier)
  expect(all).toContain(famPost.post_identifier)
  expect(all).toContain(friPost.post_identifier)

  const familyOnly = (await api.getFollowedFeed(0, 'family')).map((p) => p.post_identifier)
  expect(familyOnly).toEqual([famPost.post_identifier])

  const friendOnly = (await api.getFollowedFeed(0, 'friend')).map((p) => p.post_identifier)
  expect(friendOnly).toEqual([friPost.post_identifier])
})

// --- Saved posts (#193) ------------------------------------------------------

test('saving a post lists it as saved, newest save first', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const first = await api.createPost({ caption: 'one' })
  const second = await api.createPost({ caption: 'two' })

  await register(api, 'saver')
  expect(await api.getSavedPosts(0)).toEqual([])

  await api.savePost(first.post_identifier)
  await api.savePost(second.post_identifier)

  const saved = await api.getSavedPosts(0)
  expect(saved.map((p) => p.post_identifier)).toEqual([
    second.post_identifier,
    first.post_identifier,
  ])
  expect(saved.every((p) => p.is_saved)).toBe(true)
})

test('a post cannot be saved twice', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ caption: 'one' })

  await register(api, 'saver')
  await api.savePost(post.post_identifier)
  await expect(api.savePost(post.post_identifier)).rejects.toThrow('Already saved post')
})

test('unsaving removes the post from the saved list', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ caption: 'one' })

  await register(api, 'saver')
  await api.savePost(post.post_identifier)
  await api.unsavePost(post.post_identifier)

  expect(await api.getSavedPosts(0)).toEqual([])
  await expect(api.unsavePost(post.post_identifier)).rejects.toThrow('Post not saved yet')
})

test('a since-hidden post drops off the saved list', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ caption: 'one' })

  // The saver bookmarks it while it is still visible.
  await register(api, 'saver')
  await api.savePost(post.post_identifier)
  expect((await api.getSavedPosts(0)).length).toBe(1)

  // Enough distinct users report it to push it over the stub's hide threshold.
  for (let i = 0; i < 6; i += 1) {
    await register(api, `reporter${i}`)
    await api.reportPost(post.post_identifier, 'bad')
  }

  // Back as the saver: the now-hidden post no longer renders on the list.
  await api.login({ username_or_email: 'saver', password: 'password123' })
  expect(await api.getSavedPosts(0)).toEqual([])
})

test('setProfilePhoto reports pending then serializes the approved photo (#7)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  const res = await api.setProfilePhoto({ image_url: 'https://b.s3.amazonaws.com/ada/a.jpeg' })
  // The response mirrors the async backend contract: it reports 'pending'...
  expect(res.profile_image_status).toBe('pending')
  // ...but the stub has no classifier, so the photo is already approved and live.
  const profile = await api.getProfile('ada')
  expect(profile.profile_image_url).toBe('https://b.s3.amazonaws.com/ada/a.jpeg')
})

test('an author photo appears next to their name in feed and comments (#7)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await api.setProfilePhoto({ image_url: 'https://b.s3.amazonaws.com/ada/a.jpeg' })
  const post = await api.createPost({ caption: 'hello world caption' })

  const own = await api.getPostsForUser('ada', 0)
  const row = own.find((p) => p.post_identifier === post.post_identifier)
  expect(row?.author_profile_image_url).toBe('https://b.s3.amazonaws.com/ada/a.jpeg')

  const comment = await api.commentOnPost(post.post_identifier, 'nice one here friend')
  const comments = await api.getCommentsForThread(comment.comment_thread_identifier, 0)
  expect(comments[0]?.author_profile_image_url).toBe('https://b.s3.amazonaws.com/ada/a.jpeg')
})

test('removeProfilePhoto clears the photo (#7)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await api.setProfilePhoto({ image_url: 'https://b.s3.amazonaws.com/ada/a.jpeg' })

  const res = await api.removeProfilePhoto()
  expect(res.profile_image_status).toBe('none')
  const profile = await api.getProfile('ada')
  expect(profile.profile_image_url).toBeNull()
})

test('other users never see your pending photo status (#7)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await api.setProfilePhoto({ image_url: 'https://b.s3.amazonaws.com/ada/a.jpeg' })

  await register(api, 'bob')
  const adaFromBob = await api.getProfile('ada')
  // The owner-only moderation fields are not exposed to other viewers.
  expect(adaFromBob.profile_image_status).toBeUndefined()
  expect(adaFromBob.pending_profile_image_url).toBeUndefined()
  // But the approved photo is visible to everyone.
  expect(adaFromBob.profile_image_url).toBe('https://b.s3.amazonaws.com/ada/a.jpeg')
})

test('a post round-trips its caption font and background color (#318)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const created = await api.createPost({
    caption: 'styled words',
    caption_font: 'serif',
    background_color: 'mint',
  })

  const details = await api.getPostDetails(created.post_identifier)
  expect(details.caption_font).toBe('serif')
  expect(details.background_color).toBe('mint')

  await register(api, 'viewer')
  const feed = await api.getFeed(0)
  const post = feed.find((p) => p.post_identifier === created.post_identifier)
  expect(post?.caption_font).toBe('serif')
  expect(post?.background_color).toBe('mint')
})

test('a post defaults caption font and background color when unset (#318)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const created = await api.createPost({ caption: 'plain' })

  const details = await api.getPostDetails(created.post_identifier)
  expect(details.caption_font).toBe('default')
  expect(details.background_color).toBe('default')
})

test('a comment round-trips its inline formatting spans (#318)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ caption: 'nice' })

  const spans = [
    { start: 0, end: 4, bold: true, italic: false, size: 'normal' as const },
    { start: 5, end: 9, bold: false, italic: true, size: 'large' as const },
  ]
  const comment = await api.commentOnPost(post.post_identifier, 'love this', spans)

  const comments = await api.getCommentsForThread(comment.comment_thread_identifier, 0)
  expect(comments[0].body).toBe('love this')
  expect(comments[0].body_formatting).toEqual(spans)
})

test('a comment with no formatting reports null spans (#318)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'author')
  const post = await api.createPost({ caption: 'nice' })
  const comment = await api.commentOnPost(post.post_identifier, 'plain comment')

  const comments = await api.getCommentsForThread(comment.comment_thread_identifier, 0)
  expect(comments[0].body_formatting).toBeNull()
})

test('interest options expose the preset vocabulary', async () => {
  const api = new StatefulStubbedAPI()
  const { options } = await api.getInterestOptions()
  expect(options.length).toBeGreaterThan(0)
  expect(options.map((o) => o.slug)).toContain('nature')
})

test('setInterests stores presets and maps positive freeform to buckets (#446)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  const result = await api.setInterests({ categories: ['nature'], freeform: ['music', 'hiking'] })
  // "music" maps to the music bucket; "hiking" maps to none but is still kept.
  expect(result.categories).toEqual(['music', 'nature'])
  expect(result.freeform.accepted).toEqual(['music', 'hiking'])
  expect(result.freeform.rejected).toEqual([])

  const current = await api.getInterests()
  expect(current.categories).toEqual(['music', 'nature'])
  expect(current.freeform).toEqual(['music', 'hiking'])
})

test('setInterests rejects non-positive freeform terms (#446)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  const result = await api.setInterests({ categories: [], freeform: ['negative energy'] })
  expect(result.freeform.accepted).toEqual([])
  expect(result.freeform.rejected).toHaveLength(1)
  const current = await api.getInterests()
  expect(current.freeform).toEqual([])
})

test('setInterests full-replace removes omitted selections (#446)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')
  await api.setInterests({ categories: ['nature', 'music'], freeform: ['sports'] })

  // Resubmit with less: dropped preset and freeform are gone.
  const result = await api.setInterests({ categories: ['music'], freeform: [] })
  expect(result.categories).toEqual(['music'])
  const current = await api.getInterests()
  expect(current.categories).toEqual(['music'])
  expect(current.freeform).toEqual([])
})

test('interests picked at registration are applied (#446)', async () => {
  const api = new StatefulStubbedAPI()
  await api.register({
    username: 'grace',
    email: 'grace@example.com',
    password: 'password123',
    interest_categories: ['nature'],
    interest_freeform: ['music'],
  })
  const current = await api.getInterests()
  expect(current.categories).toEqual(['music', 'nature'])
})

test('setInterests reports a repeated rejected term once and bounds the list (#446)', async () => {
  // The stub must mirror the backend's _normalize_freeform_terms: dedupe before
  // deciding a term's fate, and bound the rejected list. Otherwise stub-backed
  // tests and offline mode see behavior production doesn't have.
  const api = new StatefulStubbedAPI()
  await register(api, 'ada')

  const bad = 'negative energy'
  const tooLong = 'z'.repeat(101)
  const result = await api.setInterests({
    categories: [],
    freeform: [bad, bad.toUpperCase(), tooLong, tooLong],
  })

  // Four entries, two distinct problems.
  expect(result.freeform.rejected).toHaveLength(2)
  // Keys the UI builds from these must be distinct.
  expect(new Set(result.freeform.rejected.map((r) => r.text)).size).toBe(2)
})

test('setInterests bounds a flood of rejected terms (#446)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'grace')

  const flood = Array.from({ length: 200 }, (_, i) => 'z'.repeat(101) + i)
  const result = await api.setInterests({ categories: [], freeform: flood })
  expect(result.freeform.rejected.length).toBeLessThanOrEqual(20)
})

test('setInterests bounds the echoed text of a huge rejected term (#446)', async () => {
  const api = new StatefulStubbedAPI()
  await register(api, 'hopper')

  const huge = 'y'.repeat(500)
  const result = await api.setInterests({ categories: [], freeform: [huge] })
  const echoed = result.freeform.rejected[0].text
  expect(echoed.length).toBeLessThanOrEqual(201) // 200 + the ellipsis
  expect(echoed.endsWith('…')).toBe(true)
  // Still clearly over the per-term limit.
  expect(echoed.length).toBeGreaterThan(100)
})
