import { ApiClient, ApiError } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

test('login posts credentials and stores the session token', async () => {
  const fetchFn = vi.fn().mockResolvedValue(
    jsonResponse({ session_management_token: 'tok123', user_id: 7, username: 'ada' }),
  )
  const client = new ApiClient({ baseUrl: 'https://api.test', fetchFn })

  const result = await client.login({
    username_or_email: 'ada',
    password: 'pw',
    ip: '127.0.0.1',
  })

  expect(result.user_id).toBe(7)
  expect(client.getToken()).toBe('tok123')
  expect(client.isAuthenticated()).toBe(true)

  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe('https://api.test/user_index/login/')
  expect(init.method).toBe('POST')
  expect(JSON.parse(init.body)).toEqual({
    username_or_email: 'ada',
    password: 'pw',
    ip: '127.0.0.1',
  })
})

test('authenticated requests send the Bearer token', async () => {
  const fetchFn = vi.fn().mockResolvedValue(jsonResponse([]))
  const client = new ApiClient({ baseUrl: 'https://api.test', token: 'tok123', fetchFn })

  await client.getFeed(0)

  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe('https://api.test/user_index/feed/0/')
  expect(init.headers.Authorization).toBe('Bearer tok123')
})

test('throws without a token on authenticated calls', async () => {
  const fetchFn = vi.fn()
  const client = new ApiClient({ baseUrl: 'https://api.test', fetchFn })

  await expect(client.getFeed(0)).rejects.toBeInstanceOf(ApiError)
  expect(fetchFn).not.toHaveBeenCalled()
})

test('surfaces the backend error message on non-2xx responses', async () => {
  const fetchFn = vi
    .fn()
    .mockResolvedValue(jsonResponse({ error: 'Invalid username or password' }, 400))
  const client = new ApiClient({ baseUrl: 'https://api.test', fetchFn })

  await expect(
    client.login({ username_or_email: 'ada', password: 'bad', ip: '127.0.0.1' }),
  ).rejects.toThrow('Invalid username or password')
})

test('logout clears the stored token', async () => {
  const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ message: 'Logout successful' }))
  const client = new ApiClient({ baseUrl: 'https://api.test', token: 'tok123', fetchFn })

  await client.logout()

  expect(client.getToken()).toBeNull()
  expect(client.isAuthenticated()).toBe(false)
})
