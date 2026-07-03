//
//  ErrorHelpers.swift
//  Positive Only Social
//

import Foundation

extension Notification.Name {
    /// Posted by the API layer when an authenticated request is rejected
    /// because the account has an active outright ban. The backend revokes
    /// the session server-side, so the app must drop its session too.
    static let accountBanned = Notification.Name("accountBanned")

    /// Posted after a post is successfully deleted, with the deleted post's
    /// identifier as the notification `object`. The Home grid listens for this
    /// so it can drop the post from its cached list — otherwise the deleted
    /// post's now-missing image lingers as an empty grey tile until the user
    /// logs out. See issue #256.
    static let postDeleted = Notification.Name("postDeleted")
}

extension Error {
    /// True when the backend rejected the request because the account has an
    /// active outright ban (the `account_banned` error code).
    var isAccountBanned: Bool {
        guard let apiError = self as? APIError else { return false }
        switch apiError {
        case .serverError(_, let message):
            return message == GVOAppConstants.accountBannedError
        case .requestFailed(let underlying):
            return underlying.isAccountBanned
        default:
            return false
        }
    }
}

extension APIError {
    /// A friendly, user-facing message suitable for an alert. Backend
    /// validation errors (`serverError`) already carry human-readable copy from
    /// the API's `error` field, so they pass through unchanged; every other case
    /// — raw status codes, transport failures, encoding/decoding problems — is
    /// mapped to plain language instead of leaking a status code or a low-level
    /// `localizedDescription` to the user.
    var userFacingMessage: String {
        switch self {
        case .serverError(_, let message):
            return message
        case .badServerResponse(let statusCode):
            return APIError.userFacingMessage(forStatusCode: statusCode)
        case .requestFailed(let underlying):
            return underlying.userFacingMessage
        case .invalidURL, .encodingError, .decodingError:
            return "Something went wrong. Please try again."
        }
    }

    /// Maps an HTTP status code to user-facing copy.
    static func userFacingMessage(forStatusCode statusCode: Int) -> String {
        switch statusCode {
        case 404:
            return "We couldn't find what you were looking for. It may have been removed."
        case 408:
            return "The request timed out. Please try again."
        case 429:
            return "You're doing that too often. Please wait a moment and try again."
        case 502, 503, 504:
            return "The server is taking too long to respond. Please try again in a moment."
        case 500...599:
            return "The server ran into a problem. Please try again in a moment."
        default:
            return "Something went wrong. Please try again."
        }
    }
}

extension Error {
    /// A friendly, user-facing description of this error suitable for showing in
    /// an alert. Delegates to `APIError.userFacingMessage` for API errors, maps
    /// URL-loading failures (offline, timeout, unreachable host) to plain
    /// language, and otherwise falls back to a generic message — so a raw
    /// `localizedDescription` is never shown to the user.
    var userFacingMessage: String {
        if let apiError = self as? APIError {
            return apiError.userFacingMessage
        }
        let nsError = self as NSError
        if nsError.domain == NSURLErrorDomain {
            switch nsError.code {
            case NSURLErrorTimedOut:
                return "The request timed out. Please check your connection and try again."
            case NSURLErrorNotConnectedToInternet, NSURLErrorNetworkConnectionLost, NSURLErrorDataNotAllowed:
                return "You appear to be offline. Please check your connection and try again."
            case NSURLErrorCannotFindHost, NSURLErrorCannotConnectToHost, NSURLErrorDNSLookupFailed:
                return "We couldn't reach the server. Please try again in a moment."
            default:
                return "Something went wrong. Please try again."
            }
        }
        return "Something went wrong. Please try again."
    }
}

extension Error {
    /// True when this error represents a cancelled task or network request
    /// rather than a real failure. SwiftUI routinely cancels the `.refreshable`
    /// task when a state change re-renders the view mid-refresh, which surfaces
    /// as `CancellationError` or `URLError.cancelled` — neither should be shown
    /// to the user as an error.
    var isCancellation: Bool {
        if self is CancellationError { return true }
        if let apiError = self as? APIError, case .requestFailed(let underlying) = apiError {
            return underlying.isCancellation
        }
        let nsError = self as NSError
        return nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled
    }
}

