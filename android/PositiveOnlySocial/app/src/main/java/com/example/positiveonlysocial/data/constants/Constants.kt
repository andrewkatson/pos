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

    // Error code the backend returns when the account's email address is unverified.
    const val EMAIL_NOT_VERIFIED = "email_not_verified"
    const val EMAIL_NOT_VERIFIED_MESSAGE =
        "Please verify your email address first — check your inbox for the verification link."

    // Error the backend returns from login/2fa/ when the challenge is gone
    // (expired or already used). The login screen matches on it to drop back to
    // the password form; kept here so the coupling to the backend string is in
    // one place rather than inline. Mirrors login_user_2fa in the backend.
    const val INVALID_OR_EXPIRED_CHALLENGE = "Invalid or expired challenge"

    const val PRIVACY_POLICY_TEXT =
        "We collect your username, email address, and password for authentication; your password is stored as a salted hash, never in plain text. We do not store your date of birth itself, only whether you are an adult and whether your identity has been verified, derived from it at signup. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment, and the IP address of your login sessions and known devices so we can alert you to logins from a new device."
}