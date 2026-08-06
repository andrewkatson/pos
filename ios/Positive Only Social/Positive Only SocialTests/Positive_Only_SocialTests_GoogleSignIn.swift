//
//  Positive_Only_SocialTests_GoogleSignIn.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// Tests for the stateless halves of the Google sign-in flow (issue #10): the
/// PKCE parameters, the authorization URL, the callback parsing, and the token
/// exchange. The ASWebAuthenticationSession part is deliberately untested here —
/// it is a system sheet with nothing of ours in it.
struct Positive_Only_SocialTests_GoogleSignIn {

    private static let clientID = "123456-abcdef.apps.googleusercontent.com"
    private static let reversed = "com.googleusercontent.apps.123456-abcdef"

    // MARK: - Reversed client ID

    @Test func testReversedClientID_ReversesTheGoogleSuffix() {
        #expect(GoogleOAuth.reversedClientID(for: Self.clientID) == Self.reversed)
    }

    @Test func testReversedClientID_RejectsSomethingThatIsNotAGoogleClientID() {
        #expect(GoogleOAuth.reversedClientID(for: "not-a-client-id") == nil)
        #expect(GoogleOAuth.reversedClientID(for: "") == nil)
        // A bare suffix has no identifier in front of it to reverse.
        #expect(GoogleOAuth.reversedClientID(for: ".apps.googleusercontent.com") == nil)
    }

    // MARK: - PKCE

    @Test func testCodeVerifier_IsUnguessableAndUrlSafe() {
        let first = GoogleOAuth.makeCodeVerifier()
        let second = GoogleOAuth.makeCodeVerifier()

        #expect(first != second)
        // RFC 7636 requires 43-128 characters from the unreserved set. 32 random
        // bytes base64url-encode to 43.
        #expect(first.count >= 43)
        let allowed = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        #expect(first.unicodeScalars.allSatisfy { allowed.contains($0) })
    }

    @Test func testCodeChallenge_IsTheS256OfTheVerifier() {
        // RFC 7636 Appendix B's worked example, so this pins the actual
        // algorithm rather than just "some hash of the input".
        let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        #expect(GoogleOAuth.codeChallenge(for: verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    }

    @Test func testCodeChallenge_IsStableForTheSameVerifier() {
        let verifier = GoogleOAuth.makeCodeVerifier()
        #expect(GoogleOAuth.codeChallenge(for: verifier) == GoogleOAuth.codeChallenge(for: verifier))
    }

    // MARK: - Authorization request

    @Test func testAuthorizationRequest_CarriesEverythingGoogleNeeds() throws {
        let request = try #require(GoogleOAuth.authorizationRequest(clientID: Self.clientID))
        let components = try #require(URLComponents(url: request.url, resolvingAgainstBaseURL: false))
        let items = try #require(components.queryItems)
        func value(_ name: String) -> String? { items.first { $0.name == name }?.value }

        #expect(components.host == "accounts.google.com")
        #expect(value("client_id") == Self.clientID)
        #expect(value("response_type") == "code")
        #expect(value("scope") == "openid email")
        #expect(value("code_challenge_method") == "S256")
        #expect(value("code_challenge") == GoogleOAuth.codeChallenge(for: request.codeVerifier))
        #expect(value("state") == request.state)
        #expect(value("redirect_uri") == request.redirectURI)
        // A replayed nonce would let a captured ID token be reused.
        #expect(value("nonce")?.isEmpty == false)
    }

    @Test func testAuthorizationRequest_RedirectsToTheReversedClientIdScheme() throws {
        let request = try #require(GoogleOAuth.authorizationRequest(clientID: Self.clientID))
        #expect(request.callbackScheme == Self.reversed)
        #expect(request.redirectURI == Self.reversed + ":/oauth2redirect")
    }

    @Test func testAuthorizationRequest_IsNilWithoutAUsableClientID() {
        #expect(GoogleOAuth.authorizationRequest(clientID: "") == nil)
    }

    @Test func testAuthorizationRequest_UsesAFreshVerifierEachTime() throws {
        let first = try #require(GoogleOAuth.authorizationRequest(clientID: Self.clientID))
        let second = try #require(GoogleOAuth.authorizationRequest(clientID: Self.clientID))
        #expect(first.codeVerifier != second.codeVerifier)
        #expect(first.state != second.state)
    }

    // MARK: - Callback parsing

    @Test func testAuthorizationCode_IsReadFromAMatchingCallback() throws {
        let url = URL(string: "\(Self.reversed):/oauth2redirect?code=auth-code&state=expected")!
        #expect(try GoogleOAuth.authorizationCode(from: url, expectedState: "expected") == "auth-code")
    }

    @Test func testAuthorizationCode_RejectsAMismatchedState() {
        // The CSRF defence: a callback we did not start must never be exchanged.
        let url = URL(string: "\(Self.reversed):/oauth2redirect?code=auth-code&state=somebody-elses")!
        #expect(throws: GoogleSignInError.invalidCallback) {
            try GoogleOAuth.authorizationCode(from: url, expectedState: "expected")
        }
    }

