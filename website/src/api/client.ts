// Typed client for the Positive Only Social backend.
//
// Endpoints and request/response shapes mirror backend/pos_backend/urls.py,
// backend/user_system/urls.py, and the corresponding views. Authenticated
// endpoints send `Authorization: Bearer <session_management_token>`, matching
// the `api_login_required` decorator in backend/user_system/views.py.

import type {
  AuthResponse,
  Comment,
  CommentOnPostResponse,
  CommentThreadRef,
  CreatePostRequest,
  CreatePostResponse,
  FeedPost,
  HealthResponse,
  LoginRequest,
  LoginWithRememberMeRequest,
  LoginWithRememberMeResponse,
  MessageResponse,
  PostDetails,
  ProfileDetails,
  RegisterRequest,
  ReplyResponse,
  RequestResetRequest,
  ResetPasswordRequest,
  UserSearchResult,
  VerifyResetRequest,
  VerifyResetResponse,
} from './types'

const DEFAULT_BASE_URL = 'http://localhost:8000'

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
  /** Backend origin, e.g. "https://api.example.com". */
  baseUrl?: string
  /** Existing session token to start authenticated. */
  token?: string
  /** Injectable fetch, primarily for testing. Defaults to global fetch. */
  fetchFn?: typeof fetch
}

export class ApiClient {
  private readonly baseUrl: string
  private readonly fetchFn: typeof fetch
  private token: string | null

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

