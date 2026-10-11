# Audience, relationships and blocking

## Relationship categories & post audience

Following is not all-or-nothing (issue #392). Every follow relationship carries
a **category** that the follower assigns to the person they follow, and the same
label does double duty: it filters your own feed *and* gates who may see your
posts. The categories, from broadest to closest, are:

- **Following** — the default "people I like" bucket every plain follow starts
  in.
- **Friend**
- **Family**

The category lives on the follow edge (`UserFollow.category`), so you can only
categorize someone you already follow, and unfollowing drops the label with it.
A follow request may set the category up front (`follow_user` accepts an
optional `category`), and an existing relationship is re-categorized with
`POST /users/<username>/category/`. A profile response carries the viewer's
`follow_category` for that user (null when not following).

Each post has an **audience** chosen at creation (`make_post` accepts an
optional `audience`, defaulting to `public` so older clients and pre-existing
posts are unaffected). The audiences are **nested circles**, each a subset of
the one before it:

- **Public** — anyone, even people who do not follow the author.
- **People I follow** (`following`) — everyone the author follows.
- **Friends** (`friends`) — people the author labeled friend *or* family.
- **Family** (`family`) — family only.

So a friends-only post also reaches family, and a family-only post reaches
family alone. The rule is enforced centrally in `visibility.py`
(`visible_posts` / `can_view_post`): a non-public post is shown to a viewer only
when the author has a follow edge to that viewer whose category is close enough
for the post's tier. The author always sees their own posts regardless of
audience, and the audience filter composes with the existing moderation
(hidden / shadow-ban / tombstone) rules and applies everywhere posts are listed
— feeds, profile grids, and post details alike.

Feeds can be **filtered by group**: the followed feed
(`GET /feed/followed/<batch>/`) takes an optional `?category=following|friend|family`
that narrows it to people you labeled with exactly that category (no argument
returns the whole following feed, as before). Feed filtering is an exact-category
match — "show me my family" means just family — while post audience nests, since
sharing with a wider circle should naturally include the closer ones.

**Comments** carry the same mechanics (issue #445). A comment or reply is
created with an optional `audience` (`comment_on_post` / `reply_to_comment_thread`
accept it, defaulting to `public` so older clients are unaffected), scoped by the
identical nested-circle rule enforced in `visibility.py`
(`visible_comments` / `audience_admits`): a non-public comment reaches a viewer
only when its author labeled that viewer closely enough, the author always sees
their own, and a comment the audience excludes is treated as absent for likes and
reports too (not just hidden from the list). The comment listings
(`GET /posts/<id>/comments/<batch>/` and
`GET /threads/<id>/comments/<batch>/`) take the same optional
`?category=following|friend|family` toggle the followed feed offers, narrowing the
shown comments to authors you labeled with exactly that category (the thread
listing keeps only threads with a matching visible comment). Like the feed filter
it is an exact-category match and naturally drops your own comments, since you do
not follow yourself.

## Private accounts (issue #96)

Any account can be made **private** from Settings (`POST /profile/private/` with
`{"is_private": true|false}`; `GET /me/` reports the current setting). A private
account's **posts** are visible only to the account itself and its approved
followers — the people with a follow edge *to* it. Everyone else, signed in or
out, gets an empty grid, and a private post's own link reads as missing.

Following a private account takes a **follow request**:

- `follow_user` on a private account files a request instead of following, and
  answers `follow_request_pending: true` (with `follow_category: null`). A
  `category` sent with the call is kept on the request and applied when it is
  approved. Asking twice is refused ("Follow already requested"), and when either
  side has blocked the other the request gets "User does not exist", the same as
  a missing account. Filing, approving and blocking take row locks on the two
  accounts, so a block can't race a request into existence or into a follow.
- The owner lists incoming requests, newest first, with
  `GET /users/follow-requests/?batch=<n>` (30 per page; the clients load more as
  the list scrolls; their own only — there is no username
  parameter; shadow-banned and cross-age-band requesters are left out, as in the
  follower list) and answers each with
  `POST /users/<username>/follow-request/approve/` or `.../deny/`. Approving
  creates the follow edge; denying just drops the request, and the requester is
  not told — they may ask again.
- The requester can withdraw their own request with
  `POST /users/<username>/follow-request/cancel/`.
- Pending requests live in their own table (`FollowRequest`), never as a
  `UserFollow` row, so no audience or feed query can mistake one for a follow.

Switching **private on** keeps every existing follower; it only changes how new
followers arrive. It also takes effect at the API, not on image bytes already
handed out: a post image URL issued while the account was public stays usable
until its CloudFront signature expires (`CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS`,
24h by default — see [Images](images.md)), and indefinitely on a deploy without
signing configured. That grace window is the same one every other visibility
change (a block, a shadow ban, a hidden post) already has; nothing new is
*served* after the switch. `follow_user` and `set_account_privacy` take a row lock
on the account, so a follow racing a privacy change is decided against the
setting it is actually written under. Switching **private off** approves every pending request, since
a public account has nothing left to approve — in bounded chunks, and only from
requesters still in the owner's age band (anyone who has since verified into the
other band has their request dropped). Blocking drops any pending request
in either direction, alongside the follow edges.

The privacy rule lives in `visibility.py` (`privacy_admits`, and `_privacy_q` in
`visible_posts` / `can_view_post`), so it applies everywhere posts are served —
discovery, following and tag feeds, profile grids, saved posts, post details and
the public share pages. Liking, reporting, commenting, and liking or reporting a
comment on a private account's post are refused to non-followers the same way —
and so are the undo actions (unlike, retract a report), so someone who interacted
while the account was public can't keep mutating or probing it by id afterward.
Note the
direction: privacy reads the **viewer → author** edge (do you follow them?) while
[post audience](#relationship-categories--post-audience) reads the **author →
viewer** edge (did they label you?). A non-public post from a private account must
pass both.

Privacy gates **posts only**. A private account's comments — including on
someone else's public post — follow each comment's own audience exactly like
anyone else's, so the commenter decides who sees them per comment. (Comments *on*
a private account's posts stay out of reach for non-followers anyway, because the
post itself is.)

On a private profile someone doesn't follow, the **counts are hidden** too: the
backend zeroes `post_count`, `follower_count` and `following_count`, and the
clients hide the stats row rather than show zeros. The header — name, photo,
bio, join number — is still shown, and a 🔒 *This account is private* note stands
in for the grid. The profile payload carries `is_private` for everyone,
`follow_request_pending` for the viewer, and (owner only) `follow_request_count`.
The Follow button reads **Requested** while a request is pending, and tapping it
cancels the request. The owner reaches the request list from Settings → Follow
Requests or from the "Follow Requests (n)" link on their own profile.

## Audience badges (issue #518)

Your **own** posts and comments carry a small badge saying who can see them:
🌐 *Public*, 👥 *Following*, 🤝 *Friends* or 🏠 *Family* (SF Symbols / Material
icons on mobile), with an accessible label spelling the tier out — "Visible to
friends and family". It appears on feed rows and the post detail header next to
the like count, as an icon-only badge on the square profile-grid tiles (no room
for a label there), and in the header of each comment row. Every tier is badged,
public included: the point is to answer "who can see this?" at a glance, and a
post you meant to keep to family but shared publicly is exactly the case a
missing badge would hide. A post or comment from an older backend that omits
`audience` is badged public, matching how the backend treats a missing value.

The badge is shown **only to the author**. Who someone chose to share with is
their information, like who liked their content
([issue #478](navigation-and-post-actions.md#who-liked-this-issue-478)), so nobody else's
post or comment ever shows one — including the non-public scope label comment
rows used to show every reader, which this replaces. The clients decide purely
from `author_username` matching the signed-in user; the API payloads already
carry `audience` on every post and comment, so no backend change was needed.

## Blocking

Users can block each other from a profile. Blocking is a toggle
(`POST /users/<username>/block/`): blocking severs any follow relationship in
both directions, hides each user's posts from the other's feeds, and stops the
blocked user from finding the blocker in search (the blocker can still search
for the blocked user). Every client has a "Blocked Users" page under Settings,
backed by `GET /users/blocked/`, that lists everyone the signed-in user has
blocked and lets them unblock (the same toggle endpoint).
