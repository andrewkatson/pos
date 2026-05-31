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

export interface CreatePostRequest {
  image_url: string
  caption: string
}

export interface CreatePostResponse {
  post_identifier: string
}

/** A post as returned by the feed/listing endpoints. */
export interface FeedPost {
  post_identifier: string
  image_url: string
  author_username: string
  caption: string
}

/** A post as returned by the post-details endpoint. */
export interface PostDetails {
  post_identifier: string
  image_url: string
  caption: string
  post_likes: number
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
