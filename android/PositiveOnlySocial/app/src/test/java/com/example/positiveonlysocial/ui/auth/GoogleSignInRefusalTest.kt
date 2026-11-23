package com.example.positiveonlysocial.ui.auth

import com.example.positiveonlysocial.data.constants.Constants
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * How LoginScreen reacts to each login/google/ error code. The one that matters
 * most here is `policy_acceptance_required`: it must open the consent dialog
 * rather than show an error, or a first Google sign-in from the login screen
 * would be stuck with no way to agree to the policies.
 */
class GoogleSignInRefusalTest {

    @Test
    fun `policy acceptance required asks for consent instead of showing an error`() {
        assertEquals(
            GoogleSignInRefusal.NeedsConsent,
            googleSignInRefusal(Constants.POLICY_ACCEPTANCE_REQUIRED)
        )
    }

    @Test
    fun `a ban is still shown as a suspension`() {
        assertEquals(
            GoogleSignInRefusal.Show(Constants.ACCOUNT_SUSPENDED_MESSAGE),
            googleSignInRefusal(Constants.ACCOUNT_BANNED)
        )
    }

    @Test
    fun `google codes map to their copy`() {
        assertEquals(
            GoogleSignInRefusal.Show(Constants.GOOGLE_EMAIL_AMBIGUOUS_MESSAGE),
            googleSignInRefusal(Constants.GOOGLE_EMAIL_AMBIGUOUS)
        )
        assertEquals(
            GoogleSignInRefusal.Show(Constants.GOOGLE_SIGN_IN_FAILED_MESSAGE),
            googleSignInRefusal(Constants.INVALID_GOOGLE_TOKEN)
        )
    }

    @Test
    fun `an unmapped message keeps its own wording`() {
        assertEquals(
            GoogleSignInRefusal.Show("Network error. Please try again."),
            googleSignInRefusal("Network error. Please try again.")
        )
    }
}
