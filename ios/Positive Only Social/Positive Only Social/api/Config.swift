//
//  Config.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

struct Config {

    static let _api : Networking = isUITesting() ? StatefulStubbedAPI() : RealAPI()

    static var api: Networking {
        get {
            return _api
        }
    }

    // Google sign-in (issue #10). Under UI tests there is no real consent
    // screen to drive, so the stub hands back a token the stubbed API decodes —
    // the same swap `api` above makes.
    static let _googleSignIn: GoogleSignInProviding = isUITesting() ? StubbedGoogleSignIn() : GoogleSignInProvider()

    static var googleSignIn: GoogleSignInProviding {
        get {
            return _googleSignIn
        }
    }
}

func isUnitTesting() -> Bool {
    // 3. It's a Unit Test if (1) is true and (2) is false
    return isTesting() && !isUITesting()
}

func isTesting() -> Bool {
    // 1. Check if ANY test is running // We removed the simulator bool so we can test images that are not fakes. 
    return ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil ||   ProcessInfo.processInfo.environment["XCODE_TEST_PLAN_NAME"] != nil
}

func isUITesting() -> Bool {
    return CommandLine.arguments.contains("--ui_testing")
}
