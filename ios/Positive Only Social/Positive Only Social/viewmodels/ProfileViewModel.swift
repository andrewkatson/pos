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
    @Published var isLoadingProfile = false // For the button
    @Published var isFollowing = false
    @Published var isBlocked = false
    
    // Private state for pagination and API
    private var batch = 0
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = AppConstants.keychainService
    
    let user: User // The user this profile is for

    convenience init(user: User, api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(user: user, api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(user: User, api: Networking, keychainHelper: KeychainHelperProtocol, account: String) {
        self.user = user
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
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
            } catch {
                NSLog("%@", "Error fetching user posts for \(user.username): \(error)")
                // Optionally set an @Published error property to show an alert
            }
            
            isLoading = false
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
    
    func toggleFollow() {
        guard !isLoadingProfile else { return } // Use same loader
        isLoadingProfile = true
            
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot toggle follow")
                    isLoadingProfile = false
                    return
                }
                let token = userSession.sessionToken

                if isFollowing {
                    // --- Unfollow Logic ---
                    let _ = try await api.unfollowUser(sessionManagementToken: token, username: user.username)
                    
                    // Update local state directly
                    self.isFollowing = false
                    if self.profileDetails != nil {
                        self.profileDetails?.followerCount -= 1
                    }
                    
                } else {
                    // --- Follow Logic ---
                    let _ = try await api.followUser(sessionManagementToken: token, username: user.username)
                    
                    // Update local state directly
                    self.isFollowing = true
                    if self.profileDetails != nil {
                        self.profileDetails?.followerCount += 1
                    }
                }
            } catch {
                NSLog("%@", "Error toggling follow: \(error)")
                // Handle error (e.g., show alert)
                // Since we update the UI *after* the await, we don't need to
                // manually roll back the change if the API call fails.
            }
            isLoadingProfile = false
        }
    }

    func toggleBlock() {
        // Toggle block status
        guard !isLoadingProfile else { return }
        isLoadingProfile = true
        
        let previousBlockState = isBlocked
        let previousFollowState = isFollowing
        // Optimistic update
        isBlocked.toggle()

        // Blocking also unfollows in our backend logic, so mirror that here.
        // Only decrement the follower count if we were actually following,
        // otherwise the count drifts (e.g. follow -> block -> follow would
        // count the same follow twice).
        if isBlocked && isFollowing {
            isFollowing = false
            if self.profileDetails != nil {
                self.profileDetails?.followerCount -= 1
            }
        }

        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot toggle block")
                    isLoadingProfile = false
                    return
                }
                let token = userSession.sessionToken

                let _ = try await api.toggleBlock(sessionManagementToken: token, username: user.username)
                
                // Success, state already updated.
            } catch {
                NSLog("%@", "Error toggling block: \(error)")
                // Revert on error, including the optimistic unfollow side-effect.
                if isBlocked && !previousBlockState && previousFollowState {
                    isFollowing = previousFollowState
                    if self.profileDetails != nil {
                        self.profileDetails?.followerCount += 1
                    }
                }
                isBlocked = previousBlockState
            }
            isLoadingProfile = false
        }
    }
}

