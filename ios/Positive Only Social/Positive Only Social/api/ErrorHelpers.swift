//
//  ErrorHelpers.swift
//  Positive Only Social
//

import Foundation

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
