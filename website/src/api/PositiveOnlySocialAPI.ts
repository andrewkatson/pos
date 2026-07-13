// The API surface shared by the real HTTP client (ApiClient) and the in-memory
// StatefulStubbedAPI, mirroring the iOS `PositiveOnlySocialAPI` protocol and the
// Android `PositiveOnlySocialAPI` interface. Endpoints correspond to
// backend/user_system/urls.py.

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
  ResendVerificationEmailRequest,
  ResetPasswordRequest,
  SubmitAppealRequest,
  SubmitAppealResponse,
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
  login(body: LoginRequest): Promise<AuthResponse>
  loginWithRememberMe(body: LoginWithRememberMeRequest): Promise<LoginWithRememberMeResponse>
  logout(): Promise<MessageResponse>
  verifyIdentity(dateOfBirth: string): Promise<MessageResponse>
  deleteAccount(): Promise<MessageResponse>

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

  // Feeds & post retrieval
  getFeed(batch: number): Promise<FeedPost[]>
  getFollowedFeed(batch: number): Promise<FeedPost[]>
  getPostsForUser(username: string, batch: number): Promise<FeedPost[]>
  getPostDetails(postIdentifier: string): Promise<PostDetails>

  // Comments
  commentOnPost(postIdentifier: string, commentText: string): Promise<CommentOnPostResponse>
  replyToCommentThread(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentText: string,
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
  getProfile(username: string): Promise<ProfileDetails>

  // Appeals
  getHiddenPosts(batch: number): Promise<HiddenPost[]>
  getHiddenComments(batch: number): Promise<HiddenComment[]>
  getMyAppeals(batch: number): Promise<MyAppeal[]>
  submitAppeal(body: SubmitAppealRequest): Promise<SubmitAppealResponse>
}
