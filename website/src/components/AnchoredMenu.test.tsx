import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import AnchoredMenu, { AnchoredMenuItem } from './AnchoredMenu'
import { anchorFrom } from './menuAnchor'

/** jsdom has no layout, so every rect is zero unless a test supplies one. */
function stubRects({ menuWidth, menuHeight }: { menuWidth: number; menuHeight: number }) {
  const original = Element.prototype.getBoundingClientRect
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: Element,
  ) {
    if (this.classList.contains('anchored-menu')) {
      return { width: menuWidth, height: menuHeight } as DOMRect
    }
    return original.call(this)
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

test('opens below the anchor and right-aligned with it', () => {
  window.innerWidth = 400
  window.innerHeight = 800
  stubRects({ menuWidth: 160, menuHeight: 100 })

  render(
    <AnchoredMenu
      anchor={{ top: 500, bottom: 520, right: 380 }}
      label="Post options"
      onDismiss={() => {}}
    >
      <AnchoredMenuItem onClick={() => {}}>Share</AnchoredMenuItem>
    </AnchoredMenu>,
  )

  const menu = screen.getByRole('menu', { name: 'Post options' })
  // Just under the button (20px tall anchor ends at 520, plus the 6px gap)...
  expect(menu).toHaveStyle({ top: '526px' })
  // ...and its right edge lines up with the button's.
  expect(menu).toHaveStyle({ left: '220px' })
})

test('flips above the anchor when there is no room below', () => {
  window.innerWidth = 400
  window.innerHeight = 800
  stubRects({ menuWidth: 160, menuHeight: 200 })

  render(
    <AnchoredMenu
      anchor={{ top: 700, bottom: 720, right: 380 }}
      label="Post options"
      onDismiss={() => {}}
    >
      <AnchoredMenuItem onClick={() => {}}>Share</AnchoredMenuItem>
    </AnchoredMenu>,
  )

  // 720 + 6 + 200 would run off the bottom, so it opens above: 700 - 6 - 200.
  expect(screen.getByRole('menu')).toHaveStyle({ top: '494px' })
})

test('never hangs off the left edge on a narrow screen', () => {
  window.innerWidth = 320
  window.innerHeight = 800
  stubRects({ menuWidth: 300, menuHeight: 100 })

  render(
    <AnchoredMenu
      anchor={{ top: 100, bottom: 120, right: 120 }}
      label="Post options"
      onDismiss={() => {}}
    >
      <AnchoredMenuItem onClick={() => {}}>Share</AnchoredMenuItem>
    </AnchoredMenu>,
  )

  // Right-aligning would put it at -180; it's clamped to the 8px margin.
  expect(screen.getByRole('menu')).toHaveStyle({ left: '8px' })
})

test('dismisses on a click outside and on Escape', async () => {
  const onDismiss = vi.fn()
  render(
    <AnchoredMenu
      anchor={{ top: 100, bottom: 120, right: 200 }}
      label="Post options"
      onDismiss={onDismiss}
    >
      <AnchoredMenuItem onClick={() => {}}>Share</AnchoredMenuItem>
    </AnchoredMenu>,
  )

  await userEvent.keyboard('{Escape}')
  expect(onDismiss).toHaveBeenCalledTimes(1)

  // Clicking a row is not a click outside, so the backdrop must not swallow it.
  await userEvent.click(screen.getByRole('menuitem', { name: 'Share' }))
  expect(onDismiss).toHaveBeenCalledTimes(1)

  await userEvent.click(document.querySelector('.anchored-menu__backdrop') as HTMLElement)
  expect(onDismiss).toHaveBeenCalledTimes(2)
})

test('anchorFrom snapshots the edges the placement needs', () => {
  const button = document.createElement('button')
  vi.spyOn(button, 'getBoundingClientRect').mockReturnValue({
    top: 10,
    bottom: 30,
    right: 90,
    left: 60,
  } as DOMRect)
  expect(anchorFrom(button)).toEqual({ top: 10, bottom: 30, right: 90 })
})
