import { characterCount, NEAR_LIMIT_FRACTION } from '../auth/requirements'

interface CharacterCounterProps {
  /** The current field text. */
  value: string
  /** The maximum allowed length, in unicode code points. */
  max: number
}

// A live "count / max" indicator that mirrors the backend length limits
// (backend/user_system/constants.py). It counts unicode code points (like the
// server's Python len()) so the displayed count matches what the server
// enforces. The text turns amber as the user nears the limit and red once over
// it; the over state is also announced assertively for screen readers.
function CharacterCounter({ value, max }: CharacterCounterProps) {
  const count = characterCount(value)
  const isOver = count > max
  const isNear = !isOver && count >= max * NEAR_LIMIT_FRACTION
  const state = isOver ? 'over' : isNear ? 'near' : 'ok'

  return (
    <div
      className={`char-counter char-counter--${state}`}
      aria-live={isOver ? 'assertive' : 'polite'}
    >
      {isOver ? `${count - max} over the ${max} character limit` : `${count} / ${max}`}
    </div>
  )
}

export default CharacterCounter
