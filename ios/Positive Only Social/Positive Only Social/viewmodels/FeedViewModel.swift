//
//  FeedViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation

// ViewModel to manage the state of the global feed
@MainActor
final class FeedViewModel: ObservableObject {
    private let api: APIProtocol
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    @Published var feedPosts: [Post] = []
    @Published var isLoadingNextPage = false
    private var canLoadMore = true
    private var currentPage = 0
    
    convenience init(api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(api: APIProtocol, keychainHelper: KeychainHelperProtocol, account: String) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }
    
    func fetchFeed() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true
        
        Task {
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
                
                let responseData = try await api.getPostsInFeed(sessionManagementToken: userSession.sessionToken, batch: currentPage)
                let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { return }
                let newPosts = try JSONDecoder().decode([DjangoObject<Post>].self, from: innerData).map { $0.fields }
                
                if newPosts.isEmpty {
                    canLoadMore = false
                } else {
                    feedPosts.append(contentsOf: newPosts)
                    currentPage += 1
                }
            } catch {
                print("Failed to fetch feed: \(error)")
            }
            isLoadingNextPage = false
        }
    }
}
