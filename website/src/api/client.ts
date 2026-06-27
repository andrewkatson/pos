// Real HTTP client for the Positive Only Social backend.
//
// Endpoints and request/response shapes mirror backend/user_system/urls.py and
// the corresponding views. Authenticated endpoints send
// `Authorization: Bearer <session_management_token>`, matching the
// `api_login_required` decorator in backend/user_system/views.py.
//
// The default base URL matches the native clients: iOS RealAPI.swift and
// Android Constants.kt both target https://api.smiling.social/user_index/.

import type { PositiveOnlySocialAPI } from './PositiveOnlySocialAPI'
import type {
  AuthResponse,
  Comment,
  CommentOnPostResponse,
  CommentThreadRef,
  CreatePostRequest,
  CreatePostResponse,
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

const DEFAULT_BASE_URL = 'https://api.smiling.social/user_index'

/** Error code the backend returns when the account has an active outright ban. */
export const ACCOUNT_BANNED = 'account_banned'

/** User-facing message shown wherever the account_banned error surfaces. */
export const ACCOUNT_SUSPENDED_MESSAGE =
  'Your account has been suspended for violating our community guidelines.'

/**
 * Friendly, user-facing copy for an HTTP status code, used when the backend did
 * not return its own `{ error }` message (e.g. a gateway timeout or routing
 * failure that returns HTML or an empty body). Keeps a raw status code from ever
 * reaching the user.
 */
function friendlyStatusMessage(status: number): string {
  switch (status) {
    case 404:
      return "We couldn't find what you were looking for. It may have been removed."
    case 408:
      return 'The request timed out. Please try again.'
    case 429:
      return "You're doing that too often. Please wait a moment and try again."
    case 502:
    case 503:
    case 504:
      return 'The server is taking too long to respond. Please try again in a moment.'
    default:
      if (status >= 500) {
        return 'The server ran into a problem. Please try again in a moment.'
      }
      return 'Something went wrong. Please try again.'
  }
}

/** User-facing copy when the request never reached the server (offline, DNS). */
const NETWORK_ERROR_MESSAGE =
  'You appear to be offline. Please check your connection and try again.'

/** Error thrown for any non-2xx response, carrying the backend's error message. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface ApiClientOptions {
  /** Backend base URL, e.g. "https://api.smiling.social/user_index". */
  baseUrl?: string
  /** Existing session token to start authenticated. */
  token?: string
  /** Injectable fetch, primarily for testing. Defaults to global fetch. */
  fetchFn?: typeof fetch
}

export class ApiClient implements PositiveOnlySocialAPI {
  private readonly baseUrl: string
  private readonly fetchFn: typeof fetch
  private token: string | null
  private onAccountBanned: (() => void) | null = null

  constructor(options: ApiClientOptions = {}) {
    const envBaseUrl =
      typeof import.meta !== 'undefined'
        ? (import.meta.env?.VITE_API_BASE_URL as string | undefined)
        : undefined
    this.baseUrl = (options.baseUrl ?? envBaseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '')
    this.token = options.token ?? null
    this.fetchFn = options.fetchFn ?? fetch.bind(globalThis)
  }

  /** Store the session token used for authenticated requests. */
  setToken(token: string | null): void {
    this.token = token
  }

  getToken(): string | null {
    return this.token
  }

  isAuthenticated(): boolean {
    return this.token !== null
  }

  /**
   * Handler invoked when an authenticated request is rejected because the
   * account is banned (the backend kills the session server-side, so the
   * app must drop its local session too).
   */
  setOnAccountBanned(handler: (() => void) | null): void {
    this.onAccountBanned = handler
  }

  private async request<T>(
    method: 'GET' | 'POST',
    path: string,
    options: { body?: unknown; auth?: boolean } = {},
  ): Promise<T> {
    const headers: Record<string, string> = {}
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }
    if (options.auth) {
      if (!this.token) {
        throw new ApiError(401, 'Not authenticated')
      }
      headers['Authorization'] = `Bearer ${this.token}`
    }

