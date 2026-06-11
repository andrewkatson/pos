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
}