    @Test func testAuthorizationCode_RejectsACallbackWithNoCode() {
        let url = URL(string: "\(Self.reversed):/oauth2redirect?state=expected")!
        #expect(throws: GoogleSignInError.invalidCallback) {
            try GoogleOAuth.authorizationCode(from: url, expectedState: "expected")
        }
    }

    @Test func testAuthorizationCode_TreatsADeclinedConsentAsACancellation() {
        // Declining on Google's screen is a choice, not a failure to report.
        let url = URL(string: "\(Self.reversed):/oauth2redirect?error=access_denied&state=expected")!
        #expect(throws: GoogleSignInError.cancelled) {
            try GoogleOAuth.authorizationCode(from: url, expectedState: "expected")
        }
    }

    @Test func testAuthorizationCode_SurfacesOtherGoogleErrors() {
        let url = URL(string: "\(Self.reversed):/oauth2redirect?error=invalid_request&state=expected")!
        #expect(throws: GoogleSignInError.tokenExchangeFailed("invalid_request")) {
            try GoogleOAuth.authorizationCode(from: url, expectedState: "expected")
        }
    }

    // MARK: - Token exchange

    @Test func testTokenRequest_PostsTheCodeAndVerifierAndNoSecret() throws {
        let request = try #require(GoogleOAuth.tokenRequest(
            clientID: Self.clientID, code: "auth-code", codeVerifier: "verifier", redirectURI: "scheme:/redirect"
        ))

        #expect(request.url?.absoluteString == GoogleOAuth.tokenEndpoint)
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/x-www-form-urlencoded")

        let body = String(data: try #require(request.httpBody), encoding: .utf8) ?? ""
        #expect(body.contains("grant_type=authorization_code"))
        #expect(body.contains("code=auth-code"))
        #expect(body.contains("code_verifier=verifier"))
        // An installed app is a public OAuth client — PKCE stands in for the
        // secret it could never keep.
        #expect(!body.contains("client_secret"))
    }

    @Test func testIdToken_IsReadFromASuccessfulExchange() throws {
        let data = Data(#"{"id_token":"a.b.c","access_token":"ignored"}"#.utf8)
        #expect(try GoogleOAuth.idToken(fromTokenResponse: data) == "a.b.c")
    }

    @Test func testIdToken_ReportsGooglesDescriptionOfAFailure() {
        let data = Data(#"{"error":"invalid_grant","error_description":"Bad Request"}"#.utf8)
        #expect(throws: GoogleSignInError.tokenExchangeFailed("Bad Request")) {
            try GoogleOAuth.idToken(fromTokenResponse: data)
        }
    }

    @Test func testIdToken_RejectsAResponseWithNoTokenAtAll() {
        let data = Data(#"{"access_token":"only-this"}"#.utf8)
        #expect(throws: (any Error).self) {
            try GoogleOAuth.idToken(fromTokenResponse: data)
        }
    }

    @Test func testIdToken_RejectsAnEmptyToken() {
        let data = Data(#"{"id_token":""}"#.utf8)
        #expect(throws: (any Error).self) {
            try GoogleOAuth.idToken(fromTokenResponse: data)
        }
    }

    // MARK: - Provider configuration

    @Test func testProvider_IsNotConfiguredWithoutAClientID() {
        // An unconfigured build hides the button rather than showing one that
        // could only ever fail.
        #expect(GoogleSignInProvider(clientID: "").isConfigured == false)
        #expect(GoogleSignInProvider(clientID: "   ").isConfigured == false)
    }

    @Test func testProvider_IsConfiguredWithAGoogleClientID() {
        #expect(GoogleSignInProvider(clientID: Self.clientID).isConfigured == true)
    }

    @Test func testProvider_RefusesToSignInWhenUnconfigured() async {
        await #expect(throws: GoogleSignInError.notConfigured) {
            try await GoogleSignInProvider(clientID: "").signIn()
        }
    }

    // MARK: - UI-test stub

    @Test func testStubbedProvider_ReturnsATokenTheStubbedApiCanRead() async throws {
        let token = try await StubbedGoogleSignIn(email: "stubperson@example.com").signIn()
        let claims = try #require(StatefulStubbedAPI.decodeIdTokenClaims(token))

        #expect(claims.sub == "stub-google-sub")
        #expect(claims.email == "stubperson@example.com")
        #expect(claims.email_verified == true)
    }
}

/// Tests for the stubbed API's Google sign-in, which is what UI tests and the
/// offline/demo build actually run. It has to make the same decisions as
/// login_user_google in backend/user_system/views.py, or the two drift.
struct Positive_Only_SocialTests_StubbedGoogleLogin {

