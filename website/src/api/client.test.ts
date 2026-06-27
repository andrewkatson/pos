import { vi, expect, test, describe } from 'vitest'
import { ACCOUNT_BANNED, ApiClient, ApiError } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('account_banned handling', () => {
  test('fires onAccountBanned when an authenticated call is rejected with account_banned', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(403, { error: ACCOUNT_BANNED }))
    const client = new ApiClient({ token: 'sometoken', fetchFn })
    const onBanned = vi.fn()
    client.setOnAccountBanned(onBanned)

    await expect(client.getFeed(0)).rejects.toThrow(ACCOUNT_BANNED)

    expect(onBanned).toHaveBeenCalledTimes(1)
  })

  test('does not fire onAccountBanned for unauthenticated calls like login', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(403, { error: ACCOUNT_BANNED }))
    const client = new ApiClient({ fetchFn })
    const onBanned = vi.fn()
    client.setOnAccountBanned(onBanned)

    await expect(
      client.login({ username_or_email: 'ada', password: 'pw', remember_me: false }),
    ).rejects.toThrow(ACCOUNT_BANNED)

    expect(onBanned).not.toHaveBeenCalled()
  })

  test('does not fire onAccountBanned for other authenticated errors', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(401, { error: 'Invalid session token' }))
    const client = new ApiClient({ token: 'sometoken', fetchFn })
    const onBanned = vi.fn()
    client.setOnAccountBanned(onBanned)

    await expect(client.getFeed(0)).rejects.toThrow(ApiError)

    expect(onBanned).not.toHaveBeenCalled()
  })
})

describe('friendly error messages', () => {
  test('passes the backend error message through unchanged', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(400, { error: 'Text is not positive' }))
    const client = new ApiClient({ token: 'sometoken', fetchFn })

    await expect(client.createPost({ image_url: 'x', caption: 'y' })).rejects.toThrow(
      'Text is not positive',
    )
  })

  test('maps a 504 with no JSON error body to friendly copy (no status code leak)', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response('<html>504 Gateway Time-out</html>', { status: 504 }),
    )
    const client = new ApiClient({ token: 'sometoken', fetchFn })

    await expect(client.createPost({ image_url: 'x', caption: 'y' })).rejects.toThrow(
      'The server is taking too long to respond. Please try again in a moment.',
    )
  })

  test('maps a 404 with no JSON error body to friendly copy', async () => {
    const fetchFn = vi.fn().mockResolvedValue(new Response('Not Found', { status: 404 }))
    const client = new ApiClient({ token: 'sometoken', fetchFn })

    let caught: unknown
    await client.getPostDetails('abc').catch((e) => (caught = e))
    expect(caught).toBeInstanceOf(ApiError)
    expect((caught as ApiError).message).not.toContain('404')
  })

  test('maps a network failure (fetch rejection) to offline copy', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = new ApiClient({ token: 'sometoken', fetchFn })

    await expect(client.getFeed(0)).rejects.toThrow(
      'You appear to be offline. Please check your connection and try again.',
    )
  })
})
