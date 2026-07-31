import { vi, expect, test, describe, afterEach } from 'vitest'
import { registerForPush } from './webPush'
import { apiClient } from '../api/client'

// No VITE_FIREBASE_* env is set under test, so isPushConfigured() is false and
// registration must short-circuit before touching Firebase, the service worker,
// or the Notification API. These tests pin that best-effort, no-op degradation.
describe('registerForPush (#342/#343)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('does nothing when Firebase push is not configured', async () => {
    vi.spyOn(apiClient, 'isAuthenticated').mockReturnValue(true)
    const registerDevice = vi.spyOn(apiClient, 'registerDevice')

    await expect(registerForPush({ promptIfNeeded: true })).resolves.toBeUndefined()
    expect(registerDevice).not.toHaveBeenCalled()
  })

  test('does nothing when the user is not authenticated', async () => {
    vi.spyOn(apiClient, 'isAuthenticated').mockReturnValue(false)
    const registerDevice = vi.spyOn(apiClient, 'registerDevice')

    await registerForPush({ promptIfNeeded: true })
    expect(registerDevice).not.toHaveBeenCalled()
  })
})
