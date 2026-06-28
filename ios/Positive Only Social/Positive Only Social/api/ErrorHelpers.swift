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
