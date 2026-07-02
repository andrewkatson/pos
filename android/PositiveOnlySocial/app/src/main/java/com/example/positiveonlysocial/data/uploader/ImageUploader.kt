package com.example.positiveonlysocial.data.uploader

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.util.Log
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/** The image upload to S3 failed (non-2xx from S3 or a transport error). */
class ImageUploadException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Uploads post images to S3 via a backend-issued presigned PUT URL.
 *
 * The app used to hold Cognito guest credentials and write to the bucket with
 * the AWS SDK, but that identity pool allowed anonymous writes to arbitrary
 * keys (issue #310). Now the backend picks the object key (scoped to the
 * authenticated user) and signs a short-lived URL for exactly that key and
 * content type, so the app needs no AWS credentials at all.
 */
class ImageUploader {

    // The presigned URL is signed over this exact content type; sending
    // anything else makes S3 reject the signature.
    private val contentType = "image/jpeg"

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        // Uploads can be up to ~10MB on a slow cellular link.
        .writeTimeout(120, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    /**
     * Compresses [data] to a JPEG and PUTs it to [uploadUrl] (a presigned S3 URL).
     * Throws [ImageUploadException] if S3 rejects the upload.
     */
    suspend fun upload(data: ByteArray, uploadUrl: String) = withContext(Dispatchers.IO) {
        val compressedData = compressImage(data, 10 * 1024 * 1024) // 10MB

        val request = Request.Builder()
            .url(uploadUrl)
            .put(compressedData.toRequestBody(contentType.toMediaType()))
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ImageUploadException("S3 rejected the upload: HTTP ${response.code}")
            }
        }
        Log.d("ImageUploader", "Successfully uploaded image via presigned URL")
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
            Log.w("ImageUploader", "Failed to check EXIF orientation: ${e.localizedMessage}")
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
            Log.d("ImageUploader", "Image is already JPEG and size (${data.size} bytes) is within limits.")
            return data
        }

        Log.d("ImageUploader", "Transcoding/compressing image to JPEG... Original size: ${data.size} bytes")

        var bitmap = BitmapFactory.decodeByteArray(data, 0, data.size) ?: throw IllegalArgumentException("Failed to decode image data for transcoding")

        bitmap = rotateImageIfRequired(data, bitmap)

        var quality = 90
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, stream)
        var compressedData = stream.toByteArray()

        // Iteratively reduce quality until size is under limit or quality is too low
        while (compressedData.size > maxSizeBytes && quality > 10) {
            val nextStream = ByteArrayOutputStream()
            quality -= 10
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, nextStream)
            compressedData = nextStream.toByteArray()
            Log.d("ImageUploader", "Compressed to quality $quality, size: ${compressedData.size} bytes")
        }

        bitmap.recycle() // Free memory
        return compressedData
    }
}
