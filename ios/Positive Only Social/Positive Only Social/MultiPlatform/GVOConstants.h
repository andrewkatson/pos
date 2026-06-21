//
//  GVOConstants.h
//  Positive Only Social
//
//  Created by KS Software on 20/06/26.
// Expose contanst here for iOS and Android.

#ifndef GVO_APP_CONSTANTS_H
#define GVO_APP_CONSTANTS_H

// --- Push and Ignore Unused Variable Warnings ---
#if defined(__GNUC__) || defined(__clang__)
    #pragma GCC diagnostic push
    #pragma GCC diagnostic ignored "-Wunused-variable"
    #pragma GCC diagnostic ignored "-Wunused-const-variable"
#elif defined(_MSC_VER)
    #pragma warning(push)
    #pragma warning(disable : 4101) // Unused local variable
    #pragma warning(disable : 4505) // Unused local function/variable
#endif

static const char* const GVO_accountBannedError = "account_banned";
static const char* const GVO_accountSuspendedMessage = "Your account has been suspended for violating our community guidelines.";
static const char* const GVO_authHeaderField = "Authorization";
static const char* const GVO_badServerResponse = "The server returned an unsuccessful status code: ";

// Maximum lengths for user-authored text
static const int GVO_maxCaptionLength = 125;
static const int GVO_maxCommentLength = 500;

static const char* const GVO_baseURL = "https://api.smiling.social/user_index/";
static const char* const GVO_bearer = "Bearer";
static const char* const GVO_decodingError = "Failed to decode the server response: ";
static const char* const GVO_encodingError = "Failed to encode the request body: ";
static const char* const GVO_get = "GET";
static const char* const GVO_httpHeaderField = "Content-Type";
static const char* const GVO_invalidURL = "The URL provided was invalid.";
static const char* const GVO_keychainService = "positive-only-social.Positive-Only-Social";
static const char* const GVO_pathSegmenProfile = "profile";
static const char* const GVO_pathSegmenSearch = "search";
static const char* const GVO_pathSegmentBlock = "block";
static const char* const GVO_pathSegmentComments = "comments";
static const char* const GVO_pathSegmentCreate = "create";
static const char* const GVO_pathSegmentDelete = "delete";
static const char* const GVO_pathSegmentDetails = "details";
static const char* const GVO_pathSegmentFollow = "follow";
static const char* const GVO_pathSegmentFollowed = "followed";
static const char* const GVO_pathSegmentLike = "like";
static const char* const GVO_pathSegmentLogin = "login";
static const char* const GVO_pathSegmentLogout = "logout";
static const char* const GVO_pathSegmentNotification = "notification";
static const char* const GVO_pathSegmentNotifications = "notifications";
static const char* const GVO_pathSegmentPassword = "password";
static const char* const GVO_pathSegmentPost = "post";
static const char* const GVO_pathSegmentPosts = "posts";
static const char* const GVO_pathSegmentRegister = "register";
static const char* const GVO_pathSegmentRemember = "remember";
static const char* const GVO_pathSegmentReply = "reply";
static const char* const GVO_pathSegmentReport = "report";
static const char* const GVO_pathSegmentRequestReset = "request-reset";
static const char* const GVO_pathSegmentReset = "reset";
static const char* const GVO_pathSegmentThreads = "threads";
static const char* const GVO_pathSegmentUnblock = "unblock";
static const char* const GVO_pathSegmentUncomment = "uncomment";
static const char* const GVO_pathSegmentUnfollow = "unfollow";
static const char* const GVO_pathSegmentUnfollowed = "unfollowed";
static const char* const GVO_pathSegmentUnlike = "unlike";
static const char* const GVO_pathSegmentUser = "user";
static const char* const GVO_pathSegmentUsers = "users";
static const char* const GVO_pathSegmentVerifyIdentity = "verify-identity";
static const char* const GVO_pathSegmentVerifyReset = "verify-reset";
static const char* const GVO_pathSregmenFeed = "feed";
static const char* const GVO_post = "POST";
static const char* const GVO_requesrFailed = "The network request failed.";
static const char* const GVO_requestType = "application/json";

// --- Pop/Restore Warnings at the end of the file ---
#if defined(__GNUC__) || defined(__clang__)
    #pragma GCC diagnostic pop
#elif defined(_MSC_VER)
    #pragma warning(pop)
#endif

#endif
