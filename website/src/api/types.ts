// Types mirroring the Django backend in backend/user_system/views.py.
// Field names match the `Fields` constants in backend/user_system/constants.py.

export interface RegisterRequest {
  username: string
  email: string
  password: string
  remember_me?: boolean
  /** YYYY-MM-DD. When provided, the account is identity-verified on creation. */
  date_of_birth?: string
}

export interface AuthResponse {
  session_management_token: string
  /** UUID string matching PositiveOnlySocialUser.id (UUIDField on the backend). */
  user_id: string
  username?: string
  // Only present when remember_me was requested.
  series_identifier?: string
  login_cookie_token?: string
}

export interface LoginRequest {
  username_or_email: string
  password: string
  remember_me?: boolean
}

/**
 * Returned by login instead of a session when the account has two-factor
 * authentication enabled. The challenge is exchanged (with a code) for the
 * real session at login/2fa/ within a few minutes, before it expires.
 */
export interface TwoFactorRequiredResponse {
  two_factor_required: true
  challenge_token: string
}

/** login can answer with a session or, for 2FA-enrolled accounts, a challenge. */
export type LoginResponse = AuthResponse | TwoFactorRequiredResponse

/** Type guard for the two-factor branch of a login response. */
export function isTwoFactorRequired(
  response: LoginResponse,
): response is TwoFactorRequiredResponse {
  return 'two_factor_required' in response && response.two_factor_required === true
}

/** Second login step: exactly one of totp_code / recovery_code is set. */
export interface LoginTwoFactorRequest {
  challenge_token: string
  totp_code?: string
  recovery_code?: string
}

export interface TwoFactorSetupResponse {
  /** Base32 TOTP secret, for manual entry into an authenticator app. */
  totp_secret: string
  /** otpauth:// provisioning URI, rendered as a QR code for scanning. */
  otpauth_uri: string
}

export interface ConfirmTotpRequest {
  totp_code: string
}

export interface ConfirmTotpResponse {
  totp_enabled: boolean
  /** Single-use recovery codes, shown exactly once at enrollment. */
  recovery_codes: string[]
}

/** Disabling requires the password plus exactly one of the two code kinds. */
export interface DisableTotpRequest {
  password: string
  totp_code?: string
  recovery_code?: string
}

export interface DisableTotpResponse {
  totp_enabled: boolean
}

export interface LoginWithRememberMeRequest {
  session_management_token: string
  series_identifier: string
  login_cookie_token: string
}

export interface LoginWithRememberMeResponse {
  session_management_token: string
  login_cookie_token: string
}

export interface MessageResponse {
  message: string
}

export interface RequestResetRequest {
  username_or_email: string
}

export interface VerifyEmailRequest {
  /** The raw token from the verification link in the welcome email. */
  verification_token: string
}

export interface ResendVerificationEmailRequest {
  username_or_email: string
}

export interface VerifyResetRequest {
  username_or_email: string
  verification_token: string
}

export interface VerifyResetResponse {
  message: string
  reset_token: string
}

export interface ResetPasswordRequest {
  username: string
  email: string
  password: string
  reset_token: string
}

export interface CreateUploadUrlResponse {
  /** Short-lived presigned S3 PUT URL to send the JPEG bytes to. */
  upload_url: string
  /** The canonical object URL (no signing query) to pass to createPost. */
  image_url: string
}

export interface CreatePostRequest {
  /** Omitted for a text-only post (#307). */
  image_url?: string
  caption: string
}

export interface CreatePostResponse {
  post_identifier: string
  /** True when the post was created hidden pending appeal (classifier flagged
   * it but the rejection is appealable). Absent/false for a normal post. */
  hidden?: boolean
  hidden_reason?: string
  /** User-facing explanation when the post is hidden pending appeal. */
  message?: string
}

