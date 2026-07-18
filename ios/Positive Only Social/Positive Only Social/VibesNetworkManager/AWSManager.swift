//
//  AWSManager.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/11/25.
//

import Foundation
import UIKit

public enum ImageUploadError: Error, LocalizedError {
    /// The presigned upload URL returned by the backend could not be parsed.
    case invalidUploadURL

    /// S3 rejected the upload (non-2xx status).
    case uploadRejected(statusCode: Int)

    /// The picked image could not be decoded and re-encoded as a JPEG. We
    /// refuse to fall back to uploading the original bytes because they may
    /// still carry EXIF metadata such as GPS coordinates (issue #346).
    case imageProcessingFailed

    public var errorDescription: String? {
        switch self {
        case .invalidUploadURL:
            return "The upload URL returned by the server was invalid."
        case .uploadRejected(let statusCode):
            return "The image upload was rejected with status code \(statusCode)."
        case .imageProcessingFailed:
            return "The image could not be processed for upload."
        }
    }
}

/// Uploads post images to S3 via a backend-issued presigned PUT URL.
///
/// The app used to hold Cognito guest credentials and write to the bucket with
/// the AWS SDK, but that identity pool allowed anonymous writes to arbitrary
/// keys (issue #310). Now the backend picks the object key (scoped to the
/// authenticated user) and signs a short-lived URL for exactly that key and
/// content type, so the app needs no AWS credentials at all.
final class S3Uploader {

    /// The presigned URL is signed over this exact content type; sending
    /// anything else makes S3 reject the signature.
    private let contentType = "image/jpeg"

    /// Compresses `data` to a JPEG and PUTs it to `uploadURL` (a presigned S3 URL).
    func upload(data: Data, to uploadURL: URL) async throws {
        let compressedData = try self.compressImage(data: data, maxSizeBytes: 10 * 1024 * 1024) // 10 MB

        var request = URLRequest(url: uploadURL)
        request.httpMethod = "PUT"
        request.setValue(contentType, forHTTPHeaderField: "Content-Type")

        let (_, response) = try await URLSession.shared.upload(for: request, from: compressedData)

        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? -1
            NSLog("❌ S3Uploader: upload rejected with status \(statusCode)")
            throw ImageUploadError.uploadRejected(statusCode: statusCode)
        }

        NSLog("✅ Successfully uploaded image via presigned URL.")
    }

    /// Compresses the image data to be within the specified maximum size, ensures
    /// it is in JPEG format, and strips its metadata.
    ///
    /// We always decode to a `UIImage` and re-encode, even when the input is
    /// already a small JPEG. Returning the original bytes untouched would upload
    /// the camera's EXIF metadata — including GPS coordinates — to the source
    /// bucket (issue #346). Re-encoding through `UIImage.jpegData` bakes any
    /// orientation into the pixels and drops that metadata.
    ///
    /// - Parameters:
    ///   - data: The original image data.
    ///   - maxSizeBytes: The maximum allowed size in bytes.
    /// - Returns: The compressed, metadata-free image data.
    /// - Throws: `ImageUploadError.imageProcessingFailed` if the image cannot be
    ///   decoded or re-encoded. Falling back to the original bytes instead would
    ///   upload their metadata, so processing failures abort the upload.
    func compressImage(data: Data, maxSizeBytes: Int) throws -> Data {
        // 1. Convert Data to UIImage
        guard let image = UIImage(data: data) else {
            NSLog("❌ Oops, Error: Could not decode image data")
            throw ImageUploadError.imageProcessingFailed
        }

        // 2. Compress using JPEG (PNG does not support compression levels). Start
        // near-lossless so an already-small photo is barely touched; the loop
        // below only steps quality down when the result exceeds the size limit.
        var compression: CGFloat = 0.95
        guard var imageData = image.jpegData(compressionQuality: compression) else {
            NSLog("❌ Oops, Error: Could not re-encode image as JPEG")
            throw ImageUploadError.imageProcessingFailed
        }

        // 3. Iteratively reduce quality until size is met
        while imageData.count > maxSizeBytes && compression > 0.1 {
            compression -= 0.1
            if let compressedImage = image.jpegData(compressionQuality: compression) {
                imageData = compressedImage
            }
        }

        // 4. If still too large at minimum quality, progressively downscale the image
        if imageData.count > maxSizeBytes {
            var currentImage = image
            var currentSize = currentImage.size

            // Safety: avoid infinite loops by enforcing a minimum dimension
            let minimumDimension: CGFloat = 1.0
            let scaleFactor: CGFloat = 0.9

            while imageData.count > maxSizeBytes &&
                  currentSize.width > minimumDimension &&
                  currentSize.height > minimumDimension {

                currentSize = CGSize(width: currentSize.width * scaleFactor,
                                     height: currentSize.height * scaleFactor)

                UIGraphicsBeginImageContextWithOptions(currentSize, false, currentImage.scale)
                currentImage.draw(in: CGRect(origin: .zero, size: currentSize))
                let resizedImage = UIGraphicsGetImageFromCurrentImageContext()
                UIGraphicsEndImageContext()

                guard let resized = resizedImage,
                      let resizedData = resized.jpegData(compressionQuality: compression) else {
                    // If resizing or encoding fails, break and use the best effort so far
                    break
                }

                currentImage = resized
                imageData = resizedData
            }
        }
        return imageData
    }
}
