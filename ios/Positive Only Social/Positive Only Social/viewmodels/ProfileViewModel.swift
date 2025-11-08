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
    
    // Private state for pagination and API
    private var batch = 0
    private let api: APIProtocol
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    
    let user: User // The user this profile is for

    convenience init(user: User, api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        self.init(user: user, api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(user: User, api: APIProtocol, keychainHelper: KeychainHelperProtocol, account: String) {
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
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
                
                // Call the API endpoint we defined in the Django views
                let responseData = try await api.getPostsForUser(
                    sessionManagementToken: userSession.sessionToken,
                    username: user.username,
                    batch: batch
                )
                
                let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { return }
                let newPosts = try JSONDecoder().decode([DjangoObject<Post>].self, from: innerData).map { $0.fields }
                
                if newPosts.isEmpty {
                    // No more posts to load
                    canLoadMore = false
                } else {
                    // Add new posts and increment the batch number
                    userPosts.append(contentsOf: newPosts)
                    batch += 1
                }
            } catch {
                print("Error fetching user posts for \(user.username): \(error)")
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
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
                
                let responseData = try await api.getProfileDetails(sessionManagementToken: userSession.sessionToken, username: user.username)
                
                let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { return }
                let details = try JSONDecoder().decode(DjangoObject<ProfileDetailsResponse>.self, from: innerData).fields
                
                self.profileDetails = details
                self.isFollowing = details.isFollowing // Set initial follow state
            } catch {
                print("Error fetching profile details: \(error)")
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
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
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
                print("Error toggling follow: \(error)")
                // Handle error (e.g., show alert)
                // Since we update the UI *after* the await, we don't need to
                // manually roll back the change if the API call fails.
            }
            isLoadingProfile = false
        }
    }
}

