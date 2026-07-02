import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import { getCurrentUserId } from '../api/session'
import { uploadImage } from '../api/s3Uploader'
import { isWithinLimit, MAX_CAPTION_LENGTH } from '../auth/requirements'
import CharacterCounter from './CharacterCounter'

interface NewPostTabProps {
  /** Called after a successful post so the shell can switch back to the Home tab. */
  onPosted: () => void
}

/**
 * The "Post" tab: write a caption and optionally pick a photo (#307). When a
 * photo is chosen it is uploaded to S3 (scoped to the signed-in user) and the
 * resulting URL is sent to the backend; without one a text-only post is
 * created. Mirrors iOS NewPostView (photo picker, preview, share button,
 * success/failure handling).
 */
function NewPostTab({ onPosted }: NewPostTabProps) {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [caption, setCaption] = useState('')
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
      const imageUrl = file ? await uploadImage(file, userId) : undefined
      const result = await apiClient.createPost(
        imageUrl ? { image_url: imageUrl, caption: caption.trim() } : { caption: caption.trim() },
      )
      setFile(null)
      setPreviewUrl(null)
      setCaption('')
      // A post flagged by automated review is created hidden pending appeal; tell
      // the user it's hidden but appealable rather than implying it's live.
      setSuccessMessage(
        result.hidden
          ? (result.message ??
              'Your post did not pass automated review. It is hidden for now but you can appeal the decision.')
          : 'Your post was shared successfully!',
      )
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
