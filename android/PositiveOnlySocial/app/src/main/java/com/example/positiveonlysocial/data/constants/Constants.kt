package com.example.positiveonlysocial.data.constants

object Constants {
    val isUnitTesting = false
    const val BASE_URL = "https://api.smiling.social/user_index/"

    // Maximum lengths for user-authored text, mirroring MAX_CAPTION_LENGTH /
    // MAX_COMMENT_LENGTH in backend/user_system/constants.py.
    const val MAX_CAPTION_LENGTH = 125
    const val MAX_COMMENT_LENGTH = 500

    // Error code the backend returns when the account has an active outright ban.
    const val ACCOUNT_BANNED = "account_banned"
    const val ACCOUNT_SUSPENDED_MESSAGE =
        "Your account has been suspended for violating our community guidelines."
}