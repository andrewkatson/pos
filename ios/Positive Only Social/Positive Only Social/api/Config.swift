//
//  Config.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

struct Config {
    
    static let _api : APIProtocol = isUITesting() ? StatefulStubbedAPI() : RealAPI()
    
    static var api: APIProtocol {
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
    return ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil
}

func isUITesting() -> Bool {
    // 2. Check if a UI Test is running
    return CommandLine.arguments.contains("-ui_testing")
}
