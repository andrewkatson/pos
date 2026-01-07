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
}

func isUnitTesting() -> Bool {
    // 3. It's a Unit Test if (1) is true and (2) is false
    return isTesting() && !isUITesting()
}

func isTesting() -> Bool {
    // 1. Check if ANY test is running
    return ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil ||  ProcessInfo.processInfo.environment["TESTMANAGERD_SIM_SOCK"] != nil || ProcessInfo.processInfo.environment["XCODE_TEST_PLAN_NAME"] != nil
}

func isUITesting() -> Bool {
    return CommandLine.arguments.contains("--ui_testing")
}
