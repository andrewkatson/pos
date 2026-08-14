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
    // MAX_COMMENT_LENGTH / MAX_BIO_LENGTH in backend/user_system/constants.py.
    static let maxCaptionLength = 125
    static let maxCommentLength = 500
    static let maxBioLength = 500
    // Positive interest tags (issues #446/#35), mirroring
    // MAX_FREEFORM_INTEREST_LENGTH / MAX_FREEFORM_INTERESTS in the backend.
    static let maxFreeformInterestLength = 100
    static let maxFreeformInterests = 20
    // How much of a rejected (over-length) term the backend echoes back, so
    // the stub can bound it identically. Well above the length limit, so an
    // elided term still reads as clearly too long.
    static let rejectedTextEchoLimit = 200
    static let baseURL = "https://api.smiling.social/user_index/"
    static let bearer = "Bearer"
    static let decodingError = "Failed to decode the server response: "
    static let emailNotVerifiedError = "email_not_verified"
    // Returned by login/2fa/ when the challenge is expired, used, or invalid.
    // A stable code (like the two above) rather than prose, so the login screen
    // can branch on it without depending on backend wording.
    static let invalidTwoFactorChallengeError = "invalid_two_factor_challenge"
    static let emailNotVerifiedMessage = "Please verify your email address first — check your inbox for the verification link."
    // Error codes login/google/ answers with (issue #10), and the copy each maps
    // to. The backend returns stable codes rather than prose (see
    // backend/user_system/constants.py), so the wording lives here.
    static let googleEmailUnverifiedError = "google_email_unverified"
    static let googleEmailUnverifiedMessage = "Google hasn't verified the email address on that account, so we can't use it to sign you in."
    static let googleEmailAmbiguousError = "google_email_ambiguous"
    static let googleEmailAmbiguousMessage = "More than one account already uses that email address. Please sign in with your password."
    static let invalidGoogleTokenError = "invalid_google_token"
    static let googleSignInUnavailableError = "google_sign_in_unavailable"
    static let googleSignInUnavailableMessage = "Google sign-in isn't available right now. Please sign in with your password."
    static let googleSignInFailedMessage = "Google sign-in failed. Please try again."
    static let encodingError = "Failed to encode the request body: "
    static let emptyString = ""
    static let get = "GET"
    static let httpHeaderField = "Content-Type"
    static let invalidURL = "The URL provided was invalid."
    static let keychainService = "positive-only-social.Positive-Only-Social"
    /// The tab index of the signed-in user's own profile (issue #347). Tapping
    /// your own username anywhere in the app selects this tab instead of
    /// pushing a second copy of your profile.
    static let profileTabIndex = 0
    static let pathSegmenProfile = "profile"
    static let pathSegmenSearch = "search"
    static let pathSegmentAppeals = "appeals"
    static let pathSegmentBio = "bio"
    static let pathSegmentBlock = "block"
    static let pathSegmentBlocked = "blocked"
    // POST /password/change/ — change the signed-in account's password (#197).
    static let pathSegmentChange = "change"
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
    // POST devices/register/ registers this device's APNs token (issue #342).
    static let pathSegmentDevices = "devices"
    static let pathSegmentDetails = "details"
    static let pathSegmentFollow = "follow"
    static let pathSegmentFollowed = "followed"
    // Relationship-category endpoint and query key (issue #392).
    static let pathSegmentCategory = "category"
    static let queryKeyCategory = "category"
    // POST login/google/ — exchange a Google ID token for a session (issue #10).
    static let pathSegmentGoogle = "google"
    static let pathSegmentFollowers = "followers"
    static let pathSegmentFollowing = "following"
    static let pathSegmentLike = "like"
    // GET .../likes/<batch>/ — who liked one of your own posts/comments (#478).
    static let pathSegmentLikes = "likes"
    static let pathSegmentLogin = "login"
    static let pathSegmentLogout = "logout"
    // GET /me/ — the signed-in account's own username + email (#194/#197).
    static let pathSegmentMe = "me"
    static let pathSegmentNotification = "notification"
    static let pathSegmentNotifications = "notifications"
    // GET/POST notifications/preferences/ — the Settings push toggles (#342/#343).
    static let pathSegmentPreferences = "preferences"
    static let pathSegmentPassword = "password"
    // Profile photo endpoints (issue #7): POST profile/photo/ sets the photo,
    // POST profile/photo/remove/ clears it. `pathSegmenProfile` supplies the
    // shared leading "profile" segment.
    static let pathSegmentPhoto = "photo"
    static let pathSegmentRemove = "remove"
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
    // Save / unsave a post to the viewer's collection (issue #193/#412).
    static let pathSegmentSave = "save"
    static let pathSegmentStatus = "status"
    static let pathSegmentTags = "tags"
    static let pathSegmentThreads = "threads"
    static let pathSegmentUnblock = "unblock"
    static let pathSegmentUploadUrl = "upload-url"
    static let pathSegmentUncomment = "uncomment"
    static let pathSegmentUnfollow = "unfollow"
    static let pathSegmentUnfollowed = "followed"
    static let pathSegmentUnlike = "unlike"
    static let pathSegmentUnsave = "unsave"
    static let pathSegmentUser = "user"
    static let pathSegmentUsers = "users"
    static let pathSegmentVerifyEmail = "verify-email"
    static let pathSegmentVerifyIdentity = "verify-identity"
    static let pathSegmentVerifyReset = "verify-reset"
    // Positive interest tags (issues #446/#35).
    static let pathSegmentInterests = "interests"
    static let pathSegmentOptions = "options"
    static let pathSegmentSet = "set"
    static let pathSregmenFeed = "feed"
    static let post = "POST"
    static let requesrFailed = "The network request failed."
    static let requestType = "application/json"
    /// One section of the terms of service (issue #493). Nested so the file
    /// adds no new top-level name — it is compiled into the test targets too.
    struct TermsSection: Identifiable {
        let heading: String
        let body: String
        var id: String { heading }
    }

    /// Shown above the terms so a reader can tell which version they accepted.
    static let termsOfServiceLastUpdated = "August 13, 2026"

    /// The terms of service, mirroring `website/src/termsOfService.ts` and
    /// `Constants.TERMS_OF_SERVICE_SECTIONS` on Android — the same duplication
    /// the privacy policy below already lives with. The canonical public copy
    /// is https://smiling.social/terms-of-service.
    static let termsOfServiceSections: [TermsSection] = [
        TermsSection(
            heading: "Agreeing to these terms",
            body: "Good Vibes Only is a positivity-only social network. By creating an account, signing in — including with Google — or otherwise using the website or the mobile apps, you agree to these terms. If you do not agree to them, please do not use the service."
        ),
        TermsSection(
            heading: "Who can use Good Vibes Only",
            body: "You must be at least 16 years old. Accounts belonging to 16- and 17-year-olds are kept in a separate visibility band from adult accounts, and the two never see each other’s posts, comments, or profiles. Give us accurate information, keep one account per person, and keep your password and any second factor to yourself — anything done from your account is treated as done by you. Tell us if you think someone else has got in."
        ),
        TermsSection(
            heading: "What you may post",
            body: "Every post, comment, username, bio, and photo has to be positive or neutral: no swearing, nudity, sexually suggestive material, gore, hate speech, harassment, bullying, or misinformation, and no photos of babies, children, or anyone under 18. Content that starts sad but ends on a happy or hopeful note is welcome. You must hold the rights to whatever you upload, and you may not impersonate anyone, spam, run bots, or try to break, overload, or reverse-engineer the service."
        ),
        TermsSection(
            heading: "How we moderate",
            body: "Submissions are checked automatically before they go up, and other users can report content and accounts. Anything that fails the guidelines is refused or hidden, and an account that breaks them can be warned, suspended for a time, banned permanently, or have its content hidden from other people without being told, where telling the holder would only help them evade enforcement. You can ask us to look again at anything of yours we hid from the “Hidden Content & Appeals” screen. Moderation is automated and imperfect in both directions, and the final call on what stays up is ours."
        ),
        TermsSection(
            heading: "Your content stays yours",
            body: "You keep ownership of everything you post. You give us permission to store, reproduce, and display it for the purpose of running the service and showing it to the audience you chose. That permission ends when the content is deleted, apart from copies still sitting in backups or anything we are required to keep by law."
        ),
        TermsSection(
            heading: "Signing in with Google",
            body: "If you sign in with Google, we receive the Google account’s verified email address and a permanent account identifier, and use them only to create or find your Good Vibes Only account. We never see your Google password and we ask for nothing else from your Google account. Your use of Google’s own services remains governed by Google’s terms and privacy policy; deleting your Good Vibes Only account ends the connection on our side."
        ),
        TermsSection(
            heading: "Ending your account",
            body: "You can delete your account at any time from Settings, or from the account & data deletion page on the website without opening an app. Deleting removes your posts and their images, comments, likes, saved posts, follows, blocks, appeals, and sessions, and cannot be undone. We may suspend or terminate an account that breaks these terms or the content guidelines."
        ),
        TermsSection(
            heading: "The service is provided as is",
            body: "Good Vibes Only is offered free of charge and as is, with no warranty of any kind. We may change, suspend, or discontinue any part of it, and to the fullest extent the law allows we are not liable for lost content or for any indirect or consequential loss. Nothing here takes away rights you have that cannot be given up under the law where you live."
        ),
        TermsSection(
            heading: "Changes to these terms",
            body: "These terms will change as the service does. The date above marks the current version, and continuing to use Good Vibes Only after an update means you accept the updated terms."
        ),
        TermsSection(
            heading: "Contact",
            body: "Questions about these terms, or anything else, can go to katsonsoftware@gmail.com."
        ),
    ]

    static let privacyPolicyText = "We collect your username, email address, and password for authentication; your password is stored as a salted hash, never in plain text. We do not store your date of birth itself, only whether you are an adult and whether your identity has been verified, derived from it at signup. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment, and the IP address of your login sessions and known devices so we can alert you to logins from a new device."
}
