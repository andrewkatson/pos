type LogoProps = {
  size?: number
  className?: string
}

/**
 * The Good Vibes Only smiley logo, mirroring the app icon used in iOS and
 * Android (a blue rounded square with a white smiley face). Kept in sync with
 * public/favicon.svg.
 */
function Logo({ size = 96, className }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      className={className}
      role="img"
      aria-label="Good Vibes Only smiley logo"
    >
      <rect x="4" y="4" width="92" height="92" rx="22" fill="#5BA4DC" />
      <circle cx="50" cy="50" r="33" fill="none" stroke="#FFFFFF" strokeWidth="3" />
      <ellipse cx="38" cy="42" rx="4" ry="7" fill="#FFFFFF" />
      <ellipse cx="62" cy="42" rx="4" ry="7" fill="#FFFFFF" />
      <path
        d="M34 58 Q50 73 66 58"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}

export default Logo
