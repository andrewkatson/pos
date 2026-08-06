// A stateful stub that mimics the Django backend logic entirely in memory.
// Mirrors ios/.../api/StatefulStubbedAPI.swift and
// android/.../api/StatefulStubbedAPI.kt. Useful for tests and offline/demo
// modes. Errors are surfaced by throwing ApiError, matching the real ApiClient.

import { ApiError, INVALID_TWO_FACTOR_CHALLENGE } from './client'
import { characterCount, MAX_BIO_LENGTH } from '../auth/requirements'
import { extractTags } from '../utils/tags'
import {
  INTEREST_OPTIONS,
  INTEREST_SLUGS,
  MAX_FREEFORM_INTERESTS,
  MAX_FREEFORM_INTEREST_LENGTH,
  REJECTED_TEXT_ECHO_LIMIT,
  matchInterestSlugs,
} from './interestVocabulary'
import type { PositiveOnlySocialAPI } from './PositiveOnlySocialAPI'
import type {
  AuthResponse,
  BackgroundColor,
  CaptionFont,
  Comment,
  CommentFormatSpan,
  CommentOnPostResponse,
  CommentThreadRef,
  ChangePasswordRequest,
  ConfirmTotpRequest,
  ConfirmTotpResponse,
  CreatePostRequest,
  CreatePostResponse,
  CreateUploadUrlResponse,
  CurrentUser,
  DisableTotpRequest,
  DisableTotpResponse,
  FeedPost,
  FollowCategory,
  HiddenComment,
  HiddenPost,
  LoginRequest,
  LoginResponse,
  LoginTwoFactorRequest,
  LoginWithRememberMeRequest,
  LoginWithRememberMeResponse,
  MessageResponse,
  MyAppeal,
  PostAudience,
  PostDetails,
  NotificationPreference,
  PostStatusResponse,
  ProfileDetails,
  ProfileImageStatus,
  RegisterDeviceRequest,
  RegisterRequest,
  RemoveProfilePhotoResponse,
  SetNotificationPreferenceResponse,
  ReplyResponse,
  RequestResetRequest,
  ResendVerificationEmailRequest,
  ResetPasswordRequest,
  SetProfilePhotoRequest,
  SetProfilePhotoResponse,
  SetBioRequest,
  SetBioResponse,
  InterestOptionsResponse,
  InterestsResponse,
  SetInterestsRequest,
  SetInterestsResponse,
  SubmitAppealRequest,
  SubmitAppealResponse,
  TwoFactorSetupResponse,
  AuthorAvatarFields,
  UserSearchResult,
  VerifyEmailRequest,
  VerifyResetRequest,
  VerifyResetResponse,
} from './types'

// Stub-specific tuning values, matching the iOS/Android StatefulStubbedAPI
// stubs. These intentionally differ from backend/user_system/constants.py
// (which uses larger batches); the stub favors small, test-friendly numbers and
// is not the source of truth for the real backend.
const POST_BATCH_SIZE = 10
const COMMENT_BATCH_SIZE = 10

// The stub has no clock-based TOTP; this fixed code is the one the stub
// accepts, mirroring the fixed codes in the iOS/Android stubs.
export const STUB_TOTP_CODE = '123456'
const STUB_RECOVERY_CODE_COUNT = 10

// The registration strength policy the real backend enforces (Patterns.password
// in backend/user_system/constants.py): at least eight non-whitespace characters
// with a lower- and upper-case letter and a digit. The stub applies it to
// changePassword too, so a weak new password fails here exactly as it would in
// production rather than silently succeeding against the stub.
const STRONG_PASSWORD = /^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\S+$).{8,}$/

/** Cryptographically secure random bytes. These feed credential-shaped values
 * (TOTP secret, recovery codes), so Math.random() is not appropriate even in a
 * stub — it would model the real flow with an insecure generator. */
function randomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return bytes
}

// Recovery codes must match the 10-hex-character format the UI and backend
// enforce (Patterns.recovery_code), so the stub is usable in demo mode.
// 5 bytes render as exactly 10 hex characters.
function stubRecoveryCode(): string {
  return Array.from(randomBytes(5), byte => byte.toString(16).padStart(2, '0')).join('')
}

// Authenticator apps require the otpauth:// `secret=` to be Base32 (RFC 4648:
// A-Z and 2-7). Deriving it from newId() would embed a hyphen, so QR/manual
// enrollment would fail in demo mode; generate a real Base32 secret instead.
// The alphabet is exactly 32 chars, so indexing a byte by % 32 is unbiased.
const BASE32_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
function stubTotpSecret(): string {
  return Array.from(randomBytes(32), byte => BASE32_ALPHABET[byte % 32]).join('')
}

interface UserMock {
  id: string
  username: string
  email: string
  passwordHash: string
  verificationToken: string | null
  resetToken: string | null
  emailVerified: boolean
  emailVerificationToken: string | null
  following: Set<string>
  /** Relationship category (issue #392) the user assigned to each person they
   * follow, keyed by that person's id. Absent entries default to 'following'. */
  followCategories: Map<string, FollowCategory>
  followers: Set<string>
  isVerified: boolean
  isAdult: boolean
  blocked: Set<string>
  blockedBy: Set<string>
  totpSecret: string | null
  totpEnabled: boolean
  /** Unused recovery codes; consumed codes are removed. */
  recoveryCodes: Set<string>
  /** Post ids the user has saved, oldest first, so the saved listing can
   * return them newest-first (issue #193). */
  savedPostIds: string[]
  /** Approved profile photo shown to everyone (issue #7), or null. */
  profileImageUrl: string | null
  /** A photo still under async review, shown to nobody until approved. */
  pendingProfileImageUrl: string | null
  profileImageStatus: ProfileImageStatus
  profileImageReasonCode: string | null
  /** Sequential join number (#198), assigned in registration order. */
  membershipNumber: number
  /** Free-text bio shown on the profile (issue #380); '' when unset. */
  bio: string
  /** Positive interest weighting buckets (issues #446/#35): picks ∪ mapped
   * freeform. */
  interestCategories: Set<string>
  /** Freeform interest terms the user typed, lowercased, in entry order. */
  freeformInterests: string[]
}

interface TwoFactorChallengeMock {
  challengeToken: string
  userId: string
  rememberMe: boolean
}

interface SessionMock {
  managementToken: string
  userId: string
}

interface LoginCookieMock {
  seriesIdentifier: string
  token: string
  userId: string
}

interface PostMock {
  postIdentifier: string
  authorId: string
  /** Null for a text-only post (#307). */
  imageUrl: string | null
  caption: string
  /** Hashtags parsed from the caption (issue #379), normalized and sorted. */
  tags: string[]
  /** Whole-caption font + whole-tile background color keys (issue #318). */
  captionFont: CaptionFont
  backgroundColor: BackgroundColor
  creationTime: number
  hidden: boolean
  hiddenReason: string
  /** Who may see the post (issue #392). */
  audience: PostAudience
  /** Public reason code recorded by the (stubbed) async classifier (#282). */
  reasonCode: string | null
  likes: Set<string>
  /** Reporting user id -> their reason, so retract flows can show the reason. */
  reports: Map<string, string>
}

interface CommentMock {
  commentIdentifier: string
  authorId: string
  body: string
  /** Inline formatting spans over `body` (issue #318); null = plain. */
  bodyFormatting: CommentFormatSpan[] | null
  /** Who may see this comment (issue #445). */
  audience: PostAudience
  creationTime: number
  hidden: boolean
  hiddenReason: string
  likes: Set<string>
  /** Reporting user id -> their reason, so retract flows can show the reason. */
  reports: Map<string, string>
}

