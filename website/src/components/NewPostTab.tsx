import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import type { BackgroundColor, CaptionFont } from '../api/types'
import { getCurrentUserId } from '../api/session'
import { uploadImage } from '../api/s3Uploader'
import { isWithinLimit, MAX_CAPTION_LENGTH } from '../auth/requirements'
import CharacterCounter from './CharacterCounter'
import {
  BACKGROUND_COLOR_OPTIONS,
  CAPTION_FONT_OPTIONS,
  backgroundColorClass,
  captionFontClass,
} from './textFormatting'

interface NewPostTabProps {
  /** Called after a successful post so the shell can switch back to the Home tab. */
  onPosted: () => void
}

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
        caption_font: captionFont,
        background_color: backgroundColor,
      }
      const result = await apiClient.createPost(
        imageUrl ? { ...base, image_url: imageUrl } : base,
      )
      setFile(null)
      setPreviewUrl(null)
      setCaption('')
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

      <div className="auth-field">
        <span className="auth-label">Photo (optional)</span>
        <button
          type="button"
          className="btn btn-outline form-section__file-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
        >
          {file ? 'Change Photo' : 'Select a Photo'}
        </button>
        {file && <span className="form-section__file-name">{file.name}</span>}
        {/* The real control is visually hidden but keeps its accessible label so
            assistive tech (and tests) still reach it; the button above drives it. */}
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

      {previewUrl && (
        <img className="form-section__preview" src={previewUrl} alt="Selected post preview" />
      )}

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

      {/* Text customization (issue #318): a whole-caption font and a whole-tile
          background color, with a live preview. */}
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

      <div className="auth-field">
        <span className="auth-label">Preview</span>
        <div className={`caption-preview post-bg ${backgroundColorClass(backgroundColor)}`}>
          <p className={`caption-preview__text ${captionFontClass(captionFont)}`}>
            {caption.trim() || 'Your caption will look like this.'}
          </p>
        </div>
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
