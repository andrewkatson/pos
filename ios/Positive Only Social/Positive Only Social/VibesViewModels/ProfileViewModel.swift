//
//  ProfileViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/20/25.
//

import Foundation
import Combine

@MainActor
class ProfileViewModel: ObservableObject {
    
    // Published properties to drive the UI
    @Published var userPosts: [Post] = []
    @Published var isLoading = false
    @Published private(set) var canLoadMore = true
    @Published var profileDetails: ProfileDetailsResponse?
    @Published var isLoadingProfile = false
    @Published var isBusy = false // For follow/block button actions
    @Published var isFollowing = false
    @Published var isBlocked = false

    // Own profile-photo controls (issue #7). Uploading reuses the post-image
    // presigned flow (createUploadUrl + S3Uploader), then calls setProfilePhoto;
    // the photo is classified asynchronously, so we reload the profile afterward
    // to reflect the new pending/approved state.
    @Published var isUpdatingPhoto = false
    @Published var photoErrorMessage: String?
    private let s3Uploader = S3Uploader()

    // Private state for pagination and API
    private var batch = 0
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    // Reconciling async post classification (issue #282): a short bounded poll
    // runs while any of the *viewer's own* posts is pending, then stops; the
    // ordinary mount/pull-to-refresh reload is the backstop after that. A
    // rejection surfaces once through `reviewNotice`.
    //
    // This lives here rather than in HomeViewModel because the Profile tab's
    // grid is this view model's (issue #347). Only your own posts ever carry a
    // status, so a profile that isn't yours simply never has anything to poll.
    @Published var reviewNotice: String?
    private var statusPollTask: Task<Void, Never>?
    private var statusPollAttempts = 0
    /// ~30s of checks, 3s apart. Internal so tests can shorten the interval.
    var statusPollIntervalSeconds: TimeInterval = 3
    private let statusPollMaxAttempts = 10
    /// At most this many pending posts are polled per round, keeping the
    /// worst case (3 posts every 3s = 60 requests/min) inside the status
    /// endpoint's 120/m per-user rate limit; older pending posts reconcile
    /// on refresh.
    private let statusPollMaxPosts = 3

    let user: User // The user this profile is for
    // The logged-in user's username, loaded once at init for own-profile detection.
    private let currentLoggedInUsername: String?

    // Listens for `.postDeleted` so a post deleted from this grid (or from its
    // detail view) also disappears here, without reloading the whole list.
    private var postDeletedCancellable: AnyCancellable?
    // Listens for `.postCreated` so a brand new post shows up on the signed-in
    // user's own profile grid right away (issue #347).
    private var postCreatedCancellable: AnyCancellable?

    /// Whether this profile belongs to the signed-in user, which hides Follow /
    /// Block and enables the classification poll.
    ///
    /// A missing session must never count as "own": `forCurrentUser` builds a
    /// `User(username: "")` when it can't load one, and an empty-to-empty
    /// comparison would otherwise silently claim an unknown profile as yours.
    var isOwnProfile: Bool {
        guard let currentLoggedInUsername, !currentLoggedInUsername.isEmpty else { return false }
        return user.username == currentLoggedInUsername
    }

    /// The compressed URL for the large header avatar (issue #7). The owner
    /// previews their own not-yet-approved upload immediately; everyone else
    /// (and the owner once approved) sees the live approved photo.
    var headerAvatarUrl: String? {
        if isOwnProfile, let pending = profileDetails?.pendingProfileImageUrl { return pending }
        return profileDetails?.profileImageUrl
    }

    /// The full-resolution fallback for the header avatar. Deliberately the
    /// previously approved photo's original — NOT the pending URL — so if a
    /// pending preview fails to load the owner still sees their live avatar
    /// (which stays visible while a new upload is under review) rather than the
    /// placeholder.
    var headerAvatarOriginalUrl: String? {
        profileDetails?.profileImageOriginalUrl
    }

    /// The owner-only moderation status of the profile photo ("pending",
    /// "rejected", ...), used to show a review/try-again hint. Nil on someone
    /// else's profile.
    var profileImageStatus: String? { profileDetails?.profileImageStatus }

    /// Whether the owner currently has any photo (live or pending), so the
    /// Remove button is offered.
    var hasProfilePhoto: Bool {
        (profileDetails?.profileImageUrl != nil) || (profileDetails?.pendingProfileImageUrl != nil)
    }

