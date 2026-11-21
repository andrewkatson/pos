// Names the signed-in account gave up this session (issue #594), stored under
// `former_usernames` as one "name<TAB>held-until epoch ms" per line. A module of
// its own so both api/session and the useOwnUsernames hook can use it — the
// hook must not import more than getCurrentUsername from api/session, which
// many tests mock with only that export.

/** A name the account gave up and the epoch ms its hold ends (issue #594). */
export interface FormerUsername {
  name: string
  heldUntil: number
}

/** Parses the stored former names, dropping any whose hold has ended. */
export function parseFormerUsernames(raw: string | null, now: number): FormerUsername[] {
  return (raw ?? '')
    .split('\n')
    .map(line => {
      const [name, heldUntil] = line.split('\t')
      return { name, heldUntil: Number(heldUntil) }
    })
    .filter(entry => entry.name && Number.isFinite(entry.heldUntil) && entry.heldUntil > now)
}
