package com.example.positiveonlysocial.util

import android.graphics.Bitmap
import android.graphics.Color
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.pow

/**
 * A minimal BlurHash decoder (issue #387) — a Kotlin port of the reference
 * algorithm at https://github.com/woltapp/blurhash. It turns the short BlurHash
 * string the backend attaches to a post into a small blurred [Bitmap] the grid
 * shows while the real photo loads, so a loading tile isn't a flat black box.
 * Vendored (a handful of pure functions) rather than taking a dependency just to
 * decode ~30 characters. Mirrors the iOS `BlurHashImage` decoder.
 */
object BlurHashDecoder {
    // The preview is upscaled to fill the tile, so a tiny decode is plenty and
    // keeps the per-tile cost negligible.
    const val DECODE_SIZE = 32

    private const val DIGITS =
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#\$%*+,-.:;=?@[]^_{|}~"

    /**
     * Decode [blurHash] into a blurred [width]x[height] bitmap, or null if the
     * string is malformed (bad length/characters) — callers then fall back to a
     * plain placeholder.
     */
    fun decode(blurHash: String?, width: Int = DECODE_SIZE, height: Int = DECODE_SIZE, punch: Float = 1f): Bitmap? {
        if (blurHash == null || blurHash.length < 6 || width <= 0 || height <= 0) return null

        val sizeFlag = decode83(blurHash, 0, 1)
        val numberOfY = (sizeFlag / 9) + 1
        val numberOfX = (sizeFlag % 9) + 1
        if (blurHash.length != 4 + 2 * numberOfX * numberOfY) return null

        val quantisedMaximumValue = decode83(blurHash, 1, 2)
        val maximumValue = (quantisedMaximumValue + 1) / 166f

        val colours = Array(numberOfX * numberOfY) { index ->
            if (index == 0) {
                decodeDc(decode83(blurHash, 2, 6))
            } else {
                decodeAc(decode83(blurHash, 4 + index * 2, 6 + index * 2), maximumValue * punch)
            }
        }

        val pixels = IntArray(width * height)
        for (y in 0 until height) {
            for (x in 0 until width) {
                var r = 0f
                var g = 0f
                var b = 0f
                for (j in 0 until numberOfY) {
                    for (i in 0 until numberOfX) {
                        val basis = (cos(Math.PI * x * i / width) * cos(Math.PI * y * j / height)).toFloat()
                        val colour = colours[i + j * numberOfX]
                        r += colour[0] * basis
                        g += colour[1] * basis
                        b += colour[2] * basis
                    }
                }
                pixels[x + y * width] = Color.rgb(linearToSrgb(r), linearToSrgb(g), linearToSrgb(b))
            }
        }

        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        bitmap.setPixels(pixels, 0, width, 0, 0, width, height)
        return bitmap
    }

    private fun decode83(string: String, from: Int, to: Int): Int {
        var value = 0
        for (index in from until to) {
            val digit = DIGITS.indexOf(string[index])
            if (digit != -1) value = value * 83 + digit
        }
        return value
    }

    private fun decodeDc(value: Int): FloatArray =
        floatArrayOf(srgbToLinear(value shr 16), srgbToLinear((value shr 8) and 255), srgbToLinear(value and 255))

    private fun decodeAc(value: Int, maximumValue: Float): FloatArray {
        val quantR = value / (19 * 19)
        val quantG = (value / 19) % 19
        val quantB = value % 19
        return floatArrayOf(
            signPow((quantR - 9) / 9f, 2f) * maximumValue,
            signPow((quantG - 9) / 9f, 2f) * maximumValue,
            signPow((quantB - 9) / 9f, 2f) * maximumValue,
        )
    }

    private fun signPow(value: Float, exponent: Float): Float {
        val magnitude = abs(value).toDouble().pow(exponent.toDouble()).toFloat()
        return if (value < 0) -magnitude else magnitude
    }

    private fun linearToSrgb(value: Float): Int {
        val clamped = value.coerceIn(0f, 1f)
        return if (clamped <= 0.0031308f) {
            (clamped * 12.92f * 255f + 0.5f).toInt()
        } else {
            ((1.055f * clamped.toDouble().pow(1 / 2.4).toFloat() - 0.055f) * 255f + 0.5f).toInt()
        }
    }

    private fun srgbToLinear(value: Int): Float {
        val v = value / 255f
        return if (v <= 0.04045f) {
            v / 12.92f
        } else {
            ((v + 0.055f) / 1.055f).toDouble().pow(2.4).toFloat()
        }
    }
}
