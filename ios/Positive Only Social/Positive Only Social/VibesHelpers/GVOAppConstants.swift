//
//  GVOAppConstants.swift
//  Positive Only Social
//

import Foundation


//This ensusres interoperabilty with Kotlin
//So we can declare consnants here and expode then to Android.

@objc class GVOAppConstants : NSObject {
    
    static let accountBannedError = "account_banned"
    static let accountSuspendedMessage = "Your account has been suspended for violating our community guidelines."
    static let authHeaderField = "Authorization"
    static let badServerResponse = "The server returned an unsuccessful status code: "
    // Maximum lengths for user-authored text, mirroring MAX_CAPTION_LENGTH /
    // MAX_COMMENT_LENGTH in backend/user_system/constants.py.
    static let maxCaptionLength = 125
    static let maxCommentLength = 500
    static let baseURL = "https://api.smiling.social/user_index/"
    static let bearer = "Bearer"
    static let decodingError = "Failed to decode the server response: "
    static let emailNotVerifiedError = "email_not_verified"
    // Returned by login/2fa/ when the challenge is expired, used, or invalid.
    // A stable code (like the two above) rather than prose, so the login screen
    // can branch on it without depending on backend wording.
    static let invalidTwoFactorChallengeError = "invalid_two_factor_challenge"
    static let emailNotVerifiedMessage = "Please verify your email address first — check your inbox for the verification link."
    static let encodingError = "Failed to encode the request body: "
    static let emptyString = ""
    static let get = "GET"
    static let httpHeaderField = "Content-Type"
    static let invalidURL = "The URL provided was invalid."
    static let keychainService = "positive-only-social.Positive-Only-Social"
    static let pathSegmenProfile = "profile"
    static let pathSegmenSearch = "search"
    static let pathSegmentAppeals = "appeals"
    static let pathSegmentBlock = "block"
    static let pathSegmentBlocked = "blocked"
    static let pathSegmentConfirm = "confirm"
    static let pathSegmentDisable = "disable"
    static let pathSegmentSetup = "setup"
    static let pathSegmentTotp = "totp"
    static let pathSegmentTwoFactor = "2fa"
    static let pathSegmentHidden = "hidden"
    static let pathSegmentMine = "mine"
    static let pathSegmentSubmit = "submit"
    // Posting a comment hits the singular `comment/` route; the plural
    // `comments/` route is only the GET that fetches a batch of threads.
    static let pathSegmentComment = "comment"
    static let pathSegmentComments = "comments"
    static let pathSegmentCreate = "create"
    static let pathSegmentDelete = "delete"
    static let pathSegmentDetails = "details"
    static let pathSegmentFollow = "follow"
    static let pathSegmentFollowed = "followed"
    static let pathSegmentLike = "like"
    static let pathSegmentLogin = "login"
    static let pathSegmentLogout = "logout"
    static let pathSegmentNotification = "notification"
    static let pathSegmentNotifications = "notifications"
    static let pathSegmentPassword = "password"
    static let pathSegmentPost = "post"
    static let pathSegmentPosts = "posts"
    static let pathSegmentRegister = "register"
    static let pathSegmentRemember = "remember"
    static let pathSegmentReply = "reply"
    static let pathSegmentReport = "report"
    static let pathSegmentRequestReset = "request-reset"
    static let pathSegmentResendVerificationEmail = "resend-verification-email"
    static let pathSegmentReset = "reset"
    static let pathSegmentRetract = "retract"
    static let pathSegmentStatus = "status"
    static let pathSegmentThreads = "threads"
    static let pathSegmentUnblock = "unblock"
    static let pathSegmentUploadUrl = "upload-url"
    static let pathSegmentUncomment = "uncomment"
    static let pathSegmentUnfollow = "unfollow"
    static let pathSegmentUnfollowed = "followed"
    static let pathSegmentUnlike = "unlike"
    static let pathSegmentUser = "user"
    static let pathSegmentUsers = "users"
    static let pathSegmentVerifyEmail = "verify-email"
    static let pathSegmentVerifyIdentity = "verify-identity"
    static let pathSegmentVerifyReset = "verify-reset"
    static let pathSregmenFeed = "feed"
    static let post = "POST"
    static let requesrFailed = "The network request failed."
    static let requestType = "application/json"
    static let privacyPolicyText = "We collect your username, email address, and password for authentication; your password is stored as a salted hash, never in plain text. We do not store your date of birth itself, only whether you are an adult and whether your identity has been verified, derived from it at signup. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment, and the IP address of your login sessions and known devices so we can alert you to logins from a new device."
}
