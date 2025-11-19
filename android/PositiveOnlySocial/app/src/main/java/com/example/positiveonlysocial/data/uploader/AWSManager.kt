package com.example.positiveonlysocial.data.uploader

import android.util.Log
import aws.sdk.kotlin.services.cognitoidentity.CognitoIdentityClient
import aws.sdk.kotlin.services.cognitoidentity.getCredentialsForIdentity
import aws.sdk.kotlin.services.cognitoidentity.getId
import aws.sdk.kotlin.services.s3.S3Client
import aws.sdk.kotlin.services.s3.model.PutObjectRequest
import aws.smithy.kotlin.runtime.auth.awscredentials.Credentials
import aws.smithy.kotlin.runtime.auth.awscredentials.CredentialsProvider
import aws.smithy.kotlin.runtime.collections.Attributes
import aws.smithy.kotlin.runtime.content.ByteStream
import java.net.URL

// Custom Exception Class
sealed class AWSManagerError(message: String, cause: Throwable? = null) : Exception(message, cause) {

    class InitializationFailed(cause: Throwable) :
        AWSManagerError("AWSManager failed to initialize: ${cause.localizedMessage}", cause)

    object ClientNotInitialized :
        AWSManagerError("AWS S3 Client is not initialized. Check logs for a detailed error.") {
        private fun readResolve(): Any = ClientNotInitialized
    }
}

/**
 * RECOMMENDED: This implementation uses the modern AWS SDK for Kotlin
 */
object AWSManager {
    // Publicly expose the region
    const val AWS_REGION = "us-east-1" // <-- CHANGE to your bucket's region
    private const val IDENTITY_POOL_ID = "us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" // <-- CHANGE to your Pool ID

    var s3Client: S3Client? = null
        private set

    var initializationError: Throwable? = null
        private set

    /**
     * In Kotlin, network operations (like setting up credentials) are suspending.
     * Call this method from your Application class or main Activity's onCreate
     * within a CoroutineScope.
     */
    fun initialize() {
        try {
            // Create a Cognito Credentials Provider
            val cognitoProvider = CognitoCredentialsProvider(
                identityPoolId = IDENTITY_POOL_ID,
                region = AWS_REGION
            )

            // Initialize the S3 Client
            s3Client = S3Client {
                region = AWS_REGION
                credentialsProvider = cognitoProvider
            }

            initializationError = null
            Log.d("AWSManager", "✅ AWSManager: S3Client initialized successfully.")

        } catch (e: Exception) {
            // Graceful handling
            Log.e("AWSManager", "❌ AWSManager: Failed to initialize AWS S3 Client: ${e.localizedMessage}")
            s3Client = null
            initializationError = AWSManagerError.InitializationFailed(e)
        }
    }
}

class S3Uploader {
    private val bucketName = "positive-social-app-posts" // <-- CHANGE to your bucket name

    /**
     * Uploads data to S3 and returns the public URL.
     * @param data The file bytes to upload
     * @param fileName The destination file name
     */
    suspend fun upload(data: ByteArray, fileName: String): URL {

        val s3Client = AWSManager.s3Client ?: run {
            // If the client is null, throw our custom error.
            throw AWSManagerError.ClientNotInitialized
        }

        val input = PutObjectRequest {
            bucket = bucketName
            key = fileName
            body = ByteStream.fromBytes(data)
            contentType = "image/jpeg"
        }

        // Perform the upload
        s3Client.putObject(input)

        // Construct the public URL
        val region = AWSManager.AWS_REGION
        val urlString = "https://$bucketName.s3.$region.amazonaws.com/$fileName"

        return try {
            val url = URL(urlString)
            Log.d("S3Uploader", "Successfully uploaded to S3. URL: $url")
            url
        } catch (e: Exception) {
            throw AWSManagerError.InitializationFailed(e) // Or a specific URLError
        }
    }
}

/**
 * Helper class to bridge Cognito Identity to the AWS Credentials Provider interface.
 * The AWS Kotlin SDK does not have a one-line "CognitoAWSCredentialIdentityResolver"
 * like Swift, so we define a simple provider.
 */
class CognitoCredentialsProvider(
    private val identityPoolId: String,
    private val region: String
) : CredentialsProvider {

    override suspend fun resolve(attributes: Attributes): Credentials {
        // 1. Get ID
        val identityClient = CognitoIdentityClient { }
        val idResponse = identityClient.getId {
            identityPoolId = this@CognitoCredentialsProvider.identityPoolId
        }

        // 2. Get Credentials for ID
        val credsResponse = identityClient.getCredentialsForIdentity {
            identityId = idResponse.identityId
        }

        val credentials = credsResponse.credentials ?: throw Exception("No credentials returned")

        return Credentials(
            accessKeyId = credentials.accessKeyId ?: "",
            secretAccessKey = credentials.secretKey ?: "",
            sessionToken = credentials.sessionToken,
            expiration = credentials.expiration
        )
    }
}