    const response = await this.fetchFn(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })

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
          : `Request failed with status ${response.status}`
      throw new ApiError(response.status, message)
    }

    return payload as T
  }

  // ===========================================================================
  // HEALTH
  // ===========================================================================

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('GET', '/health/')
  }

  // ===========================================================================
  // AUTHENTICATION
  // ===========================================================================

  async register(body: RegisterRequest): Promise<AuthResponse> {
    const result = await this.request<AuthResponse>('POST', '/user_index/register/', { body })
    this.setToken(result.session_management_token)
    return result
  }

  async login(body: LoginRequest): Promise<AuthResponse> {
    const result = await this.request<AuthResponse>('POST', '/user_index/login/', { body })
    this.setToken(result.session_management_token)
    return result
  }

  async loginWithRememberMe(
    body: LoginWithRememberMeRequest,
  ): Promise<LoginWithRememberMeResponse> {
    const result = await this.request<LoginWithRememberMeResponse>(
      'POST',
      '/user_index/login/remember/',
      { body },
    )
    this.setToken(result.session_management_token)
    return result
  }

  async logout(): Promise<MessageResponse> {
    const result = await this.request<MessageResponse>('POST', '/user_index/logout/', {
      auth: true,
    })
    this.setToken(null)
    return result
  }

  verifyIdentity(dateOfBirth: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', '/user_index/verify-identity/', {
      auth: true,
      body: { date_of_birth: dateOfBirth },
    })
  }

  async deleteAccount(): Promise<MessageResponse> {
    const result = await this.request<MessageResponse>('POST', '/user_index/user/delete/', {
      auth: true,
    })
    this.setToken(null)
    return result
  }

  // ===========================================================================
  // PASSWORD RESET
  // ===========================================================================

  requestReset(body: RequestResetRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', '/user_index/password/request-reset/', { body })
  }

  verifyReset(body: VerifyResetRequest): Promise<VerifyResetResponse> {
    return this.request<VerifyResetResponse>('POST', '/user_index/password/verify-reset/', {
      body,
    })
  }

  resetPassword(body: ResetPasswordRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', '/user_index/password/reset/', { body })
  }

  // ===========================================================================
  // POSTS
  // ===========================================================================

  createPost(body: CreatePostRequest): Promise<CreatePostResponse> {
    return this.request<CreatePostResponse>('POST', '/user_index/posts/create/', {
      auth: true,
      body,
    })
  }

  deletePost(postIdentifier: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/posts/${postIdentifier}/delete/`, {
      auth: true,
    })
  }

  reportPost(postIdentifier: string, reason: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/posts/${postIdentifier}/report/`, {
      auth: true,
      body: { reason },
    })
  }

  likePost(postIdentifier: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/posts/${postIdentifier}/like/`, {
      auth: true,
    })
  }

  unlikePost(postIdentifier: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/posts/${postIdentifier}/unlike/`, {
      auth: true,
    })
  }

  // ===========================================================================
  // FEEDS & POST RETRIEVAL
  // ===========================================================================

  getFeed(batch: number): Promise<FeedPost[]> {
    return this.request<FeedPost[]>('GET', `/user_index/feed/${batch}/`, { auth: true })
  }

  getFollowedFeed(batch: number): Promise<FeedPost[]> {
    return this.request<FeedPost[]>('GET', `/user_index/feed/followed/${batch}/`, { auth: true })
  }

  getPostsForUser(username: string, batch: number): Promise<FeedPost[]> {
    return this.request<FeedPost[]>('GET', `/user_index/users/${username}/posts/${batch}/`, {
      auth: true,
    })
  }

  getPostDetails(postIdentifier: string): Promise<PostDetails> {
    return this.request<PostDetails>('GET', `/user_index/posts/${postIdentifier}/details/`)
  }

  // ===========================================================================
  // COMMENTS
  // ===========================================================================

  commentOnPost(postIdentifier: string, commentText: string): Promise<CommentOnPostResponse> {
    return this.request<CommentOnPostResponse>(
      'POST',
      `/user_index/posts/${postIdentifier}/comment/`,
      { auth: true, body: { comment_text: commentText } },
    )
  }

  replyToCommentThread(
    postIdentifier: string,
    commentThreadIdentifier: string,
    commentText: string,
  ): Promise<ReplyResponse> {
    return this.request<ReplyResponse>(
      'POST',
      `/user_index/posts/${postIdentifier}/threads/${commentThreadIdentifier}/reply/`,
      { auth: true, body: { comment_text: commentText } },
    )
  }

  getCommentsForPost(postIdentifier: string, batch: number): Promise<CommentThreadRef[]> {
    return this.request<CommentThreadRef[]>(
      'GET',
      `/user_index/posts/${postIdentifier}/comments/${batch}/`,
      { auth: true },
    )
  }

  getCommentsForThread(
    commentThreadIdentifier: string,
    batch: number,
  ): Promise<Comment[]> {
    return this.request<Comment[]>(
      'GET',
      `/user_index/threads/${commentThreadIdentifier}/comments/${batch}/`,
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
      `/user_index/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/like/`,
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
      `/user_index/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/unlike/`,
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
      `/user_index/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/delete/`,
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
      `/user_index/posts/${postIdentifier}/threads/${commentThreadIdentifier}/comments/${commentIdentifier}/report/`,
      { auth: true, body: { reason } },
    )
  }

  // ===========================================================================
  // USERS & PROFILES
  // ===========================================================================

  searchUsers(usernameFragment: string): Promise<UserSearchResult[]> {
    return this.request<UserSearchResult[]>(
      'GET',
      `/user_index/users/search/${usernameFragment}/`,
      { auth: true },
    )
  }

  followUser(username: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/users/${username}/follow/`, {
      auth: true,
    })
  }

  unfollowUser(username: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/users/${username}/unfollow/`, {
      auth: true,
    })
  }

  toggleBlock(username: string): Promise<MessageResponse> {
    return this.request<MessageResponse>('POST', `/user_index/users/${username}/block/`, {
      auth: true,
    })
  }

  getProfile(username: string): Promise<ProfileDetails> {
    return this.request<ProfileDetails>('GET', `/user_index/users/${username}/profile/`, {
      auth: true,
    })
  }
}

/** Shared client instance for the app. */
export const apiClient = new ApiClient()
