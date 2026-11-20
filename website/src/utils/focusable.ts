/** Tabbable descendants of `root`, in DOM order. */
export function focusableIn(root: HTMLElement | null): HTMLElement[] {
  if (!root) {
    return []
  }

  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  )
}
