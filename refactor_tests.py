import sys
import re

path = "/Users/andrewkatson/pos/ios/Positive Only Social/Positive Only SocialUITests/Positive_Only_SocialUITests.swift"
with open(path, "r") as f:
    content = f.read()

# 1. Add class variable
content = re.sub(r'(final class Positive_Only_SocialUITests: XCTestCase \{\n\s+)(var testUsername: String = "")', r'\1var app: XCUIApplication!\n    \2', content)

# 2. Modify setUpWithError
content = re.sub(
    r'(continueAfterFailure = false)',
    r'\1\n        \n        app = XCUIApplication()\n        app.launchArguments.append("--ui_testing")\n        app.launch()',
    content,
    count=1
)

# 3. Remove boilerplate
# We match optional whitespace and newlines leading up to it
boilerplate = r'\n[ \t]*// UI tests must launch the application that they test\.\n[ \t]*let app = XCUIApplication\(\)\n[ \t]*app\.launchArguments\.append\("--ui_testing"\)\n[ \t]*\n[ \t]*app\.launch\(\)\n*'
content = re.sub(boilerplate, '\n', content)

# 4. Remove all app.terminate()
content = re.sub(r'\n[ \t]*app\.terminate\(\)', '', content)

# 5. Add app.terminate() back to tearDownWithError
content = content.replace('XCUIApplication().terminate()', 'app.terminate()')

# 6. Handle testLaunchPerformance (removing local let app =)
perf_boilerplate = r'\n[ \t]*let app = XCUIApplication\(\)\n[ \t]*app\.launch\(\)'
content = re.sub(perf_boilerplate, '\n            app.launch()', content)

with open(path, "w") as f:
    f.write(content)

print("Done")
