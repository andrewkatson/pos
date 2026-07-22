import type { ReactNode } from 'react'

interface ModalProps {
  title: string
  /** Optional plain-text body rendered above `children`. */
  body?: string
  children: ReactNode
}

/**
 * The app's modal shell: overlay, dialog role, title, and optional body.
 *
 * Shared so the dialog markup and ARIA live in one place — accessibility or
 * focus fixes then apply everywhere rather than drifting between copies.
 */
function Modal({ title, body, children }: ModalProps) {
  return (
    <div className="modal-overlay">
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2 className="modal__title">{title}</h2>
        {body && <p className="modal__body">{body}</p>}
        {children}
      </div>
    </div>
  )
}

export default Modal