interface AppealMock {
  appealIdentifier: string
  appellantId: string
  targetType: 'post' | 'comment'
  targetId: string
  reason: string
  contentSnapshot: string
  status: 'pending' | 'approved' | 'denied'
  creationTime: number
}

interface CommentThreadMock {
  threadIdentifier: string
  postId: string
  comments: CommentMock[]
}

let uuidCounter = 0
function newId(): string {
  // Deterministic ids keep tests readable; crypto.randomUUID would also work.
  uuidCounter += 1
  return `stub-${uuidCounter}`
}

/** Whole years from a YYYY-MM-DD date of birth to today, or null if malformed. */
function ageFromDateOfBirth(dateOfBirth: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateOfBirth)) {
    return null
  }
  const birth = new Date(dateOfBirth)
  const now = new Date()
  let age = now.getFullYear() - birth.getFullYear()
  const monthDelta = now.getMonth() - birth.getMonth()
  if (monthDelta < 0 || (monthDelta === 0 && now.getDate() < birth.getDate())) {
    age -= 1
  }
  return age
}

export class StatefulStubbedAPI implements PositiveOnlySocialAPI {
  private users: UserMock[] = []
  private sessions: SessionMock[] = []
  private loginCookies: LoginCookieMock[] = []
  private twoFactorChallenges: TwoFactorChallengeMock[] = []
  private posts: PostMock[] = []
  private commentThreads: CommentThreadMock[] = []
  private appeals: AppealMock[] = []

  // Mirrors the "Authorization: Bearer <token>" header.
  private token: string | null = null

  // ---------------------------------------------------------------------------
  // Token management
  // ---------------------------------------------------------------------------

  setToken(token: string | null): void {
    this.token = token
  }

  getToken(): string | null {
    return this.token
  }

