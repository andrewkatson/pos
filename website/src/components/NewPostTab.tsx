import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import type { BackgroundColor, CaptionFont, PostAudience } from '../api/types'
import { getCurrentUserId, getCurrentUsername } from '../api/session'
import { uploadImage } from '../api/s3Uploader'
import { isWithinLimit, MAX_CAPTION_LENGTH } from '../auth/requirements'
import CharacterCounter from './CharacterCounter'
import Avatar from './Avatar'
import CaptionTile from './CaptionTile'
import { BACKGROUND_COLOR_OPTIONS, CAPTION_FONT_OPTIONS } from './textFormatting'

interface NewPostTabProps {
  /** Called after a successful post so the shell can switch back to the Home tab. */
  onPosted: () => void
}

/**
 * The photo preview is always a locally-created object URL (`URL.createObjectURL`
 * of the picked File), never remote or user-authored text. Restricting the
 * `<img src>` to the `blob:` scheme makes that explicit and keeps anything else
 * from reaching the image. (CodeQL's js/xss-through-dom still flags the File →
 * createObjectURL → src flow; that's an accepted false positive — an `<img src>`
 * is not reinterpreted as HTML — dismissed the same way as the prior single-image
 * preview alert.)
 */
function blobPreviewSrc(url: string | null): string | undefined {
  return url && url.startsWith('blob:') ? url : undefined
}

/** Audience options, broadest to closest (issue #392). */
const AUDIENCE_OPTIONS: { value: PostAudience; label: string; hint: string }[] = [
  { value: 'public', label: 'Public', hint: 'Anyone can see this post' },
  { value: 'following', label: 'People I follow', hint: 'Everyone you follow' },
  { value: 'friends', label: 'Friends', hint: 'Friends and family only' },
  { value: 'family', label: 'Family', hint: 'Family only' },
]

/**
 * The "Post" tab: write a caption and optionally pick a photo (#307). When a
 * photo is chosen it is uploaded to S3 via a backend-issued presigned URL (the
 * backend scopes the key to the signed-in user) and the resulting URL is sent
 * to the backend; without one a text-only post is created. Mirrors iOS
 * NewPostView (photo picker, preview, share button, success/failure handling).
 */
