import type { MouseEventHandler } from 'react'
import type { BackgroundColor, CaptionFont } from '../api/types'
import { backgroundColorClass, captionFontClass } from './textFormatting'

/**
 * The visual stand-in for a text-only post's image (#307): the caption rendered
 * centered on a themed gradient background. Used wherever posts render as image
 * tiles — grid cells clamp the text to a few lines, the detail view shows the
 * full caption, and the appeals list shows a small thumbnail-sized tile.
 *
 * The author's chosen caption font and background color (issue #318) are
 * applied here; `default`/absent keeps the original themed gradient and font.
 */
function CaptionTile({
  caption,
  captionFont,
  backgroundColor,
  variant,
  className,
  onDoubleClick,
}: {
  caption: string
  captionFont?: CaptionFont
  backgroundColor?: BackgroundColor
  variant?: 'detail' | 'thumb'
  className?: string
  onDoubleClick?: MouseEventHandler<HTMLDivElement>
}) {
  const variantClass = variant ? ` caption-tile--${variant}` : ''
  const combinedClass = className ? ` ${className}` : ''
  const bgClass = backgroundColorClass(backgroundColor)
  const bgClassName = bgClass ? ` post-bg ${bgClass}` : ''
  const fontClass = captionFontClass(captionFont)
  const textFontClass = fontClass ? ` ${fontClass}` : ''
  return (
    <div
      className={`caption-tile${variantClass}${bgClassName}${combinedClass}`}
      role="img"
      aria-label={caption}
      onDoubleClick={onDoubleClick}
    >
      <span className={`caption-tile__text${textFontClass}`}>{caption}</span>
    </div>
  )
}

export default CaptionTile
