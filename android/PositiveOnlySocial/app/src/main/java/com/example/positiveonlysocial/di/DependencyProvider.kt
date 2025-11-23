package com.example.positiveonlysocial.di

import android.content.Context
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.security.KeychainHelper
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol

object DependencyProvider {

    private var appContext: Context? = null

    // 1. Call this method once in your Application class
    fun initialize(context: Context) {
        // Crucial: Use .applicationContext to prevent memory leaks!
        this.appContext = context.applicationContext
    }

    val api: PositiveOnlySocialAPI by lazy {
        StatefulStubbedAPI()
    }

    val keychainHelper: KeychainHelperProtocol by lazy {
        // 2. Check if context is available before using it
        val context = appContext ?: throw IllegalStateException("DependencyProvider.initialize(context) must be called before accessing properties.")

        KeychainHelper(context)
    }

    val authManager: AuthenticationManager by lazy {
        AuthenticationManager(keychainHelper)
    }
}
