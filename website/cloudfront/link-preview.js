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
// Runs on the cloudfront-js-2.0 runtime: no ES modules, no async, no fetch.
// Tested by link-preview.test.js, which loads this exact file.

var PREVIEW_ORIGIN = 'https://api.smiling.social/user_index'

// The unfurlers worth serving. Matching on an allowlist rather than "anything
// that isn't a known browser" keeps a mis-detected human from being bounced off
// the site — the cost of missing a crawler is a bland preview, the cost of a
// false positive is a broken link.
var CRAWLERS = new RegExp(
  [
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
  ].join('|'),
  'i',
)

// `/post/<uuid>`, with or without a trailing slash. The uri CloudFront hands us
// never includes the query string or the fragment, so a `#comment-<id>` link
// resolves to the same preview as the post itself — which is correct: a shared
// comment unfurls as the post it lives on.
var POST_PATH = /^\/post\/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\/?$/

// `/profile/<username>`, with or without a trailing slash. Usernames are word
// characters (the backend's `Patterns.username`; it registers nothing
// else), at least 10 long and at most 150 — the username column's max_length —
// and the match is what goes into the redirect URL, so the same shape is
// enforced here — anything else is not a profile we could preview and passes
// through.
//
// The uri CloudFront hands us is still percent-encoded, and the backend admits
// Unicode letters and digits, so a non-ASCII username arrives as `%XX` byte
// sequences rather than as characters. Those are accepted alongside ASCII word
// characters and forwarded verbatim (still encoded) — the backend decodes and
// validates the name itself. JavaScript's `\w` alone is ASCII-only and would
// leave such profiles unfurling as the generic site card. A character can
// take up to four encoded bytes, so the pattern admits up to 600 units and
// the 10-150 character rule is then checked on the decoded name
// (profileNameLength); the backend still validates the name itself.
var PROFILE_PATH = /^\/profile\/((?:\w|%[0-9A-Fa-f]{2}){10,600})\/?$/
var MIN_USERNAME_LENGTH = 10
var MAX_USERNAME_LENGTH = 150

// Length of an encoded username in characters (code points, as the backend
// counts them), or -1 when the bytes are not valid UTF-8.
function profileNameLength(encoded) {
  var decoded
  try {
    decoded = decodeURIComponent(encoded)
  } catch (e) {
    return -1
  }
  // Count a surrogate pair (an astral character) once.
  return decoded.replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, '_').length
}

// ASCII characters that are not word characters, and any whitespace. The
// encoded bytes can decode to anything, so the backend's `\w` rule is checked
// on the decoded name: exactly for ASCII (where `\w` is [A-Za-z0-9_]), and for
// the rest only as far as ES5 regexes can without Unicode property escapes —
// whitespace is never a word character. Anything subtler is left to the
// backend, which applies the precise rule.
var NON_WORD = /[\x00-\x2F\x3A-\x40\x5B-\x5E\x60\x7B-\x7F]|\s/

// Whether an encoded profile segment decodes to a plausible username: 10-150
// characters (see PROFILE_PATH) with no character NON_WORD rules out.
function isPlausibleUsername(encoded) {
  var length = profileNameLength(encoded)
  if (length < MIN_USERNAME_LENGTH || length > MAX_USERNAME_LENGTH) {
    return false
  }
  return !NON_WORD.test(decodeURIComponent(encoded))
}

// The backend preview path for a request URI, or null when the URI is not a
// page we render previews for.
function previewPath(uri) {
  var post = POST_PATH.exec(uri)
  if (post) {
    return '/public/posts/' + post[1] + '/preview/'
  }
  var profile = PROFILE_PATH.exec(uri)
  if (profile) {
    if (!isPlausibleUsername(profile[1])) {
      return null
    }
    return '/public/profiles/' + profile[1] + '/preview/'
  }
  return null
}

function handler(event) {
  var request = event.request

  var path = previewPath(request.uri)
  if (!path) {
    return request
  }

  var userAgent = request.headers['user-agent'] ? request.headers['user-agent'].value : ''
  if (!CRAWLERS.test(userAgent)) {
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
