package com.example.positiveonlysocial.data.security

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.Gson
import java.io.IOException
import java.security.GeneralSecurityException
import java.security.KeyStore
import androidx.core.content.edit

private const val TAG = "KeychainHelper"

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

    private val appContext = context.applicationContext

    // A single, hardcoded file name for all secure preferences.
    // The 'service' and 'account' params will be used to create unique *keys*
    // inside this one encrypted file.
    //
    // Kept in sync with the <exclude> entries in res/xml/backup_rules.xml and
    // res/xml/data_extraction_rules.xml, which keep this file (and only this
    // file) out of cloud backup and device-to-device transfer. Those entries
    // name the file as it lands on disk — "positive_only_social_secure_prefs.xml",
    // this value plus the .xml suffix SharedPreferences appends — so renaming
    // here means renaming there too, suffix included.
    private val prefsFilename = "positive_only_social_secure_prefs"

    private val encryptedPrefs: SharedPreferences by lazy { openEncryptedPrefs() }

    private fun createEncryptedPrefs(): SharedPreferences {
        // 1. Create the Master Key from the Android Keystore
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        // 2. Create the EncryptedSharedPreferences instance
        return EncryptedSharedPreferences.create(
            appContext,
            prefsFilename,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    /**
     * Opens the encrypted store, discarding and rebuilding it if the existing
     * one can't be read (issue #503).
     *
     * The store is only openable while the AndroidKeyStore still holds the
     * master key that encrypted it. That pairing breaks when the file outlives
     * the key — a backup restored onto a new device, a keystore entry
     * invalidated by a lock-screen credential reset, a vendor keystore that
     * loses entries across an update. When it does, *every* open throws, so the
     * app can no longer read or write a session and each screen silently
     * renders nothing.
     *
     * Recovery deliberately throws the contents away rather than trying to
     * salvage them: undecryptable ciphertext has no salvage path, and what is
     * stored here is a session token and remember-me tokens, so the whole cost
     * of being wrong is one sign-in. Being wrong the other way — leaving the
     * store unopenable — bricks the app until the user clears its data.
     *
     * Catching broadly is deliberate for the same reason. Tink surfaces a
     * damaged keyset as several unrelated types (an [IOException] subclass, a
     * [GeneralSecurityException], or a plain [RuntimeException] out of the
     * keystore), and there is no benefit to staying wedged on the ones we
     * failed to enumerate.
     */
    private fun openEncryptedPrefs(): SharedPreferences = try {
        createEncryptedPrefs()
    } catch (e: Exception) {
        Log.w(TAG, "Secure storage is unreadable; discarding it and starting fresh", e)
        discardUnreadableStore()
        // Not caught: if a store we just deleted still can't be created, the
        // device's keystore is broken in a way we can't paper over, and the
        // callers report it rather than pretending the write succeeded.
        createEncryptedPrefs()
    }

    /**
     * Removes both halves of the broken pairing: the preferences file (which
     * also holds Tink's data keysets) and the master key that encrypts them.
     * Each step is independently best-effort — a partial cleanup still leaves
     * [createEncryptedPrefs] a consistent pair to rebuild from.
     */
    private fun discardUnreadableStore() {
        try {
            appContext.deleteSharedPreferences(prefsFilename)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to delete $prefsFilename", e)
        }
        try {
            KeyStore.getInstance("AndroidKeyStore")
                .apply { load(null) }
                .deleteEntry(MasterKey.DEFAULT_MASTER_KEY_ALIAS)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to delete the master key", e)
        }
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