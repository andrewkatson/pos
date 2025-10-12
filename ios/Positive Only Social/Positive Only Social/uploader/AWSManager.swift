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

// RECOMMENDED: This implementation uses the modern AWS SDK for Swift (v3)
final class AWSManager {
    static let shared = AWSManager()

    /// Publicly expose the S3 client for use in other parts of the app (like S3Uploader)
    let s3Client: S3Client

    /// Publicly expose the region for URL construction
    let awsRegion = "us-east-1" // <-- CHANGE to your bucket's region
    private let identityPoolId = "us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" // <-- CHANGE to your Cognito Pool ID

    private init() {
        do {
            // This is the recommended and secure approach
            let credentialsResolver = try CognitoAWSCredentialIdentityResolver(identityPoolId: identityPoolId)
                
            let configuration = try S3Client.Config(awsCredentialIdentityResolver: credentialsResolver, region: awsRegion)
            
            // Initialize the S3 client with the configuration
            self.s3Client = S3Client(config: configuration)
        } catch {
            // In a real app, you might want to handle this error more gracefully
            fatalError("Failed to initialize AWS S3 Client: \(error)")
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
