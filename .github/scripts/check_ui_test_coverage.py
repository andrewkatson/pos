#!/usr/bin/env python3
"""Fail if any iOS UI test is not scheduled by the CI matrix.

The iOS workflow schedules UI tests by naming each one individually in
`-only-testing:` entries, split across matrix groups. That gives us control
over how long each group runs, but it is silent when it drifts: a test added
to the Swift file simply never runs, and nothing reports it. Three tests were
found that way (testChangePassword, testEnableTwoFactorAuthentication and the
whole Positive_Only_SocialUITestsLaunchTests class), the oldest of which had
been dormant for months.

This closes that hole from the other side: it compares what the Swift files
declare against what the workflow schedules, and fails the build on any
mismatch in either direction — a test that is never run, or an entry naming a
test that no longer exists.
"""

import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ios-tests.yml"
UI_TEST_DIR = REPO / "ios" / "Positive Only Social" / "Positive Only SocialUITests"
UI_TARGET = "Positive Only SocialUITests"


def strip_comments(src):
    """Blank out comments, preserving offsets so positions stay comparable.

    Without this, prose containing the word "class" is parsed as a declaration
    - this file's own sources contain the phrase "between class name and method
    name", which was enough to attribute every test to a class called "name".
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        two = src[i : i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            # Keep newlines so line-based reasoning elsewhere still works.
            out.append("".join(c if c == "\n" else " " for c in src[i:j]))
            i = j
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def declared_tests():
    """Every `Target/Class/method` the UI test sources define."""
    found = set()
    # rglob, not glob: Xcode groups often become real subdirectories, and a
    # check that silently ignores them would recreate the very hole it exists
    # to close.
    for path in sorted(UI_TEST_DIR.rglob("*.swift")):
        src = strip_comments(path.read_text(encoding="utf-8"))
        # Track where every class starts, so methods are attributed to the right
        # one when a file declares more than one. Deliberately not keyed on
        # ": XCTestCase" - a class extending a shared base (class FooTests:
        # BaseUITestCase) is still a test class, and keying on the direct
        # superclass would make every test inside it invisible to this check the
        # day someone extracts such a base.
        #
        # Anchored on the opening brace of the declaration so that `class` used
        # as a member modifier (`override class var foo: Bool {`) is not mistaken
        # for a type declaration named "var".
        classes = [
            (m.start(), m.group(1))
            for m in re.finditer(r"\bclass\s+(\w+)\s*(?::[^{]*?)?\{", src)
        ]
        if not classes:
            continue
        # Require an empty parameter list: XCTest only collects no-argument
        # test methods, so this keeps a helper like `testHelper(for:)` from
        # being reported as a test that is never scheduled.
        for m in re.finditer(r"\bfunc\s+(test\w*)\s*\(\s*\)", src):
            enclosing = [name for start, name in classes if start < m.start()]
            if enclosing:
                found.add(f"{UI_TARGET}/{enclosing[-1]}/{m.group(1)}")
    return found


def scheduled_tests():
    """Every UI test the workflow names, in order, keeping duplicates.

    A list rather than a set: the same test named in two groups would run
    twice, quietly paying for itself again on a job whose whole point is
    runtime. That is invisible to a set-based comparison.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    return re.findall(rf'"({re.escape(UI_TARGET)}/\w+/\w+)"', text)


def main():
    declared = declared_tests()
    scheduled = scheduled_tests()
    scheduled_set = set(scheduled)

    if not declared:
        print(f"error: no UI tests found under {UI_TEST_DIR} - has the layout moved?")
        return 1

    counts = Counter(scheduled)
    unscheduled = sorted(declared - scheduled_set)
    stale = sorted(scheduled_set - declared)
    duplicated = sorted(name for name, n in counts.items() if n > 1)

    for name in unscheduled:
        print(f"error: {name} is never run - add it to a test-group in ios-tests.yml")
    for name in stale:
        print(f"error: {name} is scheduled but no longer exists - remove it from ios-tests.yml")
    for name in duplicated:
        print(
            f"error: {name} is scheduled {counts[name]} times - "
            "it would run once per group; leave it in only one"
        )

    if unscheduled or stale or duplicated:
        print(
            f"\n{len(declared)} UI tests declared, {len(scheduled)} scheduled "
            f"({len(scheduled_set)} distinct). "
            "Every UI test must appear in exactly one matrix group."
        )
        return 1

    print(f"All {len(declared)} UI tests are scheduled exactly once by the matrix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
