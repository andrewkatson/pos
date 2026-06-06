import type { Requirement } from './requirements'

interface RequirementHintsProps {
  requirements: Requirement[]
  label: string
}

// Renders a checklist of validation requirements. The met/unmet state is shown
// visually with color + a CSS ✓/✗ glyph, and conveyed to assistive tech via an
// aria-label on each row (the glyph itself is decorative and not announced).
function RequirementHints({ requirements, label }: RequirementHintsProps) {
  return (
    <ul className="auth-hints" aria-label={label}>
      {requirements.map(r => (
        <li
          key={r.label}
          className={`auth-hint ${r.met ? 'auth-hint--met' : 'auth-hint--unmet'}`}
          aria-label={`${r.label}: ${r.met ? 'met' : 'not met'}`}
        >
          {r.label}
        </li>
      ))}
    </ul>
  )
}

export default RequirementHints
