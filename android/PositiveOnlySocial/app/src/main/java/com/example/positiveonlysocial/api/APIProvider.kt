package com.example.positiveonlysocial.api

import android.os.Build
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.BuildConfig

object APIProvider {

    private val stubbedService = StatefulStubbedAPI()
    
    @Volatile
    private var realService: PositiveOnlySocialAPI? = null


    /**
     * Returns the API service.
     * Note: The 'baseUrl' is only used if the service has not been created yet,
     * or if it was recently reset.
     */
    fun returnDenariiService(baseUrl: String): PositiveOnlySocialAPI {
        // 1. Check Debug configurations
        if (Constants.isUnitTesting || isUITesting) {
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
        return Retrofit.Builder()
            .baseUrl(url)
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
