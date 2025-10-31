//
//  FollowingFeedViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/26/25.
//

import Foundation

// ViewModel to manage the state of the "Following" feed
@MainActor
final class FollowingFeedViewModel: ObservableObject {
    private let api: APIProtocol
    @Published var followingPosts: [Post] = []
    @Published var isLoadingNextPage = false
    private var canLoadMore = true
    private var currentPage = 0
    
    init(api: APIProtocol) { self.api = api }
    
    func fetchFollowingFeed() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true
        
        Task {
            do {
                let token = try KeychainHelper.shared.load(String.self, from: "positive-only-social.Positive-Only-Social", account: "userSessionToken") ?? ""
                
                // --- KEY CHANGE ---
                // Call the API endpoint for followed users
                let responseData = try await api.getPostsForFollowedUsers(sessionManagementToken: token, batch: currentPage)
                // --- END KEY CHANGE ---
                
                let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { return }
                let newPosts = try JSONDecoder().decode([DjangoObject<Post>].self, from: innerData).map { $0.fields }
                
                if newPosts.isEmpty {
                    canLoadMore = false
                } else {
                    // Add new posts to the followingPosts array
                    followingPosts.append(contentsOf: newPosts)
                    currentPage += 1
                }
            } catch {
                print("Failed to fetch following feed: \(error)")
            }
            isLoadingNextPage = false
        }
    }
}
