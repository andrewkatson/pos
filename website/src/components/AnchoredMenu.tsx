import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react'
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
 * can't be read as a click outside. It also closes on a scroll or resize, since
 * its placement is a snapshot of where the button was and would otherwise drift
 * away from it.
 *
 * Keyboard: focus moves into the menu on open, the arrow keys / Home / End walk
 * the rows and Escape closes — what `role="menu"` promises assistive tech.
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

  // Escape is handled at the window rather than on the menu, so it still closes
  // the menu if focus has wandered off it.
  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onDismiss()
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [onDismiss])

  // The placement above is a snapshot of where the button was, so let the menu
  // go rather than let it drift away from its anchor. Capture phase, so a scroll
  // inside any container counts, not just the window's own.
  useEffect(() => {
    window.addEventListener('scroll', onDismiss, true)
    window.addEventListener('resize', onDismiss)
    return () => {
      window.removeEventListener('scroll', onDismiss, true)
      window.removeEventListener('resize', onDismiss)
    }
  }, [onDismiss])

  // Opening a menu moves focus into it, so a keyboard user isn't left behind on
  // the button with an open menu they can't reach.
  useEffect(() => {
    menuItems(menuRef.current)[0]?.focus()
  }, [])

  function onKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const items = menuItems(menuRef.current)
    if (items.length === 0) return
    // -1 when focus is somewhere else entirely, which the +1/-1 below turn into
    // the first/last row — the conventional entry points for ↓ and ↑.
    const current = items.indexOf(document.activeElement as HTMLButtonElement)
    let next: number
    switch (event.key) {
      case 'ArrowDown':
        next = (current + 1) % items.length
        break
      case 'ArrowUp':
        next = (current - 1 + items.length) % items.length
        break
      case 'Home':
        next = 0
        break
      case 'End':
        next = items.length - 1
        break
      default:
        return
    }
    // Only now, once the key is one we handle: ↑/↓ would otherwise scroll the
    // page out from under the menu.
    event.preventDefault()
    items[next]?.focus()
  }

  return (
    <>
      {/* Invisible; it exists to take the click that closes the menu. */}
      <div className="anchored-menu__backdrop" onClick={onDismiss} />
      <div
        ref={menuRef}
        className="anchored-menu"
        role="menu"
        aria-label={label}
        onKeyDown={onKeyDown}
        style={{ top: `${placement.top}px`, left: `${placement.left}px` }}
      >
        {children}
      </div>
    </>
  )
}

/** The menu's rows, in DOM order, for arrow-key navigation. */
function menuItems(menu: HTMLDivElement | null): HTMLButtonElement[] {
  return Array.from(menu?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? [])
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
