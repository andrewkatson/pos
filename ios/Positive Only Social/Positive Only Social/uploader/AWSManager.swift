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
            print("✅ AWSManager: S3Client initialized successfully.")
            
        } catch {
            // 3. This is the new graceful handling.
            // Instead of crashing, we log the error and set our client to nil.
            print("❌ AWSManager: Failed to initialize AWS S3 Client: \(error)")
            self.s3Client = nil
            self.initializationError = AWSManagerError.initializationFailed(error)
        }
    }
}

final class S3Uploader {
    private let s3Client = AWSManager.shared.s3Client
    private let bucketName = "positive-social-app-posts" // <-- CHANGE to your bucket name

    /// Uploads data to S3 and returns the public URL.
    func upload(data: Data, fileName: String) async throws -> URL {
        let input = PutObjectInput(
            body: .data(data),
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

        print("Successfully uploaded to S3. URL: \(url)")
        return url
    }
}
