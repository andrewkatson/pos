// Shared text-formatting helpers for posts and comments (issue #318).
//
// Fonts, background colors, and text sizes are curated keys that map to CSS
// classes defined in MainApp.css. Keeping the mapping here (and the concrete
// colors/fonts in CSS) means the picker UIs, the caption tiles, and the
// comment renderer all agree on the same finite set of styles.

import type { BackgroundColor, CaptionFont, TextSize } from '../api/types'

export interface CaptionFontOption {
  key: CaptionFont
  label: string
}

export interface BackgroundColorOption {
  key: BackgroundColor
  label: string
}

/** Selectable caption fonts, in display order (default first). */
export const CAPTION_FONT_OPTIONS: readonly CaptionFontOption[] = [
  { key: 'default', label: 'Default' },
  { key: 'serif', label: 'Serif' },
  { key: 'monospace', label: 'Monospace' },
  { key: 'rounded', label: 'Rounded' },
  { key: 'handwriting', label: 'Handwriting' },
]

/** Selectable post background colors, in display order (default first). */
export const BACKGROUND_COLOR_OPTIONS: readonly BackgroundColorOption[] = [
  { key: 'default', label: 'Default' },
  { key: 'sky', label: 'Sky' },
  { key: 'mint', label: 'Mint' },
  { key: 'blush', label: 'Blush' },
  { key: 'lemon', label: 'Lemon' },
  { key: 'lavender', label: 'Lavender' },
]

/** Selectable inline text sizes for comments, in ascending order. */
export const TEXT_SIZE_OPTIONS: readonly TextSize[] = ['small', 'normal', 'large', 'xlarge']

/** CSS class applying a caption font, or '' for the default (no override). */
export function captionFontClass(font: CaptionFont | undefined | null): string {
  return font && font !== 'default' ? `caption-font--${font}` : ''
}

/** CSS class applying a post background color, or '' for the default. */
export function backgroundColorClass(color: BackgroundColor | undefined | null): string {
  return color && color !== 'default' ? `post-bg--${color}` : ''
}

/** CSS class applying an inline text size, or '' for the normal size. */
export function textSizeClass(size: TextSize | undefined | null): string {
  return size && size !== 'normal' ? `fmt-size--${size}` : ''
}
