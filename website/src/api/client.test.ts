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