    convenience init(user: User, api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(user: user, api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }

    /// Builds the view model for the signed-in user's own profile — the Profile
    /// tab shows the same profile the rest of the app pushes for other users
    /// (issue #347), so it needs the username from the stored session.
    static func forCurrentUser(api: Networking,
                               keychainHelper: KeychainHelperProtocol,
                               account: String = "userSessionToken") -> ProfileViewModel {
        let session = try? keychainHelper.load(UserSession.self, from: GVOAppConstants.keychainService, account: account)
        let user = User(username: session?.username ?? "", identityIsVerified: session?.isIdentityVerified ?? false)
        return ProfileViewModel(user: user, api: api, keychainHelper: keychainHelper, account: account)
    }

    init(user: User, api: Networking, keychainHelper: KeychainHelperProtocol, account: String,
         notificationCenter: NotificationCenter = .default) {
        self.user = user
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
        self.currentLoggedInUsername = try? keychainHelper.load(UserSession.self, from: GVOAppConstants.keychainService, account: account)?.username

        // Drop a deleted post from the grid rather than reloading it — the list
        // the user is looking at shouldn't reshuffle because of one deletion.
        postDeletedCancellable = notificationCenter.publisher(for: .postDeleted)
            .receive(on: RunLoop.main)
            .sink { [weak self] notification in
                guard let postIdentifier = notification.object as? String else { return }
                self?.userPosts.removeAll { $0.id == postIdentifier }
            }

        // A newly created post only ever belongs on the author's own profile.
        postCreatedCancellable = notificationCenter.publisher(for: .postCreated)
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                Task { @MainActor in
                    guard let self, self.isOwnProfile else { return }
                    await self.refreshUserPosts()
                }
            }
    }

    /// Fetches the next batch of posts for the current user.
    func fetchUserPosts() {
        // Don't fetch if we're already loading or if we've reached the end
        guard !isLoading, canLoadMore else { return }
        
        isLoading = true
        
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot fetch posts")
                    isLoading = false
                    return
                }

                // Call the API endpoint we defined in the Django views
                let responseData = try await api.getPostsForUser(
                    sessionManagementToken: userSession.sessionToken,
                    username: user.username,
                    batch: batch
                )
                let newPosts = try JSONDecoder().decode([Post].self, from: responseData)
                
