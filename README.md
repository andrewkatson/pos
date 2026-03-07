# POS
[![Android Tests](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/android-tests.yml)
[![iOS Tests](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/ios-tests.yml)
[![Backend Tests](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/andrewkatson/pos/actions/workflows/backend-tests.yml)

Good Vibes Only Social

Social media site that only allows "positive" text and image posts. The guidelines are as follows.

1. No swear words
2. No nudity
3. No gore
4. No hate speech
5. No harassment
6. No bullying

These will be updated as time goes on.

## Known Failing Tests

The following iOS UI tests are currently failing (as of CI run [22808882962](https://github.com/andrewkatson/pos/actions/runs/22808882962/job/66162377482)):

- `Positive_Only_SocialUITests.testLikeAndUnlikeCommentOnPostAndThread()`
- `Positive_Only_SocialUITests.testFollowAndUnfollowFromSearch()`
- `Positive_Only_SocialUITests.testResetPassword()`
- `Positive_Only_SocialUITests.testVerifyIdentity()`
- `Positive_Only_SocialUITests.testBlockAndUnblockUser()`
- `Positive_Only_SocialUITests.testReportPost()`
- `Positive_Only_SocialUITests.testFollowAndUnfollowFromPost()`
- `Positive_Only_SocialUITests.testDeleteAccount()`
- `Positive_Only_SocialUITests.testLikeAndUnlikePost()`
- `Positive_Only_SocialUITests.testReportComment()`
