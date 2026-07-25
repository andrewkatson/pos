import { Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import { splitCaptionByTags, tagPathFor } from '../utils/tags'

/**
 * A post caption with its `#hashtags` rendered as links to the tag feed
 * (issue #379). Non-tag text is rendered verbatim, so this is a drop-in
 * replacement for rendering `{caption}` directly.
 */
export function CaptionText({ caption }: { caption: string }) {
  const navigate = useNavigate()
  const segments = splitCaptionByTags(caption)

  return (
    <>
      {segments.map((segment, index) => {
        if (segment.type === 'text') {
          return <Fragment key={index}>{segment.text}</Fragment>
        }
        return (
          <button
            key={index}
            type="button"
            className="caption-tag"
            onClick={() => navigate(tagPathFor(segment.tag))}
          >
            {segment.text}
          </button>
        )
      })}
    </>
  )
}
