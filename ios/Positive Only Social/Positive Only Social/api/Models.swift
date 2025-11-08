//
//  Models.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import Foundation

// MARK: - API Response Models

/// The outermost JSON object, which contains the response list as a STRING.
struct APIWrapperResponse: Codable {
    let responseList: String

    enum CodingKeys: String, CodingKey {
        case responseList = "response_list"
    }
}

/// The structure inside the `responseList` string, mirroring Django's serializer output.
struct DjangoLoginResponseObject: Codable {
    let model: String
    let pk: Int?
    let fields: LoginResponseFields
}

/// The actual data fields you care about.
/// Properties are optional since "remember me" tokens may not be present.
struct LoginResponseFields: Codable {
    // This property can now be returned by both login methods
    let sessionManagementToken: String
    let seriesIdentifier: String?
    let loginCookieToken: String?

    enum CodingKeys: String, CodingKey {
        case sessionManagementToken = "session_management_token"
        case seriesIdentifier = "series_identifier"
        case loginCookieToken = "login_cookie_token"
    }
}

// Represents a single post in the user's grid.
// Conforms to Identifiable and Hashable to be used in grids and lists.
struct Post: Codable, Identifiable, Hashable {
    var id: String { postIdentifier }
    let postIdentifier: String
    let imageUrl: String
    let caption: String
    let authorUsername: String

    enum CodingKeys: String, CodingKey {
        case postIdentifier = "post_identifier"
        case imageUrl = "image_url"
        case caption = "caption"
        case authorUsername = "authorUsername"
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

    enum CodingKeys: String, CodingKey {
        case username
        case postCount = "post_count"
        case followerCount = "follower_count"
        case followingCount = "following_count"
        case isFollowing = "is_following"
    }
}

// The user session we can save and load
struct UserSession: Codable, Equatable {
    let sessionToken: String
    let username: String
    let isIdentityVerified: Bool
}
