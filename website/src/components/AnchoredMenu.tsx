import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import type { MenuAnchor } from './menuAnchor'

interface AnchoredMenuProps {
  anchor: MenuAnchor
  /** Accessible name for the menu, e.g. "Post options". */
  label: string
  onDismiss: () => void
  /** The menu's rows — `AnchoredMenuItem`s. */
  children: ReactNode
}

/** Space between the menu and the button it hangs off. */
const ANCHOR_GAP = 6
/** Smallest gap kept between the menu and the edge of the viewport. */
const VIEWPORT_MARGIN = 8

/**
 * A small menu that opens next to the control that was clicked rather than in
 * the middle of the screen (issue #477), used for the three-dots options menus
 * on posts and comments.
 *
 * Positioned `fixed` from the anchor's viewport rect: below the button when
 * there's room underneath and flipped above it when there isn't, right-aligned
 * with the button (the ⋯ sits at the right end of its row) and clamped so the
 * menu never hangs off an edge on a narrow screen.
 *
 * Dismissed by clicking the transparent backdrop or pressing Escape — a
 * backdrop rather than a document-level click listener so a click on a menu row
 * can't be read as a click outside.
 */
function AnchoredMenu({ anchor, label, onDismiss, children }: AnchoredMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)
  // Starts at the un-measured guess below and is corrected before paint, once
  // the menu's own size is known.
  const [placement, setPlacement] = useState({
    top: anchor.bottom + ANCHOR_GAP,
    left: anchor.right,
  })

  useLayoutEffect(() => {
    const menu = menuRef.current
    if (!menu) return
    const { width, height } = menu.getBoundingClientRect()
    const maxLeft = Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN)
    const left = Math.min(Math.max(VIEWPORT_MARGIN, anchor.right - width), maxLeft)

    let top = anchor.bottom + ANCHOR_GAP
    if (top + height > window.innerHeight - VIEWPORT_MARGIN) {
      const above = anchor.top - ANCHOR_GAP - height
      // Above the button when it fits there; otherwise pinned to the bottom
      // edge, which is the best a menu taller than the gap can do.
      top =
        above >= VIEWPORT_MARGIN
          ? above
          : Math.max(VIEWPORT_MARGIN, window.innerHeight - height - VIEWPORT_MARGIN)
    }
    setPlacement({ top, left })
  }, [anchor])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onDismiss()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onDismiss])

  return (
    <>
      {/* Invisible, but it takes the click that closes the menu — and keeps the
          page from being scrolled out from under an anchored menu. */}
      <div className="anchored-menu__backdrop" onClick={onDismiss} />
      <div
        ref={menuRef}
        className="anchored-menu"
        role="menu"
        aria-label={label}
        style={{ top: `${placement.top}px`, left: `${placement.left}px` }}
      >
        {children}
      </div>
    </>
  )
}

interface AnchoredMenuItemProps {
  onClick: () => void
  /** Tints the row for a destructive action (Delete). */
  destructive?: boolean
  children: ReactNode
}

/** One row of an `AnchoredMenu`. */
export function AnchoredMenuItem({ onClick, destructive, children }: AnchoredMenuItemProps) {
  return (
    <button
      type="button"
      role="menuitem"
      className={destructive ? 'anchored-menu__item anchored-menu__item--danger' : 'anchored-menu__item'}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

export default AnchoredMenu
