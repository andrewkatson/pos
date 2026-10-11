# Sharing

Every post's options menu offers **Share**, and every comment's options menu on
the post-detail screen does too (issue #34). Sharing hands off a link to the
item — the website's post page, `https://smiling.social/post/<post_identifier>`,
with a comment additionally carrying a `#comment-<comment_identifier>` fragment.
Share is available on any post or comment, your own and everyone else's; unlike
Like or Delete it has no ownership condition.

A **profile** can be shared the same way (issue #510). Every profile — your own
and everyone else's — carries a three-dots (⋯) options menu at the top of its
header whose one item is **Share**, handing off the website's profile page,
`https://smiling.social/profile/<username>`. Like a post link it works signed
out: see [What a recipient sees](#what-a-recipient-sees-issue-381) below.

Each client uses its native mechanism: iOS presents the system share sheet,
Android fires an `ACTION_SEND` chooser, and the website uses the Web Share API
when the browser offers it (typically mobile), otherwise copying the link to the
clipboard and confirming with a "Link copied" prompt.

## What a recipient sees (issue #381)

A shared link opens the website's post page **whether or not the recipient has
an account**. Signed out, the page is read-only: the image, caption, like count
and the comment threads are all there, but liking, commenting, replying,
reporting and the relationship filter are replaced by a prompt to log in or
join. Share itself still works, so a link can be passed along.

Comments are paged, and the post page has no "load more": it renders the first
batch of threads (10), but within each of those threads it loads **every**
comment, walking the 30-comment batches until one comes back short. That is the
same for signed-in viewers, so a very busy post shows its opening threads in
full rather than every thread. Each batch is a DB-level LIMIT/OFFSET, so
walking a long thread costs one batch-sized query per page, not a full-thread
query per page.

What is public is deliberately narrower than what a signed-in viewer sees. A
signed-out visitor is resolved against a fixed anonymous viewer, so a post is
served only when it is:

- not hidden — approved, not pending classification, not hidden by reports, and
  not a final-rejection tombstone;
- `public` audience — a following/friends/family post is never public, because
  an anonymous visitor is on nobody's follow list;
- by an author who is **not shadow banned** (an outright ban stops the account
  from acting but is not a content takedown, so their approved posts stay up);
- by an author who is **not a verified minor** — an anonymous visitor's age is
  unknown, which puts them in the adult band, and the two bands are mutually
  invisible (see [Age and identity](age-and-identity.md)). A minor's post is
  therefore never served to the open internet.

Comments are filtered by the same rule, so a public post can serve an empty
comment list when every comment on it is hidden or narrowly scoped.

Anything that fails these checks is reported as **404, identical to a post that
never existed** — the endpoints cannot be used to probe moderation state. The
answer does not depend on who asks: a signed-in browser, a signed-out one, and a
crawler all get the same bytes.

### A shared profile (issue #510)

A shared profile link opens the website's profile page, signed in or not. Signed
out it is read-only: the avatar, join number, bio, the Posts / Followers /
Following counts and the post grid are all there, but Follow, Block and the
grid's in-place like / save / report controls are replaced by a prompt to log in
or join. Tapping a tile opens the post page above, and the profile's own Share
still works.

The public profile is decided by the same anonymous viewer. An account is
served only when `searchable_users` would list it for that viewer — **not
shadow banned** and **not a verified minor** — exactly the accounts a signed-in
adult could find by name. Its grid is `visible_posts` for the same viewer, so it
holds precisely the posts whose own shared links would resolve; a friends-only
or hidden post is absent from the grid and from the post count alike, and the
follower/following counts exclude accounts that are themselves not public
(the same agreement between counts and lists that issue #398 established).
Nothing per-viewer is served — no follow or block state — and none of the
owner-only photo-review fields: the owner's own browser on the public page sees
what a stranger would.

An account that is not public is reported as **404, identical to a username
that was never registered**, so the endpoints cannot confirm a shadow ban or
locate a minor's account. The three endpoints are
`GET /public/profiles/<username>/details/`,
`GET /public/profiles/<username>/posts/<batch>/` and the crawler preview
`GET /public/profiles/<username>/preview/`, all IP rate limited like the post
ones.

A comment link's `#comment-<id>` fragment is resolved by the post page itself.
The API serves the **containing thread**, not the comment alone — a reply only
makes sense inside the conversation it belongs to — and the page scrolls to that
comment and marks it out.

Because the page renders one batch of threads, a link into the 11th thread would
otherwise point at something never rendered. So a fragment is the one thing that
makes the page keep paging threads: it fetches further thread batches until the
target appears, stopping at 5 batches (~50 threads). Earlier batches stay on
screen, so the comment is read in context. Within a thread there is no limit —
every comment is loaded — so a comment past the 30th in its thread is reached
too.

## Link previews

The website is a client-only SPA, so a crawler that fetches
`https://smiling.social/post/<id>` gets an empty root div and nothing to unfurl.
CloudFront's viewer-request function (`website/cloudfront/link-preview.js`)
redirects known link-preview crawlers — and only those — to a backend endpoint
that returns a meta-only HTML document with the post's Open Graph and Twitter
Card tags. Real browsers are untouched and get the SPA. The preview endpoint
applies exactly the public-visibility rule above, so a post it may not show
unfurls as the generic site card rather than leaking anything.

A shared profile link, `https://smiling.social/profile/<username>`, unfurls the
same way (issue #510): the card is the username, the bio (or the generic site
line when there is none) and the profile photo, with `og:type` `profile`. A
profile that is not public gets the generic site card with a 404, so a crawler
cannot tell it from an unregistered name. The function forwards only a
well-formed username — word characters or percent-encoded bytes, since the URI
it sees is still encoded and usernames may contain Unicode letters, that decode
to 10–150 characters with no ASCII punctuation, whitespace, characters from the
dedicated combining-mark blocks (such as U+0301) or non-underscore connector
punctuation (the backend applies the precise `\w` rule to anything else, such
as marks interleaved with a script's letters) — because the match goes
straight into the redirect URL.

Two pieces of CloudFront configuration make this work and are not managed by
`website/deploy-web.sh` (which warns about the first): custom error responses
mapping 403/404 to `/index.html` with a 200, so a cold load of a client-side
`/post/<id>` route resolves at all; and the published function association
itself.

## Opening the app instead of the browser (issue #382)

On a phone with the app installed, a shared link opens the **app**, not the
browser: iOS via Universal Links (`applinks:smiling.social` in the app's
entitlements) and Android via App Links (an `autoVerify` intent-filter for
`https://smiling.social/post/*` and `/profile/*`). Both are claimed by a file
the OS fetches from the website at install time, published by
`website/deploy-web.sh`:

- `/.well-known/apple-app-site-association` — checked into
  `website/public/.well-known/` and scoped to `/post/*` and `/profile/*`;
- `/.well-known/assetlinks.json` — generated at deploy time, because it needs
  the release signing certificate's SHA-256 fingerprint, which lives in Play
  Console rather than the repo. Export `ANDROID_SHA256_CERT_FINGERPRINTS` to
  publish it; without it the deploy leaves the file alone and Android App Links
  simply do not verify (links keep opening the browser, which still works
  because the web page is public).

Only `/post/*` and `/profile/*` are claimed. Every other route — login, tags,
the privacy policy — belongs to the website, and claiming them would hijack
links the app has no screen for. A shared **profile** link (issue #510) opens
that user's profile screen in the app — the same screen a search result opens;
your own username lands on the Profile tab itself — and, like a post link, waits
for login when opened signed out. A `/profile/` segment that could not be a
username (anything but 10–150 letters, digits and underscores — the backend's
`Patterns.username`) is rejected by both parsers rather than routed.

Each client parses the URL itself rather than letting the navigation framework
resolve it (`ShareURL.parse` on iOS, `ShareLinks.parseSharedLink` on Android),
because the post detail and profile screens are **authenticated**. The parsed
post id or username goes onto the same small router a tapped push notification
uses, which holds the request until a session exists — so a link opened while
signed out waits for login instead of dropping the user on a screen with no
session behind it. Both parsers are strict about scheme, host and path shape: a `VIEW` intent
or an `.onOpenURL` callback can carry any URL, and one that merely looks similar
must not navigate anywhere. A `#comment-<id>` fragment is parsed and the post
still opens; scrolling to the specific comment is web-only today.

If the app is not installed, the link opens the public web page as before.
