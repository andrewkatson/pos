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
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

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
    const val AWS_REGION = "us-east-2"
    private const val IDENTITY_POOL_ID = "us-east-2:445cf6ff-6f59-4cff-94c9-51db170ad81e"

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
    private val bucketName = "goodvibesonly-images"

    /**
     * Uploads data to S3 and returns the public URL.
     * @param data The file bytes to upload
     * @param fileName The destination file name
     */
    suspend fun upload(data: ByteArray, fileName: String): URL = withContext(Dispatchers.IO) {

        val s3Client = AWSManager.s3Client ?: run {
            // If the client is null, throw our custom error.
            throw AWSManagerError.ClientNotInitialized
        }

        val compressedData = compressImage(data, 10 * 1024 * 1024) // 10MB

        val input = PutObjectRequest {
            bucket = bucketName
            key = fileName
            body = ByteStream.fromBytes(compressedData)
            contentType = "image/jpeg"
        }

        // Perform the upload
        s3Client.putObject(input)

        // Construct the public URL
        val region = AWSManager.AWS_REGION
        val urlString = "https://$bucketName.s3.$region.amazonaws.com/$fileName"

        try {
            val url = URL(urlString)
            Log.d("S3Uploader", "Successfully uploaded to S3. URL: $url")
            url
        } catch (e: Exception) {
            throw AWSManagerError.InitializationFailed(e) // Or a specific URLError
        }
    }

    private fun isJpeg(data: ByteArray): Boolean {
        return data.size >= 2 && data[0] == 0xFF.toByte() && data[1] == 0xD8.toByte()
    }

    private fun rotateImageIfRequired(data: ByteArray, bitmap: Bitmap): Bitmap {
        try {
            val exifInterface = ExifInterface(ByteArrayInputStream(data))
            val orientation = exifInterface.getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )
            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
                else -> return bitmap
            }
            val rotatedBitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            bitmap.recycle()
            return rotatedBitmap
        } catch (e: Exception) {
            Log.w("S3Uploader", "Failed to check EXIF orientation: ${e.localizedMessage}")
            return bitmap
        }
    }

    /**
     * Compresses the image data to be within the specified max size.
     * @param data The original image data
     * @param maxSizeBytes The maximum allowed size in bytes
     * @return The compressed image data
     */
    private fun compressImage(data: ByteArray, maxSizeBytes: Long): ByteArray {
        if (data.size <= maxSizeBytes && isJpeg(data)) {
            Log.d("S3Uploader", "Image is already JPEG and size (${data.size} bytes) is within limits.")
            return data
        }

        Log.d("S3Uploader", "Transcoding/compressing image to JPEG... Original size: ${data.size} bytes")

        var bitmap = BitmapFactory.decodeByteArray(data, 0, data.size) ?: run {
            Log.e("S3Uploader", "Failed to decode bitmap for compression.")
            return data
        }

        bitmap = rotateImageIfRequired(data, bitmap)

        var quality = 90
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, stream)
        var compressedData = stream.toByteArray()

        // Iteratively reduce quality until size is under limit or quality is too low
        while (compressedData.size > maxSizeBytes && quality >= 10) {
            val nextStream = ByteArrayOutputStream()
            quality -= 10
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, nextStream)
            compressedData = nextStream.toByteArray()
            Log.d("S3Uploader", "Compressed to quality $quality, size: ${compressedData.size} bytes")
        }

        bitmap.recycle() // Free memory
        return compressedData
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

    override suspend fun resolve(attributes: Attributes): Credentials = withContext(Dispatchers.IO) {
        // The AWS Kotlin SDK requires an explicit region — on Android there is no
        // ambient region (no env vars / instance metadata), so omitting it makes
        // the first call throw a region-resolution error before any request is
        // sent, which surfaced as posts "failing immediately" (issue #292).
        val identityClient = CognitoIdentityClient {
            region = this@CognitoCredentialsProvider.region
        }
        identityClient.use { client ->
            // 1. Get ID
            val idResponse = client.getId {
                identityPoolId = this@CognitoCredentialsProvider.identityPoolId
            }

            // 2. Get Credentials for ID
            val credsResponse = client.getCredentialsForIdentity {
                identityId = idResponse.identityId
            }

            val credentials = credsResponse.credentials ?: throw Exception("No credentials returned")

            Credentials(
                accessKeyId = credentials.accessKeyId ?: "",
                secretAccessKey = credentials.secretKey ?: "",
                sessionToken = credentials.sessionToken,
                expiration = credentials.expiration
            )
        }
    }
}