/** A post as returned by the feed/listing endpoints. */
export interface FeedPost {
  post_identifier: string
  /** Null for a text-only post (#307), which renders as a caption tile. */
  image_url: string | null
  /** The full-resolution original image URL, used as a fallback when the
   * compressed `image_url` fails to load. The compressed copy is produced by an
   * async Lambda, so a just-posted (or recently hidden-pending-appeal) image may
   * not exist in the compressed bucket yet; without this fallback those grid
   * tiles render as broken images until the user re-logs in (issues #252/#254).
   * Older responses that predate the field omit it. */
  original_image_url?: string | null
  author_username: string
  caption: string
}

/** A post as returned by the post-details endpoint. */
export interface PostDetails {
  post_identifier: string
  /** Null for a text-only post (#307), which renders as a caption tile. */
  image_url: string | null
  /** The full-resolution original image URL, used as a fallback when the
   * compressed `image_url` fails to load (see `FeedPost.original_image_url`).
   * Older responses that predate the field omit it. */
  original_image_url?: string | null
  caption: string
  /** ISO-8601 timestamp of when the post was created. The backend column is
   * nullable, so this can be null; older responses that predate the field
   * omit it entirely. */
  creation_time?: string | null
  post_likes: number
  /** Whether the requesting user has liked this post. */
  is_liked?: boolean
  /** Whether the requesting user has an active report against this post. */
  is_reported?: boolean
  /** The requesting user's own report reason, so a retract dialog can show it
   * pre-populated (issue #176). Null/absent when they haven't reported it. */
  report_reason?: string | null
  author_username: string
}

export interface CommentOnPostResponse {
  comment_thread_identifier: string
  comment_identifier: string
}

export interface ReplyResponse {
  comment_identifier: string
}

export interface CommentThreadRef {
  comment_thread_identifier: string
}

export interface Comment {
  comment_identifier: string
  body: string
  author_username: string
  creation_time: string
  updated_time: string
  comment_likes: number
  /** Whether the requesting user has liked this comment. */
  is_liked?: boolean
  /** Whether the requesting user has an active report against this comment. */
  is_reported?: boolean
  /** The requesting user's own report reason, so a retract dialog can show it
   * pre-populated (issue #176). Null/absent when they haven't reported it. */
  report_reason?: string | null
}

export interface UserSearchResult {
  username: string
  identity_is_verified: boolean
}

export interface ProfileDetails {
  username: string
  post_count: number
  follower_count: number
  following_count: number
  is_following: boolean
  is_blocked: boolean
  identity_is_verified: boolean
  is_adult: boolean
}

// ---------------------------------------------------------------------------
// Appeals (backend/user_system/views.py appeal endpoints)
// ---------------------------------------------------------------------------

/** What a content appeal can target in-app. Ban appeals go via email. */
export type AppealTargetType = 'post' | 'comment'

/** One of the signed-in user's hidden posts. */
export interface HiddenPost {
  post_identifier: string
  /** Null for a text-only post (#307). */
  image_url: string | null
  caption: string
  /** Why it was hidden: 'classifier', 'reports', or '' (unspecified). */
  hidden_reason: string
  creation_time: string
  /** True once an appeal has been filed for it (it can only be appealed once). */
  has_appeal: boolean
}

/** One of the signed-in user's hidden comments. */
export interface HiddenComment {
  comment_identifier: string
  body: string
  hidden_reason: string
  creation_time: string
  has_appeal: boolean
}

/** An appeal the signed-in user has filed, with its current status. */
export interface MyAppeal {
  appeal_identifier: string
  /** 'post' | 'comment' | 'ban', or null once a resolved target was removed. */
  target_type: AppealTargetType | 'ban' | null
  target_identifier: string | null
  /** 'pending' | 'approved' | 'denied'. */
  status: string
  reason: string
  /** Snapshot of the appealed content, kept when the target was removed. */
  content_snapshot: string | null
  resolution_note: string | null
  creation_time: string
  resolved_time: string | null
}

export interface SubmitAppealRequest {
  target_type: AppealTargetType
  target_identifier: string
  reason: string
}

export interface SubmitAppealResponse {
  appeal_identifier: string
}
