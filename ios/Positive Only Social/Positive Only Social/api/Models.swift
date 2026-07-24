//
//  Models.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import Foundation

// MARK: - API Response Models

/// The actual data fields returned by the login/register endpoints.
/// Properties are optional since "remember me" tokens may not be present.
struct LoginResponseFields: Codable {
    let sessionManagementToken: String
    let username: String?
    let userId: String?
    let seriesIdentifier: String?
    let loginCookieToken: String?

    enum CodingKeys: String, CodingKey {
        case sessionManagementToken = "session_management_token"
        case username
        case userId = "user_id"
        case seriesIdentifier = "series_identifier"
        case loginCookieToken = "login_cookie_token"
    }
}

/// Returned by login instead of a session when the account has two-factor
/// authentication enabled (issue #348). The challenge is exchanged (with a
/// TOTP or recovery code) for the real session at `login/2fa/` before it
/// expires a few minutes later.
struct TwoFactorRequiredFields: Codable {
    let twoFactorRequired: Bool
    let challengeToken: String

    enum CodingKeys: String, CodingKey {
        case twoFactorRequired = "two_factor_required"
        case challengeToken = "challenge_token"
    }
}

/// The response from starting TOTP enrollment: the shared secret (for manual
/// entry) and the otpauth:// provisioning URI (rendered as a QR code).
struct TotpSetupFields: Codable {
    let totpSecret: String
    let otpauthUri: String

    enum CodingKeys: String, CodingKey {
        case totpSecret = "totp_secret"
        case otpauthUri = "otpauth_uri"
    }
}

/// The response from confirming TOTP enrollment. The recovery codes are
/// single-use and shown exactly once.
struct ConfirmTotpFields: Codable {
    let totpEnabled: Bool
    let recoveryCodes: [String]

    enum CodingKeys: String, CodingKey {
        case totpEnabled = "totp_enabled"
        case recoveryCodes = "recovery_codes"
    }
}

/// The response from disabling two-factor authentication.
struct DisableTotpFields: Codable {
    let totpEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case totpEnabled = "totp_enabled"
    }
}

// Represents a single post in the user's grid.
// Conforms to Identifiable and Hashable to be used in grids and lists.
struct Post: Codable, Identifiable, Hashable {
    var id: String { postIdentifier }
    let postIdentifier: String
    /// Nil for a text-only post (#307), which renders as a caption tile.
    let imageUrl: String?
    /// The full-resolution original image URL, used as a fallback when the
    /// compressed `imageUrl` fails to load. The compressed copy is produced by
    /// an async Lambda, so a just-posted (or recently hidden-pending-appeal)
    /// image may not exist in the compressed bucket yet — without this fallback
    /// those grid tiles render as empty grey boxes until the user re-logs in.
    /// Optional for backward compatibility with responses that predate the field.
    let originalImageUrl: String?
    let caption: String
    /// Whole-caption font + whole-tile background color keys (issue #318).
    /// "default" reproduces the original rendering. Defaulted on decode so
    /// responses that predate the fields still decode.
    var captionFont: String = "default"
    var backgroundColor: String = "default"
    let authorUsername: String
    /// Author-only classification state (issue #282): present on the viewer's
    /// own posts so grids can render pending/rejected states. Other users'
    /// posts never carry these (their pending/hidden posts are filtered out
    /// server-side entirely). One of "pending", "approved", "rejected",
    /// "rejected_final"; nil on older backends or others' posts.
    var status: String? = nil
    var hidden: Bool? = nil
    var hiddenReason: String? = nil
    var appealable: Bool? = nil

    /// The interaction state the post lists need to offer like / report /
    /// retract-report / delete in place, without opening the post (issue #267).
    /// These carry exactly what `get_post_details` returns, and the three
    /// listing endpoints now return them too. They're `var` so an action can
    /// optimistically update the cached post, and defaulted when decoding so a
    /// response from an older backend (which omits them) still decodes.
    var postLikes: Int
    var isLiked: Bool
    var isReported: Bool
    var reportReason: String?

    /// How many comments on this post are visible to the viewer, and when the
    /// post was made — the extra context the feed rows show (issue #249). Kept
    /// as the raw timestamp string so `Post` still round-trips through `Codable`
    /// unchanged; use `createdDate` to render it.
    var commentCount: Int
    var creationTime: String?

