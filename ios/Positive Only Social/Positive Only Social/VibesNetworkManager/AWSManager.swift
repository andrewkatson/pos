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

    public var errorDescription: String? {
        switch self {
        case .invalidUploadURL:
            return "The upload URL returned by the server was invalid."
        case .uploadRejected(let statusCode):
            return "The image upload was rejected with status code \(statusCode)."
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
        let compressedData = self.compressImage(data: data, maxSizeBytes: 10 * 1024 * 1024) // 10 MB

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

    private func isJpeg(data: Data) -> Bool {
        guard data.count >= 2 else { return false }
        return data.prefix(2) == Data([0xFF, 0xD8])
    }

    /// Compresses the image data to be within the specified maximum size, and ensures it is in JPEG format.
    ///
    /// - Parameters:
    ///   - data: The original image data.
    ///   - maxSizeBytes: The maximum allowed size in bytes.
    /// - Returns: The compressed image data.
    func compressImage(data: Data, maxSizeBytes: Int) -> Data {
        // 1. Check if already within limits and is already JPEG
        if data.count <= maxSizeBytes && isJpeg(data: data) {
            NSLog("✅ Good news, Image size (\(data.count) bytes) is within limits.")
            return data
        }

        // 2. Convert Data to UIImage
        guard let image = UIImage(data: data) else {
            NSLog("❌ Oops,Error: Could not decode image data")
            return data // Return original data if conversion fails
        }

        // 3. Compress using JPEG (PNG does not support compression levels)
        var compression: CGFloat = 0.9
        guard var imageData = image.jpegData(compressionQuality: compression) else {
            return data
        }

        // 4. Iteratively reduce quality until size is met
        while imageData.count > maxSizeBytes && compression > 0.1 {
            compression -= 0.1
            if let compressedImage = image.jpegData(compressionQuality: compression) {
                imageData = compressedImage
            }
        }

        // 5. If still too large at minimum quality, progressively downscale the image
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
