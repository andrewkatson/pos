//
//  HomeViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation
import Combine

@MainActor
final class HomeViewModel: ObservableObject {
    // MARK: - Properties
    private let api: APIProtocol
    
    // Data for the view
    @Published var userPosts: [Post] = []
    @Published var searchedUsers: [User] = []
    @Published var searchText = ""
    
    // State tracking
    @Published var isLoadingNextPage = false
    @Published var errorMessage: String?
    private var canLoadMorePosts = true
    private var currentPage = 0
    
    // For debouncing search text
    private var searchCancellable: AnyCancellable?

    // MARK: - Initializer
    init(api: APIProtocol) {
        self.api = api
        
        // This subscriber automatically triggers a search when the user stops typing.
        searchCancellable = $searchText
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main) // Wait 500ms after user stops typing
            .removeDuplicates()
            .sink { [weak self] searchText in
                self?.performSearch(for: searchText)
            }
    }

    // MARK: - Public Methods
    
    /// Fetches the next page of the current user's posts.
    func fetchMyPosts() {
        // Prevent multiple fetches at the same time or fetching beyond the end
        guard !isLoadingNextPage && canLoadMorePosts else { return }
        
        isLoadingNextPage = true
        
        Task {
            do {
                // In a real app, you'd get the username from a profile object.
                // Here, we'll assume a logged-in user for the stubbed API.
                let myUsername = "testuser" // Placeholder
                let sessionToken = try KeychainHelper.shared.load(String.self, from: "positive-only-social.Positive-Only-Social", account: "userSessionToken") ?? ""

                // Call the API
                let newPosts = try await fetchPosts(for: myUsername, token: sessionToken, page: currentPage)

                if newPosts.isEmpty {
                    // No more posts to load
                    self.canLoadMorePosts = false
                } else {
                    self.userPosts.append(contentsOf: newPosts)
                    self.currentPage += 1
                }
                
            } catch {
                self.errorMessage = error.localizedDescription
            }
            
            self.isLoadingNextPage = false
        }
    }

    // MARK: - Private Helpers
    
    /// Called automatically by the search text subscriber.
    private func performSearch(for query: String) {
        // Only search if query is 3+ characters
        guard query.count >= 3 else {
            searchedUsers = []
            return
        }
        
        Task {
            do {
                let sessionToken = try KeychainHelper.shared.load(String.self, from: "positive-only-social.Positive-Only-Social", account: "userSessionToken") ?? ""
                self.searchedUsers = try await searchForUsers(fragment: query, token: sessionToken)
            } catch {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    // Decodes the API response for get_posts_for_user
    private func fetchPosts(for username: String, token: String, page: Int) async throws -> [Post] {
        let responseData = try await api.getPostsForUser(sessionManagementToken: token, username: username, batch: page)
        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
        guard let innerData = wrapper.responseList.data(using: .utf8) else { return [] }
        let responseArray = try JSONDecoder().decode([DjangoObject<Post>].self, from: innerData)
        return responseArray.map { $0.fields }
    }
    
    // Decodes the API response for get_users_matching_fragment
    private func searchForUsers(fragment: String, token: String) async throws -> [User] {
        let responseData = try await api.getUsersMatchingFragment(sessionManagementToken: token, usernameFragment: fragment)
        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
        guard let innerData = wrapper.responseList.data(using: .utf8) else { return [] }
        let responseArray = try JSONDecoder().decode([DjangoObject<User>].self, from: innerData)
        return responseArray.map { $0.fields }
    }
}

// A generic helper to decode the Django serializer format
struct DjangoObject<T: Codable>: Codable {
    let fields: T
}