    /// When the post was made, or nil when the backend didn't send a timestamp
    /// (or sent one we can't parse) — in which case the feed omits the label.
    var createdDate: Date? {
        guard let creationTime else { return nil }
        return RelativeTime.date(from: creationTime)
    }

    enum CodingKeys: String, CodingKey {
        case postIdentifier = "post_identifier"
        case imageUrl = "image_url"
        case originalImageUrl = "original_image_url"
        case caption = "caption"
        case captionFont = "caption_font"
        case backgroundColor = "background_color"
        case authorUsername = "author_username"
        case postLikes = "post_likes"
        case isLiked = "is_liked"
        case isReported = "is_reported"
        case reportReason = "report_reason"
        case commentCount = "comment_count"
        case creationTime = "creation_time"
        case status
        case hidden
        case hiddenReason = "hidden_reason"
        case appealable
    }

    init(
        postIdentifier: String,
        imageUrl: String?,
        originalImageUrl: String? = nil,
        caption: String,
        captionFont: String = "default",
        backgroundColor: String = "default",
        authorUsername: String,
        postLikes: Int = 0,
        isLiked: Bool = false,
        isReported: Bool = false,
        reportReason: String? = nil,
        commentCount: Int = 0,
        creationTime: String? = nil,
        status: String? = nil,
        hidden: Bool? = nil,
        hiddenReason: String? = nil,
        appealable: Bool? = nil
    ) {
        self.postIdentifier = postIdentifier
        self.imageUrl = imageUrl
        self.originalImageUrl = originalImageUrl
        self.caption = caption
        self.captionFont = captionFont
        self.backgroundColor = backgroundColor
        self.authorUsername = authorUsername
        self.postLikes = postLikes
        self.isLiked = isLiked
        self.isReported = isReported
        self.reportReason = reportReason
        self.commentCount = commentCount
        self.creationTime = creationTime
        self.status = status
        self.hidden = hidden
        self.hiddenReason = hiddenReason
        self.appealable = appealable
    }

    // Decodes the interaction fields leniently so a response that predates them
    // (an older server, or a cached payload) still yields a usable post.
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        postIdentifier = try container.decode(String.self, forKey: .postIdentifier)
        imageUrl = try container.decodeIfPresent(String.self, forKey: .imageUrl)
        originalImageUrl = try container.decodeIfPresent(String.self, forKey: .originalImageUrl)
        caption = try container.decode(String.self, forKey: .caption)
        captionFont = try container.decodeIfPresent(String.self, forKey: .captionFont) ?? "default"
        backgroundColor = try container.decodeIfPresent(String.self, forKey: .backgroundColor) ?? "default"
        authorUsername = try container.decode(String.self, forKey: .authorUsername)
        postLikes = try container.decodeIfPresent(Int.self, forKey: .postLikes) ?? 0
        isLiked = try container.decodeIfPresent(Bool.self, forKey: .isLiked) ?? false
        isReported = try container.decodeIfPresent(Bool.self, forKey: .isReported) ?? false
        reportReason = try container.decodeIfPresent(String.self, forKey: .reportReason)
        commentCount = try container.decodeIfPresent(Int.self, forKey: .commentCount) ?? 0
        creationTime = try container.decodeIfPresent(String.self, forKey: .creationTime)
        // Author-only classification state (#282); absent on others' posts.
        status = try container.decodeIfPresent(String.self, forKey: .status)
        hidden = try container.decodeIfPresent(Bool.self, forKey: .hidden)
        hiddenReason = try container.decodeIfPresent(String.self, forKey: .hiddenReason)
        appealable = try container.decodeIfPresent(Bool.self, forKey: .appealable)
    }
}

// MARK: - Post Creation (upload-url and create endpoints)

/// The response from createUploadUrl: a short-lived presigned S3 PUT URL to
/// send the JPEG bytes to, and the canonical object URL (no signing query)
/// to hand back to makePost.
struct UploadUrlResponse: Codable {
    let uploadUrl: String
    let imageUrl: String

    enum CodingKeys: String, CodingKey {
        case uploadUrl = "upload_url"
        case imageUrl = "image_url"
    }
}

