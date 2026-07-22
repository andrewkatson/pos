import { vi, expect, test, describe } from 'vitest'
import {
  ACCOUNT_BANNED,
  EMAIL_NOT_VERIFIED,
  ApiClient,
  ApiError,
  sanitizeErrorMessage,
} from './client'

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

describe('email_not_verified handling', () => {
  test('fires onEmailNotVerified when an authenticated call is rejected with email_not_verified', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(403, { error: EMAIL_NOT_VERIFIED }))
    const client = new ApiClient({ token: 'sometoken', fetchFn })
    const onEmailNotVerified = vi.fn()
    client.setOnEmailNotVerified(onEmailNotVerified)

    await expect(client.getFeed(0)).rejects.toThrow(EMAIL_NOT_VERIFIED)

    expect(onEmailNotVerified).toHaveBeenCalledTimes(1)
  })

  test('does not fire onEmailNotVerified for unauthenticated calls like login', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(403, { error: EMAIL_NOT_VERIFIED }))
    const client = new ApiClient({ fetchFn })
    const onEmailNotVerified = vi.fn()
    client.setOnEmailNotVerified(onEmailNotVerified)

    await expect(
      client.login({ username_or_email: 'ada', password: 'pw', remember_me: false }),
    ).rejects.toThrow(EMAIL_NOT_VERIFIED)

    expect(onEmailNotVerified).not.toHaveBeenCalled()
  })

  test('does not fire onEmailNotVerified for other authenticated errors', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(401, { error: 'Invalid session token' }))
    const client = new ApiClient({ token: 'sometoken', fetchFn })
    const onEmailNotVerified = vi.fn()
    client.setOnEmailNotVerified(onEmailNotVerified)

    await expect(client.getFeed(0)).rejects.toThrow(ApiError)

    expect(onEmailNotVerified).not.toHaveBeenCalled()
  })
})

describe('post classification status (#282)', () => {
  test('getPostStatus hits the author-only status endpoint and returns its payload', async () => {
    const payload = {
      post_identifier: 'p1',
      status: 'pending',
      reason_code: null,
      appealable: false,
      hidden: true,
      hidden_reason: 'pending_classification',
      message: 'Your post is being reviewed and will be visible to others once it is approved.',
    }
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(200, payload))
    const client = new ApiClient({ token: 'sometoken', fetchFn })

    const result = await client.getPostStatus('p1')

    expect(fetchFn).toHaveBeenCalledWith(
      'https://api.smiling.social/user_index/posts/p1/status/',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(payload)
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

describe('sanitizeErrorMessage', () => {
  test('does not modify unrelated error messages', () => {
    expect(sanitizeErrorMessage('Text is not positive')).toBe('Text is not positive')
    expect(sanitizeErrorMessage('User already exists')).toBe('User already exists')
  })

  test('sanitizes single token invalid fields', () => {
    expect(sanitizeErrorMessage("Invalid fields ['USERNAME']")).toBe('Username is incorrect')
    expect(sanitizeErrorMessage("Invalid fields ['PASSWORD']")).toBe('Password is incorrect')
  })

  test('sanitizes multiple token invalid fields with and', () => {
    expect(sanitizeErrorMessage("Invalid fields ['USERNAME', 'PASSWORD']")).toBe('Username and Password are incorrect')
    expect(sanitizeErrorMessage("Invalid fields ['USERNAME', 'PASSWORD', 'EMAIL']")).toBe('Username, Password, and Email are incorrect')
  })

  test('sanitizes single token messages without brackets', () => {
    expect(sanitizeErrorMessage('Invalid post_identifier')).toBe('Post identifier is incorrect')
    expect(sanitizeErrorMessage('Invalid target_type')).toBe('Target type is incorrect')
  })

  test('leaves human-readable invalid messages untouched', () => {
    expect(sanitizeErrorMessage('Invalid comment text')).toBe('Invalid comment text')
    expect(sanitizeErrorMessage('Invalid batch parameter')).toBe('Invalid batch parameter')
  })
})

describe('two-factor authentication endpoints', () => {
  test('login does not store a session token when 2fa is required', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(200, { two_factor_required: true, challenge_token: 'c'.repeat(64) }),
      )
    const client = new ApiClient({ fetchFn })

    const response = await client.login({ username_or_email: 'ada', password: 'pw' })

    expect('two_factor_required' in response).toBe(true)
    expect(client.isAuthenticated()).toBe(false)
  })

  test('loginWithTwoFactor posts to /login/2fa/ and stores the session token', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse(200, { session_management_token: 'tok', user_id: 'u1', username: 'ada' }),
    )
    const client = new ApiClient({ baseUrl: 'https://api.test', fetchFn })

    await client.loginWithTwoFactor({ challenge_token: 'c'.repeat(64), totp_code: '123456' })

    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('https://api.test/login/2fa/')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      challenge_token: 'c'.repeat(64),
      totp_code: '123456',
    })
    expect(client.getToken()).toBe('tok')
  })

  test('setupTotp and confirmTotp hit the 2fa endpoints with the bearer token', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, { totp_secret: 'S', otpauth_uri: 'otpauth://totp/x' }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { totp_enabled: true, recovery_codes: ['a'] }))
    const client = new ApiClient({ baseUrl: 'https://api.test', token: 'sometoken', fetchFn })

    await client.setupTotp()
    await client.confirmTotp({ totp_code: '123456' })

    const [setupUrl, setupInit] = fetchFn.mock.calls[0]
    expect(setupUrl).toBe('https://api.test/2fa/totp/setup/')
    expect((setupInit as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer sometoken',
    })
    const [confirmUrl] = fetchFn.mock.calls[1]
    expect(confirmUrl).toBe('https://api.test/2fa/totp/confirm/')
  })

  test('disableTotp posts the password and code to /2fa/disable/', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(200, { totp_enabled: false }))
    const client = new ApiClient({ baseUrl: 'https://api.test', token: 'sometoken', fetchFn })

    await client.disableTotp({ password: 'pw', recovery_code: 'abcdef0123' })

    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('https://api.test/2fa/disable/')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      password: 'pw',
      recovery_code: 'abcdef0123',
    })
  })
})

