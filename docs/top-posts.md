# Top scoreboards

The Feed tab has a third segment, **Top**, beside For You and Following. It
holds two boards, switched with a **Posts / People** toggle:

- **Posts** (issue #558): the most-liked **public** posts across the whole app
  over a period the viewer picks: **Today**, **This week** (the default),
  **This month** or **This year**. Each row is numbered by its rank and carries
  the same author line, caption and action bar as the other feeds.
- **People** (issue #562): the most-followed accounts **right now**, each row
  numbered by rank with the avatar, username, verified badge and follower
  count, tapping through to the profile. It has no period picker; most-followed
  over a period is a follow-up.

## Posts board

### Endpoint

`GET /feed/top/<batch>/?period=day|week|month|year` returns the ranking in the
usual `POST_BATCH_SIZE` batches with the same per-post payload as the other
listing endpoints (see [Navigation and post actions](navigation-and-post-actions.md)).
An absent or empty `period` means `week`; anything else outside the four values
is a 400.

- **Window.** Periods are rolling lookbacks from now — 1, 7, 30 and 365 days
  (`TOP_POST_PERIOD_DAYS`). `PostLike` has no timestamp, so "top this week"
  means posts *created* in the last 7 days, ranked by their total likes.
- **Ranking.** Like count descending, then newest first, then the post id, so
  the order is deterministic for a given state of the data. Likes are counted
  `distinct`, since `visible_posts` joins the author's follow edges and would
  otherwise count each like once per edge.
- **Paging is live, not a snapshot.** Batches are LIMIT/OFFSET over the current
  ranking, so a post whose likes change between two page requests can move
  across a page boundary and be repeated or skipped by the next page. Clients
  number rows by list position, so ranks are approximate past the first page
  while the board is moving. Clients drop a repeated post when appending a page,
  so the list never holds the same post twice, and keep fetching past a page
  made up only of repeats so pagination doesn't stall on it. Serving pages from a stable snapshot comes with
  pre-computation (issue #559).
- **Switching period.** All three clients discard a response that arrives for
  a period the viewer has since switched away from, always reload page 0 for
  the newly selected period even if a load was still in flight, and clear the
  old list as soon as the period changes — so a previous board is never shown
  under the new period, or left behind if the new load fails. On iOS and
  Android that also means the new page's rows are freshly created, so the last
  row's appear hook can still request the next page.
- **Switching feed.** The website shows one list for all three feeds, so it
  applies the same discard-and-clear handling when switching between For You,
  Following and Top (and the Following group). iOS and Android keep a separate
  view model per feed, so switching feed leaves each feed's own list and any
  in-flight request in place; nothing from one feed can land in another.
- **Depth.** The board stops at `TOP_POSTS_LIMIT` (100). Batches past it are
  empty: it is a "top N", not a second endless feed.

### Eligibility

- Only `audience = public` posts compete — a scoreboard is a public ranking, so
  a restricted post stays off it even for viewers its audience admits.
- Posts by private accounts (issue #96) never compete either, even for the
  approved followers who can otherwise see them, for the same reason.
- Only classifier-approved posts compete, the viewer's own included: an author
  never sees their own pending or rejected post ranked.
- Everything else is the standard listing rule — `visible_posts` plus the block
  filters in both directions. Hidden content and shadow-banned authors stay off
  the board for everyone else, and because of age segregation each age band
  effectively gets its own board (see [Age and identity](age-and-identity.md)).

### Computation

The ranking is computed on the fly per request. Pre-computing each period's
board on a schedule is tracked in issue #559.

## People board

`GET /users/top/<batch>/` returns the ranking in batches of
`TOP_USERS_BATCH_SIZE` (10), each row carrying `username`,
`identity_is_verified`, the author avatar fields and `follower_count`. It stops
at `TOP_USERS_LIMIT` (100); later batches are empty.

- **Count.** `follower_count` is counted exactly as the profile header counts
  it (`with_visible_follower_count` in `visibility.py`): followers who are
  shadow-banned or outside the viewer's age band don't count (issue #398). So
  the number on the board always matches the profile it opens.
- **Ranking.** Follower count descending, then username. Like the posts board
  this is live OFFSET paging, so someone whose count changes between two page
  requests can repeat or be skipped; the clients drop repeats and page past a
  page of nothing but repeats, exactly as for posts.
- **Eligibility.** The user-search rule (`searchable_users`: no shadow-banned or
  cross-age-band accounts, so each age band gets its own board), the block
  filters in both directions, no account under an outright ban, and only
  accounts with at least one counted follower. The viewer can appear on their
  own board unless their account is private.
- **Private accounts** (issue #96) are left off the board entirely, so it can
  never reveal a follower count their profile hides from non-followers.
