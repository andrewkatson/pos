package com.example.positiveonlysocial

import android.app.Application
import com.example.positiveonlysocial.api.APIProvider
import com.example.positiveonlysocial.data.uploader.AWSManager
import com.example.positiveonlysocial.di.DependencyProvider
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

        DependencyProvider.initialize(this)

        // A banned account has its sessions revoked server-side; drop the
        // local session and let the navigation layer return to Welcome.
        APIProvider.onAccountBanned = {
            CoroutineScope(Dispatchers.IO).launch {
                DependencyProvider.authManager.forceLogout()
            }
        }

        CoroutineScope(Dispatchers.IO).launch {
            AWSManager.initialize()
        }
    }
}