                if newPosts.isEmpty {
                    // No more posts to load
                    canLoadMore = false
                } else {
                    // Add new posts and increment the batch number
                    userPosts.append(contentsOf: newPosts)
                    batch += 1
                }
                startStatusPollIfNeeded()
            } catch {
                NSLog("%@", "Error fetching user posts for \(user.username): \(error)")
                // Optionally set an @Published error property to show an alert
            }
            
            isLoading = false
        }
    }
    
    /// Pull-to-refresh: resets pagination and reloads the user's posts from the
    /// first page, replacing the existing list with the freshest posts from the
    /// backend. `async` so SwiftUI's `.refreshable` keeps the spinner visible
    /// until the new posts have actually loaded.
    func refreshUserPosts() async {
        guard !isLoading else { return }
        isLoading = true
        // Reset the loading flag on every exit path so it can't be left stuck on.
        defer { isLoading = false }

        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot refresh posts")
                return
            }

            let responseData = try await api.getPostsForUser(
                sessionManagementToken: userSession.sessionToken,
                username: user.username,
                batch: 0
            )
            let newPosts = try JSONDecoder().decode([Post].self, from: responseData)

            // Replace the list and reset pagination so the next infinite-scroll
            // fetch continues from page 1.
            self.userPosts = newPosts
            self.canLoadMore = !newPosts.isEmpty
            self.batch = newPosts.isEmpty ? 0 : 1
            // A fresh first page grants a fresh reconcile-poll budget (#282).
            self.statusPollAttempts = 0
            startStatusPollIfNeeded()
        } catch {
            NSLog("%@", "Error refreshing user posts for \(user.username): \(error)")
        }
    }

    // MARK: - Async Classification Reconciliation (issue #282)

    /// Starts (or continues) the short bounded status poll when any of the
    /// viewer's own posts is still pending classification. No-op when nothing
    /// is pending, a poll is already running, or the budget is spent.
    private func startStatusPollIfNeeded() {
        // The grid is newest-first, so this polls the most recent pending posts.
        let pendingIds = userPosts.filter { $0.status == "pending" }.prefix(statusPollMaxPosts).map { $0.id }
        guard !pendingIds.isEmpty,
              statusPollTask == nil,
              statusPollAttempts < statusPollMaxAttempts else { return }

        // The interval is read up front and self is only strong-captured after
        // the sleep: holding self across the wait would keep the view model —
        // and its polling — alive after the profile has been dismissed.
        statusPollTask = Task { [weak self, interval = statusPollIntervalSeconds] in
            try? await Task.sleep(for: .seconds(interval))
            guard !Task.isCancelled, let self else { return }
            // Clear before polling so the poll round itself can re-arm the
            // next round (directly or via the reload it triggers).
            self.statusPollTask = nil
            self.statusPollAttempts += 1
            await self.pollPendingStatuses(pendingIds)
        }
    }

    /// One poll round: check each pending post's status. When any has
    /// resolved, reload the grid (approved posts lose their badge; final
    /// rejections drop out) and surface a rejection notice; otherwise re-arm
    /// the timer within the budget.
    private func pollPendingStatuses(_ pendingIds: [String]) async {
        guard let user = try? keychainHelper.load(UserSession.self, from: keychainService, account: account) else { return }

        var anyResolved = false
        for postId in pendingIds {
            guard let data = try? await api.getPostStatus(sessionManagementToken: user.sessionToken, postIdentifier: postId),
                  let status = try? JSONDecoder().decode(PostStatusResponse.self, from: data) else { continue }
            if status.status != "pending" {
                anyResolved = true
                if status.status == "rejected" || status.status == "rejected_final" {
                    reviewNotice = status.message ?? "One of your recent posts did not pass automated review."
                }
            }
        }

        if anyResolved {
            await refreshUserPosts()
        } else {
            startStatusPollIfNeeded()
        }
    }

    /// Pull-to-refresh companion to `refreshUserPosts()`: reloads the profile
    /// stats and follow/block status so they don't go stale on refresh. `async`
    /// so `.refreshable` keeps the spinner up until both posts and details load.
    func refreshProfileDetails() async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot refresh profile details")
                return
            }

            let responseData = try await api.getProfileDetails(sessionManagementToken: userSession.sessionToken, username: user.username)
            let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: responseData)

            self.profileDetails = details
            self.isFollowing = details.isFollowing
            self.isBlocked = details.isBlocked
        } catch {
            NSLog("%@", "Error refreshing profile details for \(user.username): \(error)")
        }
    }

    /// Fetches the user's profile stats and follow status.
    func fetchProfileDetails() {
        guard !isLoadingProfile else { return }
        isLoadingProfile = true
        
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot fetch profile")
                    isLoadingProfile = false
                    return
                }

                let responseData = try await api.getProfileDetails(sessionManagementToken: userSession.sessionToken, username: user.username)
                let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: responseData)
                
                self.profileDetails = details
                self.isFollowing = details.isFollowing // Set initial follow state
                self.isBlocked = details.isBlocked // Set initial block state
            } catch {
                NSLog("%@", "Error fetching profile details: \(error)")
                // Handle error (e.g., show alert)
            }
            isLoadingProfile = false
        }
    }
    
    /// Adjusts the follower count by `delta`, clamped at zero. Copies the struct
    /// and reassigns rather than mutating `profileDetails?.followerCount` in place,
    /// so we never read and write `profileDetails` in the same expression (which
    /// Swift rejects as an exclusive-access violation).
    private func adjustFollowerCount(by delta: Int) {
        guard var details = profileDetails else { return }
        details.followerCount = max(0, details.followerCount + delta)
        profileDetails = details
    }

    func toggleFollow() {
        guard !isBusy else { return }
        isBusy = true

        // Optimistic update: change UI immediately, revert on error.
        let wasFollowing = isFollowing
        isFollowing = !wasFollowing
        adjustFollowerCount(by: wasFollowing ? -1 : 1)

        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot toggle follow")
                    revertFollow(wasFollowing: wasFollowing)
                    isBusy = false
                    return
                }
                let token = userSession.sessionToken

                if wasFollowing {
                    let _ = try await api.unfollowUser(sessionManagementToken: token, username: user.username)
                } else {
                    let _ = try await api.followUser(sessionManagementToken: token, username: user.username)
                }
            } catch {
                NSLog("%@", "Error toggling follow: \(error)")
                revertFollow(wasFollowing: wasFollowing)
            }
            isBusy = false
        }
    }

    private func revertFollow(wasFollowing: Bool) {
        isFollowing = wasFollowing
        adjustFollowerCount(by: wasFollowing ? 1 : -1)
    }

    func toggleBlock() {
        guard !isBusy else { return }
        isBusy = true

        let previousBlockState = isBlocked
        let previousFollowState = isFollowing

        isBlocked.toggle()
        // Blocking also unfollows on the backend; mirror that locally.
        if isBlocked && isFollowing {
            isFollowing = false
            adjustFollowerCount(by: -1)
        }

        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot toggle block")
                    revertBlock(previousBlockState: previousBlockState, previousFollowState: previousFollowState)
                    isBusy = false
                    return
                }
                let token = userSession.sessionToken

                let _ = try await api.toggleBlock(sessionManagementToken: token, username: user.username)
            } catch {
                NSLog("%@", "Error toggling block: \(error)")
                revertBlock(previousBlockState: previousBlockState, previousFollowState: previousFollowState)
            }
            isBusy = false
        }
    }

    private func revertBlock(previousBlockState: Bool, previousFollowState: Bool) {
        isBlocked = previousBlockState
        // Only restore the follow state if we had optimistically unfollowed (i.e. we were blocking).
        if !previousBlockState && previousFollowState {
            isFollowing = previousFollowState
            adjustFollowerCount(by: 1)
        }
    }

    // MARK: - Profile Photo (issue #7)

    /// Uploads the picked JPEG to a presigned S3 URL (reusing the post-image
    /// flow) and sets it as the signed-in user's profile photo, then reloads the
    /// profile so the header reflects the new pending/approved state. The bytes
    /// are compressed and EXIF-stripped by `S3Uploader`, exactly like a post
    /// image.
    func updateProfilePhoto(imageData: Data) async {
        guard !isUpdatingPhoto else { return }
        isUpdatingPhoto = true
        photoErrorMessage = nil
        defer { isUpdatingPhoto = false }

        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot update profile photo")
                photoErrorMessage = "You must be logged in to update your photo."
                return
            }
            let token = userSession.sessionToken

            // Reuse the backend-issued presigned S3 URL flow (#310) for the
            // bytes. Under test the real S3 PUT is skipped (there's no live
            // bucket), mirroring NewPostView.
            var imageURLString = "https://picsum.photos/400/400"
            if !isTesting() {
                let uploadUrlData = try await api.createUploadUrl(sessionManagementToken: token)
                let uploadUrlResponse = try JSONDecoder().decode(UploadUrlResponse.self, from: uploadUrlData)
                guard let uploadURL = URL(string: uploadUrlResponse.uploadUrl) else {
                    throw ImageUploadError.invalidUploadURL
                }
                try await s3Uploader.upload(data: imageData, to: uploadURL)
                imageURLString = uploadUrlResponse.imageUrl
            }

            _ = try await api.setProfilePhoto(sessionManagementToken: token, imageURL: imageURLString)
            // Reload so the header shows the new photo / review state.
            await refreshProfileDetails()
        } catch {
            NSLog("%@", "Error updating profile photo: \(error)")
            photoErrorMessage = "Could not update your profile photo. Please try again."
        }
    }

    /// Removes the signed-in user's profile photo, then reloads the profile so
    /// the header reverts to the placeholder.
    func removeProfilePhoto() async {
        guard !isUpdatingPhoto else { return }
        isUpdatingPhoto = true
        photoErrorMessage = nil
        defer { isUpdatingPhoto = false }

        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot remove profile photo")
                photoErrorMessage = "You must be logged in to remove your photo."
                return
            }
            _ = try await api.removeProfilePhoto(sessionManagementToken: userSession.sessionToken)
            await refreshProfileDetails()
        } catch {
            NSLog("%@", "Error removing profile photo: \(error)")
            photoErrorMessage = "Could not remove your profile photo. Please try again."
        }
    }
}

