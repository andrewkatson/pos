import type { PostAudience } from '../api/types'

interface AudienceBadgeProps {
  /** The post's or comment's audience. Absent on older responses, which the
   * backend treats as public — so does the badge. */
  audience?: PostAudience | null
  /** Icon only, for the narrow profile-grid tiles; the label still reaches
   * assistive tech and the tooltip. */
  compact?: boolean
}

/** One entry per audience tier (issue #392), broadest to closest. `label` is the
 * short visible text; `description` is what the badge announces and shows on
 * hover, spelling out who is admitted. */
const AUDIENCE_BADGES: Record<PostAudience, { icon: string; label: string; description: string }> = {
  public: { icon: '🌐', label: 'Public', description: 'Visible to anyone' },
  following: { icon: '👥', label: 'Following', description: 'Visible to people you follow' },
  friends: { icon: '🤝', label: 'Friends', description: 'Visible to friends and family' },
  family: { icon: '🏠', label: 'Family', description: 'Visible to family only' },
}

/**
 * A small badge telling the signed-in user who can see one of their own posts
 * or comments (issue #518). Callers render it only on the viewer's own content:
 * who an author chose to share with is the author's information, the same way
 * "who liked this" is (#478), so a third party never sees it.
 *
 * Every tier gets a badge, public included — the point is to answer "who can
 * see this?" at a glance, and a post you meant to keep to family but posted
 * publicly is exactly the case a missing badge would hide.
 */
function AudienceBadge({ audience, compact = false }: AudienceBadgeProps) {
  // An unknown tier from a newer backend falls back to public rather than
  // rendering an empty badge.
  const tier: PostAudience = audience && audience in AUDIENCE_BADGES ? audience : 'public'
  const badge = AUDIENCE_BADGES[tier]
  return (
    <span
      className={compact ? 'audience-badge audience-badge--compact' : 'audience-badge'}
      title={badge.description}
      aria-label={badge.description}
      data-audience={tier}
    >
      <span aria-hidden="true">{badge.icon}</span>
      {!compact && <span aria-hidden="true">{badge.label}</span>}
    </span>
  )
}

export default AudienceBadge
