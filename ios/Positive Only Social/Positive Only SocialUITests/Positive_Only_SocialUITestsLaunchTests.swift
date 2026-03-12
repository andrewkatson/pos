//
//  Positive_Only_SocialUITestsLaunchTests.swift
//  Positive Only SocialUITests
//
//  Created by Andrew Katson on 8/29/25.
//

import XCTest

final class Positive_Only_SocialUITestsLaunchTests: XCTestCase {

    override class var runsForEachTargetApplicationUIConfiguration: Bool {
        true
    }

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testLaunch() throws {
        let app = XCUIApplication()
        
        // get the name and remove the opening
        var baseName = self.name.replacingOccurrences(of: "-[", with: "")

        // And then you'll need to remove the closing square bracket at the end of the test name
        baseName = baseName.replacingOccurrences(of: "]", with: "")
        
        app.launchArguments.append("--ui_testing")
        app.launchEnvironment["test-name"] = baseName
        app.launch()

        // Insert steps here to perform after app launch but before taking a screenshot,
        // such as logging into a test account or navigating somewhere in the app

        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Launch Screen"
        attachment.lifetime = .keepAlways
        add(attachment)

        app.terminate()
    }
}
