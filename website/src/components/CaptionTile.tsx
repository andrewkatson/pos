import type { MouseEventHandler } from 'react'

/**
 * The visual stand-in for a text-only post's image (#307): the caption rendered
 * centered on a themed gradient background. Used wherever posts render as image
 * tiles — grid cells clamp the text to a few lines, the detail view shows the
 * full caption, and the appeals list shows a small thumbnail-sized tile.
 */
function CaptionTile({
  caption,
  variant,
  className,
  onDoubleClick,
}: {
  caption: string
  variant?: 'detail' | 'thumb'
  className?: string
  onDoubleClick?: MouseEventHandler<HTMLDivElement>
}) {
  const variantClass = variant ? ` caption-tile--${variant}` : ''
  const combinedClass = className ? ` ${className}` : ''
  return (
    <div
      className={`caption-tile${variantClass}${combinedClass}`}
      role="img"
      aria-label={caption}
      onDoubleClick={onDoubleClick}
    >
      <span className="caption-tile__text">{caption}</span>
    </div>
  )
}

export default CaptionTile
