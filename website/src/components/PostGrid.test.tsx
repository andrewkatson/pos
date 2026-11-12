import { render, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import PostGrid from './PostGrid'
import type { FeedPost } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {},
}))

function makePosts(count: number): FeedPost[] {
  return Array.from({ length: count }, (_, i) => ({
    post_identifier: `p${i}`,
    image_url: `http://img/${i}.jpg`,
    author_username: 'ada',
    caption: '',
  }))
}

// jsdom has no layout, so stand in for the grid's box: `bottom` is where the
// grid ends relative to the top of the viewport.
let gridBottom = 0
let gridHeight = 0

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    const height = this.classList.contains('post-grid') ? gridHeight : 0
    const bottom = this.classList.contains('post-grid') ? gridBottom : 0
    return {
      top: bottom - height,
      bottom,
      height,
      left: 0,
      right: 0,
      width: 0,
      x: 0,
      y: 0,
    } as DOMRect
  })
  vi.stubGlobal('innerHeight', 800)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function renderGrid(posts: FeedPost[], onFillRequest?: () => void) {
  return render(
    <MemoryRouter>
      <PostGrid
        posts={posts}
        currentUsername="me"
        onPostDeleted={() => {}}
        onError={() => {}}
        readOnly
        onFillRequest={onFillRequest}
      />
    </MemoryRouter>,
  )
}

test('asks for more while the grid ends above the bottom of the screen', () => {
  gridHeight = 500
  gridBottom = 600
  const onFillRequest = vi.fn()

  renderGrid(makePosts(9), onFillRequest)

  expect(onFillRequest).toHaveBeenCalledTimes(1)
})

test('asks for more to complete a partial last row, even past the screen', () => {
  gridHeight = 1500
  gridBottom = 1600
  const onFillRequest = vi.fn()

  renderGrid(makePosts(10), onFillRequest)

  expect(onFillRequest).toHaveBeenCalledTimes(1)
})

test('stops once full rows run past the bottom of the screen', () => {
  gridHeight = 1500
  gridBottom = 1600
  const onFillRequest = vi.fn()

  renderGrid(makePosts(30), onFillRequest)

  expect(onFillRequest).not.toHaveBeenCalled()
})

test('re-checks when the window grows, asking only once per batch', () => {
  gridHeight = 1500
  gridBottom = 1600
  const onFillRequest = vi.fn()
  renderGrid(makePosts(30), onFillRequest)
  expect(onFillRequest).not.toHaveBeenCalled()

  // Zooming out shrinks the grid so it no longer reaches the bottom.
  gridHeight = 500
  gridBottom = 600
  fireEvent(window, new Event('resize'))
  fireEvent(window, new Event('resize'))

  expect(onFillRequest).toHaveBeenCalledTimes(1)
})

test('asks again after the next batch arrives if the screen still is not full', () => {
  gridHeight = 300
  gridBottom = 400
  const onFillRequest = vi.fn()
  const { rerender } = renderGrid(makePosts(10), onFillRequest)
  expect(onFillRequest).toHaveBeenCalledTimes(1)

  // The owner withdraws the callback while the batch loads...
  rerender(
    <MemoryRouter>
      <PostGrid
        posts={makePosts(10)}
        currentUsername="me"
        onPostDeleted={() => {}}
        onError={() => {}}
        readOnly
      />
    </MemoryRouter>,
  )
  // ...and offers it again once it lands.
  rerender(
    <MemoryRouter>
      <PostGrid
        posts={makePosts(20)}
        currentUsername="me"
        onPostDeleted={() => {}}
        onError={() => {}}
        readOnly
        onFillRequest={onFillRequest}
      />
    </MemoryRouter>,
  )

  expect(onFillRequest).toHaveBeenCalledTimes(2)
})

test('does nothing for a grid with no layout box', () => {
  gridHeight = 0
  gridBottom = 0
  const onFillRequest = vi.fn()

  renderGrid(makePosts(10), onFillRequest)

  expect(onFillRequest).not.toHaveBeenCalled()
})
