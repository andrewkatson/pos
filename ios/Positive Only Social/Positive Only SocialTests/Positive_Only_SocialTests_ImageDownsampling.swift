//
//  Positive_Only_SocialTests_ImageDownsampling.swift
//  Positive Only Social
//

import Testing
import CoreGraphics
import Foundation
@testable import Positive_Only_Social

struct Positive_Only_SocialTests_ImageDownsampling {

    @Test func fillCapCoversViewInPixelsWithOverscan() {
        // A 130pt grid tile on a 3x screen is 390px; the 2x overscan keeps a
        // 4:3 photo's short edge (585px) above that when cropped to fill.
        #expect(ImageDownsampling.maxPixelSize(toFill: 130, scale: 3) == 780)
    }

    @Test func fillCapIsFarBelowACameraPhoto() {
        // Even a full-width iPhone tile decodes well under a 12 MP photo's 4032px.
        #expect(ImageDownsampling.maxPixelSize(toFill: 430, scale: 3) < 4032)
    }

    @Test func unmeasuredViewFallsBackToDetailCap() {
        #expect(ImageDownsampling.maxPixelSize(toFill: 0, scale: 3) == ImageDownsampling.detailMaxPixelSize)
    }

    @Test func signedURLCacheKeyIgnoresSignature() {
        let first = URL(string: "https://images.example.net/user/photo.jpg?Expires=100&Signature=abc&Key-Pair-Id=K1")!
        let second = URL(string: "https://images.example.net/user/photo.jpg?Expires=200&Signature=def&Key-Pair-Id=K1")!
        #expect(SignedImageURL.cacheKey(for: first) == "https://images.example.net/user/photo.jpg")
        #expect(SignedImageURL.cacheKey(for: first) == SignedImageURL.cacheKey(for: second))
    }

    @Test func signedURLCacheKeyKeepsCompressedAndOriginalApart() {
        let compressed = URL(string: "https://images.example.net/user/photo.jpg?Signature=abc")!
        let original = URL(string: "https://originals.example.net/user/photo.jpg?Signature=abc")!
        #expect(SignedImageURL.cacheKey(for: compressed) != SignedImageURL.cacheKey(for: original))
    }

    @Test func invalidURLStringHasNoSource() {
        #expect(SignedImageURL.source(for: "") == nil)
    }
}
