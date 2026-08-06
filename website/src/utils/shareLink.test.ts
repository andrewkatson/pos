import { afterEach, describe, expect, test, vi } from 'vitest'
import { commentShareUrl, postShareUrl, shareLink, sharedCommentId } from './shareLink'

// jsdom serves window.location.origin as http://localhost:3000 by default.
const ORIGIN = window.location.origin

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('postShareUrl / commentShareUrl', () => {
  test('post URL is the origin-rooted /post/:id route', () => {
    expect(postShareUrl('abc-123')).toBe(`${ORIGIN}/post/abc-123`)
  })

  test('comment URL appends a #comment-<id> fragment to the post URL', () => {
    expect(commentShareUrl('abc-123', 'def-456')).toBe(`${ORIGIN}/post/abc-123#comment-def-456`)
  })
})

describe('sharedCommentId', () => {
  const COMMENT_ID = '3f1b9a2c-6d4e-4f8a-9b1c-2d3e4f5a6b7c'

  test('round-trips the fragment commentShareUrl produces', () => {
    const url = commentShareUrl('9a1e0b6f-1111-4222-8333-444455556666', COMMENT_ID)

    expect(sharedCommentId(`#${url.split('#')[1]}`)).toBe(COMMENT_ID)
  })

  test('is case-insensitive about the uuid', () => {
    expect(sharedCommentId(`#comment-${COMMENT_ID.toUpperCase()}`)).toBe(COMMENT_ID.toUpperCase())
  })

  test('ignores a hash that is not a comment link', () => {
    for (const hash of ['', '#', '#top', '#comment-', '#comment-not-a-uuid', `#post-${COMMENT_ID}`]) {
      expect(sharedCommentId(hash)).toBeNull()
    }
  })

  test('ignores anything that could be smuggled into a DOM id or selector', () => {
    // The value builds a DOM id; a hash is attacker-supplied whenever a link is.
    for (const hash of [
      '#comment-<script>alert(1)</script>',
      `#comment-${COMMENT_ID}"]`,
      `#comment-${COMMENT_ID} extra`,
    ]) {
      expect(sharedCommentId(hash)).toBeNull()
    }
  })
})

describe('shareLink', () => {
  test('uses the Web Share API when available and reports "shared"', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share })

    await expect(shareLink('https://x/post/1')).resolves.toBe('shared')
    expect(share).toHaveBeenCalledWith({ url: 'https://x/post/1' })
  })

  test('treats the user dismissing the share sheet as a no-op, not a failure', async () => {
    const share = vi.fn().mockRejectedValue(new DOMException('cancelled', 'AbortError'))
    vi.stubGlobal('navigator', { share })

    await expect(shareLink('https://x/post/1')).resolves.toBe('shared')
  })

  test('treats a non-DOMException cancel (name "AbortError") as a no-op too', async () => {
    // A cross-realm or non-DOM rejection won't pass `instanceof DOMException`,
    // so the check reads `name` directly — a plain object still counts as a
    // dismissal rather than falling through to the clipboard.
    const share = vi.fn().mockRejectedValue({ name: 'AbortError' })
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share, clipboard: { writeText } })

    await expect(shareLink('https://x/post/1')).resolves.toBe('shared')
    expect(writeText).not.toHaveBeenCalled()
  })

  test('falls back to the clipboard when there is no share API and reports "copied"', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await expect(shareLink('https://x/post/1')).resolves.toBe('copied')
    expect(writeText).toHaveBeenCalledWith('https://x/post/1')
  })

  test('falls back to the clipboard when the share sheet errors for a real reason', async () => {
    const share = vi.fn().mockRejectedValue(new DOMException('boom', 'NotAllowedError'))
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share, clipboard: { writeText } })

    await expect(shareLink('https://x/post/1')).resolves.toBe('copied')
    expect(writeText).toHaveBeenCalledWith('https://x/post/1')
  })

  test('reports "failed" when neither sharing nor copying works', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('blocked'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await expect(shareLink('https://x/post/1')).resolves.toBe('failed')
  })

  test('reports "failed" when the browser exposes neither capability', async () => {
    vi.stubGlobal('navigator', {})

    await expect(shareLink('https://x/post/1')).resolves.toBe('failed')
  })
})
