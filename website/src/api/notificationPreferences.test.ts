import { expect, test } from 'vitest'
import { visibleNotificationRows } from './notificationPreferences'
import type { NotificationPreference } from './types'

const tree = (overrides: Record<string, boolean> = {}): NotificationPreference[] =>
  [
    { type: 'all', label: 'Push notifications', parent: null },
    { type: 'post_rejected', label: 'Post moderation', parent: 'all' },
    { type: 'new_post', label: 'New posts', parent: 'all' },
    { type: 'new_post_friend', label: 'From friends', parent: 'new_post' },
    { type: 'new_like', label: 'Likes', parent: 'all' },
    { type: 'new_like_other', label: 'From everyone else', parent: 'new_like' },
  ].map(p => ({ ...p, enabled: overrides[p.type] ?? true }))

const shown = (prefs: NotificationPreference[]) =>
  visibleNotificationRows(prefs).map(r => `${r.depth}:${r.pref.type}`)

test('indents each row under its parent', () => {
  expect(shown(tree())).toEqual([
    '0:all', '1:post_rejected', '1:new_post', '2:new_post_friend', '1:new_like', '2:new_like_other',
  ])
})

test('an off parent hides its whole subtree', () => {
  expect(shown(tree({ new_post: false }))).toEqual([
    '0:all', '1:post_rejected', '1:new_post', '1:new_like', '2:new_like_other',
  ])
  expect(shown(tree({ all: false }))).toEqual(['0:all'])
})

test('rows without a known parent stay at the top level', () => {
  expect(shown([
    { type: 'post_rejected', label: 'Post moderation', enabled: true },
    { type: 'x', label: 'X', parent: 'missing', enabled: true },
  ])).toEqual(['0:post_rejected', '0:x'])
})