/// The response from makePost. On current backends classification runs
/// asynchronously (issue #282): `status` is "pending" and the post is hidden
/// until review finishes, with the outcome reconciled via getPostStatus or a
/// grid refresh. On older inline-classifying backends `hidden` means the post
/// was flagged but is appealable.
struct MakePostResponse: Codable {
    let postIdentifier: String
    let status: String?
    let hidden: Bool?
    let hiddenReason: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case postIdentifier = "post_identifier"
        case status
        case hidden
        case hiddenReason = "hidden_reason"
        case message
    }
}

/// The response from getPostStatus (issue #282): the author-only
/// classification state of one of the signed-in user's posts.
struct PostStatusResponse: Codable {
    let postIdentifier: String
    /// "pending", "approved", "rejected", or "rejected_final".
    let status: String
    /// Public reason code of a rejection ("profanity", "gore", ...), else nil.
    let reasonCode: String?
    let appealable: Bool
    let hidden: Bool
    let hiddenReason: String
    /// User-facing explanation for pending/rejected states; nil when approved.
    let message: String?

    enum CodingKeys: String, CodingKey {
        case postIdentifier = "post_identifier"
        case status
        case reasonCode = "reason_code"
        case appealable
        case hidden
        case hiddenReason = "hidden_reason"
        case message
    }
}

// MARK: - Appeals (backend appeal endpoints)

/// One of the signed-in user's hidden posts, from the appeals endpoint.
struct HiddenPost: Codable, Identifiable, Hashable {
    var id: String { postIdentifier }
    let postIdentifier: String
    /// Nil for a text-only post (#307).
    let imageUrl: String?
    let caption: String
    /// Caption font + background color keys (issue #318); nil on older
    /// responses that predate the fields.
    let captionFont: String?
    let backgroundColor: String?
    let hiddenReason: String
    let hasAppeal: Bool

    enum CodingKeys: String, CodingKey {
        case postIdentifier = "post_identifier"
        case imageUrl = "image_url"
        case caption
        case captionFont = "caption_font"
        case backgroundColor = "background_color"
        case hiddenReason = "hidden_reason"
        case hasAppeal = "has_appeal"
    }
}

/// One of the signed-in user's hidden comments.
struct HiddenComment: Codable, Identifiable, Hashable {
    var id: String { commentIdentifier }
    let commentIdentifier: String
    let body: String
    /// Inline formatting spans over `body` (issue #318); nil = plain text.
    let bodyFormatting: [CommentFormatSpan]?
    let hiddenReason: String
    let hasAppeal: Bool

    enum CodingKeys: String, CodingKey {
        case commentIdentifier = "comment_identifier"
        case body
        case bodyFormatting = "body_formatting"
        case hiddenReason = "hidden_reason"
        case hasAppeal = "has_appeal"
    }
}

/// An appeal the signed-in user has filed, with its current status.
struct MyAppeal: Codable, Identifiable, Hashable {
    var id: String { appealIdentifier }
    let appealIdentifier: String
    let targetType: String?
    let status: String
    let reason: String
    let contentSnapshot: String?
    let resolutionNote: String?

    enum CodingKeys: String, CodingKey {
        case appealIdentifier = "appeal_identifier"
        case targetType = "target_type"
        case status
        case reason
        case contentSnapshot = "content_snapshot"
        case resolutionNote = "resolution_note"
    }
}

// Represents a user from the search results.
struct User: Codable, Identifiable, Hashable {
    var id: String { username }
    let username: String
    let identityIsVerified: Bool
    
    enum CodingKeys: String, CodingKey {
        case username
        case identityIsVerified = "identity_is_verified"
    }
}

// Represents another user's profile
struct ProfileDetailsResponse: Codable, Identifiable, Hashable {
    var id: String { username }
    var username: String
    var postCount: Int
    var followerCount: Int
    var followingCount: Int
    var isFollowing: Bool
    var isBlocked: Bool = false
    var identityIsVerified: Bool = false
    var isAdult: Bool = false

