import type { Requirement } from './requirements'

interface RequirementHintsProps {
  requirements: Requirement[]
  label: string
}

// Renders a checklist of validation requirements. Required rows show a met/unmet
// state visually (color + a CSS ✓/✗ glyph) and via an aria-label. Optional
// suggestions never render as "failed": until satisfied they sit in a neutral
// state announced as "optional", switching to "met" once present. The glyph
// itself is decorative and not announced.
function RequirementHints({ requirements, label }: RequirementHintsProps) {
  return (
    <ul className="auth-hints" aria-label={label}>
      {requirements.map(r => {
        const state = r.didMeetRequirement ? 'met' : r.optional ? 'optional' : 'unmet'
        const announced = r.didMeetRequirement ? 'met' : r.optional ? 'optional' : 'not met'
        return (
          <li
            key={r.label}
            className={`auth-hint auth-hint--${state}`}
            aria-label={`${r.label}: ${announced}`}
          >
            {r.label}
          </li>
        )
      })}
    </ul>
  )
}

export default RequirementHints
