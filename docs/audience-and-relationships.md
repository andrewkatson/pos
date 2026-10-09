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
