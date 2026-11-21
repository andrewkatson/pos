// Fired on window when the cached signed-in username changes, e.g. after a
// rename on this or another device (issue #594). Its own module so the hook
// below keeps working in tests that mock api/session.
export const USERNAME_CHANGED_EVENT = 'session-username-changed'
