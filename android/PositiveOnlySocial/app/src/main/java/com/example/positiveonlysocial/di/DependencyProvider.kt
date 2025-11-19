package com.example.positiveonlysocial.di

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.security.KeychainHelper
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol

object DependencyProvider {
    val api: PositiveOnlySocialAPI by lazy {
        StatefulStubbedAPI()
    }

    val keychainHelper: KeychainHelperProtocol by lazy {
        KeychainHelper()
    }

    val authManager: com.example.positiveonlysocial.data.auth.AuthenticationManager by lazy {
        com.example.positiveonlysocial.data.auth.AuthenticationManager(keychainHelper)
    }
}
