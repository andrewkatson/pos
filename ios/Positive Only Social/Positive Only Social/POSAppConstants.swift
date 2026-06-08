//
//  POSAppConstants.swift
//  Positive Only Social
//

import Foundation


//This ensusres interoperabilty with Kotlin
//So we can declare consnants here and expode then to Android.

@objc class POSAppConstants : NSObject {
    
    static let authHeaderField = "Authorization"
    static let badServerResponse = "The server returned an unsuccessful status code: "
    static let baseURL = "https://api.smiling.social/user_index/"
    static let bearer = "Bearer"
    static let decodingError = "Failed to decode the server response: "
    static let encodingError = "Failed to encode the request body: "
    static let get = "GET"
    static let httpHeaderField = "Content-Type"
    static let invalidURL = "The URL provided was invalid."
    static let keychainService = "positive-only-social.Positive-Only-Social"
    static let pathSegmenProfile = "profile"
    static let pathSegmenSearch = "search"
    static let pathSegmentBlock = "block"
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
    static let pathSegmentReset = "reset"
    static let pathSegmentThreads = "threads"
    static let pathSegmentUnblock = "unblock"
    static let pathSegmentUncomment = "uncomment"
    static let pathSegmentUnfollow = "unfollow"
    static let pathSegmentUnfollowed = "followed"
    static let pathSegmentUnlike = "unlike"
    static let pathSegmentUser = "user"
    static let pathSegmentUsers = "users"
    static let pathSegmentVerifyIdentity = "verify-identity"
    static let pathSegmentVerifyReset = "verify-reset"
    static let pathSregmenFeed = "feed"
    static let post = "POST"
    static let requesrFailed = "The network request failed."
    static let requestType = "application/json"
}
