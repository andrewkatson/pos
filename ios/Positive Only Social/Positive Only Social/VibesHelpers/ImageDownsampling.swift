//
//  ImageDownsampling.swift
//  Positive Only Social
//

import CoreGraphics
import Kingfisher
import SwiftUI

/// Decode-size caps for the Kingfisher-backed image views.
///
/// Without a processor Kingfisher decodes every photo at full resolution, so a
/// 12 MP camera shot (4032x3024) became a ~48 MB bitmap even for a 32pt avatar
/// or a third-of-the-screen grid tile. ImageIO's hardware path can't produce a
/// buffer that size in RGBA and logs "CVPixelBufferCreate returned err -6680"
/// before falling back to a slow software decode, and the oversized bitmaps
/// thrash Kingfisher's memory cache — which is why iOS loaded images far slower
/// than Android, whose Coil loader decodes to the view's size by default.
enum ImageDownsampling {
    /// `DownsamplingImageProcessor` caps the image's *long* edge, but the grid
    /// and avatars crop with `scaledToFill`, so the *short* edge has to cover
    /// the view. Overshooting by 2x keeps photos up to a 2:1 aspect ratio sharp.
    static let fillOverscan: CGFloat = 2

    /// Long-edge cap for the post detail view, which fits the photo inside a
    /// full-width square. Matches the compression Lambda's cap, so it only ever
    /// shrinks the full-resolution fallback (or a pre-cap compressed copy).
    static let detailMaxPixelSize: CGFloat = 1440

    /// The long-edge pixel cap for a photo cropped to fill a view whose longer
    /// side is `pointSize` points on a screen of the given `scale`.
    /// Falls back to the detail cap for an unmeasured (zero-size) view rather
    /// than asking ImageIO for a zero-pixel thumbnail.
    static func maxPixelSize(toFill pointSize: CGFloat, scale: CGFloat) -> CGFloat {
        guard pointSize > 0 else { return detailMaxPixelSize }
        return pointSize * scale * fillOverscan
    }
}

extension KFImage {
    /// Decodes the image straight to at most `maxPixelSize` pixels on its long
    /// edge via ImageIO's thumbnail API, so the full-size bitmap is never built.
    /// The downloaded original is disk-cached too, so another view of the same
    /// URL at a different size (grid tile → detail view) reuses the download.
    func downsampled(toMaxPixelSize maxPixelSize: CGFloat) -> KFImage {
        // The processor's size is in points multiplied by the `scaleFactor`
        // option, which defaults to 1, so this size is in pixels.
        setProcessor(DownsamplingImageProcessor(size: CGSize(width: maxPixelSize, height: maxPixelSize)))
            .cacheOriginalImage()
    }
}
