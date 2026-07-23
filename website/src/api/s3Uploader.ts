// Uploads a picked photo to S3 and returns its public URL, mirroring the native
// clients' uploader (ios/.../uploader/AWSManager.swift and
// android/.../data/uploader/ImageUploader.kt).
//
// The site used to hold unauthenticated Cognito guest credentials and write to
// the bucket with the AWS SDK, but that identity pool allowed anonymous writes
// to arbitrary keys (issue #310). Now the backend picks the object key (scoped
// to the authenticated user) and signs a short-lived presigned PUT URL for
// exactly that key and content type, so the browser holds no AWS credentials.
//
// NOTE: a browser PUT requires the S3 bucket to allow the site's origin via CORS
// (the native SDKs aren't subject to CORS). The bucket's CORS policy must permit
// PUT from wherever the web app is served.

import { apiClient } from './client'

const MAX_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB, matching the native uploaders.

// The presigned URL is signed over this exact content type; sending anything
// else makes S3 reject the signature.
const CONTENT_TYPE = 'image/jpeg'

/**
 * Uploads an image file to S3 via a backend-issued presigned PUT URL and
 * returns the public URL of the object.
 *
 * @param file The image picked by the user.
 */
export async function uploadImage(file: File): Promise<string> {
  const body = await compressImage(file, MAX_SIZE_BYTES)
  const { upload_url, image_url } = await apiClient.createUploadUrl()

  const response = await fetch(upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': CONTENT_TYPE },
    body,
  })
  if (!response.ok) {
    throw new Error(`The image upload was rejected (HTTP ${response.status}).`)
  }

  return image_url
}

/**
 * Re-encodes the image as JPEG and, if it exceeds `maxSizeBytes`, iteratively
 * lowers quality and then downscales until it fits — the same strategy the
 * native uploaders use.
 *
 * Re-encoding through a canvas also strips the photo's metadata: the output
 * blob carries no EXIF, so the camera's GPS coordinates never reach the source
 * bucket (issue #346). Do not add a fast path that uploads the original file
 * untouched — that would leak that metadata.
 */
async function compressImage(file: File, maxSizeBytes: number): Promise<Blob> {
  const bitmap = await createImageBitmap(file)
  try {
    let width = bitmap.width
    let height = bitmap.height
    let quality = 0.9

    let blob = await encodeJpeg(bitmap, width, height, quality)

    // 1. Reduce quality.
    while (blob.size > maxSizeBytes && quality > 0.1) {
      quality -= 0.1
      blob = await encodeJpeg(bitmap, width, height, quality)
    }

    // 2. Still too big — progressively downscale at the lowest quality.
    while (blob.size > maxSizeBytes && width > 1 && height > 1) {
      width = Math.max(1, Math.floor(width * 0.9))
      height = Math.max(1, Math.floor(height * 0.9))
      blob = await encodeJpeg(bitmap, width, height, quality)
    }

    return blob
  } finally {
    bitmap.close()
  }
}

function encodeJpeg(
  bitmap: ImageBitmap,
  width: number,
  height: number,
  quality: number,
): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return Promise.reject(new Error('Could not get a 2D canvas context'))
  }
  ctx.drawImage(bitmap, 0, 0, width, height)
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      blob => (blob ? resolve(blob) : reject(new Error('Image encoding failed'))),
      'image/jpeg',
      quality,
    )
  })
}
