// Tests for the CloudFront viewer-request function that routes link-preview
// crawlers to the backend's Open Graph document (issue #381).
//
// The function file is loaded and evaluated as source rather than imported:
// CloudFront's runtime has no module system, so the deployable artifact cannot
// carry an `export`. Reading it here means the tests exercise exactly the bytes
// that get published, not a copy that can drift from them.

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'link-preview.js'),
  'utf-8',
)
const handler = new Function(`${source}; return handler`)()

const POST_ID = '3f1b9a2c-6d4e-4f8a-9b1c-2d3e4f5a6b7c'

function request(uri, userAgent) {
  const headers = userAgent === undefined ? {} : { 'user-agent': { value: userAgent } }
  return handler({ request: { uri, headers } })
}

const CHROME =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'

describe('crawlers', () => {
  it.each([
    ['facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'],
    ['Twitterbot/1.0'],
    ['Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'],
    ['Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)'],
    ['WhatsApp/2.23.20.0'],
    ['Mozilla/5.0 (compatible; TelegramBot/1.0)'],
    ['LinkedInBot/1.0 (compatible; Mozilla/5.0)'],
    ['Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)'],
  ])('%s is redirected to the preview endpoint', userAgent => {
    const response = request(`/post/${POST_ID}`, userAgent)

    expect(response.statusCode).toBe(302)
    expect(response.headers.location.value).toBe(
      `https://api.smiling.social/user_index/public/posts/${POST_ID}/preview/`,
    )
  })

  it('does not let the redirect be cached against a path browsers also request', () => {
    expect(request(`/post/${POST_ID}`, 'Twitterbot/1.0').headers['cache-control'].value).toBe(
      'no-store',
    )
  })

  it('accepts a trailing slash', () => {
    expect(request(`/post/${POST_ID}/`, 'Twitterbot/1.0').statusCode).toBe(302)
  })

  it('matches the user agent case-insensitively', () => {
    expect(request(`/post/${POST_ID}`, 'SLACKBOT 1.0').statusCode).toBe(302)
  })
})

describe('everything else passes through untouched', () => {
  it('a real browser gets the SPA', () => {
    const result = request(`/post/${POST_ID}`, CHROME)

    expect(result.uri).toBe(`/post/${POST_ID}`)
    expect(result.statusCode).toBeUndefined()
  })

  it('a crawler on a non-post path gets the SPA', () => {
    for (const uri of ['/', '/home', '/profile/someone', '/tags/sunset']) {
      expect(request(uri, 'Twitterbot/1.0').uri).toBe(uri)
    }
  })

  it('a missing user-agent header does not throw', () => {
    expect(request(`/post/${POST_ID}`).uri).toBe(`/post/${POST_ID}`)
  })

  it('a post path whose id is not a uuid is not redirected', () => {
    // The id goes straight into the preview URL, so only a well-formed one is
    // ever forwarded.
    for (const uri of ['/post/not-a-uuid', '/post/', `/post/${POST_ID}/extra`, '/post/../../etc']) {
      expect(request(uri, 'Twitterbot/1.0').uri).toBe(uri)
    }
  })
})