    enum CodingKeys: String, CodingKey {
        case username
        case postCount = "post_count"
        case followerCount = "follower_count"
        case followingCount = "following_count"
        case isFollowing = "is_following"
        case isBlocked = "is_blocked"
        case identityIsVerified = "identity_is_verified"
        case isAdult = "is_adult"
    }
}

// The user session we can save and load
struct UserSession: Codable, Equatable {
    let sessionToken: String
    let username: String
    let userId: String
    let isIdentityVerified: Bool

    init(sessionToken: String, username: String, userId: String, isIdentityVerified: Bool) {
        self.sessionToken = sessionToken
        self.username = username
        self.userId = userId
        self.isIdentityVerified = isIdentityVerified
    }

    // Decodes gracefully from older persisted sessions that lack `userId`.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        sessionToken = try c.decode(String.self, forKey: .sessionToken)
        username = try c.decode(String.self, forKey: .username)
        userId = try c.decodeIfPresent(String.self, forKey: .userId) ?? ""
        isIdentityVerified = try c.decodeIfPresent(Bool.self, forKey: .isIdentityVerified) ?? false
    }
}

// A simple, identifiable struct representing the post in the post detail view
struct PostDisplayData: Identifiable, Equatable {
    let id: String // postIdentifier
    /// Nil for a text-only post (#307).
    let imageURL: String?
    /// The full-resolution original image URL, used as a fallback when the
    /// compressed `imageURL` fails to load (see `Post.originalImageUrl`).
    /// Optional for backward compatibility with responses that predate the field.
    let originalImageURL: String?
    let caption: String
    /// Caption font + background color keys (issue #318); "default" is normal.
    var captionFont: String = "default"
    var backgroundColor: String = "default"
    let likeCount: Int
    let isLiked: Bool // Whether the current user has liked this post
    let authorUsername: String // Added for context
    /// When the post was created. Optional for backward compatibility with
    /// backend responses that predate the field.
    let createdDate: Date?
    /// Whether the current user has an active report against this post, and
    /// their own report reason so the retract dialog can show it pre-populated
    /// (issue #176).
    var isReported: Bool = false
    var reportReason: String? = nil
}

// A struct representing a single comment, for use in the view
struct CommentViewData: Identifiable, Equatable {
    let id: String // commentIdentifier
    let threadId: String // commentThreadIdentifier
    let authorUsername: String
    let body: String
    /// Inline formatting spans over `body` (issue #318); nil = plain text.
    var formatting: [CommentFormatSpan]? = nil
    let likeCount: Int
    let isLiked: Bool // Whether the current user has liked this comment
    let createdDate: Date
    /// Whether the current user has an active report against this comment, and
    /// their own report reason for the pre-populated retract dialog (issue #176).
    var isReported: Bool = false
    var reportReason: String? = nil
}

// A struct representing a full thread, which is just a list of comments
// We make the *first* comment the ID for the thread
struct CommentThreadViewData: Identifiable, Equatable {
    var id: String { comments.first?.threadId ?? UUID().uuidString }
    var comments: [CommentViewData]
}

// MARK: - Text formatting (issue #318)

/// One inline-formatting span over a comment's plain `body` (issue #318).
/// Offsets are UTF-16 code-unit indices (matching the web/Android clients and
/// the backend contract): `0 <= start < end <= body.utf16.count`. The plain
/// `body` text is never modified — formatting is separate metadata, so
/// moderation still classifies plain text.
struct CommentFormatSpan: Codable, Equatable, Hashable {
    let start: Int
    let end: Int
    let bold: Bool
    let italic: Bool
    /// One of "small", "normal", "large", "xlarge".
    let size: String

    init(start: Int, end: Int, bold: Bool = false, italic: Bool = false, size: String = "normal") {
        self.start = start
        self.end = end
        self.bold = bold
        self.italic = italic
        self.size = size
    }

    // Decode leniently: the backend always sends bold/italic/size, but default
    // them so a hand-written or partial payload still decodes.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        start = try c.decode(Int.self, forKey: .start)
        end = try c.decode(Int.self, forKey: .end)
        bold = try c.decodeIfPresent(Bool.self, forKey: .bold) ?? false
        italic = try c.decodeIfPresent(Bool.self, forKey: .italic) ?? false
        size = try c.decodeIfPresent(String.self, forKey: .size) ?? "normal"
    }
}
