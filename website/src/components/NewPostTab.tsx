import { useState, type FormEvent } from 'react'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'

interface NewPostTabProps {
  /** Called after a successful post so the shell can switch back to the Home tab. */
  onPosted: () => void
}

/**
 * The "Post" tab: create a new post from an image URL and caption. The native
 * apps upload a picked photo to S3 first; the web build has no uploader, so it
 * takes the hosted image URL directly (matching the backend's `image_url`
 * field). Mirrors iOS NewPostView (preview, share button, success/failure).
 */
function NewPostTab({ onPosted }: NewPostTabProps) {
  const [imageUrl, setImageUrl] = useState('')
  const [caption, setCaption] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const isFormValid = imageUrl.trim().length > 0 && caption.trim().length > 0

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!isFormValid) return
    setIsLoading(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      await apiClient.createPost({ image_url: imageUrl.trim(), caption: caption.trim() })
      setImageUrl('')
      setCaption('')
      setSuccessMessage('Your post was shared successfully!')
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
        <label className="auth-label" htmlFor="imageUrl">
          Image URL
        </label>
        <input
          id="imageUrl"
          className="search-bar"
          type="url"
          inputMode="url"
          autoCapitalize="none"
          placeholder="https://example.com/photo.jpg"
          value={imageUrl}
          onChange={e => setImageUrl(e.target.value)}
          disabled={isLoading}
        />
      </div>

      {imageUrl.trim().length > 0 && (
        <img className="form-section__preview" src={imageUrl} alt="Selected post preview" />
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
          onChange={e => setCaption(e.target.value)}
          disabled={isLoading}
        />
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
