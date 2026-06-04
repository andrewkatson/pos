// Uploads a picked photo to S3 and returns its public URL, mirroring the native
// clients' uploader (ios/.../uploader/AWSManager.swift and
// android/.../data/uploader/AWSManager.kt).
//
// Like the apps, this uses an unauthenticated AWS Cognito Identity Pool to mint
// temporary credentials in the browser, then PUTs the (JPEG-compressed) image
// directly to the shared bucket. The object key is scoped to the signed-in
// user's id, matching `\(userId)/\(uuid).jpeg` on iOS.
//
// NOTE: a browser PUT requires the S3 bucket to allow the site's origin via CORS
// (the native SDKs aren't subject to CORS). The bucket's CORS policy must permit
// PUT from wherever the web app is served.

import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3'
// The dedicated Cognito provider is browser-safe; the umbrella
// `@aws-sdk/credential-providers` pulls in the Node-only IMDS provider, which
// can't be bundled for the browser.
import { fromCognitoIdentityPool } from '@aws-sdk/credential-provider-cognito-identity'

const AWS_REGION = 'us-east-2'
const IDENTITY_POOL_ID = 'us-east-2:445cf6ff-6f59-4cff-94c9-51db170ad81e'
const BUCKET_NAME = 'goodvibesonly-images'
const MAX_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB, matching the native uploaders.

let cachedClient: S3Client | null = null

function getClient(): S3Client {
  if (!cachedClient) {
    cachedClient = new S3Client({
      region: AWS_REGION,
      credentials: fromCognitoIdentityPool({
        identityPoolId: IDENTITY_POOL_ID,
        clientConfig: { region: AWS_REGION },
      }),
    })
  }
  return cachedClient
}

/**
 * Uploads an image file to S3 and returns the public URL of the object.
 *
 * @param file   The image picked by the user.
 * @param userId The signed-in user's id, used to scope the object key.
 */
export async function uploadImage(file: File, userId: string): Promise<string> {
  const body = await compressImage(file, MAX_SIZE_BYTES)
  const key = `${userId}/${crypto.randomUUID()}.jpeg`

  await getClient().send(
    new PutObjectCommand({
      Bucket: BUCKET_NAME,
      Key: key,
      Body: body,
      ContentType: 'image/jpeg',
    }),
  )

  return `https://${BUCKET_NAME}.s3.${AWS_REGION}.amazonaws.com/${key}`
}

/**
 * Re-encodes the image as JPEG and, if it exceeds `maxSizeBytes`, iteratively
 * lowers quality and then downscales until it fits — the same strategy the
 * native uploaders use.
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
