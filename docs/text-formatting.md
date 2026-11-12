# Text formatting (issue #318)

Authors can style their text. The two surfaces work differently because the
styling means different things:

- **Post captions** carry a **whole-caption font** (`caption_font`) and a
  **whole-tile background color** (`background_color`). Both are single
  curated **keys**, not free-form values: fonts are `default`, `serif`,
  `monospace`, `rounded`, `handwriting`; colors are `default`, `sky`, `mint`,
  `blush`, `lemon`, `lavender`. Each client maps a key to a concrete,
  contrast-checked font/color, so rendering stays consistent and legible across
  web, iOS, and Android. Unknown keys are rejected; `default` reproduces the
  original rendering, so legacy posts and older clients are unaffected. The
  background color only shows on **text-only** posts: on a photo post the image
  fills the tile, so the color has no visible effect. To avoid promising a
  change that never appears, the composer **hides the background-color control
  on an image post** and sends `default` for it (issue #421); the font, which
  does style an image post's caption, stays available. The font applies
  **wherever the caption is shown** — the feed row's caption under the photo as
  well as the post detail view (issue #450) — so a post looks the same whether
  it is scrolled past or opened.
- **The composer keeps the two kinds of post apart (issue #520).** A
  **Text / Image** switch at the top of the New Post screen picks which one is
  being written; it opens on Text. A **text post** is just the caption (no
  photo picker is shown, and a photo picked earlier on the Image tab is never
  sent). An **image post** shows the photo picker and **cannot be shared until
  a photo is chosen** — the caption alone is a text post, so the Share button
  stays disabled. The caption, character counter and audience are shared by
  both. The formatting controls live in one collapsible group whose default
  depends on the kind of post: on a text post it is titled **"Text
  formatting"** and starts **expanded** (the caption *is* the post), on an
  image post it is titled **"Advanced options"** and starts **collapsed**;
  switching tabs resets it to that tab's default, and the user can toggle it
  either way. Both kinds show a **live preview** laid out as the feed will
  render the post: a text post previews as its styled tile; an image post
  previews the photo — or a "your photo will appear here" placeholder before
  one is picked — with the caption underneath in the chosen font, so the
  caption styling is visible before the photo exists. Switching tabs keeps
  the caption, the picked photo and the chosen color in state, so flipping
  back and forth loses nothing.
  Mapping a key to a *distinct* face is part of the contract, not a detail: web
  and iOS reach `rounded` through a system face (`ui-rounded`,
  `.system(design: .rounded)`), but Android has no rounded system family, so it
  bundles Nunito (SIL Open Font License, `android/PositiveOnlySocial/licenses/`)
  rather than falling back to a generic sans — a fallback would make picking
  "Rounded" a silent no-op.
- **Comments** carry **inline** formatting (`body_formatting`): a list of range
  **spans** over the plain comment text, each `{start, end, bold, italic,
  size}`, where `size` is one of `small`/`normal`/`large`/`xlarge` and offsets
  are **UTF-16 code-unit** indices (so JS/Kotlin/Swift index the string
  identically). Spans must stay within bounds, be sorted and non-overlapping,
  carry at least one active style, and number at most 100.

The key invariant: **formatting never changes the text itself.** The caption
and comment body are stored and moderated exactly as before — the AI
classifiers and every input-validation rule run on the untouched plain text,
and the formatting is separate metadata. There is no markup to parse, sanitize,
or classify, and clients render styles by applying attributes to plain-text
spans rather than interpreting embedded markup.
