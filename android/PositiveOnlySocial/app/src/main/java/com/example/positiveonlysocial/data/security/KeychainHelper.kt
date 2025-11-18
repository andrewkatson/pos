package com.example.positiveonlysocial.data.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.Gson
import java.io.IOException
import java.security.GeneralSecurityException
import androidx.core.content.edit

/**
 * Kotlin equivalent of the KeychainHelperProtocol.
 * Provides an interface for secure, persistent storage of small data.
 */
interface KeychainHelperProtocol {
    /**
     * Securely saves a value.
     * @param value The object to save. It will be serialized to JSON.
     * @param service A string identifying the service (e.g., "app-main").
     * @param account A string identifying the key (e.g., "sessionToken").
     * @throws GeneralSecurityException if encryption fails.
     * @throws IOException if writing to disk fails.
     */
    @Throws(GeneralSecurityException::class, IOException::class, Exception::class)
    fun <T> save(value: T, service: String, account: String)

    /**
     * Loads a securely-stored value.
     * @param type The Class of the object to deserialize (e.g., String::class.java).
     * @param service The service identifier used when saving.
     * @param account The account identifier used when saving.
     * @return The deserialized object, or `null` if not found.
     * @throws GeneralSecurityException if decryption fails.
     * @throws IOException if reading from disk fails.
     */
    @Throws(GeneralSecurityException::class, IOException::class, Exception::class)
    fun <T> load(type: Class<T>, service: String, account: String): T?

    /**
     * Deletes a securely-stored value.
     * @param service The service identifier used when saving.
     * @param account The account identifier used when saving.
     * @throws GeneralSecurityException if encryption fails.
     * @throws IOException if writing to disk fails.
     */
    @Throws(GeneralSecurityException::class, IOException::class, Exception::class)
    fun delete(service: String, account: String)
}

/**
 * Android implementation of [KeychainHelperProtocol] using [EncryptedSharedPreferences].
 *
 * This class is the idiomatic Android equivalent of the iOS Keychain helper.
 * It uses the Android Keystore to create a master key, which is then used to encrypt
 * all data saved into a SharedPreferences file.
 *
 * Note: [EncryptedSharedPreferences] is already thread-safe, so no external lock is needed.
 *
 * @param context The application context.
 */
class KeychainHelper(context: Context) : KeychainHelperProtocol {

    private val gson = Gson()

    // A single, hardcoded file name for all secure preferences.
    // The 'service' and 'account' params will be used to create unique *keys*
    // inside this one encrypted file.
    private val prefsFilename = "positive_only_social_secure_prefs"

    private val encryptedPrefs: SharedPreferences by lazy {
        // 1. Create the Master Key from the Android Keystore
        val masterKey = MasterKey.Builder(context.applicationContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        // 2. Create the EncryptedSharedPreferences instance
        EncryptedSharedPreferences.create(
            context.applicationContext,
            prefsFilename,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    /**
     * Generates a unique key for the SharedPreferences from the service and account.
     */
    private fun makeKey(service: String, account: String): String {
        return "$service:$account"
    }

    @Throws(Exception::class)
    override fun <T> save(value: T, service: String, account: String) {
        val key = makeKey(service, account)
        val jsonValue = gson.toJson(value)
        encryptedPrefs.edit { putString(key, jsonValue) }
    }

    @Throws(Exception::class)
    override fun <T> load(type: Class<T>, service: String, account: String): T? {
        val key = makeKey(service, account)
        val jsonValue = encryptedPrefs.getString(key, null)

        return if (jsonValue != null) {
            try {
                gson.fromJson(jsonValue, type)
            } catch (e: Exception) {
                // Handle JSON deserialization errors, e.g., if the data model changed
                // Or re-throw if you want the caller to handle it
                null
            }
        } else {
            null
        }
    }

    @Throws(Exception::class)
    override fun delete(service: String, account: String) {
        val key = makeKey(service, account)
        encryptedPrefs.edit { remove(key) }
    }
}