    let response: Response
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      })
    } catch {
      // fetch rejects (typically a TypeError) when the request never reached the
      // server — offline, DNS failure, connection refused. Surface plain copy
      // instead of a raw "Failed to fetch".
      throw new ApiError(0, NETWORK_ERROR_MESSAGE)
    }

    let payload: unknown = null
    const text = await response.text()
    if (text) {
      try {
        payload = JSON.parse(text)
      } catch {
        payload = text
      }
    }

    if (!response.ok) {
      const message =
        payload && typeof payload === 'object' && 'error' in payload
          ? String((payload as { error: unknown }).error)
          : friendlyStatusMessage(response.status)
      if (options.auth && message === ACCOUNT_BANNED) {
        this.onAccountBanned?.()
      }
      throw new ApiError(response.status, message)
    }

    return payload as T
  }

  // ===========================================================================
  // AUTHENTICATION
  // ===========================================================================

  async register(body: RegisterRequest): Promise<AuthResponse> {
    const result = await this.request<AuthResponse>('POST', '/register/', { body })
    this.setToken(result.session_management_token)
    return result
  }

  async login(body: LoginRequest): Promise<AuthResponse> {
    const result = await this.request<AuthResponse>('POST', '/login/', { body })
    this.setToken(result.session_management_token)
    return result
  }

  async loginWithRememberMe(
    body: LoginWithRememberMeRequest,
  ): Promise<LoginWithRememberMeResponse> {
    const result = await this.request<LoginWithRememberMeResponse>('POST', '/login/remember/', {
      body,
    })
    this.setToken(result.session_management_token)
    return result
  }

  async logout(): Promise<MessageResponse> {
    const result = await this.request<MessageResponse>('POST', '/logout/', { auth: true })
    this.setToken(null)
    return result
  }

  verifyIdentity(dateOfBirth: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', '/verify-identity/', {
      auth: true,
      body: { date_of_birth: dateOfBirth },
    })
  }

  async deleteAccount(): Promise<MessageResponse> {
    const result = await this.request<MessageResponse>('POST', '/user/delete/', { auth: true })
    this.setToken(null)
    return result
  }

  // ===========================================================================
  // PASSWORD RESET
  // ===========================================================================

  requestReset(body: RequestResetRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', '/password/request-reset/', { body })
  }

  verifyReset(body: VerifyResetRequest): Promise<VerifyResetResponse> {
    return this.request<VerifyResetResponse>('POST', '/password/verify-reset/', { body })
  }

  resetPassword(body: ResetPasswordRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', '/password/reset/', { body })
  }

  // ===========================================================================
  // POSTS
  // ===========================================================================

  createPost(body: CreatePostRequest): Promise<CreatePostResponse> {
    return this.request<CreatePostResponse>('POST', '/posts/create/', { auth: true, body })
  }

  deletePost(postIdentifier: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/posts/${postIdentifier}/delete/`, {
      auth: true,
    })
  }

  reportPost(postIdentifier: string, reason: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/posts/${postIdentifier}/report/`, {
      auth: true,
      body: { reason },
    })
  }

  likePost(postIdentifier: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/posts/${postIdentifier}/like/`, { auth: true })
  }

  unlikePost(postIdentifier: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/posts/${postIdentifier}/unlike/`, {
      auth: true,
    })
  }

  // ===========================================================================
  // FEEDS & POST RETRIEVAL
  // ===========================================================================

  getFeed(batch: number): Promise<FeedPost[]> {
    return this.request<FeedPost[]>('GET', `/feed/${batch}/`, { auth: true })
  }

  getFollowedFeed(batch: number): Promise<FeedPost[]> {
    return this.request<FeedPost[]>('GET', `/feed/followed/${batch}/`, { auth: true })
  }

  getPostsForUser(username: string, batch: number): Promise<FeedPost[]> {
    return this.request<FeedPost[]>('GET', `/users/${username}/posts/${batch}/`, { auth: true })
  }

  getPostDetails(postIdentifier: string): Promise<PostDetails> {
    return this.request<PostDetails>('GET', `/posts/${postIdentifier}/details/`)
  }

  // ===========================================================================
  // COMMENTS
  // ===========================================================================

  commentOnPost(postIdentifier: string, commentText: string): Promise<CommentOnPostResponse> {
    return this.request<CommentOnPostResponse>('POST', `/posts/${postIdentifier}/comment/`, {
      auth: true,
      body: { comment_text: commentText },
    })
  }

  replyToCommentThread(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentText: string,
  ): Promise<ReplyResponse> {
    return this.request<ReplyResponse>(
      'POST',
      `/posts/${postIdentifier}/threads/${commentThreadIdentifier}/reply/`,
      { auth: true, body: { comment_text: commentText } },
    )
  }

  getCommentsForPost(postIdentifier: string, batch: number): Promise<CommentThreadRef[]> {
    return this.request<CommentThreadRef[]>(
      'GET',
      `/posts/${postIdentifier}/comments/${batch}/`,
      { auth: true },
    )
  }

  getCommentsForThread(commentThreadIdentifier: string, batch: number): Promise<Comment[]> {
    return this.request<Comment[]>(
      'GET',
      `/threads/${commentThreadIdentifier}/comments/${batch}/`,
      { auth: true },
    )
  }

  likeComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    return this.request<MessageResponse>(
      'POST',
      `/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/like/`,
      { auth: true },
    )
  }

  unlikeComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    return this.request<MessageResponse>(
      'POST',
      `/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/unlike/`,
      { auth: true },
    )
  }

  deleteComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
  ): Promise<MessageResponse> {
    return this.request<MessageResponse>(
      'POST',
      `/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/delete/`,
      { auth: true },
    )
  }

  reportComment(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentIdentifier: string,
    reason: string,
  ): Promise<MessageResponse> {
    return this.request<MessageResponse>(
      'POST',
      `/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/report/`,
      { auth: true, body: { reason } },
    )
  }

  // ===========================================================================
  // USERS & PROFILES
  // ===========================================================================

  searchUsers(usernameFragment: string): Promise<UserSearchResult[]> {
    return this.request<UserSearchResult[]>('GET', `/users/search/${usernameFragment}/`, {
      auth: true,
    })
  }

  followUser(username: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/users/${username}/follow/`, { auth: true })
  }

  unfollowUser(username: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/users/${username}/unfollow/`, { auth: true })
  }

  toggleBlock(username: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/users/${username}/block/`, { auth: true })
  }

  getProfile(username: string): Promise<ProfileDetails> {
    return this.request<ProfileDetails>('GET', `/users/${username}/profile/`, { auth: true })
  }

  // ===========================================================================
  // APPEALS
  // ===========================================================================

  getHiddenPosts(batch: number): Promise<HiddenPost[]> {
    return this.request<HiddenPost[]>('GET', `/appeals/hidden/posts/${batch}/`, { auth: true })
  }

  getHiddenComments(batch: number): Promise<HiddenComment[]> {
    return this.request<HiddenComment[]>('GET', `/appeals/hidden/comments/${batch}/`, { auth: true })
  }

  getMyAppeals(batch: number): Promise<MyAppeal[]> {
    return this.request<MyAppeal[]>('GET', `/appeals/mine/${batch}/`, { auth: true })
  }

  submitAppeal(body: SubmitAppealRequest): Promise<SubmitAppealResponse> {
    return this.request<SubmitAppealResponse>('POST', '/appeals/submit/', { auth: true, body })
  }
}

/** Shared client instance for the app. */
export const apiClient = new ApiClient()
