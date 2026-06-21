package com.example.positiveonlysocial.data.constants


import kotlinx.cinterop.toKString
import gvo_constants.* // Target binding package

object Constants {
     //TODO (@eBlender) INTEGRATE THIS ONCE ABLE TO COMPILE THIS on PC//
    val isUnitTesting = false
    // Error code the backend returns when the account has an active outright ban.
    val accountBanned: String = GVO_accountBanned.toKString()
    val accountSuspendedMessage: String = GVO_accountSuspendedMessage.toKString()

    // Error code the backend returns when the account has an active outright ban.
    const val ACCOUNT_BANNED = "account_banned"
    const val ACCOUNT_SUSPENDED_MESSAGE =
        "Your account has been suspended for violating our community guidelines."
    //TODO (@eBlender) INTEGRATE THIS ONCE ABLE TO COMPILE THIS on PC//
    //
    //Exposed from C to KT (e.g., @C.GVO_accountBannedError.toKString())
    //Readme.md for more info//
    val accountBannedError: String = GVO_accountBannedError.toKString()
    val accountSuspendedMessage: String = GVO_accountSuspendedMessage.toKString()
    //TODO (@eBlender) INTEGRATE THIS ONCE ABLE TO COMPILE THIS on PC//
    val authHeaderField: String = GVO_authHeaderField.toKString()
    val badServerResponse: String = GVO_badServerResponse.toKString()
    val maxCaptionLength: Int = GVO_maxCaptionLength
    val maxCommentLength: Int = GVO_maxCommentLength
    val baseURL: String = GVO_baseURL.toKString()
    val bearer: String = GVO_bearer.toKString()
    val decodingError: String = GVO_decodingError.toKString()
    val encodingError: String = GVO_encodingError.toKString()
    val get: String = GVO_get.toKString()
    val httpHeaderField: String = GVO_httpHeaderField.toKString()
    val invalidURL: String = GVO_invalidURL.toKString()
    val keychainService: String = GVO_keychainService.toKString()
    val pathSegmenProfile: String = GVO_pathSegmenProfile.toKString()
    val pathSegmenSearch: String = GVO_pathSegmenSearch.toKString()
    val pathSegmentBlock: String = GVO_pathSegmentBlock.toKString()
    val pathSegmentComments: String = GVO_pathSegmentComments.toKString()
    val pathSegmentCreate: String = GVO_pathSegmentCreate.toKString()
    val pathSegmentDelete: String = GVO_pathSegmentDelete.toKString()
    val pathSegmentDetails: String = GVO_pathSegmentDetails.toKString()
    val pathSegmentFollow: String = GVO_pathSegmentFollow.toKString()
    val pathSegmentFollowed: String = GVO_pathSegmentFollowed.toKString()
    val pathSegmentLike: String = GVO_pathSegmentLike.toKString()
    val pathSegmentLogin: String = GVO_pathSegmentLogin.toKString()
    val pathSegmentLogout: String = GVO_pathSegmentLogout.toKString()
    val pathSegmentNotification: String = GVO_pathSegmentNotification.toKString()
    val pathSegmentNotifications: String = GVO_pathSegmentNotifications.toKString()
    val pathSegmentPassword: String = GVO_pathSegmentPassword.toKString()
    val pathSegmentPost: String = GVO_pathSegmentPost.toKString()
    val pathSegmentPosts: String = GVO_pathSegmentPosts.toKString()
    val pathSegmentRegister: String = GVO_pathSegmentRegister.toKString()
    val pathSegmentRemember: String = GVO_pathSegmentRemember.toKString()
    val pathSegmentReply: String = GVO_pathSegmentReply.toKString()
    val pathSegmentReport: String = GVO_pathSegmentReport.toKString()
    val pathSegmentRequestReset: String = GVO_pathSegmentRequestReset.toKString()
    val pathSegmentReset: String = GVO_pathSegmentReset.toKString()
    val pathSegmentThreads: String = GVO_pathSegmentThreads.toKString()
    val pathSegmentUnblock: String = GVO_pathSegmentUnblock.toKString()
    val pathSegmentUncomment: String = GVO_pathSegmentUncomment.toKString()
    val pathSegmentUnfollow: String = GVO_pathSegmentUnfollow.toKString()
    val pathSegmentUnfollowed: String = GVO_pathSegmentUnfollowed.toKString()
    val pathSegmentUnlike: String = GVO_pathSegmentUnlike.toKString()
    val pathSegmentUser: String = GVO_pathSegmentUser.toKString()
    val pathSegmentUsers: String = GVO_pathSegmentUsers.toKString()
    val pathSegmentVerifyIdentity: String = GVO_pathSegmentVerifyIdentity.toKString()
    val pathSegmentVerifyReset: String = GVO_pathSegmentVerifyReset.toKString()
    val pathSregmenFeed: String = GVO_pathSregmenFeed.toKString()
    val post: String = GVO_post.toKString()
    val requesrFailed: String = GVO_requesrFailed.toKString()
    val requestType: String = GVO_requestType.toKString()
}