package com.example.positiveonlysocial.api

import android.os.Build
import okhttp3.OkHttpClient
import org.json.JSONObject
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.BuildConfig
import java.util.concurrent.TimeUnit

object APIProvider {

    private val stubbedService = StatefulStubbedAPI()

    /**
     * Invoked when an authenticated request is rejected because the account
     * has an active outright ban. Wired up in PositiveOnlySocialApp to force
     * a logout (the backend has already revoked the session server-side).
     */
    @Volatile
    var onAccountBanned: (() -> Unit)? = null

    /**
     * Invoked when an authenticated request is rejected because the account's
     * email address is unverified. The session can't do anything until the
     * emailed link is used, so it is dropped like a ban.
     */
    @Volatile
    var onEmailNotVerified: (() -> Unit)? = null
    
    @Volatile
    private var realService: PositiveOnlySocialAPI? = null


    /**
     * Returns the API service.
     * Note: The 'baseUrl' is only used if the service has not been created yet,
     * or if it was recently reset.
     */
    fun returnGoodVibesOnlyAPI(baseUrl: String, isUITesting: Boolean = false): PositiveOnlySocialAPI {
        // 1. Check Debug configurations
        if (Constants.isUnitTesting || isUITesting || this.isUITesting) {
            return stubbedService
        }

        // 2. Return existing instance if it exists
        val currentService = realService
        if (currentService != null) {
            return currentService
        }

        // 3. Create instance safely if it doesn't exist
        return synchronized(this) {
            realService ?: createRetrofitService(baseUrl).also {
                realService = it
            }
        }
    }

    /**
     * Resets the cached service instance.
     * Call this if the Base URL needs to change at runtime.
     */
    fun resetService() {
        synchronized(this) {
            realService = null
        }
    }

    private fun createRetrofitService(url: String): PositiveOnlySocialAPI {
        val client = OkHttpClient.Builder()
            // Creating a post waits on server-side AI classification, so the
            // read timeout must comfortably exceed that work; otherwise a slow
            // (but successful) request is dropped client-side as a timeout. The
            // defaults (10s) are too tight for that path.
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val original = chain.request()
                val authHeader = original.header("Authorization")
                val request = if (authHeader != null && !authHeader.startsWith("Bearer ")) {
                    original.newBuilder()
                        .header("Authorization", "Bearer $authHeader")
                        .build()
                } else {
                    original
                }
                val response = chain.proceed(request)
                if (response.code == 403 && request.header("Authorization") != null) {
                    // Peek so the body stays readable for the Retrofit consumer.
                    val errorCode = try {
                        JSONObject(response.peekBody(1024).string()).getString("error")
                    } catch (e: Exception) {
                        null
                    }
                    when (errorCode) {
                        Constants.ACCOUNT_BANNED -> onAccountBanned?.invoke()
                        Constants.EMAIL_NOT_VERIFIED -> onEmailNotVerified?.invoke()
                    }
                }
                response
            }
            .build()
        return Retrofit.Builder()
            .baseUrl(url)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(PositiveOnlySocialAPI::class.java)
    }

    private val isUITesting: Boolean
        get() {
            if (BuildConfig.DEBUG) return true
            return (Build.FINGERPRINT.startsWith("generic")
                    || Build.FINGERPRINT.startsWith("unknown")
                    || Build.MODEL.contains("google_sdk")
                    || Build.MODEL.contains("Emulator")
                    || Build.MODEL.contains("Android SDK built for x86")
                    || Build.BOARD == "QC_Reference_Phone" // bluestacks
                    || Build.MANUFACTURER.contains("Genymotion")
                    || Build.HOST.startsWith("Build") // MSI App Player
                    || (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic"))
                    || "google_sdk" == Build.PRODUCT)
        }
}
