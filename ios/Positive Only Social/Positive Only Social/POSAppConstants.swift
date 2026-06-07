//
//  POSAppConstants.swift
//  Positive Only Social
//

import Foundation


//This ensusres interoperabilty with Kotlin
//So we can declare consnants here and expode then to Android.

@objc class POSAppConstants : NSObject {
    
    //Add categoy and comment below, to keep it sorted.
    
    //ErrorDescription
    static let keychainService = "positive-only-social.Positive-Only-Social"
    static let invalidURL = "The URL provided was invalid."
    static let badServerResponse = "The server returned an unsuccessful status code: "
    static let requesrFailed = "The network request failed."
    static let decodingError = "Failed to decode the server response: "
    static let encodingError = "Failed to encode the request body: "
    
    //HTTPMethods
    static let get = "GET"
    static let post = "POST"
    
    //Requests
    static let baseURL = "https://api.smiling.social/user_index/"
    static let bearer = "Bearer"
    static let requestType = "application/json"
    static let httpHeaderField = "Content-Type"
    static let authHeaderField = "Authorization"
    static let pathSegmentRegister = "register"
    static let pathSegmentLogin = "login"
    static let pathSegmentRemember = "remember"
    static let pathSegmentPassword = "password"
    static let pathSegmentReset = "reset"
    static let pathSegmentRequestReset = "request-reset"
   static let  pathSegmentVerifyIdentity = "verify-identity"
    static let pathSegmentVerifyReset = "verify-reset"
    static let pathSegmentLogout = "logout"
    static let pathSegmentDelete = "delete"
    static let pathSegmentUsers = "users"
    static let pathSegmentUser = "user"
    static let pathSegmentFollow = "follow"
    static let pathSegmentUnfollow = "unfollow"
    static let pathSegmentUnfollowed = "followed"
    static let pathSegmentUnblock = "unblock"
    static let pathSegmentBlock = "block"
    static let pathSegmentPost = "post"
    static let pathSegmentCreate = "create"
    static let pathSegmentReport = "report"
    static let pathSegmentLike = "like"
    static let pathSegmentUnlike = "unlike"
    static let pathSegmentComment = "comment"
    static let pathSegmentUncomment = "uncomment"
    static let pathSegmentThreads = "threads"
    static let pathSegmenSearch = "search"
    static let pathSegmentNotifications = "notifications"
    static let pathSegmentNotification = "notification"
    static let pathSegmenProfile = "profile"
}
