# Navigation and post actions

Every client (website, iOS, Android) shows the same four-item bottom bar:
**Profile**, **Feed**, **Post**, and **Settings**.

The Profile tab is the signed-in user's own profile — their Posts / Followers /
Following counts above their post grid — so it is always one tap away. It also
hosts the user-search bar; while a search is active the results list replaces
the profile body. Follow and Block are hidden on your own profile, since
neither applies to yourself.

**User search** (`GET /users/search/<fragment>/?batch=N`) matches usernames by
case-insensitive prefix and returns them in deterministic batches of ten,
ordered by username; `batch` defaults to 0, and a batch shorter than ten means
there are no more. The search bar fires for queries of three or more characters
(debounced) and shows the first batch inline. On the website, if that batch is
full the client also fetches batch 1 to decide whether to offer a **View all
results** button; that button opens a dialog listing everything fetched so far
with a **Load more** control that pages one further batch per press — never a
loop over every batch, since the endpoint is rate-limited to 30 requests per
minute per user. Retyping discards any in-flight page for the old query. The
dialog is a proper modal: focus moves into it on open, Tab cycles within it,
Escape closes it, and focus returns to the button that opened it. iOS and
Android currently show the first batch only. Results run through
`searchable_users` and the block filters described under [Blocking](audience-and-relationships.md#blocking).

Your **Followers** and **Following** counts are tappable on your own profile
only: each opens a list of those users, and tapping a name opens that user's
profile. These lists are private — you can only see your own. The endpoints
(`GET /users/followers/`, `GET /users/following/`) take no username and always
return the signed-in user's own lists, so another user's followers/following
can't be requested. On anyone else's profile the counts are shown but are not
tappable.

Tapping another user's name anywhere (a post author, a search result, a comment
author) opens that same profile view for them, with Follow and Block shown.
Tapping **your own** name goes to the Profile tab instead of pushing a separate
copy of the profile screen, so you always land on the same profile, with the
bottom bar and search still in place.

