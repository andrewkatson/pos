/**
 * Version of the privacy policy below *and* the terms of service
 * (termsOfService.ts), as the date of the last material change to either. Sent
 * as `policy_version` whenever the user agrees to them, so the backend records
 * the version this build actually showed. Bump it with any material change to
 * either text, together with POLICY_VERSION in backend/user_system/constants.py
 * and the iOS and Android copies.
 */
export const POLICY_VERSION = '2026-08-13'

export const PRIVACY_POLICY_TEXT =
  'We collect your username, email address, and password for authentication; your password is stored as a salted hash, never in plain text. We do not store your date of birth itself, only whether you are an adult and whether your identity has been verified, derived from it at signup. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment, and the IP address of your login sessions and known devices so we can alert you to logins from a new device.'