  isAuthenticated(): boolean {
    return this.token !== null
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  private requireUser(): UserMock {
    if (!this.token) {
      throw new ApiError(401, 'Unauthorized')
    }
    const session = this.sessions.find((s) => s.managementToken === this.token)
    const user = session && this.users.find((u) => u.id === session.userId)
    if (!user) {
      throw new ApiError(401, 'Invalid session')
    }
    return user
  }

  private findUserByName(username: string): UserMock | undefined {
    return this.users.find((u) => u.username === username)
  }

  private findPost(postId: string): PostMock {
    const post = this.posts.find((p) => p.postIdentifier === postId)
    if (!post) {
      throw new ApiError(404, 'No post with that identifier')
    }
    return post
  }

  private findComment(postId: string, threadId: string, commentId: string): CommentMock {
    const thread = this.commentThreads.find(
      (t) => t.threadIdentifier === threadId && t.postId === postId,
    )
    const comment = thread?.comments.find((c) => c.commentIdentifier === commentId)
    if (!comment) {
      throw new ApiError(404, 'Comment not found')
    }
    return comment
  }

  private batch<T>(list: T[], batchIndex: number, batchSize: number): T[] {
    const start = batchIndex * batchSize
    if (start >= list.length) {
      return []
    }
    return list.slice(start, start + batchSize)
  }

  // ---------------------------------------------------------------------------
  // Authentication
  // ---------------------------------------------------------------------------

  async register(body: RegisterRequest): Promise<AuthResponse> {
    if (this.users.some((u) => u.username === body.username || u.email === body.email)) {
      throw new ApiError(400, 'User already exists')
    }

    // When a DOB is supplied, the backend marks the account identity-verified
    // and derives is_adult from the age (backend/user_system/views.py).
    const age = body.date_of_birth ? ageFromDateOfBirth(body.date_of_birth) : null
    const user: UserMock = {
      id: newId(),
      username: body.username,
      email: body.email,
      passwordHash: body.password,
      verificationToken: null,
      resetToken: null,
      // The real backend starts accounts unverified and gates everything on
      // the emailed link; the stub has no inbox, so accounts start verified to
      // keep offline/demo mode usable.
      emailVerified: true,
      emailVerificationToken: null,
      following: new Set(),
      followCategories: new Map(),
      followers: new Set(),
      isVerified: Boolean(body.date_of_birth),
      isAdult: age !== null && age >= 18,
      blocked: new Set(),
      blockedBy: new Set(),
      totpSecret: null,
      totpEnabled: false,
      recoveryCodes: new Set(),
      savedPostIds: [],
      profileImageUrl: null,
      pendingProfileImageUrl: null,
      profileImageStatus: 'none',
      profileImageReasonCode: null,
      // Next join number, one past the current highest (#198).
      membershipNumber: this.users.reduce((max, u) => Math.max(max, u.membershipNumber), 0) + 1,
      bio: '',
      interestCategories: new Set(),
      freeformInterests: [],
    }
    this.users.push(user)

    // Interests picked during sign-up ride along in the register payload
    // (issues #446/#35). Best-effort, exactly like the backend.
    if (body.interest_categories?.length || body.interest_freeform?.length) {
      this.applyInterests(user, body.interest_categories ?? [], body.interest_freeform ?? [])
    }

    const sessionToken = newId()
    this.sessions.push({ managementToken: sessionToken, userId: user.id })

    let seriesIdentifier: string | undefined
    let loginCookieToken: string | undefined
    if (body.remember_me) {
      seriesIdentifier = newId()
      loginCookieToken = newId()
      this.loginCookies.push({ seriesIdentifier, token: loginCookieToken, userId: user.id })
    }

    this.setToken(sessionToken)
    return {
      session_management_token: sessionToken,
      user_id: user.id,
      username: user.username,
      series_identifier: seriesIdentifier,
      login_cookie_token: loginCookieToken,
      membership_number: user.membershipNumber,
    }
  }

  async login(body: LoginRequest): Promise<LoginResponse> {
    const user = this.users.find(
      (u) => u.username === body.username_or_email || u.email === body.username_or_email,
    )
    if (!user || user.passwordHash !== body.password) {
      throw new ApiError(400, 'Invalid username or password')
    }

    // 2FA-enrolled accounts get a challenge instead of a session, mirroring
    // login_user in backend/user_system/views.py.
    if (user.totpEnabled) {
      // No session is issued until the second factor is verified; clear any
      // prior token so the stub doesn't look authenticated in the meantime.
      this.setToken(null)
      const challengeToken = newId()
      this.twoFactorChallenges.push({
        challengeToken,
        userId: user.id,
        rememberMe: Boolean(body.remember_me),
      })
      return { two_factor_required: true, challenge_token: challengeToken }
    }

    const sessionToken = newId()
    this.sessions.push({ managementToken: sessionToken, userId: user.id })

    let seriesIdentifier: string | undefined
    let loginCookieToken: string | undefined
    if (body.remember_me) {
      seriesIdentifier = newId()
      loginCookieToken = newId()
      this.loginCookies.push({ seriesIdentifier, token: loginCookieToken, userId: user.id })
    }

    this.setToken(sessionToken)
    return {
      session_management_token: sessionToken,
      user_id: user.id,
      username: user.username,
      series_identifier: seriesIdentifier,
      login_cookie_token: loginCookieToken,
      membership_number: user.membershipNumber,
    }
  }

  async loginWithRememberMe(
    body: LoginWithRememberMeRequest,
  ): Promise<LoginWithRememberMeResponse> {
    const cookie = this.loginCookies.find((c) => c.seriesIdentifier === body.series_identifier)
    if (!cookie) {
      throw new ApiError(400, 'Series identifier does not exist')
    }
    if (cookie.token !== body.login_cookie_token) {
      throw new ApiError(400, 'Login cookie token does not match')
    }

    // Rotate the cookie token.
    cookie.token = newId()

    const oldSession = this.sessions.find(
      (s) => s.managementToken === body.session_management_token,
    )
    const userId = oldSession ? oldSession.userId : cookie.userId
    const newSessionToken = newId()
    this.sessions.push({ managementToken: newSessionToken, userId })

    this.setToken(newSessionToken)
    return {
      login_cookie_token: cookie.token,
      session_management_token: newSessionToken,
    }
  }

  async loginWithTwoFactor(body: LoginTwoFactorRequest): Promise<AuthResponse> {
    const challenge = this.twoFactorChallenges.find(
      (c) => c.challengeToken === body.challenge_token,
    )
    if (!challenge) {
      throw new ApiError(400, INVALID_TWO_FACTOR_CHALLENGE)
    }
    const user = this.users.find((u) => u.id === challenge.userId)
    if (!user) {
      throw new ApiError(400, INVALID_TWO_FACTOR_CHALLENGE)
    }

    let codeOk = false
    if (body.totp_code && !body.recovery_code) {
      codeOk = body.totp_code === STUB_TOTP_CODE
    } else if (body.recovery_code && !body.totp_code) {
      // Recovery codes are single-use: consume on success.
      codeOk = user.recoveryCodes.delete(body.recovery_code)
    } else {
      throw new ApiError(400, "Invalid fields ['TOTP_CODE', 'RECOVERY_CODE']")
    }
    if (!codeOk) {
      throw new ApiError(400, 'Invalid two-factor code')
    }

    this.twoFactorChallenges = this.twoFactorChallenges.filter(
      (c) => c.challengeToken !== body.challenge_token,
    )

    const sessionToken = newId()
    this.sessions.push({ managementToken: sessionToken, userId: user.id })

    let seriesIdentifier: string | undefined
    let loginCookieToken: string | undefined
    if (challenge.rememberMe) {
      seriesIdentifier = newId()
      loginCookieToken = newId()
      this.loginCookies.push({ seriesIdentifier, token: loginCookieToken, userId: user.id })
    }

    this.setToken(sessionToken)
    return {
      session_management_token: sessionToken,
      user_id: user.id,
      username: user.username,
      series_identifier: seriesIdentifier,
      login_cookie_token: loginCookieToken,
      membership_number: user.membershipNumber,
    }
  }

  async setupTotp(): Promise<TwoFactorSetupResponse> {
    const user = this.requireUser()
    if (user.totpEnabled) {
      throw new ApiError(400, 'Two-factor authentication is already enabled')
    }
    user.totpSecret = stubTotpSecret()
    return {
      totp_secret: user.totpSecret,
      otpauth_uri: `otpauth://totp/Positive%20Only%20Social:${encodeURIComponent(user.email)}?secret=${user.totpSecret}&issuer=Positive%20Only%20Social`,
    }
  }

  async confirmTotp(body: ConfirmTotpRequest): Promise<ConfirmTotpResponse> {
    const user = this.requireUser()
    if (user.totpEnabled) {
      throw new ApiError(400, 'Two-factor authentication is already enabled')
    }
    if (!user.totpSecret) {
      throw new ApiError(400, 'Two-factor setup has not been started')
    }
    if (user.passwordHash !== body.password) {
      throw new ApiError(400, 'Invalid password')
    }
    if (body.totp_code !== STUB_TOTP_CODE) {
      throw new ApiError(400, 'Invalid two-factor code')
    }
    user.totpEnabled = true
    user.recoveryCodes = new Set(
      Array.from({ length: STUB_RECOVERY_CODE_COUNT }, stubRecoveryCode),
    )
    return { totp_enabled: true, recovery_codes: [...user.recoveryCodes] }
  }

  async disableTotp(body: DisableTotpRequest): Promise<DisableTotpResponse> {
    const user = this.requireUser()
    if (!user.totpEnabled) {
      throw new ApiError(400, 'Two-factor authentication is not enabled')
    }
    if (user.passwordHash !== body.password) {
      throw new ApiError(400, 'Invalid password')
    }
    // Exactly one of totp_code / recovery_code must be supplied, matching the
    // backend's field validation (both-or-neither is a bad request, not a
    // wrong code).
    if (Boolean(body.totp_code) === Boolean(body.recovery_code)) {
      throw new ApiError(400, "Invalid fields ['TOTP_CODE', 'RECOVERY_CODE']")
    }
    const codeOk = body.totp_code
      ? body.totp_code === STUB_TOTP_CODE
      : user.recoveryCodes.delete(body.recovery_code as string)
    if (!codeOk) {
      throw new ApiError(400, 'Invalid two-factor code')
    }
    user.totpSecret = null
    user.totpEnabled = false
    user.recoveryCodes = new Set()
    this.twoFactorChallenges = this.twoFactorChallenges.filter((c) => c.userId !== user.id)
    return { totp_enabled: false }
  }

  async logout(): Promise<MessageResponse> {
    this.requireUser()
    this.sessions = this.sessions.filter((s) => s.managementToken !== this.token)
    this.setToken(null)
    return { message: 'Logout successful' }
  }

  async verifyIdentity(dateOfBirth: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const age = ageFromDateOfBirth(dateOfBirth)
    if (age === null) {
      throw new ApiError(400, 'Invalid date format, expected YYYY-MM-DD')
    }
    user.isVerified = true
    user.isAdult = age >= 18
    return { message: 'Identity verified' }
  }

  async deleteAccount(): Promise<MessageResponse> {
    const user = this.requireUser()
    this.posts = this.posts.filter((p) => p.authorId !== user.id)
    this.sessions = this.sessions.filter((s) => s.userId !== user.id)
    this.loginCookies = this.loginCookies.filter((c) => c.userId !== user.id)
    this.users = this.users.filter((u) => u.id !== user.id)
    this.setToken(null)
    return { message: 'User deleted successfully' }
  }

  async getCurrentUser(): Promise<CurrentUser> {
    const user = this.requireUser()
    return { username: user.username, email: user.email }
  }

  // ---------------------------------------------------------------------------
  // Password reset
  // ---------------------------------------------------------------------------

  async verifyEmail(body: VerifyEmailRequest): Promise<MessageResponse> {
    const user = this.users.find(
      (u) => u.emailVerificationToken !== null && u.emailVerificationToken === body.verification_token,
    )
    if (!user) {
      throw new ApiError(400, 'Invalid or expired verification token')
    }
    user.emailVerified = true
    user.emailVerificationToken = null
    return { message: 'Email verified' }
  }

  async resendVerificationEmail(body: ResendVerificationEmailRequest): Promise<MessageResponse> {
    const user = this.users.find(
      (u) => u.username === body.username_or_email || u.email === body.username_or_email,
    )
    if (!user) {
      throw new ApiError(400, 'No user with that username or email')
    }
    if (user.emailVerified) {
      throw new ApiError(400, 'Email already verified')
    }
    user.emailVerificationToken = `stub_email_verification_token_${user.username}`
    return { message: 'Verification email sent' }
  }

  async requestReset(body: RequestResetRequest): Promise<MessageResponse> {
    const user = this.users.find(
      (u) => u.email === body.username_or_email || u.username === body.username_or_email,
    )
    if (!user) {
      throw new ApiError(400, 'No user with that username or email')
    }
    user.verificationToken = `stub_verification_token_${user.username}`
    return { message: 'Reset email sent' }
  }

  async verifyReset(body: VerifyResetRequest): Promise<VerifyResetResponse> {
    const user = this.users.find(
      (u) => u.username === body.username_or_email || u.email === body.username_or_email,
    )
    if (user && user.verificationToken && user.verificationToken === body.verification_token) {
      const resetToken = `stub_reset_token_${user.username}`
      user.verificationToken = null
      user.resetToken = resetToken
      return { message: 'Verification successful', reset_token: resetToken }
    }
    throw new ApiError(400, 'Invalid or expired verification token')
  }

  async resetPassword(body: ResetPasswordRequest): Promise<MessageResponse> {
    const user = this.users.find(
      (u) => u.username === body.username && u.email === body.email,
    )
    if (user && user.resetToken && user.resetToken === body.reset_token) {
      user.passwordHash = body.password
      user.resetToken = null
      this.sessions = this.sessions.filter((s) => s.userId !== user.id)
      this.loginCookies = this.loginCookies.filter((c) => c.userId !== user.id)
      return { message: 'Password reset successfully' }
    }
    throw new ApiError(400, 'Invalid reset token')
  }

  async changePassword(body: ChangePasswordRequest): Promise<MessageResponse> {
    const user = this.requireUser()
    // Field validation first, mirroring the backend: the new password must meet
    // the registration strength policy before the current password is checked.
    if (!STRONG_PASSWORD.test(body.new_password)) {
      throw new ApiError(400, "Invalid fields ['NEW_PASSWORD']")
    }
    if (user.passwordHash !== body.password) {
      throw new ApiError(400, 'Invalid password')
    }
    if (user.passwordHash === body.new_password) {
      throw new ApiError(400, 'New password must be different from the current password')
    }
    user.passwordHash = body.new_password
    // Evict other devices but keep the current session (mirrors the backend).
    this.sessions = this.sessions.filter(
      (s) => s.userId !== user.id || s.managementToken === this.token,
    )
    this.loginCookies = this.loginCookies.filter((c) => c.userId !== user.id)
    return { message: 'Password changed successfully' }
  }

  // ---------------------------------------------------------------------------
  // Posts
  // ---------------------------------------------------------------------------

  async createUploadUrl(): Promise<CreateUploadUrlResponse> {
    const user = this.requireUser()
    // Mirror the backend: a fresh key under the user's prefix, returned as
    // both a "presigned" upload URL and the canonical image URL.
    const imageUrl = `https://stub-bucket.s3.us-east-2.amazonaws.com/${user.id}/stub-${newId()}.jpeg`
    return { upload_url: `${imageUrl}?X-Amz-Signature=stub`, image_url: imageUrl }
  }

  async createPost(body: CreatePostRequest): Promise<CreatePostResponse> {
    const user = this.requireUser()
    // Stub pre-filter, mirroring the backend's cheap inline check (#282): a
    // blatant hit is rejected immediately and the post is never created.
    if (body.caption.includes('negative')) {
      throw new ApiError(400, 'Text is not positive because your caption did not meet our positivity guidelines. This decision is final and cannot be appealed.')
    }
    const post: PostMock = {
      postIdentifier: newId(),
      authorId: user.id,
      imageUrl: body.image_url ?? null,
      caption: body.caption,
      tags: extractTags(body.caption).sort(),
      captionFont: body.caption_font ?? 'default',
      backgroundColor: body.background_color ?? 'default',
      creationTime: Date.now(),
      hidden: true,
      hiddenReason: 'pending_classification',
      audience: body.audience ?? 'public',
      reasonCode: null,
      likes: new Set(),
      reports: new Map(),
    }
    this.posts.push(post)
    // The real backend classifies asynchronously in a worker; the stub
    // resolves instantly (like the backend's eager dev mode) but still
    // returns the pending response, so clients exercise the reconcile path.
    this.classifyPost(post)
    return {
      post_identifier: post.postIdentifier,
      status: 'pending',
      hidden: true,
      hidden_reason: 'pending_classification',
      appealable: false,
      message: 'Your post is being reviewed and will be visible to others once it is approved.',
    }
  }

  /** Stubbed async classifier (#282): a caption containing 'borderline'
   * becomes an appealable rejection; everything else is approved.
   *
   * A caption containing 'moderated' stands in for content a human moderator
   * hid after reviewing user reports (issue #467). Since report counts hide
   * nothing, that decision — which no client-side action can reproduce — is the
   * only way content reaches hidden_reason 'reports', so the stub needs a seam
   * for it. */
  private classifyPost(post: PostMock): void {
    if (post.caption.includes('moderated')) {
      post.hidden = true
      post.hiddenReason = 'reports'
    } else if (post.caption.includes('borderline')) {
      post.hidden = true
      post.hiddenReason = 'classifier'
      post.reasonCode = 'guidelines'
    } else {
      post.hidden = false
      post.hiddenReason = ''
    }
  }

  /** The report-triggered re-review (issue #467), stubbed.
   *
   * A report is not a vote: it re-examines the CONTENT, and only a rejection
   * hides anything — the number of reports never enters into it. The stub's
   * seam for content the creation-time classifier let through but a re-review
   * rejects is the word 'reviewable'; anything else stays visible however many
   * people report it. */
  private reviewReportedContent(
    content: { hidden: boolean; hiddenReason: string },
    text: string,
  ): void {
    if (content.hidden || !text.includes('reviewable')) return
    content.hidden = true
    content.hiddenReason = 'classifier'
  }

  /** Author-facing classification status, mirroring Post.classification_status. */
  private classificationStatus(post: PostMock): 'pending' | 'approved' | 'rejected' | 'rejected_final' {
    if (post.hiddenReason === 'pending_classification') return 'pending'
    if (post.hiddenReason === 'classifier') return 'rejected'
    if (post.hiddenReason === 'classifier_final') return 'rejected_final'
    return 'approved'
  }

  private isAppealable(post: PostMock): boolean {
    return (
      post.hidden &&
      post.hiddenReason !== 'pending_classification' &&
      post.hiddenReason !== 'classifier_final'
    )
  }

  /** An author's approved profile photo, merged next to author_username in
   * every list/detail payload (issue #7). Mirrors the backend: only the
   * approved photo is exposed, compressed variant plus original fallback (the
   * stub has no separate compressed bucket, so both are the same URL). */
  private authorAvatarFields(authorId: string): AuthorAvatarFields {
    const author = this.users.find((u) => u.id === authorId)
    const url = author ? author.profileImageUrl : null
    return {
      author_profile_image_url: url,
      author_profile_image_original_url: url,
    }
  }

  /** The author-only classification fields merged into post payloads. */
  private authorStatusFields(post: PostMock, viewerId: string): Partial<FeedPost> {
    if (post.authorId !== viewerId) return {}
    return {
      status: this.classificationStatus(post),
      hidden: post.hidden,
      hidden_reason: post.hiddenReason,
      reason_code: post.reasonCode,
      appealable: this.isAppealable(post),
    }
  }

  async deletePost(postIdentifier: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    if (post.authorId !== user.id) {
      throw new ApiError(400, 'No post with that identifier by that user')
    }
    this.posts = this.posts.filter((p) => p.postIdentifier !== postIdentifier)
    return { message: 'Post deleted' }
  }

  async reportPost(postIdentifier: string, reason: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    if (post.authorId === user.id) {
      throw new ApiError(400, 'Cannot report own post')
    }
    if (post.reports.has(user.id)) {
      throw new ApiError(400, 'Cannot report post twice')
    }
    post.reports.set(user.id, reason)
    this.reviewReportedContent(post, post.caption)
    return { message: 'Post reported' }
  }

  async retractReportPost(postIdentifier: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    if (!post.reports.has(user.id)) {
      throw new ApiError(400, 'Post not reported yet')
    }
    // Retracting never un-hides either: hiding is a moderation decision, not a
    // reversible group vote (issue #467).
    post.reports.delete(user.id)
    return { message: 'Post report retracted' }
  }

  async likePost(postIdentifier: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    if (post.authorId === user.id) {
      throw new ApiError(400, 'Cannot like own post')
    }
    if (post.likes.has(user.id)) {
      throw new ApiError(400, 'Already liked post')
    }
    post.likes.add(user.id)
    return { message: 'Post liked' }
  }

  async unlikePost(postIdentifier: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    if (!post.likes.has(user.id)) {
      throw new ApiError(400, 'Post not liked yet')
    }
    post.likes.delete(user.id)
    return { message: 'Post unliked' }
  }

  async savePost(postIdentifier: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    // Only posts the user can see are worth saving, mirroring the backend.
    if (!this.canViewPost(post, user)) {
      throw new ApiError(400, 'No post with that identifier')
    }
    if (user.savedPostIds.includes(postIdentifier)) {
      throw new ApiError(400, 'Already saved post')
    }
    user.savedPostIds.push(postIdentifier)
    return { message: 'Post saved' }
  }

  async unsavePost(postIdentifier: string): Promise<MessageResponse> {
    const user = this.requireUser()
    this.findPost(postIdentifier)
    if (!user.savedPostIds.includes(postIdentifier)) {
      throw new ApiError(400, 'Post not saved yet')
    }
    user.savedPostIds = user.savedPostIds.filter((id) => id !== postIdentifier)
    return { message: 'Post unsaved' }
  }

  // ---------------------------------------------------------------------------
  // Feeds & retrieval
  // ---------------------------------------------------------------------------

  private toFeedPost(post: PostMock, viewer: UserMock): FeedPost {
    const author = this.users.find((u) => u.id === post.authorId)
    return {
      post_identifier: post.postIdentifier,
      image_url: post.imageUrl,
      // Mirrors the backend: the full-resolution original, used as a client-side
      // fallback when the compressed image isn't available yet (issues #252/#254).
      original_image_url: post.imageUrl,
      author_username: author ? author.username : '',
      caption: post.caption,
      audience: post.audience,
      tags: post.tags,
      is_saved: viewer.savedPostIds.includes(post.postIdentifier),
      ...this.authorAvatarFields(post.authorId),
      caption_font: post.captionFont,
      background_color: post.backgroundColor,
      ...this.authorStatusFields(post, viewer.id),
    }
  }

  /**
   * Mirrors visibility._audience_allows (issue #392/#445): whether a post's or
   * comment's audience admits `viewerId`. Public admits everyone and the author
   * always sees their own content; otherwise the author must have labeled the
   * viewer with a category close enough for the audience's nested tier — a
   * "friends" tier reaches friends and family, "family" only family.
   */
  private audienceAdmits(
    content: { audience: PostAudience; authorId: string },
    viewerId: string,
  ): boolean {
    if (content.audience === 'public' || content.authorId === viewerId) {
      return true
    }
    const author = this.users.find((u) => u.id === content.authorId)
    const category = author?.followCategories.get(viewerId)
    if (!category) {
      return false
    }
    const rank: Record<FollowCategory, number> = { following: 1, friend: 2, family: 3 }
    const required: Record<Exclude<PostAudience, 'public'>, number> = {
      following: 1,
      friends: 2,
      family: 3,
    }
    return rank[category] >= required[content.audience]
  }

  /** The followed-feed toggle applied to a comment author (issue #445): whether
   * the viewer follows `authorId` and labeled them with exactly `category`. A
   * plain follow counts as 'following'. Mirrors visibility._labeled_author_ids. */
  private labeledAs(viewer: UserMock, authorId: string, category: FollowCategory): boolean {
    if (!viewer.following.has(authorId)) {
      return false
    }
    return (viewer.followCategories.get(authorId) ?? 'following') === category
  }

  /** Whether a post is visible to a viewer, mirroring backend can_view_post:
   * the author always sees their own posts; everyone else only sees live ones.
   * Final-rejection tombstones are visible to nobody (#282). */
  private canViewPost(post: PostMock, viewer: UserMock): boolean {
    if (post.hiddenReason === 'classifier_final') return false
    if (post.authorId === viewer.id) return true
    if (post.hidden) return false
    return !viewer.blocked.has(post.authorId) && !viewer.blockedBy.has(post.authorId)
  }

  async getFeed(batch: number): Promise<FeedPost[]> {
    const user = this.requireUser()
    const visible = this.posts
      .filter(
        (p) =>
          !p.hidden &&
          !user.blocked.has(p.authorId) &&
          !user.blockedBy.has(p.authorId) &&
          this.audienceAdmits(p, user.id),
      )
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p, user))
  }

  async getFollowedFeed(batch: number, category?: FollowCategory): Promise<FeedPost[]> {
    const user = this.requireUser()
    const visible = this.posts
      .filter(
        (p) =>
          !p.hidden &&
          user.following.has(p.authorId) &&
          !user.blocked.has(p.authorId) &&
          !user.blockedBy.has(p.authorId) &&
          this.audienceAdmits(p, user.id) &&
          // Exact-category feed filter (issue #392): no argument returns the
          // whole following feed, as before.
          (!category || (user.followCategories.get(p.authorId) ?? 'following') === category),
      )
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p, user))
  }

  async getPostsForUser(username: string, batch: number): Promise<FeedPost[]> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User not found')
    }
    if (user.blocked.has(target.id) || target.blocked.has(user.id)) {
      return []
    }
    // Mirrors visible_posts: authors see their own hidden posts (pending,
    // appealable, report-hidden) in their grid; everyone else only sees live
    // ones. Final-rejection tombstones are visible to nobody (#282).
    const visible = this.posts
      .filter((p) => p.authorId === target.id)
      .filter((p) => p.hiddenReason !== 'classifier_final')
      .filter((p) => (user.id === target.id ? true : !p.hidden))
      .filter((p) => this.audienceAdmits(p, user.id))
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p, user))
  }

  async getSavedPosts(batch: number): Promise<FeedPost[]> {
    const user = this.requireUser()
    // Newest save first (savedPostIds is oldest-first), and only posts that are
    // still visible — a since-hidden post silently drops off (issue #193).
    const saved = [...user.savedPostIds]
      .reverse()
      .map((id) => this.posts.find((p) => p.postIdentifier === id))
      .filter((p): p is PostMock => p !== undefined && this.canViewPost(p, user))
    return this.batch(saved, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p, user))
  }

  async getPostsByTag(tag: string, batch: number): Promise<FeedPost[]> {
    const user = this.requireUser()
    const normalized = tag.toLowerCase()
    // Same visibility + block rules as the other feeds: not hidden (unless the
    // viewer is the author), author not blocked either way, carrying the tag.
    const visible = this.posts
      .filter((p) => p.tags.includes(normalized))
      .filter((p) => p.hiddenReason !== 'classifier_final')
      .filter((p) => (p.authorId === user.id ? true : !p.hidden))
      .filter((p) => !user.blocked.has(p.authorId) && !user.blockedBy.has(p.authorId))
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p, user))
  }

  async getPostDetails(postIdentifier: string): Promise<PostDetails> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    // Mirror can_view_post: a restricted post the viewer isn't in the audience
    // for reads exactly like a missing one (issue #392).
    if (post.authorId !== user.id && !this.audienceAdmits(post, user.id)) {
      throw new ApiError(400, 'No post with that identifier')
    }
    const author = this.users.find((u) => u.id === post.authorId)
    return {
      post_identifier: post.postIdentifier,
      image_url: post.imageUrl,
      original_image_url: post.imageUrl,
      caption: post.caption,
      caption_font: post.captionFont,
      background_color: post.backgroundColor,
      creation_time: new Date(post.creationTime).toISOString(),
      post_likes: post.likes.size,
      is_liked: post.likes.has(user.id),
      is_saved: user.savedPostIds.includes(post.postIdentifier),
      is_reported: post.reports.has(user.id),
      report_reason: post.reports.get(user.id) ?? null,
      author_username: author ? author.username : '',
      audience: post.audience,
      tags: post.tags,
      ...this.authorAvatarFields(post.authorId),
      ...this.authorStatusFields(post, user.id),
    }
  }

  async getPostStatus(postIdentifier: string): Promise<PostStatusResponse> {
    const user = this.requireUser()
    const post = this.posts.find(
      (p) => p.postIdentifier === postIdentifier && p.authorId === user.id,
    )
    if (!post) {
      throw new ApiError(400, 'No post with that identifier by that user')
    }
    const status = this.classificationStatus(post)
    const response: PostStatusResponse = {
      post_identifier: post.postIdentifier,
      status,
      reason_code: post.reasonCode,
      appealable: this.isAppealable(post),
      hidden: post.hidden,
      hidden_reason: post.hiddenReason,
    }
    if (status === 'pending') {
      response.message = 'Your post is being reviewed and will be visible to others once it is approved.'
    } else if (status === 'rejected') {
      response.message =
        'Your post did not pass automated review. It is hidden for now but you can appeal the decision.'
    } else if (status === 'rejected_final') {
      response.message =
        'Your post did not pass automated review. This decision is final and cannot be appealed.'
    }
    return response
  }

  // ---------------------------------------------------------------------------
  // Comments
  // ---------------------------------------------------------------------------

  async commentOnPost(
    postIdentifier: string,
    commentText: string,
    formatting?: CommentFormatSpan[],
    audience?: PostAudience,
  ): Promise<CommentOnPostResponse> {
    const user = this.requireUser()
    this.findPost(postIdentifier)
    const thread: CommentThreadMock = {
      threadIdentifier: newId(),
      postId: postIdentifier,
      comments: [],
    }
    this.commentThreads.push(thread)
    const comment: CommentMock = {
      commentIdentifier: newId(),
      authorId: user.id,
      body: commentText,
      bodyFormatting: formatting && formatting.length > 0 ? formatting : null,
      audience: audience ?? 'public',
      creationTime: Date.now(),
      hidden: false,
      hiddenReason: '',
      likes: new Set(),
      reports: new Map(),
    }
    thread.comments.push(comment)
    return {
      comment_thread_identifier: thread.threadIdentifier,
      comment_identifier: comment.commentIdentifier,
    }
  }

  async replyToCommentThread(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentText: string,
    formatting?: CommentFormatSpan[],
    audience?: PostAudience,
  ): Promise<ReplyResponse> {
    const user = this.requireUser()
    const thread = this.commentThreads.find(
      (t) => t.threadIdentifier === commentThreadIdentifier && t.postId === postIdentifier,
    )
    if (!thread) {
      throw new ApiError(400, 'Comment thread not found for the given post')
    }
    const comment: CommentMock = {
      commentIdentifier: newId(),
      authorId: user.id,
      body: commentText,
      bodyFormatting: formatting && formatting.length > 0 ? formatting : null,
      audience: audience ?? 'public',
      creationTime: Date.now(),
      hidden: false,
      hiddenReason: '',
      likes: new Set(),
      reports: new Map(),
    }
    thread.comments.push(comment)
    return { comment_identifier: comment.commentIdentifier }
  }

  /** Comments in a thread the viewer may see: not hidden (unless their own),
   * audience-admitted, and — when a `category` filter is on — by an author the
   * viewer labeled with exactly that category (issue #445). */
  private visibleComments(
    thread: CommentThreadMock,
    viewer: UserMock,
    category?: FollowCategory,
  ): CommentMock[] {
    return thread.comments.filter((c) => {
      if (c.authorId === viewer.id) {
        // The exact-category toggle drops your own comments, since you do not
        // follow yourself — matching the followed-feed filter.
        return category ? false : true
      }
      if (c.hidden) return false
      if (!this.audienceAdmits(c, viewer.id)) return false
      return !category || this.labeledAs(viewer, c.authorId, category)
    })
  }

  async getCommentsForPost(
    postIdentifier: string,
    batch: number,
    category?: FollowCategory,
  ): Promise<CommentThreadRef[]> {
    const user = this.requireUser()
    const threads = this.commentThreads
      .filter((t) => t.postId === postIdentifier)
      .filter((t) => this.visibleComments(t, user, category).length > 0)
    return this.batch(threads, batch, COMMENT_BATCH_SIZE).map((t) => ({
      comment_thread_identifier: t.threadIdentifier,
    }))
  }

  async getCommentsForThread(
    commentThreadIdentifier: string,
    batch: number,
    category?: FollowCategory,
  ): Promise<Comment[]> {
    const user = this.requireUser()
    const thread = this.commentThreads.find(
      (t) => t.threadIdentifier === commentThreadIdentifier,
    )
    if (!thread) {
      throw new ApiError(400, 'No comment thread with that identifier')
    }
    const visible = this.visibleComments(thread, user, category).sort(
      (a, b) => a.creationTime - b.creationTime,
    )
    return this.batch(visible, batch, COMMENT_BATCH_SIZE).map((c) => {
      const author = this.users.find((u) => u.id === c.authorId)
      const time = new Date(c.creationTime).toISOString()
      return {
        comment_identifier: c.commentIdentifier,
        body: c.body,
        body_formatting: c.bodyFormatting,
        audience: c.audience,
        author_username: author ? author.username : '',
        ...this.authorAvatarFields(c.authorId),
        creation_time: time,
        updated_time: time,
        comment_likes: c.likes.size,
        is_liked: c.likes.has(user.id),
        is_reported: c.reports.has(user.id),
        report_reason: c.reports.get(user.id) ?? null,
      }
    })
  }

  async likeComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    const user = this.requireUser()
    const comment = this.findComment(postIdentifier, commentThreadIdentifier, commentIdentifier)
    if (comment.authorId === user.id) {
      throw new ApiError(400, 'Cannot like own comment')
    }
    if (comment.likes.has(user.id)) {
      throw new ApiError(400, 'Already liked comment')
    }
    comment.likes.add(user.id)
    return { message: 'Comment liked' }
  }

  async unlikeComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    const user = this.requireUser()
    const comment = this.findComment(postIdentifier, commentThreadIdentifier, commentIdentifier)
    if (!comment.likes.has(user.id)) {
      throw new ApiError(400, 'Comment not liked yet')
    }
    comment.likes.delete(user.id)
    return { message: 'Comment unliked' }
  }

  async deleteComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    const user = this.requireUser()
    const thread = this.commentThreads.find(
      (t) => t.threadIdentifier === commentThreadIdentifier && t.postId === postIdentifier,
    )
    const comment = thread?.comments.find((c) => c.commentIdentifier === commentIdentifier)
    if (!thread || !comment) {
      throw new ApiError(400, 'Comment not found')
    }
    if (comment.authorId !== user.id) {
      throw new ApiError(400, 'Not authorized to delete comment')
    }
    thread.comments = thread.comments.filter((c) => c.commentIdentifier !== commentIdentifier)
    return { message: 'Comment deleted' }
  }

  async reportComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
    reason: string,
  ): Promise<MessageResponse> {
    const user = this.requireUser()
    const comment = this.findComment(postIdentifier, commentThreadIdentifier, commentIdentifier)
    if (comment.authorId === user.id) {
      throw new ApiError(400, 'Cannot report own comment')
    }
    if (comment.reports.has(user.id)) {
      throw new ApiError(400, 'Cannot report comment twice')
    }
    comment.reports.set(user.id, reason)
    this.reviewReportedContent(comment, comment.body)
    return { message: 'Comment reported' }
  }

  async retractReportComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    const user = this.requireUser()
    const comment = this.findComment(postIdentifier, commentThreadIdentifier, commentIdentifier)
    if (!comment.reports.has(user.id)) {
      throw new ApiError(400, 'Comment not reported yet')
    }
    comment.reports.delete(user.id)
    return { message: 'Comment report retracted' }
  }

  // ---------------------------------------------------------------------------
  // Users & profiles
  // ---------------------------------------------------------------------------

  async searchUsers(usernameFragment: string): Promise<UserSearchResult[]> {
    const current = this.requireUser()
    return this.users
      .filter(
        (u) =>
          u.username.toLowerCase().includes(usernameFragment.toLowerCase()) &&
          u.id !== current.id &&
          !current.blockedBy.has(u.id),
      )
      .slice(0, 10)
      .map((u) => ({
        username: u.username,
        identity_is_verified: u.isVerified,
        ...this.authorAvatarFields(u.id),
      }))
  }

  async followUser(username: string, category?: FollowCategory): Promise<MessageResponse> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User does not exist')
    }
    if (user.id === target.id) {
      throw new ApiError(400, 'Cannot follow self')
    }
    if (user.following.has(target.id)) {
      throw new ApiError(400, 'Already following user')
    }
    const followCategory = category ?? 'following'
    user.following.add(target.id)
    user.followCategories.set(target.id, followCategory)
    target.followers.add(user.id)
    return { message: 'User followed', follow_category: followCategory }
  }

  async unfollowUser(username: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User does not exist')
    }
    if (!user.following.has(target.id)) {
      throw new ApiError(400, 'Not following user')
    }
    user.following.delete(target.id)
    user.followCategories.delete(target.id)
    target.followers.delete(user.id)
    return { message: 'User unfollowed' }
  }

  async setFollowCategory(username: string, category: FollowCategory): Promise<MessageResponse> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User does not exist')
    }
    if (user.id === target.id) {
      throw new ApiError(400, 'Cannot categorize self')
    }
    if (!user.following.has(target.id)) {
      throw new ApiError(400, 'Not following user')
    }
    user.followCategories.set(target.id, category)
    return { message: 'Category updated', follow_category: category }
  }

  async toggleBlock(username: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User does not exist')
    }
    if (user.id === target.id) {
      throw new ApiError(400, 'Cannot block self')
    }
    if (user.blocked.has(target.id)) {
      user.blocked.delete(target.id)
      target.blockedBy.delete(user.id)
      return { message: 'User unblocked' }
    }
    user.blocked.add(target.id)
    target.blockedBy.add(user.id)
    // Blocking severs follow relationships in both directions.
    user.following.delete(target.id)
    user.followCategories.delete(target.id)
    target.followers.delete(user.id)
    target.following.delete(user.id)
    target.followCategories.delete(user.id)
    user.followers.delete(target.id)
    return { message: 'User blocked' }
  }

  async getBlockedUsers(): Promise<UserSearchResult[]> {
    const user = this.requireUser()
    return this.users
      .filter((u) => user.blocked.has(u.id))
      .sort((a, b) => a.username.localeCompare(b.username))
      .map((u) => ({
        username: u.username,
        identity_is_verified: u.isVerified,
        ...this.authorAvatarFields(u.id),
      }))
  }

  async getFollowers(): Promise<UserSearchResult[]> {
    const user = this.requireUser()
    return this.users
      .filter((u) => user.followers.has(u.id))
      .sort((a, b) => a.username.localeCompare(b.username))
      .map((u) => ({
        username: u.username,
        identity_is_verified: u.isVerified,
        ...this.authorAvatarFields(u.id),
      }))
  }

  async getFollowing(): Promise<UserSearchResult[]> {
    const user = this.requireUser()
    return this.users
      .filter((u) => user.following.has(u.id))
      .sort((a, b) => a.username.localeCompare(b.username))
      .map((u) => ({
        username: u.username,
        identity_is_verified: u.isVerified,
        ...this.authorAvatarFields(u.id),
      }))
  }

  async getProfile(username: string): Promise<ProfileDetails> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User not found')
    }
    const isBlockedBy = user.blockedBy.has(target.id)
    const postCount = isBlockedBy ? 0 : this.posts.filter((p) => p.authorId === target.id).length
    const isFollowing = isBlockedBy ? false : user.following.has(target.id)
    const liveAvatar = isBlockedBy ? null : target.profileImageUrl
    const details: ProfileDetails = {
      username: target.username,
      post_count: postCount,
      follower_count: isBlockedBy ? 0 : target.followers.size,
      following_count: isBlockedBy ? 0 : target.following.size,
      is_following: isFollowing,
      follow_category: isFollowing ? (user.followCategories.get(target.id) ?? 'following') : null,
      is_blocked: user.blocked.has(target.id),
      identity_is_verified: target.isVerified,
      is_adult: target.isAdult,
      profile_image_url: liveAvatar,
      profile_image_original_url: liveAvatar,
      membership_number: target.membershipNumber,
      // Redacted for a blocked requester, like the stats/avatar above.
      bio: isBlockedBy ? '' : target.bio,
    }
    // Owner-only moderation state, mirroring the backend.
    if (target.id === user.id) {
      details.profile_image_status = target.profileImageStatus
      details.profile_image_reason_code = target.profileImageReasonCode
      details.pending_profile_image_url = target.pendingProfileImageUrl
    }
    return details
  }

  async setProfilePhoto(body: SetProfilePhotoRequest): Promise<SetProfilePhotoResponse> {
    const user = this.requireUser()
    // The real backend stores the photo pending and classifies it off the
    // request path; the stub has no classifier, so — like the backend's eager
    // (no-Redis) mode — it approves immediately, while the response still
    // reports the initial 'pending' state.
    user.profileImageUrl = body.image_url
    user.pendingProfileImageUrl = null
    user.profileImageStatus = 'approved'
    user.profileImageReasonCode = null
    return {
      profile_image_status: 'pending',
      message: 'Your photo is being reviewed and will be shown once it is approved.',
    }
  }

  async removeProfilePhoto(): Promise<RemoveProfilePhotoResponse> {
    const user = this.requireUser()
    user.profileImageUrl = null
    user.pendingProfileImageUrl = null
    user.profileImageStatus = 'none'
    user.profileImageReasonCode = null
    return { profile_image_status: 'none', message: 'Your profile photo has been removed.' }
  }

  async setBio(body: SetBioRequest): Promise<SetBioResponse> {
    const user = this.requireUser()
    // A blank bio just clears it — nothing to moderate.
    if (!body.bio.trim()) {
      user.bio = ''
      return { bio: '', message: 'Your bio has been cleared.' }
    }
    if (characterCount(body.bio) > MAX_BIO_LENGTH) {
      throw new ApiError(400, `Bio exceeds maximum length of ${MAX_BIO_LENGTH} characters`)
    }
    // The backend disallows the semicolon in user text; mirror that here.
    if (body.bio.includes(';')) {
      throw new ApiError(400, 'Your bio cannot contain a semicolon (;).')
    }
    // The stub has no classifier; like the backend's TESTING text classifier it
    // rejects anything containing "negative" and accepts the rest, so tests can
    // drive the reject path. A rejected bio is never stored.
    if (body.bio.toLowerCase().includes('negative')) {
      throw new ApiError(400, 'Text is not positive because your bio did not meet our positivity guidelines.')
    }
    user.bio = body.bio
    return { bio: user.bio, message: 'Your bio has been updated.' }
  }

  // ===========================================================================
  // POSITIVE INTEREST TAGS (issues #446/#35)
  // ===========================================================================

  /** Mirrors the backend apply_user_interests: full-replace of a user's
   * interest state. Preset slugs are kept if known; each freeform term is
   * positivity-checked (reject anything containing "negative", like the backend
   * TESTING classifier) and mapped to buckets; the weighting set is the union
   * of picks and mapped buckets. */
  private applyInterests(
    user: UserMock,
    categories: string[],
    freeform: string[],
  ): SetInterestsResponse {
    // Normalize before matching, mirroring the backend's strip().lower() — a
    // slug arriving as " Nature" must resolve the same way here as in production.
    const picked = Array.isArray(categories)
      ? [
          ...new Set(
            categories
              .filter((s) => typeof s === 'string')
              .map((s) => s.trim().toLowerCase())
              .filter((s) => INTEREST_SLUGS.has(s)),
          ),
        ]
      : []

    const accepted: string[] = []
    const rejected: SetInterestsResponse['freeform']['rejected'] = []
    const union = new Set<string>(picked)
    const seen = new Set<string>()

    if (Array.isArray(freeform)) {
      for (const raw of freeform) {
        if (typeof raw !== 'string') continue
        const term = raw.trim()
        if (!term) continue
        // Dedupe before deciding the term's fate and bound the rejected list,
        // mirroring the backend's _normalize_freeform_terms: deduping only the
        // accepted terms let a repeated bad term be reported once per
        // occurrence, and an unbounded list diverges from what the real API
        // returns (duplicate React keys, inflated responses).
        const key = term.toLowerCase()
        if (seen.has(key)) continue
        seen.add(key)
        if (characterCount(term) > MAX_FREEFORM_INTEREST_LENGTH) {
          if (rejected.length < MAX_FREEFORM_INTERESTS) {
            // Echo bounded the same way the backend bounds it, so a huge term
            // doesn't produce a huge response. Still well over the limit, so an
            // elided term reads as too long.
            const echo =
              characterCount(term) > REJECTED_TEXT_ECHO_LIMIT
                ? [...term].slice(0, REJECTED_TEXT_ECHO_LIMIT).join('') + '…'
                : term
            rejected.push({
              text: echo,
              reason_code: 'too_long',
              reason: `is longer than ${MAX_FREEFORM_INTEREST_LENGTH} characters`,
            })
          }
          continue
        }
        if (key.includes('negative')) {
          if (rejected.length < MAX_FREEFORM_INTERESTS) {
            rejected.push({
              text: key,
              reason_code: 'guidelines',
              reason: 'did not meet our positivity guidelines',
            })
          }
          continue
        }
        accepted.push(key)
        for (const slug of matchInterestSlugs(key)) union.add(slug)
        if (accepted.length >= MAX_FREEFORM_INTERESTS) break
      }
    }

    user.freeformInterests = accepted
    user.interestCategories = union
    return {
      categories: [...union].sort(),
      freeform: { accepted, rejected },
    }
  }

  async getInterestOptions(): Promise<InterestOptionsResponse> {
    return { options: INTEREST_OPTIONS.map((o) => ({ ...o })) }
  }

  async getInterests(): Promise<InterestsResponse> {
    const user = this.requireUser()
    return {
      categories: [...user.interestCategories].sort(),
      freeform: [...user.freeformInterests],
    }
  }

  async setInterests(body: SetInterestsRequest): Promise<SetInterestsResponse> {
    const user = this.requireUser()
    const result = this.applyInterests(user, body.categories ?? [], body.freeform ?? [])
    return { ...result, message: 'Your interests have been updated.' }
  }

  // ---------------------------------------------------------------------------
  // Push notifications (issues #342/#343)
  // ---------------------------------------------------------------------------

  async registerDevice(_body: RegisterDeviceRequest): Promise<MessageResponse> {
    // The stub keeps no device table; registration always "succeeds" so the
    // push bootstrap flow can be exercised in UI mode without a real backend.
    this.requireUser()
    return { message: 'Device registered.' }
  }

  // The push types the stub knows about, mirroring the backend's
  // PUSH_TYPE_CHOICES. Preferences default to enabled; toggling stores an
  // override in this map.
  private notificationOverrides: Record<string, boolean> = {}

  async getNotificationPreferences(): Promise<NotificationPreference[]> {
    this.requireUser()
    return [{
      type: 'post_rejected',
      label: 'Post moderation',
      enabled: this.notificationOverrides['post_rejected'] ?? true,
    }]
  }

  async setNotificationPreference(
    type: string,
    enabled: boolean,
  ): Promise<SetNotificationPreferenceResponse> {
    this.requireUser()
    this.notificationOverrides[type] = enabled
    return { type, enabled }
  }

  // ---------------------------------------------------------------------------
  // Appeals
  // ---------------------------------------------------------------------------

  private hasAppeal(targetId: string): boolean {
    return this.appeals.some((a) => a.targetId === targetId)
  }

  async getHiddenPosts(batch: number): Promise<HiddenPost[]> {
    const user = this.requireUser()
    // Pending posts have nothing to appeal yet and final rejections are
    // terminal, so neither belongs on the appeals screen (#282).
    const hidden = this.posts
      .filter((p) => p.authorId === user.id && p.hidden && this.isAppealable(p))
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(hidden, batch, POST_BATCH_SIZE).map((p) => ({
      post_identifier: p.postIdentifier,
      image_url: p.imageUrl,
      caption: p.caption,
      caption_font: p.captionFont,
      background_color: p.backgroundColor,
      hidden_reason: p.hiddenReason,
      creation_time: new Date(p.creationTime).toISOString(),
      has_appeal: this.hasAppeal(p.postIdentifier),
    }))
  }

  async getHiddenComments(batch: number): Promise<HiddenComment[]> {
    const user = this.requireUser()
    const hidden = this.commentThreads
      .flatMap((t) => t.comments)
      .filter((c) => c.authorId === user.id && c.hidden)
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(hidden, batch, COMMENT_BATCH_SIZE).map((c) => ({
      comment_identifier: c.commentIdentifier,
      body: c.body,
      body_formatting: c.bodyFormatting,
      hidden_reason: c.hiddenReason,
      creation_time: new Date(c.creationTime).toISOString(),
      has_appeal: this.hasAppeal(c.commentIdentifier),
    }))
  }

  async getMyAppeals(batch: number): Promise<MyAppeal[]> {
    const user = this.requireUser()
    const mine = this.appeals
      .filter((a) => a.appellantId === user.id)
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(mine, batch, POST_BATCH_SIZE).map((a) => ({
      appeal_identifier: a.appealIdentifier,
      target_type: a.targetType,
      target_identifier: a.targetId,
      status: a.status,
      reason: a.reason,
      content_snapshot: a.contentSnapshot,
      resolution_note: null,
      creation_time: new Date(a.creationTime).toISOString(),
      resolved_time: null,
    }))
  }

  async submitAppeal(body: SubmitAppealRequest): Promise<SubmitAppealResponse> {
    const user = this.requireUser()
    let snapshot: string
    if (body.target_type === 'post') {
      const post = this.posts.find(
        (p) =>
          p.postIdentifier === body.target_identifier &&
          p.authorId === user.id &&
          p.hidden &&
          this.isAppealable(p),
      )
      if (!post) {
        throw new ApiError(400, 'No appealable item with that identifier')
      }
      snapshot = post.caption
    } else if (body.target_type === 'comment') {
      const comment = this.commentThreads
        .flatMap((t) => t.comments)
        .find((c) => c.commentIdentifier === body.target_identifier && c.authorId === user.id && c.hidden)
      if (!comment) {
        throw new ApiError(400, 'No appealable item with that identifier')
      }
      snapshot = comment.body
    } else {
      // Match the backend, which rejects any target_type other than
      // post/comment rather than treating it as a comment.
      throw new ApiError(400, 'Invalid target_type')
    }
    if (this.hasAppeal(body.target_identifier)) {
      throw new ApiError(400, 'This item has already been appealed')
    }
    const appeal: AppealMock = {
      appealIdentifier: newId(),
      appellantId: user.id,
      targetType: body.target_type,
      targetId: body.target_identifier,
      reason: body.reason,
      contentSnapshot: snapshot,
      status: 'pending',
      creationTime: Date.now(),
    }
    this.appeals.push(appeal)
    return { appeal_identifier: appeal.appealIdentifier }
  }
}
