//
//  TestConstants.swift
//  Positive Only Social
//

import Foundation

/// Centralized timeout constants used across all unit and UI tests.
enum TestConstants {
    /// 3 seconds — element existence checks and simple UI state transitions.
    static let shortTimeout: TimeInterval = 3
    /// 10 seconds — async reload cycles and network-dependent UI updates.
    static let timeout: TimeInterval = 10
    /// 30 seconds — heavyweight operations such as app launch or multi-step flows.
    static let longTimeout: TimeInterval = 30
}
