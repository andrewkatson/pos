//
//  Config.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

struct Config {
    
    static let _api : APIProtocol = UITesting() ? StatefulStubbedAPI() : RealAPI()
    
    static var api: APIProtocol {
        get {
            return _api
        }
    }
}

private func UITesting() -> Bool {
    return ProcessInfo.processInfo.arguments.contains("UI-TESTING") || CommandLine.arguments.contains("UI-TESTING")
}