Each user may set a **profile photo**, shown next to their name everywhere it
appears — post authors in the feed and on post details, comment authors, search
results, the follower/following and blocked-user lists, and as a large avatar in
the profile header. A user sets or replaces their own photo from their Profile
tab (see [Profile photos](profiles.md#profile-photos)); a user with no photo falls back to a neutral
placeholder.

Posts can be acted on directly from any list — the Profile grid, another user's
profile grid, and the Feed — without opening the post first:

- **Like / unlike**, with the current like count. Hidden on your own posts,
  which the backend refuses to let you like. The count stays either way, but
  without the heart to explain it the bare number is ambiguous, so on your own
  posts it reads "n likes" — the label the post detail already uses (issue
  #476).
- **Save / unsave** (issue #193), a personal bookmark. Unlike a like it is
  offered on every post, including your own, since the saved list is a private
  collection rather than a public signal. Saved posts are collected on the
  **Saved Posts** screen, reachable from the Settings tab.
- **Report**, with a reason. A flag marks posts you have an active report on.
  Reporting opens a moderation review of the content; it never hides anything by
  itself, however many people report the same post (see
  [Reporting and user moderation](reporting.md)).
- **Retract report**, which shows the reason you originally gave.
- **Delete**, offered only on your own posts.
- **Share**, offered on every post (see [Sharing](sharing.md)).

Save, Report, Retract report, Delete and Share live behind a **three-dots (⋯)
options menu** on the post's action row, and the post-detail screen offers the
same menu for the post and for each comment. The menu opens **anchored to the
three dots that were tapped** — a popover next to the button, not a dialog in
the middle or at the top of the screen (issue #477) — so on a long list it is
obvious which item the options belong to. On mobile a long-press on the post
image or a comment opens that same menu, still positioned at that item's three
dots. Confirmations the menu leads to (report reason, retract, delete) remain
modal dialogs.

Each feed row additionally shows the author, the caption under the photo, how
long ago the post was made, and a comment count that opens the post when tapped.
The square profile tiles omit these — there is no room for them. A text-only
post already renders its caption as the tile in place of a photo, so the caption
is not repeated beneath it.

The post listing endpoints (`get_posts_in_feed`, `get_posts_for_followed_users`,
`get_posts_for_user`) therefore return `post_likes`, `is_liked`, `is_saved`,
`is_reported`, `report_reason`, `comment_count`, `creation_time` and `audience`
per post,
matching what the post-details endpoint returns. The state is gathered in grouped queries per
batch rather than per post, so a larger batch does not add queries. The comment
count respects the same visibility rule as the thread listing, so a row never
advertises comments the viewer would not be shown.

Deleting a post from a list removes just that row; the list is not reloaded,
which would otherwise reshuffle the weighted feed ordering under the user.

## Who liked this (issue #478)

Tapping the **like count** on one of your **own** posts or comments opens a
scrollable dialog listing everyone who liked it, newest like first, each row a
tap-through to that user's profile. On anyone else's post or comment the count is
shown but is not tappable: who liked a piece of content is its author's
information, and a third party only ever sees the number.

The endpoints are `GET /posts/<post_identifier>/likes/<batch>/` and
`GET /posts/<post_identifier>/threads/<thread_identifier>/comments/<comment_identifier>/likes/<batch>/`.
Both scope the lookup to the caller's own posts/comments, so asking about
somebody else's is answered exactly like asking about one that does not exist —
there is no oracle for whose content an identifier names. Owning the post is not
owning the comment: only a comment's own author may list its likers.

Likers arrive a batch at a time (`LIKE_BATCH_SIZE`) rather than all at once, so a
post with thousands of likes costs one screenful of rows to open; the clients
append the next batch on demand. Ordering is by the like row's auto-increment id
descending — `PostLike`/`CommentLike` carry no timestamp, but the id is monotonic
with insertion order and unique per (user, target), so batches can't drop or
repeat a row.

The list runs through `searchable_users` and the block filters for the same
reasons the follower/following lists do: a cross-age-band account must not be
revealed at all, a shadow-banned one stays hidden from everyone but itself, and a
blocked account (either direction) stays out of the blocker's listings. So the
list can be shorter than the like count shown on the post — the count is the raw
total, and a hidden liker's like still counts toward it, exactly as their content
still exists while being invisible.

## Saved posts

The **Saved Posts** screen (`get_saved_posts`) lists the posts you have saved,
most recently saved first. It runs through the same visibility filter as every
other listing, so a post that is hidden or whose author is shadow-banned after
you saved it silently drops off rather than rendering as an empty tile.
Unsaving a post from that screen removes its tile.

## Disabling / locking comments (issue #492)

A post's author can turn off commenting on it — either from the moment the
post is created, or afterward once it already has comments. Either way it is
the same field, `Post.comments_disabled` (default `False`, so every
pre-existing post keeps accepting comments), and either way it only blocks
**new** top-level comments and replies; comments already on the post stay
exactly as visible as they were.

- **At creation**: `POST /posts/create/` accepts an optional `comments_disabled`
  boolean; omitting it (or sending `false`) preserves the old behavior.
- **Afterward**: `POST /posts/<post_identifier>/comments/lock/` and
  `POST /posts/<post_identifier>/comments/unlock/` toggle it on an existing
  post. Both are owner-only — the same "look it up via `request.user.post_set`"
  pattern `delete_post` uses, so locking someone else's post answers exactly
  like the post does not exist.

`comment_on_post` and `reply_to_comment_thread` both check the flag (on the
post directly, or via the parent post of the thread being replied to) right
after resolving and visibility-checking the target, and reject with a 403
before the request ever reaches the AI classifier if commenting is off. The
field rides along in every post payload (feed, followed feed, profile grid,
post details, and the public share view) as `comments_disabled`, so a client
can hide its comment composer and "Reply" controls and show a plain "Comments
are turned off for this post" notice instead. Every client also offers a
"Turn on/off commenting" action in the post's own three-dots menu, right next
to Delete, alongside a toggle in the post-creation form.
