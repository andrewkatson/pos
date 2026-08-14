//
//  Positive_Only_SocialTests_TermsOfService.swift
//  Positive Only Social
//
//  The terms of service shipped in the app (issue #493).
//

import Testing
@testable import Positive_Only_Social

struct Positive_Only_SocialTests_TermsOfService {

    @Test func everySectionCarriesTextToShow() {
        let sections = GVOAppConstants.termsOfServiceSections
        #expect(!sections.isEmpty)
        for section in sections {
            #expect(!section.heading.isEmpty)
            #expect(!section.body.isEmpty)
        }
        #expect(!GVOAppConstants.termsOfServiceLastUpdated.isEmpty)
    }

    @Test func headingsAreUniqueSoTheyCanIdentifyRows() {
        // TermsOfServiceView's ForEach keys on the heading; a duplicate would
        // make SwiftUI drop a section rather than draw both.
        let headings = GVOAppConstants.termsOfServiceSections.map(\.heading)
        #expect(Set(headings).count == headings.count)
    }

    @Test func saysWhatSigningInWithGoogleShares() {
        // Google's OAuth consent screen links to these terms, so the Google
        // section has to be here and not only on the website.
        let google = GVOAppConstants.termsOfServiceSections
            .first { $0.heading == "Signing in with Google" }
        #expect(google != nil)
        #expect(google?.body.contains("verified email address") == true)
    }
}
