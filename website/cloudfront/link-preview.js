// CloudFront Function (viewer-request) for the website distribution — issue #381.
//
// The website is a client-only Vite SPA on S3, so every path CloudFront serves
// returns the same index.html. A link-preview crawler never runs the router, so
// a shared `https://smiling.social/post/<id>` link would unfurl as the generic
// site card no matter which post it points at. The same goes for a shared
// profile, `https://smiling.social/profile/<username>` (issue #510).
//
// This function redirects *crawlers only* to the backend's per-post (or
// per-profile) Open Graph document, which does know the title, caption/bio and
// image. A real browser is untouched and gets the SPA, which then renders the
// page itself through the public endpoints — so the two paths never disagree
// about what is visible: the preview endpoints apply the same public-visibility
// rule as the JSON API.
//
// A 302 (not a rewrite) is used deliberately: CloudFront Functions cannot pick
// a different origin, and every major unfurler follows redirects and reads the
// meta tags from the final URL. `Cache-Control: no-store` keeps the redirect
// itself from being cached against a path a browser will later request.
//
// Deploy: CloudFront > distribution EMS8KP5TZ1KB3 > Functions, published and
// associated with the default cache behavior on *viewer request*. Update
// PREVIEW_ORIGIN if the API's base URL changes.
//
// This runs on EVERY request to the website, and a function that fails or goes
// over CloudFront's compute budget answers 503 for all of them, home page
// included. A regex-based version did that in production, so: no regular
// expressions, and any
// path that cannot have a preview returns before anything else happens. Before
// publishing, check compute utilization on the Test tab (Development stage),
// including with a long non-ASCII username, because the Node tests here cannot
// measure it.
//
// Runs on the cloudfront-js-2.0 runtime: no ES modules, no async, no fetch.
// Tested by link-preview.test.js, which loads this exact file.

var PREVIEW_ORIGIN = 'https://api.smiling.social/user_index'

var POST_PREFIX = '/post/'
var PROFILE_PREFIX = '/profile/'

// The unfurlers worth serving, lowercase. Matching on an allowlist rather than
// "anything that isn't a known browser" keeps a mis-detected human from being
// bounced off the site — the cost of missing a crawler is a bland preview, the
// cost of a false positive is a broken link.
var CRAWLERS = [
  'facebookexternalhit',
  'facebookcatalog',
  'twitterbot',
  'slackbot',
  'slack-imgproxy',
  'linkedinbot',
  'discordbot',
  'telegrambot',
  'whatsapp',
  'redditbot',
  'pinterest',
  'skypeuripreview',
  'applebot',
  'bingbot',
  'googlebot',
  'mastodon',
  'bluesky',
  'embedly',
  'iframely',
  'quora link preview',
  'vkshare',
  'snapchat',
  'signal',
]

// Usernames are word characters (the backend's `Patterns.username`), at least
// 10 long and at most 150 — the username column's max_length. A character can
// take up to four encoded bytes, so an encoded name is at most 600 units, and a
// unit is at most three characters (`%XX`).
var MIN_USERNAME_LENGTH = 10
var MAX_USERNAME_LENGTH = 150
var MAX_ENCODED_UNITS = 600

// Inclusive [low, high] pairs of non-ASCII characters that are never word
// characters: any whitespace, the dedicated combining-mark blocks (Python's `\w`
// rejects marks, so `e` + U+0301 is not a username), and every connector
// punctuation character. Marks interleaved with a script's letters (Indic vowel
// signs and the like) are left to the backend, which applies the precise rule.
var NON_WORD_RANGES = [
  0x00a0, 0x00a0, 0x1680, 0x1680, 0x2000, 0x200a, 0x2028, 0x2029, 0x202f, 0x202f,
  0x205f, 0x205f, 0x3000, 0x3000, 0xfeff, 0xfeff,
  0x0300, 0x036f, 0x0483, 0x0489, 0x1ab0, 0x1aff, 0x1dc0, 0x1dff, 0x20d0, 0x20ff,
  0xfe20, 0xfe2f,
  0x203f, 0x2040, 0x2054, 0x2054, 0xfe33, 0xfe34, 0xfe4d, 0xfe4f, 0xff3f, 0xff3f,
]

function isCrawler(userAgent) {
  var agent = userAgent.toLowerCase()
  for (var i = 0; i < CRAWLERS.length; i++) {
    if (agent.indexOf(CRAWLERS[i]) !== -1) {
      return true
    }
  }
  return false
}

function isHexDigit(code) {
  return (
    (code >= 48 && code <= 57) || // 0-9
    (code >= 65 && code <= 70) || // A-F
    (code >= 97 && code <= 102) // a-f
  )
}