    /// An unsigned token carrying the claims the stub reads. Not a credential —
    /// the real backend would reject it outright.
    private func idToken(sub: String, email: String, emailVerified: Bool = true) -> String {
        let header = GoogleOAuth.base64URLEncode(Data(#"{"alg":"none"}"#.utf8))
        let claims = "{\"sub\":\"\(sub)\",\"email\":\"\(email)\",\"email_verified\":\(emailVerified)}"
        return "\(header).\(GoogleOAuth.base64URLEncode(Data(claims.utf8))).sig"
    }

    private func decodeLogin(_ data: Data) throws -> LoginResponseFields {
        try JSONDecoder().decode(LoginResponseFields.self, from: data)
    }

    @Test func testFirstSignInCreatesAnAccountAndASession() async throws {
        let api = StatefulStubbedAPI()
        let data = try await api.loginWithGoogle(
            idToken: idToken(sub: "sub-1", email: "hopefulperson@example.com"),
            rememberMe: "false", ip: "127.0.0.1"
        )
        let login = try decodeLogin(data)

        #expect(login.createdAccount == true)
        #expect(login.membershipNumber != nil)
        #expect(login.username == "hopefulperson")
        #expect(login.sessionManagementToken.isEmpty == false)
    }

    @Test func testShortLocalPartIsPaddedToAValidUsername() async throws {
        let api = StatefulStubbedAPI()
        let data = try await api.loginWithGoogle(
            idToken: idToken(sub: "sub-1", email: "amy@example.com"), rememberMe: "false", ip: "127.0.0.1"
        )
        // Usernames need at least 10 word characters, matching the backend.
        let username = try #require(try decodeLogin(data).username)
        #expect(username.hasPrefix("amy"))
        #expect(username.count >= 10)
    }

    @Test func testSecondSignInReusesTheSameAccount() async throws {
        let api = StatefulStubbedAPI()
        let token = idToken(sub: "sub-1", email: "hopefulperson@example.com")

        let first = try decodeLogin(try await api.loginWithGoogle(idToken: token, rememberMe: "false", ip: "127.0.0.1"))
        let second = try decodeLogin(try await api.loginWithGoogle(idToken: token, rememberMe: "false", ip: "127.0.0.1"))

        #expect(first.userId == second.userId)
        #expect(second.createdAccount == false)
        #expect(second.membershipNumber == nil)
    }

    @Test func testAChangedEmailStillFindsTheAccountByItsGoogleSub() async throws {
        let api = StatefulStubbedAPI()
        let first = try decodeLogin(try await api.loginWithGoogle(
            idToken: idToken(sub: "sub-1", email: "hopefulperson@example.com"), rememberMe: "false", ip: "127.0.0.1"
        ))
        let second = try decodeLogin(try await api.loginWithGoogle(
            idToken: idToken(sub: "sub-1", email: "renamedmailbox@example.com"), rememberMe: "false", ip: "127.0.0.1"
        ))

        #expect(first.userId == second.userId)
    }

    @Test func testAMatchingEmailLinksToTheExistingAccount() async throws {
        let api = StatefulStubbedAPI()
        let registered = try decodeLogin(try await api.register(
            username: "existingperson", email: "sharedaddress@example.com", password: "Password123",
            rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1990-01-01",
            interestCategories: [], interestFreeform: []
        ))

        let google = try decodeLogin(try await api.loginWithGoogle(
            idToken: idToken(sub: "sub-1", email: "SharedAddress@example.com"), rememberMe: "false", ip: "127.0.0.1"
        ))

        #expect(google.userId == registered.userId)
        #expect(google.createdAccount == false)
    }

    @Test func testRememberMeReturnsCookieTokens() async throws {
        let api = StatefulStubbedAPI()
        let login = try decodeLogin(try await api.loginWithGoogle(
            idToken: idToken(sub: "sub-1", email: "hopefulperson@example.com"), rememberMe: "true", ip: "127.0.0.1"
        ))

        #expect(login.seriesIdentifier != nil)
        #expect(login.loginCookieToken != nil)
    }

    @Test func testAnUnverifiedGoogleEmailIsRefused() async throws {
        let api = StatefulStubbedAPI()
        await #expect(throws: (any Error).self) {
            _ = try await api.loginWithGoogle(
                idToken: idToken(sub: "sub-1", email: "unverified@example.com", emailVerified: false),
                rememberMe: "false", ip: "127.0.0.1"
            )
        }
    }

    @Test func testAMalformedTokenIsRefused() async throws {
        let api = StatefulStubbedAPI()
        await #expect(throws: (any Error).self) {
            _ = try await api.loginWithGoogle(idToken: "not-a-jwt", rememberMe: "false", ip: "127.0.0.1")
        }
    }
}
