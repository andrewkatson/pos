import { useId, type ReactNode } from 'react'

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
 *
 * The dialog is named by the rendered heading (`aria-labelledby`) rather than a
 * duplicated `aria-label`, and described by the body paragraph when there is
 * one, so screen readers announce both on open.
 */
function Modal({ title, body, children }: ModalProps) {
  const titleId = useId()
  const bodyId = useId()

  return (
    <div className="modal-overlay">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={body ? bodyId : undefined}
      >
        <h2 className="modal__title" id={titleId}>
          {title}
        </h2>
        {body && (
          <p className="modal__body" id={bodyId}>
            {body}
          </p>
        )}
        {children}
      </div>
    </div>
  )
}

export default Modal
