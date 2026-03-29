//
//  AWSManager.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/11/25.
//

import Foundation
import AWSClientRuntime
import AWSS3
import AWSSDKIdentity
import AWSCognitoIdentity
import AWSCognitoIdentityProvider
import AwsCommonRuntimeKit
import UIKit

public enum AWSManagerError: Error, LocalizedError {
    /// The client failed to initialize during app launch.
    /// The associated error contains the reason (e.g., network, bad credentials).
    case initializationFailed(Error)
    
    /// An attempt was made to use the client, but it was not initialized.
    case clientNotInitialized
    
    public var errorDescription: String? {
        switch self {
        case .initializationFailed(let error):
            return "AWSManager failed to initialize: \(error.localizedDescription)"
        case .clientNotInitialized:
            return "AWS S3 Client is not initialized. Check logs for a detailed error."
        }
    }
}

// RECOMMENDED: This implementation uses the modern AWS SDK for Swift (v3)
final class AWSManager {
    static let shared = AWSManager()

    /// Publicly expose the S3 client for use in other parts of the app (like S3Uploader)
    private(set) var s3Client: S3Client?
    
    private(set) var initializationError: Error?
    
    /// Publicly expose the region for URL construction
    let awsRegion = "us-east-2"
    private let identityPoolId = "us-east-2:445cf6ff-6f59-4cff-94c9-51db170ad81e"

    private init() {
        do {
            let credentialsResolver = try CognitoAWSCredentialIdentityResolver(identityPoolId: identityPoolId)
            
            let configuration = try S3Client.Config(awsCredentialIdentityResolver: credentialsResolver, region: awsRegion)
            
            // Initialize the S3 client
            self.s3Client = S3Client(config: configuration)
            self.initializationError = nil
            
            // A log message is very helpful for debugging
            // We use NSLog() instead of a print() because it shows local and in Firebase.
            //See https://shorturl.at/KF2XX for more info.
            NSLog("✅ AWSManager: S3Client initialized successfully.")
            
        } catch {
            // 3. This is the new graceful handling.
            // Instead of crashing, we log the error and set our client to nil.
            
            NSLog("❌ AWSManager: Failed to initialize AWS S3 Client: \(error)")
            self.s3Client = nil
            self.initializationError = AWSManagerError.initializationFailed(error)
        }
    }
}

final class S3Uploader {
    private let s3Client = AWSManager.shared.s3Client
    private let bucketName = "goodvibesonly-images"

    /// Uploads data to S3 and returns the public URL.
    func upload(data: Data, fileName: String) async throws -> URL {
        
        let compressedData = self.compressImage(data:data,maxSizeBytes: 10 * 1024 * 1024) //10 MB
        
        let input = PutObjectInput(
            body: .data(compressedData),
            bucket: bucketName,
            contentType: "image/jpeg",
            key: fileName
        )
        
       
        guard let s3Client = self.s3Client else {
            // If the client is nil, throw our custom error.
            // The call site (e.g., your ViewModel) can now catch this.
            throw AWSManagerError.clientNotInitialized
        }

        _ = try await s3Client.putObject(input: input)

        // Construct the public URL for the uploaded object
        let region = AWSManager.shared.awsRegion
        let urlString = "https://\(bucketName).s3.\(region).amazonaws.com/\(fileName)"
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }

        NSLog("✅ Successfully uploaded to S3. URL: \(url)")
        return url
    }
        
    /**
         * Compresses the image data to be within the specified max size.
         * @param data The original image data
         * @param maxSizeBytes The maximum allowed size in bytes
         * @return The compressed image data
         */
    func compressImage(data: Data, maxSizeBytes: Int) -> Data {
        // 1. Check if already within limits
        if data.count <= maxSizeBytes {
            NSLog("✅ Good news ,Image size (\(data.count) bytes) is within limits.")
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

