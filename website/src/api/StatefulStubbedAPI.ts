// A stateful stub that mimics the Django backend logic entirely in memory.
// Mirrors ios/.../api/StatefulStubbedAPI.swift and
// android/.../api/StatefulStubbedAPI.kt. Useful for tests and offline/demo
// modes. Errors are surfaced by throwing ApiError, matching the real ApiClient.

import { ApiError } from './client'
import type { PositiveOnlySocialAPI } from './PositiveOnlySocialAPI'
import type {
  AuthResponse,
  Comment,
  CommentOnPostResponse,
  CommentThreadRef,
  CreatePostRequest,
  CreatePostResponse,
  CreateUploadUrlResponse,
  FeedPost,
  HiddenComment,
  HiddenPost,
  LoginRequest,
  LoginWithRememberMeRequest,
  LoginWithRememberMeResponse,
  MessageResponse,
  MyAppeal,
  PostDetails,
  ProfileDetails,
  RegisterRequest,
  ReplyResponse,
  RequestResetRequest,
  ResetPasswordRequest,
  SubmitAppealRequest,
  SubmitAppealResponse,
  UserSearchResult,
  VerifyResetRequest,
  VerifyResetResponse,
} from './types'

// Stub-specific tuning values, matching the iOS/Android StatefulStubbedAPI
// stubs. These intentionally differ from backend/user_system/constants.py
// (which uses larger batches and report thresholds); the stub favors small,
// test-friendly numbers and is not the source of truth for the real backend.
const POST_BATCH_SIZE = 10
const COMMENT_BATCH_SIZE = 10
const MAX_BEFORE_HIDING_POST = 5
const MAX_BEFORE_HIDING_COMMENT = 5

interface UserMock {
  id: string
  username: string
  email: string
  passwordHash: string
  verificationToken: string | null
  resetToken: string | null
  following: Set<string>
  followers: Set<string>
  isVerified: boolean
  isAdult: boolean
  blocked: Set<string>
  blockedBy: Set<string>
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
  imageUrl: string
  caption: string
  creationTime: number
  hidden: boolean
  hiddenReason: string
  likes: Set<string>
  reports: Set<string>
}

