// The API surface shared by the real HTTP client (ApiClient) and the in-memory
// StatefulStubbedAPI, mirroring the iOS `PositiveOnlySocialAPI` protocol and the
// Android `PositiveOnlySocialAPI` interface. Endpoints correspond to
// backend/user_system/urls.py.

import type {
  AuthResponse,
  Comment,
  CommentFormatSpan,
  CommentOnPostResponse,
  CommentThreadRef,
  ConfirmTotpRequest,
  ConfirmTotpResponse,
  CreatePostRequest,
  CreatePostResponse,
  CreateUploadUrlResponse,
  DisableTotpRequest,
  DisableTotpResponse,
  FeedPost,
  HiddenComment,
  HiddenPost,
  LoginRequest,
  LoginResponse,
  LoginTwoFactorRequest,
  LoginWithRememberMeRequest,
  LoginWithRememberMeResponse,
  MessageResponse,
  MyAppeal,
  PostDetails,
  PostStatusResponse,
  ProfileDetails,
  RegisterRequest,
  RemoveProfilePhotoResponse,
  ReplyResponse,
  RequestResetRequest,
  ResendVerificationEmailRequest,
  ResetPasswordRequest,
  SetProfilePhotoRequest,
  SetProfilePhotoResponse,
  SubmitAppealRequest,
  SubmitAppealResponse,
  TwoFactorSetupResponse,
  UserSearchResult,
  VerifyEmailRequest,
  VerifyResetRequest,
  VerifyResetResponse,
} from './types'

export interface PositiveOnlySocialAPI {
  // Session token management. The token is stored on the client and sent as
  // `Authorization: Bearer <token>` on authenticated calls.
  setToken(token: string | null): void
  getToken(): string | null
  isAuthenticated(): boolean

  // Authentication
  register(body: RegisterRequest): Promise<AuthResponse>
  login(body: LoginRequest): Promise<LoginResponse>
  loginWithRememberMe(body: LoginWithRememberMeRequest): Promise<LoginWithRememberMeResponse>
  logout(): Promise<MessageResponse>
  verifyIdentity(dateOfBirth: string): Promise<MessageResponse>
  deleteAccount(): Promise<MessageResponse>

  // Two-factor authentication (TOTP)
  loginWithTwoFactor(body: LoginTwoFactorRequest): Promise<AuthResponse>
  setupTotp(): Promise<TwoFactorSetupResponse>
  confirmTotp(body: ConfirmTotpRequest): Promise<ConfirmTotpResponse>
  disableTotp(body: DisableTotpRequest): Promise<DisableTotpResponse>

  // Email verification
  verifyEmail(body: VerifyEmailRequest): Promise<MessageResponse>
  resendVerificationEmail(body: ResendVerificationEmailRequest): Promise<MessageResponse>

  // Password reset
  requestReset(body: RequestResetRequest): Promise<MessageResponse>
  verifyReset(body: VerifyResetRequest): Promise<VerifyResetResponse>
  resetPassword(body: ResetPasswordRequest): Promise<MessageResponse>

  // Posts
  createUploadUrl(): Promise<CreateUploadUrlResponse>
  createPost(body: CreatePostRequest): Promise<CreatePostResponse>
  deletePost(postIdentifier: string): Promise<MessageResponse>
  reportPost(postIdentifier: string, reason: string): Promise<MessageResponse>
  retractReportPost(postIdentifier: string): Promise<MessageResponse>
  likePost(postIdentifier: string): Promise<MessageResponse>
  unlikePost(postIdentifier: string): Promise<MessageResponse>
  /** Bookmark a post so it appears on the Saved Posts screen (issue #193). */
  savePost(postIdentifier: string): Promise<MessageResponse>
  unsavePost(postIdentifier: string): Promise<MessageResponse>

  // Feeds & post retrieval
  getFeed(batch: number): Promise<FeedPost[]>
  getFollowedFeed(batch: number): Promise<FeedPost[]>
  getPostsForUser(username: string, batch: number): Promise<FeedPost[]>
  /** The signed-in user's saved posts, newest save first (issue #193). */
  getSavedPosts(batch: number): Promise<FeedPost[]>
  getPostDetails(postIdentifier: string): Promise<PostDetails>
  /** Classification status of one of the caller's own posts (issue #282). */
  getPostStatus(postIdentifier: string): Promise<PostStatusResponse>

  // Comments. `formatting` carries optional inline styling spans (issue #318).
  commentOnPost(
    postIdentifier: string,
    commentText: string,
    formatting?: CommentFormatSpan[],
  ): Promise<CommentOnPostResponse>
  replyToCommentThread(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentText: string,
    formatting?: CommentFormatSpan[],
  ): Promise<ReplyResponse>
  getCommentsForPost(postIdentifier: string, batch: number): Promise<CommentThreadRef[]>
  getCommentsForThread(commentThreadIdentifier: string, batch: number): Promise<Comment[]>
  likeComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse>
  unlikeComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse>
  deleteComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse>
  reportComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
    reason: string,
  ): Promise<MessageResponse>
  retractReportComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse>

  // Users & profiles
  searchUsers(usernameFragment: string): Promise<UserSearchResult[]>
  followUser(username: string): Promise<MessageResponse>
  unfollowUser(username: string): Promise<MessageResponse>
  toggleBlock(username: string): Promise<MessageResponse>
  getBlockedUsers(): Promise<UserSearchResult[]>
  getFollowers(): Promise<UserSearchResult[]>
  getFollowing(): Promise<UserSearchResult[]>
  getProfile(username: string): Promise<ProfileDetails>
  /** Set the signed-in user's profile photo to an already-uploaded image
   * (issue #7). The photo is classified asynchronously and shown to others only
   * once approved; the response reports the initial 'pending' state. */
  setProfilePhoto(body: SetProfilePhotoRequest): Promise<SetProfilePhotoResponse>
  /** Remove the signed-in user's profile photo entirely. */
  removeProfilePhoto(): Promise<RemoveProfilePhotoResponse>

  // Appeals
  getHiddenPosts(batch: number): Promise<HiddenPost[]>
  getHiddenComments(batch: number): Promise<HiddenComment[]>
  getMyAppeals(batch: number): Promise<MyAppeal[]>
  submitAppeal(body: SubmitAppealRequest): Promise<SubmitAppealResponse>
}
