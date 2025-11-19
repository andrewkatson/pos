package com.example.positiveonlysocial

import android.app.Application
import com.example.positiveonlysocial.data.uploader.AWSManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Custom Application class.
 * This is the entry point of your app.
 */
class PositiveOnlySocialApp : Application() {
    override fun onCreate() {
        super.onCreate()

        CoroutineScope(Dispatchers.IO).launch {
            AWSManager.initialize()
        }
    }
}