interface CommentMock {
  commentIdentifier: string
  authorId: string
  body: string
  creationTime: number
  hidden: boolean
  hiddenReason: string
  likes: Set<string>
  reports: Set<string>
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
      following: new Set(),
      followers: new Set(),
      isVerified: Boolean(body.date_of_birth),
      isAdult: age !== null && age >= 18,
      blocked: new Set(),
      blockedBy: new Set(),
    }
    this.users.push(user)

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
    }
  }

  async login(body: LoginRequest): Promise<AuthResponse> {
    const user = this.users.find(
      (u) => u.username === body.username_or_email || u.email === body.username_or_email,
    )
    if (!user || user.passwordHash !== body.password) {
      throw new ApiError(400, 'Invalid username or password')
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

  // ---------------------------------------------------------------------------
  // Password reset
  // ---------------------------------------------------------------------------

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
    // Stub "positivity" check, mirroring the native stubs.
    if (body.caption.includes('negative')) {
      throw new ApiError(400, 'Text is not positive')
    }
    const post: PostMock = {
      postIdentifier: newId(),
      authorId: user.id,
      imageUrl: body.image_url,
      caption: body.caption,
      creationTime: Date.now(),
      hidden: false,
      hiddenReason: '',
      likes: new Set(),
      reports: new Set(),
    }
    this.posts.push(post)
    return { post_identifier: post.postIdentifier }
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

  async reportPost(postIdentifier: string, _reason: string): Promise<MessageResponse> {
    const user = this.requireUser()
    const post = this.findPost(postIdentifier)
    if (post.authorId === user.id) {
      throw new ApiError(400, 'Cannot report own post')
    }
    if (post.reports.has(user.id)) {
      throw new ApiError(400, 'Cannot report post twice')
    }
    post.reports.add(user.id)
    if (post.reports.size > MAX_BEFORE_HIDING_POST) {
      post.hidden = true
      post.hiddenReason = 'reports'
    }
    return { message: 'Post reported' }
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

  // ---------------------------------------------------------------------------
  // Feeds & retrieval
  // ---------------------------------------------------------------------------

  private toFeedPost(post: PostMock): FeedPost {
    const author = this.users.find((u) => u.id === post.authorId)
    return {
      post_identifier: post.postIdentifier,
      image_url: post.imageUrl,
      // Mirrors the backend: the full-resolution original, used as a client-side
      // fallback when the compressed image isn't available yet (issues #252/#254).
      original_image_url: post.imageUrl,
      author_username: author ? author.username : '',
      caption: post.caption,
    }
  }

  async getFeed(batch: number): Promise<FeedPost[]> {
    const user = this.requireUser()
    const visible = this.posts
      .filter((p) => !p.hidden && !user.blocked.has(p.authorId) && !user.blockedBy.has(p.authorId))
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p))
  }

  async getFollowedFeed(batch: number): Promise<FeedPost[]> {
    const user = this.requireUser()
    const visible = this.posts
      .filter(
        (p) =>
          !p.hidden &&
          user.following.has(p.authorId) &&
          !user.blocked.has(p.authorId) &&
          !user.blockedBy.has(p.authorId),
      )
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p))
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
    const visible = this.posts
      .filter((p) => !p.hidden && p.authorId === target.id)
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(visible, batch, POST_BATCH_SIZE).map((p) => this.toFeedPost(p))
  }

  async getPostDetails(postIdentifier: string): Promise<PostDetails> {
    const post = this.findPost(postIdentifier)
    const author = this.users.find((u) => u.id === post.authorId)
    return {
      post_identifier: post.postIdentifier,
      image_url: post.imageUrl,
      caption: post.caption,
      post_likes: post.likes.size,
      author_username: author ? author.username : '',
    }
  }

  // ---------------------------------------------------------------------------
  // Comments
  // ---------------------------------------------------------------------------

  async commentOnPost(
    postIdentifier: string,
    commentText: string,
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
      creationTime: Date.now(),
      hidden: false,
      hiddenReason: '',
      likes: new Set(),
      reports: new Set(),
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
      creationTime: Date.now(),
      hidden: false,
      hiddenReason: '',
      likes: new Set(),
      reports: new Set(),
    }
    thread.comments.push(comment)
    return { comment_identifier: comment.commentIdentifier }
  }

  async getCommentsForPost(
    postIdentifier: string,
    batch: number,
  ): Promise<CommentThreadRef[]> {
    this.requireUser()
    const threads = this.commentThreads.filter((t) => t.postId === postIdentifier)
    return this.batch(threads, batch, COMMENT_BATCH_SIZE).map((t) => ({
      comment_thread_identifier: t.threadIdentifier,
    }))
  }

  async getCommentsForThread(
    commentThreadIdentifier: string,
    batch: number,
  ): Promise<Comment[]> {
    this.requireUser()
    const thread = this.commentThreads.find(
      (t) => t.threadIdentifier === commentThreadIdentifier,
    )
    if (!thread) {
      throw new ApiError(400, 'No comment thread with that identifier')
    }
    const visible = thread.comments
      .filter((c) => !c.hidden)
      .sort((a, b) => a.creationTime - b.creationTime)
    return this.batch(visible, batch, COMMENT_BATCH_SIZE).map((c) => {
      const author = this.users.find((u) => u.id === c.authorId)
      const time = new Date(c.creationTime).toISOString()
      return {
        comment_identifier: c.commentIdentifier,
        body: c.body,
        author_username: author ? author.username : '',
        creation_time: time,
        updated_time: time,
        comment_likes: c.likes.size,
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
    _reason: string,
  ): Promise<MessageResponse> {
    const user = this.requireUser()
    const comment = this.findComment(postIdentifier, commentThreadIdentifier, commentIdentifier)
    if (comment.authorId === user.id) {
      throw new ApiError(400, 'Cannot report own comment')
    }
    if (comment.reports.has(user.id)) {
      throw new ApiError(400, 'Cannot report comment twice')
    }
    comment.reports.add(user.id)
    if (comment.reports.size > MAX_BEFORE_HIDING_COMMENT) {
      comment.hidden = true
      comment.hiddenReason = 'reports'
    }
    return { message: 'Comment reported' }
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
      .map((u) => ({ username: u.username, identity_is_verified: u.isVerified }))
  }

  async followUser(username: string): Promise<MessageResponse> {
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
    user.following.add(target.id)
    target.followers.add(user.id)
    return { message: 'User followed' }
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
    target.followers.delete(user.id)
    return { message: 'User unfollowed' }
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
    target.followers.delete(user.id)
    target.following.delete(user.id)
    user.followers.delete(target.id)
    return { message: 'User blocked' }
  }

  async getProfile(username: string): Promise<ProfileDetails> {
    const user = this.requireUser()
    const target = this.findUserByName(username)
    if (!target) {
      throw new ApiError(400, 'User not found')
    }
    const isBlockedBy = user.blockedBy.has(target.id)
    const postCount = isBlockedBy ? 0 : this.posts.filter((p) => p.authorId === target.id).length
    return {
      username: target.username,
      post_count: postCount,
      follower_count: isBlockedBy ? 0 : target.followers.size,
      following_count: isBlockedBy ? 0 : target.following.size,
      is_following: isBlockedBy ? false : user.following.has(target.id),
      is_blocked: user.blocked.has(target.id),
      identity_is_verified: target.isVerified,
      is_adult: target.isAdult,
    }
  }

  // ---------------------------------------------------------------------------
  // Appeals
  // ---------------------------------------------------------------------------

  private hasAppeal(targetId: string): boolean {
    return this.appeals.some((a) => a.targetId === targetId)
  }

  async getHiddenPosts(batch: number): Promise<HiddenPost[]> {
    const user = this.requireUser()
    const hidden = this.posts
      .filter((p) => p.authorId === user.id && p.hidden)
      .sort((a, b) => b.creationTime - a.creationTime)
    return this.batch(hidden, batch, POST_BATCH_SIZE).map((p) => ({
      post_identifier: p.postIdentifier,
      image_url: p.imageUrl,
      caption: p.caption,
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
        (p) => p.postIdentifier === body.target_identifier && p.authorId === user.id && p.hidden,
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
