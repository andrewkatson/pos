// CloudFront Function (viewer-request) for the website distribution — issue #381.
//
// The website is a client-only Vite SPA on S3, so every path CloudFront serves
// returns the same index.html. A link-preview crawler never runs the router, so
// a shared `https://smiling.social/post/<id>` link would unfurl as the generic
// site card no matter which post it points at.
//
// This function redirects *crawlers only* to the backend's per-post Open Graph
// document, which does know the post's title, caption and image. A real browser
// is untouched and gets the SPA, which then renders the post itself through the
// public endpoints — so the two paths never disagree about what is visible: the
// preview endpoint applies the same public-visibility rule as the JSON API.
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

function handler(event) {
  var request = event.request

  var match = POST_PATH.exec(request.uri)
  if (!match) {
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
      location: { value: PREVIEW_ORIGIN + '/public/posts/' + match[1] + '/preview/' },
      'cache-control': { value: 'no-store' },
    },
  }
}