function NewPostTab({ onPosted }: NewPostTabProps) {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [caption, setCaption] = useState('')
  const [audience, setAudience] = useState<PostAudience>('public')
  const [captionFont, setCaptionFont] = useState<CaptionFont>('default')
  const [backgroundColor, setBackgroundColor] = useState<BackgroundColor>('default')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Revoke the preview object URL when it changes or the component unmounts.
  // (The URL is created in handleFileChange, not here, to avoid a synchronous
  // setState inside the effect.)
  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  function handleFileChange(next: File | null) {
    setFile(next)
    setPreviewUrl(next ? URL.createObjectURL(next) : null)
  }

  const isFormValid = caption.trim().length > 0 && isWithinLimit(caption, MAX_CAPTION_LENGTH)

  // The signed-in user's name for the preview's author line, so the preview
  // reads like the real post the feed will render (issue #418).
  const username = getCurrentUsername()
  const trimmedCaption = caption.trim()
  // Guarded object URL (blob: only) shared by the picker tile and the preview.
  const previewSrc = blobPreviewSrc(previewUrl)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!isFormValid) return

    const userId = getCurrentUserId()
    if (!userId) {
      setErrorMessage('You must be logged in to post.')
      return
    }

    setIsLoading(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      const imageUrl = file ? await uploadImage(file) : undefined
      const base = {
        caption: caption.trim(),
        audience,
        caption_font: captionFont,
        background_color: backgroundColor,
      }
      const result = await apiClient.createPost(
        imageUrl ? { ...base, image_url: imageUrl } : base,
      )
      setFile(null)
      setPreviewUrl(null)
      setCaption('')
      setAudience('public')
      setCaptionFont('default')
      setBackgroundColor('default')
      // Classification is asynchronous (issue #282): the backend accepts the
      // post in a pending state and reviews it in the background, so tell the
      // user it's under review — the Home grid shows its progress and outcome.
      // Older backends classified inline; their hidden response means the post
      // was flagged but is appealable.
      if (result.status === 'pending' || result.hidden_reason === 'pending_classification') {
        setSuccessMessage(
          result.message ??
            'Your post is being reviewed and will be visible to others once it is approved.',
        )
      } else if (result.hidden) {
        setSuccessMessage(
          result.message ??
            'Your post did not pass automated review. It is hidden for now but you can appeal the decision.',
        )
      } else {
        setSuccessMessage('Your post was shared successfully!')
      }
      onPosted()
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Failed to share post.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form className="form-section" onSubmit={handleSubmit} noValidate>
      {errorMessage && (
        <div className="auth-error" role="alert">
          <p>{errorMessage}</p>
          <button
            type="button"
            className="auth-error__dismiss"
            aria-label="Dismiss error"
            onClick={() => setErrorMessage(null)}
          >
            ✕
          </button>
        </div>
      )}

      {successMessage && (
        <div className="auth-success" role="status">
          {successMessage}
        </div>
      )}

      {/* The photo picker is the image itself (issue #417): tapping the tile
          opens the file chooser. Before a photo is picked it's a grey box with a
          "+"; afterwards it shows the chosen photo, and tapping it re-picks. */}
      <div className="auth-field">
        <span className="auth-label">Photo (optional)</span>
        <button
          type="button"
          className="photo-picker"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          aria-label={file ? 'Change photo' : 'Add a photo'}
        >
          {previewUrl ? (
            <img className="photo-picker__image" src={previewSrc} alt="Selected post preview" />
          ) : (
            <span className="photo-picker__placeholder" aria-hidden="true">
              +
            </span>
          )}
        </button>
        {/* The real control is visually hidden but keeps its accessible label so
            assistive tech (and tests) still reach it; the tile above drives it. */}
        <input
          ref={fileInputRef}
          id="photo"
          className="visually-hidden"
          type="file"
          accept="image/*"
          aria-label="Choose a photo"
          onChange={e => handleFileChange(e.target.files?.[0] ?? null)}
          disabled={isLoading}
        />
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor="caption">
          Caption
        </label>
        <textarea
          id="caption"
          className="text-area"
          rows={4}
          value={caption}
          placeholder="Put a description here"
          onChange={e => setCaption(e.target.value)}
          disabled={isLoading}
        />
        <CharacterCounter value={caption} max={MAX_CAPTION_LENGTH} />
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor="audience">
          Audience
        </label>
        <select
          id="audience"
          className="select-input"
          value={audience}
          onChange={e => setAudience(e.target.value as PostAudience)}
          disabled={isLoading}
        >
          {AUDIENCE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label} — {opt.hint}
            </option>
          ))}
        </select>
      </div>

      {/* Text customization (issue #318) is a secondary concern, so it's tucked
          behind an "Advanced options" disclosure to keep the primary flow short
          and let Share Post sit at the very bottom (issue #419). */}
      <details className="advanced-options">
        <summary className="advanced-options__summary">Advanced options</summary>

        <div className="auth-field">
          <label className="auth-label" htmlFor="caption-font">
            Font
          </label>
          <select
            id="caption-font"
            className="auth-input"
            value={captionFont}
            onChange={e => setCaptionFont(e.target.value as CaptionFont)}
            disabled={isLoading}
          >
            {CAPTION_FONT_OPTIONS.map(option => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="auth-field">
          <span className="auth-label" id="bg-color-label">
            Background color
          </span>
          {/* Toggle buttons in a labeled group rather than an ARIA radiogroup:
              a radiogroup implies roving-tabindex/arrow-key navigation we don't
              implement, so aria-pressed toggles are the more honest semantics. */}
          <div className="color-swatches" role="group" aria-labelledby="bg-color-label">
            {BACKGROUND_COLOR_OPTIONS.map(option => (
              <button
                key={option.key}
                type="button"
                aria-pressed={option.key === backgroundColor}
                aria-label={option.label}
                className={`color-swatch post-bg--${option.key}${
                  option.key === backgroundColor ? ' color-swatch--selected' : ''
                }`}
                onClick={() => setBackgroundColor(option.key)}
                disabled={isLoading}
              />
            ))}
          </div>
        </div>
      </details>

      {/* A full-post preview (issue #418): the author line, the square image (or
          the caption tile for a text-only post) and the caption underneath —
          laid out exactly as the feed renders it, so the user sees where each
          element lands rather than just a style swatch. */}
      <div className="auth-field">
        <span className="auth-label">Preview</span>
        <article className="post-preview">
          <div className="author-line">
            <Avatar username={username ?? undefined} size="sm" />
            <span className="feed-post__author">{username ?? 'You'}</span>
          </div>
          <div className="post-preview__media">
            {previewUrl ? (
              // Decorative here: the picker above already carries the labeled
              // copy of this same image, so the preview copy needs no alt.
              <img className="post-preview__image" src={previewSrc} alt="" />
            ) : (
              <CaptionTile
                caption={trimmedCaption || 'Your caption will look like this.'}
                captionFont={captionFont}
                backgroundColor={backgroundColor}
              />
            )}
          </div>
          {/* An image post shows its caption below the photo, matching the feed;
              a text-only post already shows it as the tile above. */}
          {previewUrl && trimmedCaption && (
            <p className="feed-post__caption">{trimmedCaption}</p>
          )}
        </article>
      </div>

      {isLoading ? (
        <div className="center-spinner">
          <span className="spinner" />
        </div>
      ) : (
        <button type="submit" className="btn btn-primary" disabled={!isFormValid}>
          Share Post
        </button>
      )}
    </form>
  )
}

export default NewPostTab
