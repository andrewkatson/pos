//
//  Positive_Only_SocialTests_ErrorHelpers.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// Tests for `Error.isCancellation`, which gates user-facing alerts in the
/// view models: cancellations must be detected in every shape they arrive in
/// (Swift concurrency, URLSession, or wrapped by the API layer), and real
/// failures must never be misclassified as cancellations.
struct Positive_Only_SocialTests_ErrorHelpers {

    // --- Cancellation shapes that must be detected ---

    @Test func testCancellationError_IsCancellation() {
        #expect(CancellationError().isCancellation == true)
    }

    @Test func testURLErrorCancelled_IsCancellation() {
        #expect(URLError(.cancelled).isCancellation == true)
    }

    @Test func testNSURLErrorCancelled_IsCancellation() {
        let error = NSError(domain: NSURLErrorDomain, code: NSURLErrorCancelled)
        #expect(error.isCancellation == true)
    }

    @Test func testRequestFailedWrappingCancellationError_IsCancellation() {
        #expect(APIError.requestFailed(CancellationError()).isCancellation == true)
    }

    @Test func testRequestFailedWrappingURLErrorCancelled_IsCancellation() {
        #expect(APIError.requestFailed(URLError(.cancelled)).isCancellation == true)
    }

    // --- Real failures that must NOT be treated as cancellations ---

    @Test func testURLErrorTimedOut_IsNotCancellation() {
        #expect(URLError(.timedOut).isCancellation == false)
    }

    @Test func testRequestFailedWrappingTimedOut_IsNotCancellation() {
        #expect(APIError.requestFailed(URLError(.timedOut)).isCancellation == false)
    }

    @Test func testServerError_IsNotCancellation() {
        let error = APIError.serverError(statusCode: 400, serverMessage: "Bad request")
        #expect(error.isCancellation == false)
    }

    @Test func testBadServerResponse_IsNotCancellation() {
        #expect(APIError.badServerResponse(statusCode: 500).isCancellation == false)
    }

    @Test func testCancelledCodeInOtherDomain_IsNotCancellation() {
        // NSURLErrorCancelled's raw value (-999) only means "cancelled" in
        // NSURLErrorDomain; the same code elsewhere is a real failure.
        let error = NSError(domain: "SomeOtherDomain", code: NSURLErrorCancelled)
        #expect(error.isCancellation == false)
    }

    // --- Account-banned detection ---

    @Test func testServerErrorWithAccountBanned_IsAccountBanned() {
        let error = APIError.serverError(statusCode: 403, serverMessage: GVOAppConstants.accountBannedError)
        #expect(error.isAccountBanned == true)
    }

    @Test func testRequestFailedWrappingAccountBanned_IsAccountBanned() {
        let accountBannedError = APIError.serverError(statusCode: 403, serverMessage: GVOAppConstants.accountBannedError)
        #expect(APIError.requestFailed(accountBannedError).isAccountBanned == true)
    }

    @Test func testServerErrorWithOtherMessage_IsNotAccountBanned() {
        let error = APIError.serverError(statusCode: 403, serverMessage: "Forbidden")
        #expect(error.isAccountBanned == false)
    }

    @Test func testBadServerResponse_IsNotAccountBanned() {
        #expect(APIError.badServerResponse(statusCode: 403).isAccountBanned == false)
    }

    @Test func testNonAPIError_IsNotAccountBanned() {
        let error = NSError(domain: "SomeDomain", code: 403)
        #expect(error.isAccountBanned == false)
    }

    // --- User-facing message mapping ---

    @Test func testServerError_PassesBackendMessageThrough() {
        // The backend's own validation copy is already user-appropriate.
        let error = APIError.serverError(statusCode: 400, serverMessage: "Text is not positive")
        #expect(error.userFacingMessage == "Text is not positive")
    }

    @Test func testGatewayTimeout_IsFriendly() {
        // A 504 must never surface as a raw status code to the user.
        let message = APIError.badServerResponse(statusCode: 504).userFacingMessage
        #expect(message == "The server is taking too long to respond. Please try again in a moment.")
        #expect(message.contains("504") == false)
    }

    @Test func testNotFound_IsFriendly() {
        let message = APIError.badServerResponse(statusCode: 404).userFacingMessage
        #expect(message.contains("404") == false)
        #expect(message.isEmpty == false)
    }

    @Test func testServerErrorRange_IsFriendly() {
        #expect(
            APIError.badServerResponse(statusCode: 500).userFacingMessage
                == "The server ran into a problem. Please try again in a moment.")
    }

    @Test func testRateLimited_IsFriendly() {
        #expect(
            APIError.badServerResponse(statusCode: 429).userFacingMessage
                == "You're doing that too often. Please wait a moment and try again.")
    }

    @Test func testRequestFailedWrappingTimeout_IsFriendly() {
        let message = APIError.requestFailed(URLError(.timedOut)).userFacingMessage
        #expect(message == "The request timed out. Please check your connection and try again.")
    }

    @Test func testRequestFailedWrappingOffline_IsFriendly() {
        let message = APIError.requestFailed(URLError(.notConnectedToInternet)).userFacingMessage
        #expect(message == "You appear to be offline. Please check your connection and try again.")
    }

    @Test func testOfflineNSError_IsFriendly() {
        let error = NSError(domain: NSURLErrorDomain, code: NSURLErrorNotConnectedToInternet)
        #expect(error.userFacingMessage == "You appear to be offline. Please check your connection and try again.")
    }

    @Test func testUnknownError_FallsBackToGeneric() {
        let error = NSError(domain: "SomeDomain", code: 1)
        #expect(error.userFacingMessage == "Something went wrong. Please try again.")
    }
}
