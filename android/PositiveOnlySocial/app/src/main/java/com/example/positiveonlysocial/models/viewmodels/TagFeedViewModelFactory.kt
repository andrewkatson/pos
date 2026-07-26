package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol

class TagFeedViewModelFactory(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val tag: String,
    private val account: String = "userSessionToken"
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(TagFeedViewModel::class.java)) {
            return TagFeedViewModel(api, keychainHelper, tag, account) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
