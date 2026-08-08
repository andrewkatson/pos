/**
 * Where an open menu should point: the viewport rect of the control that opened
 * it. Only the edges `AnchoredMenu` places against are kept, so the caller can
 * hold this in state without pinning the DOM node alive.
 *
 * Its own module rather than part of AnchoredMenu.tsx so that file exports only
 * components (the fast-refresh rule).
 */
export interface MenuAnchor {
  top: number
  bottom: number
  right: number
}

/** Snapshots the button the user just clicked, for `AnchoredMenu`'s `anchor`. */
export function anchorFrom(element: HTMLElement): MenuAnchor {
  const { top, bottom, right } = element.getBoundingClientRect()
  return { top, bottom, right }
}