/// Maps backend raw field tokens to friendly display names.
private let errorTokenMap: [String: String] = [
    "USERNAME": "Username",
    "EMAIL": "Email",
    "PASSWORD": "Password",
    "USERNAME_OR_EMAIL": "Username or email",
    "USER_ID": "User ID",
    "IMAGE_URL": "Image URL",
    "COMMENT": "Comment",
    "RESET_TOKEN": "Reset token",
    "VERIFICATION_TOKEN": "Verification token",
    "IP": "IP address",
    "SESSION_MANAGEMENT_TOKEN": "Session token",
    "SERIES_IDENTIFIER": "Series identifier",
    "LOGIN_COOKIE_TOKEN": "Cookie token",
    "REMEMBER_ME": "Remember me flag",
    "CAPTION": "Caption",
    "POST_IDENTIFIER": "Post identifier",
    "REASON": "Reason",
    "COMMENT_TEXT": "Comment text",
    "COMMENT_THREAD_IDENTIFIER": "Comment thread identifier",
    "COMMENT_IDENTIFIER": "Comment identifier",
    "USERNAME_FRAGMENT": "Username fragment",
    "DATE_OF_BIRTH": "Date of birth",
    "TARGET_TYPE": "Target type",
    "TARGET_IDENTIFIER": "Target identifier"
]

/// Sanitizes backend raw token error messages into human-legible sentences.
func sanitizeErrorMessage(_ message: String) -> String {
    let invalidFieldsPrefix = "Invalid fields"
    let invalidPrefix = "Invalid "
    
    let suffix: String
    let isInvalidFields: Bool
    
    if message.hasPrefix(invalidFieldsPrefix) {
        suffix = String(message.dropFirst(invalidFieldsPrefix.count))
        isInvalidFields = true
    } else if message.hasPrefix(invalidPrefix) {
        suffix = String(message.dropFirst(invalidPrefix.count))
        isInvalidFields = false
        let cleaned = suffix.replacingOccurrences(of: "[\\[\\]'\"]", with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if cleaned.contains(" ") {
            return message
        }
    } else {
        return message
    }
    
    let range = NSRange(location: 0, length: suffix.utf16.count)
    guard let regex = try? NSRegularExpression(pattern: "[a-zA-Z0-9_]+") else {
        return message
    }
    
    let matches = regex.matches(in: suffix, options: [], range: range)
    var tokens: [String] = []
    for match in matches {
        if let tokenRange = Range(match.range, in: suffix) {
            tokens.append(String(suffix[tokenRange]))
        }
    }
    
    if tokens.isEmpty {
        return isInvalidFields ? "Some fields are incorrect" : message
    }

    var friendlyNames: [String] = []
    for token in tokens {
        let upperToken = token.uppercased()
        if let name = errorTokenMap[upperToken] {
            if !friendlyNames.contains(name) {
                friendlyNames.append(name)
            }
        } else {
            let parts = token.split(separator: "_")
            let humanized = parts.enumerated().map { (index, part) -> String in
                let partStr = String(part).lowercased()
                if index == 0 {
                    return partStr.prefix(1).uppercased() + partStr.dropFirst()
                } else {
                    return partStr
                }
            }.joined(separator: " ")
            if !friendlyNames.contains(humanized) && !humanized.isEmpty {
                friendlyNames.append(humanized)
            }
        }
    }
    
    if friendlyNames.isEmpty {
        return isInvalidFields ? "Some fields are incorrect" : message
    }
    
    if friendlyNames.count == 1 {
        return "\(friendlyNames[0]) is incorrect"
    }
    
    if friendlyNames.count == 2 {
        return "\(friendlyNames[0]) and \(friendlyNames[1]) are incorrect"
    }
    
    var list = friendlyNames
    let last = list.removeLast()
    return "\(list.joined(separator: ", ")), and \(last) are incorrect"
}