// A-Z, a-z, 0-9 and underscore.
function isAsciiWord(code) {
  return (
    (code >= 48 && code <= 57) ||
    (code >= 65 && code <= 90) ||
    (code >= 97 && code <= 122) ||
    code === 95
  )
}

function isNonWord(code) {
  if (code < 0x80) {
    return !isAsciiWord(code)
  }
  for (var i = 0; i < NON_WORD_RANGES.length; i += 2) {
    if (code >= NON_WORD_RANGES[i] && code <= NON_WORD_RANGES[i + 1]) {
      return true
    }
  }
  return false
}

// The path segment after a prefix, without one optional trailing slash. The uri
// CloudFront hands us never includes the query string or the fragment, so a
// `#comment-<id>` link resolves to the same preview as the post itself — which
// is correct: a shared comment unfurls as the post it lives on.
function segmentAfter(uri, prefix) {
  var segment = uri.slice(prefix.length)
  if (segment.charAt(segment.length - 1) === '/') {
    return segment.slice(0, segment.length - 1)
  }
  return segment
}

// 8-4-4-4-12 hex digits. The id goes into the redirect URL, so only this exact
// shape is forwarded.
function isUuid(id) {
  if (id.length !== 36) {
    return false
  }
  for (var i = 0; i < id.length; i++) {
    var code = id.charCodeAt(i)
    if (i === 8 || i === 13 || i === 18 || i === 23) {
      if (code !== 45) {
        return false
      }
    } else if (!isHexDigit(code)) {
      return false
    }
  }
  return true
}

// Whether a segment is only ASCII word characters and `%XX` bytes, in a number
// of units a username could occupy. The uri is still percent-encoded and the
// backend admits Unicode letters and digits, so a non-ASCII username arrives as
// `%XX` sequences. It is forwarded verbatim (still encoded); the backend decodes
// and validates the name itself.
function isEncodedName(encoded) {
  if (encoded.length > MAX_ENCODED_UNITS * 3) {
    return false
  }
  var units = 0
  var i = 0
  while (i < encoded.length) {
    var code = encoded.charCodeAt(i)
    if (code === 37) {
      if (!isHexDigit(encoded.charCodeAt(i + 1)) || !isHexDigit(encoded.charCodeAt(i + 2))) {
        return false
      }
      i += 3
    } else if (isAsciiWord(code)) {
      i += 1
    } else {
      return false
    }
    units += 1
  }
  return units >= MIN_USERNAME_LENGTH && units <= MAX_ENCODED_UNITS
}

// Whether an encoded segment decodes to a plausible username: valid UTF-8, 10-150
// characters (code points, as the backend counts them), none of them non-word.
function isPlausibleUsername(encoded) {
  if (!isEncodedName(encoded)) {
    return false
  }
  var decoded
  try {
    decoded = decodeURIComponent(encoded)
  } catch (e) {
    return false
  }
  var length = 0
  for (var i = 0; i < decoded.length; i++) {
    var code = decoded.charCodeAt(i)
    if (isNonWord(code)) {
      return false
    }
    length += 1
    // A surrogate pair is one character, so skip its second half.
    if (code >= 0xd800 && code <= 0xdbff) {
      i += 1
    }
  }
  return length >= MIN_USERNAME_LENGTH && length <= MAX_USERNAME_LENGTH
}

// The backend preview path for a request URI, or null when the URI is not a
// page we render previews for.
function previewPath(uri) {
  if (uri.indexOf(POST_PREFIX) === 0) {
    var id = segmentAfter(uri, POST_PREFIX)
    return isUuid(id) ? '/public/posts/' + id + '/preview/' : null
  }
  var username = segmentAfter(uri, PROFILE_PREFIX)
  return isPlausibleUsername(username) ? '/public/profiles/' + username + '/preview/' : null
}

function handler(event) {
  var request = event.request
  var uri = request.uri

  // Nearly every request stops here, including all of the site's assets.
  if (uri.indexOf(POST_PREFIX) !== 0 && uri.indexOf(PROFILE_PREFIX) !== 0) {
    return request
  }

  var userAgent = request.headers['user-agent'] ? request.headers['user-agent'].value : ''
  if (!isCrawler(userAgent)) {
    return request
  }

  var path = previewPath(uri)
  if (!path) {
    return request
  }

  return {
    statusCode: 302,
    statusDescription: 'Found',
    headers: {
      location: { value: PREVIEW_ORIGIN + path },
      'cache-control': { value: 'no-store' },
    },
  }
}
