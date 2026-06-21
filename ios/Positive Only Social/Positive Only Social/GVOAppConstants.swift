//
//  GVOAppConstants.swift
//  Positive Only Social
//

import Foundation


//This ensusres interoperabilty with Kotlin
//So we can declare consnants here and expode then to Android.

import Foundation

@objc class GVOAppConstants : NSObject {
    static let accountBannedError = String(cString: GVO_accountBannedError)
    static let accountSuspendedMessage = String(cString: GVO_accountSuspendedMessage)
    static let authHeaderField = String(cString: GVO_authHeaderField)
    static let badServerResponse = String(cString: GVO_badServerResponse)
    static let maxCaptionLength = Int(GVO_maxCaptionLength)
    static let maxCommentLength = Int(GVO_maxCommentLength)
    static let baseURL = String(cString: GVO_baseURL)
    static let bearer = String(cString: GVO_bearer)
    static let decodingError = String(cString: GVO_decodingError)
    static let encodingError = String(cString: GVO_encodingError)
    static let get = String(cString: GVO_get)
    static let httpHeaderField = String(cString: GVO_httpHeaderField)
    static let invalidURL = String(cString: GVO_invalidURL)
    static let keychainService = String(cString: GVO_keychainService)
    static let pathSegmenProfile = String(cString: GVO_pathSegmenProfile)
    static let pathSegmenSearch = String(cString: GVO_pathSegmenSearch)
    static let pathSegmentBlock = String(cString: GVO_pathSegmentBlock)
    static let pathSegmentComments = String(cString: GVO_pathSegmentComments)
    static let pathSegmentCreate = String(cString: GVO_pathSegmentCreate)
    static let pathSegmentDelete = String(cString: GVO_pathSegmentDelete)
    static let pathSegmentDetails = String(cString: GVO_pathSegmentDetails)
    static let pathSegmentFollow = String(cString: GVO_pathSegmentFollow)
    static let pathSegmentFollowed = String(cString: GVO_pathSegmentFollowed)
    static let pathSegmentLike = String(cString: GVO_pathSegmentLike)
    static let pathSegmentLogin = String(cString: GVO_pathSegmentLogin)
    static let pathSegmentLogout = String(cString: GVO_pathSegmentLogout)
    static let pathSegmentNotification = String(cString: GVO_pathSegmentNotification)
    static let pathSegmentNotifications = String(cString: GVO_pathSegmentNotifications)
    static let pathSegmentPassword = String(cString: GVO_pathSegmentPassword)
    static let pathSegmentPost = String(cString: GVO_pathSegmentPost)
    static let pathSegmentPosts = String(cString: GVO_pathSegmentPosts)
    static let pathSegmentRegister = String(cString: GVO_pathSegmentRegister)
    static let pathSegmentRemember = String(cString: GVO_pathSegmentRemember)
    static let pathSegmentReply = String(cString: GVO_pathSegmentReply)
    static let pathSegmentReport = String(cString: GVO_pathSegmentReport)
    static let pathSegmentRequestReset = String(cString: GVO_pathSegmentRequestReset)
    static let pathSegmentReset = String(cString: GVO_pathSegmentReset)
    static let pathSegmentThreads = String(cString: GVO_pathSegmentThreads)
    static let pathSegmentUnblock = String(cString: GVO_pathSegmentUnblock)
    static let pathSegmentUncomment = String(cString: GVO_pathSegmentUncomment)
    static let pathSegmentUnfollow = String(cString: GVO_pathSegmentUnfollow)
    static let pathSegmentUnfollowed = String(cString: GVO_pathSegmentUnfollowed)
    static let pathSegmentUnlike = String(cString: GVO_pathSegmentUnlike)
    static let pathSegmentUser = String(cString: GVO_pathSegmentUser)
    static let pathSegmentUsers = String(cString: GVO_pathSegmentUsers)
    static let pathSegmentVerifyIdentity = String(cString: GVO_pathSegmentVerifyIdentity)
    static let pathSegmentVerifyReset = String(cString: GVO_pathSegmentVerifyReset)
    static let pathSregmenFeed = String(cString: GVO_pathSregmenFeed)
    static let post = String(cString: GVO_post)
    static let requesrFailed = String(cString: GVO_requesrFailed)
    static let requestType = String(cString: GVO_requestType)
}
