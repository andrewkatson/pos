import { ApiError } from './client'
import { StatefulStubbedAPI } from './StatefulStubbedAPI'
import type { RegisterRequest } from './types'

function register(api: StatefulStubbedAPI, username: string) {
  const body: RegisterRequest = {
    username,
    email: `${username}@example.com`,
    password: 'password123',
    ip: '127.0.0.1',
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
    ip: '127.0.0.1',
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
    ip: '127.0.0.1',
    date_of_birth: `${thisYear - 10}-01-01`,
  })

  const profile = await api.getProfile('kid')
  expect(profile.identity_is_verified).toBe(true)
  expect(profile.is_adult).toBe(false)
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
    api.login({ username_or_email: 'ada', password: 'wrong', ip: '127.0.0.1' }),
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
    ip: '127.0.0.1',
  })
  expect(login.username).toBe('ada')
})
