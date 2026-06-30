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
