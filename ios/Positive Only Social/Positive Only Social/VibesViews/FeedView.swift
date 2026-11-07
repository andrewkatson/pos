//
//  FeedView.swift
//  Vibes
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI

// An enum to define our top tabs
enum FeedType: String, CaseIterable {
    case forYou = "For You"
    case following = "Following"
    case top = "Top"
}

struct FeedView: View {
    @StateObject private var forYouViewModel: FeedViewModel
    @StateObject private var followingViewModel: FollowingFeedViewModel
    @StateObject private var topViewModel: TopPostsViewModel
    @StateObject private var topProfilesViewModel: TopProfilesViewModel
    // Powers the like / report / delete controls on each feed row (issue #267).
    @StateObject private var postActions: PostActionsViewModel

    // Store api and keychainHelper to pass to navigation destinations
    let api: Networking
    let keychainHelper: KeychainHelperProtocol

    // State to track the selected top tab
    @State private var selectedFeed: FeedType = .forYou
    // Which board the Top segment shows (issue #588). Held here rather than in
    // TopFeedView so it survives switching to another feed and back.
    @State private var topBoard: TopBoard = .posts

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        _forYouViewModel = StateObject(wrappedValue: FeedViewModel(api: api, keychainHelper: keychainHelper))
        _followingViewModel = StateObject(wrappedValue: FollowingFeedViewModel(api: api, keychainHelper: keychainHelper))
        _topViewModel = StateObject(wrappedValue: TopPostsViewModel(api: api, keychainHelper: keychainHelper))
        _topProfilesViewModel = StateObject(wrappedValue: TopProfilesViewModel(api: api, keychainHelper: keychainHelper))
        _postActions = StateObject(wrappedValue: PostActionsViewModel(api: api, keychainHelper: keychainHelper))

        self.api = api
        self.keychainHelper = keychainHelper
    }

    var body: some View {
        NavigationStack {
            VStack {
                // This Picker creates the segmented top tabs
                Picker("Feed Type", selection: $selectedFeed) {
                    ForEach(FeedType.allCases, id: \.self) { type in
                        Text(type.rawValue).tag(type).accessibilityIdentifier(type.rawValue)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .accessibilityIdentifier("FeedTypePicker")

                // The content switches based on the selected tab
                switch selectedFeed {
                case .forYou:
                    ForYouFeedView(viewModel: forYouViewModel, postActions: postActions)
                case .following:
                    FollowingFeedView(viewModel: followingViewModel, postActions: postActions)
                case .top:
                    TopFeedView(viewModel: topViewModel, profilesViewModel: topProfilesViewModel,
                                board: $topBoard, postActions: postActions)
                }
            }
            .navigationTitle("Feed")
            .postActionDialogs(postActions)

            // Handles navigation when a User object is passed
            .navigationDestination(for: User.self) { user in
                ProfileView(user: user, api: api, keychainHelper: keychainHelper)
            }
            
            // Handles navigation when a FeedPost object is passed
            .navigationDestination(for: Post.self) { post in
                PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
            }
            .onChange(of: selectedFeed) { oldValue, newValue in
                 // Fetch fresh data whenever the tab changes
                 switch newValue {
                 case .forYou:
                     Task { await forYouViewModel.refreshFeed() }
                 case .following:
                     Task { await followingViewModel.refreshFeed() }
                 case .top:
                     switch topBoard {
                     case .posts: Task { await topViewModel.refreshFeed() }
                     case .profiles: Task { await topProfilesViewModel.refresh() }
                     }
                 }
             }
        }
    }
}


// MARK: - Sub-views for Each Tab

/// The view for the "For You" feed, containing the scrolling list of posts.
struct ForYouFeedView: View {
    @ObservedObject var viewModel: FeedViewModel
    @ObservedObject var postActions: PostActionsViewModel
    @StateObject private var celebration = EndOfListCelebration()

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 25) {
                ForEach(viewModel.feedPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {

                        // Tapping the author opens their profile — or the
                        // Profile tab when it's you (issue #347). Their profile
                        // photo sits next to the name (issue #7).
                        HStack(spacing: 8) {
                            ProfileAvatarView(
                                imageUrl: post.authorProfileImageUrl,
                                originalImageUrl: post.authorProfileImageOriginalUrl,
                                blurHash: post.authorProfileImageBlurHash,
                                size: 32
                            )
                            AuthorNameLink(
                                username: post.authorUsername,
                                isCurrentUser: postActions.state(for: post).isOwn
                            ) {
                                Text(post.authorUsername)
                                    .font(.headline)
                                    .fontWeight(.bold)
                            }
                            .accessibilityIdentifier("PostAuthor")
                            Spacer()
                        }
                        .padding(.horizontal)

                        // Wrap image in a NavigationLink to go to post details.
                        // Force every post into an identical square, cropping to
                        // fill so images no longer keep their original dimensions.
                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        blurHash: post.blurHash,
                                        caption: postActions.caption(for: post),
                                        captionFont: post.captionFont,
                                        backgroundColor: post.backgroundColor,
                                        placeholderColor: Color(.systemGray5)
                                    )
                                }
                                .clipped()
                                .border(Color.gray, width: 0.5)
                                .cornerRadius(15)
                                .shadow(color: Color.black.opacity(0.4), radius: 10, x: 0, y: 0)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            if post.id == viewModel.feedPosts.last?.id {
                                viewModel.fetchFeed()
                            }
                        }
                        .accessibilityIdentifier("ForYouPostImage")

                        // The caption under the photo (issue #378). Text-only
                        // posts (#307) already render their caption as the tile
                        // above, so it isn't repeated for them. The author's
                        // chosen caption font (issue #318) applies here too, so
                        // the feed matches the detail view (issue #450).
                        if post.imageUrl != nil {
                            Text(postActions.caption(for: post))
                                .font(TextFormatting.captionFont(post.captionFont, size: UIFont.preferredFont(forTextStyle: .body).pointSize))
                                .padding(.horizontal)
                                .accessibilityIdentifier("PostCaption")
                        }

                        // Like / report / delete, the comment count and the
                        // post's age (issues #267 and #249).
                        PostActionBar(post: post, postActions: postActions, showsPostDetails: true)
                            .padding(.horizontal)
                    }
                }
                // Loading indicator at the bottom of the list
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }

                if viewModel.reachedEnd && !viewModel.feedPosts.isEmpty {
                    FeedEndBanner(message: FeedEndMessage.forYou, celebration: celebration)
                }
            }
            .padding(.top)
        }
        .celebratesEndOfList(celebration, reachedEnd: viewModel.reachedEnd)
        .refreshable {
            // Pull-to-refresh: reload the newest posts from the backend.
            // Run the reload in an unstructured Task so SwiftUI cancelling
            // the refreshable task on a re-render can't cancel the request.
            await Task { await viewModel.refreshFeed() }.value
        }
        .onAppear {
            if viewModel.feedPosts.isEmpty {
                viewModel.fetchFeed()
            }
        }
    }
}

/// The view for the "Following" feed.
struct FollowingFeedView: View {
    @ObservedObject var viewModel: FollowingFeedViewModel
    @ObservedObject var postActions: PostActionsViewModel
    @StateObject private var celebration = EndOfListCelebration()

    var body: some View {
        VStack(spacing: 0) {
            // Group filter (issue #392): narrow the following feed to a
            // relationship category, or show everyone.
            Picker("Group", selection: Binding(
                get: { viewModel.selectedCategory },
                set: { viewModel.selectCategory($0) }
            )) {
                Text("Everyone").tag(FollowCategory?.none)
                ForEach(FollowCategory.allCases) { category in
                    Text(category.displayName).tag(FollowCategory?.some(category))
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.top, 8)
            .accessibilityIdentifier("FollowingGroupPicker")

            feedScroll
        }
    }

    private var feedScroll: some View {
        // We use the same UI structure as ForYouFeedView
        ScrollView {
            LazyVStack(spacing: 25) {
                // Iterate over the followingPosts array
                ForEach(viewModel.followingPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {

                        // Tapping the author opens their profile — or the
                        // Profile tab when it's you (issue #347). Their profile
                        // photo sits next to the name (issue #7).
                        HStack(spacing: 8) {
                            ProfileAvatarView(
                                imageUrl: post.authorProfileImageUrl,
                                originalImageUrl: post.authorProfileImageOriginalUrl,
                                blurHash: post.authorProfileImageBlurHash,
                                size: 32
                            )
                            AuthorNameLink(
                                username: post.authorUsername,
                                isCurrentUser: postActions.state(for: post).isOwn
                            ) {
                                Text(post.authorUsername)
                                    .font(.headline)
                                    .fontWeight(.bold)
                            }
                            Spacer()
                        }
                        .padding(.horizontal)

                        // Wrap image in a NavigationLink to go to post details.
                        // Force every post into an identical square, cropping to
                        // fill so images no longer keep their original dimensions.
                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        blurHash: post.blurHash,
                                        caption: postActions.caption(for: post),
                                        captionFont: post.captionFont,
                                        backgroundColor: post.backgroundColor,
                                        placeholderColor: Color(.systemGray5)
                                    )
                                }
                                .clipped()
                                // Match the For You feed's rounded corners so the
                                // two feeds are visually consistent (issue #414).
                                .border(Color.gray, width: 0.5)
                                .cornerRadius(15)
                                .shadow(color: Color.black.opacity(0.4), radius: 10, x: 0, y: 0)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            // Use followingPosts and fetchFollowingFeed
                            if post.id == viewModel.followingPosts.last?.id {
                                viewModel.fetchFollowingFeed()
                            }
                        }
                        .accessibilityIdentifier("FollowingPostImage")

                        // The caption under the photo (issue #378). Text-only
                        // posts (#307) already render their caption as the tile
                        // above, so it isn't repeated for them. The author's
                        // chosen caption font (issue #318) applies here too, so
                        // the feed matches the detail view (issue #450).
                        if post.imageUrl != nil {
                            Text(postActions.caption(for: post))
                                .font(TextFormatting.captionFont(post.captionFont, size: UIFont.preferredFont(forTextStyle: .body).pointSize))
                                .padding(.horizontal)
                                .accessibilityIdentifier("PostCaption")
                        }

                        // Like / report / delete, the comment count and the
                        // post's age (issues #267 and #249).
                        PostActionBar(post: post, postActions: postActions, showsPostDetails: true)
                            .padding(.horizontal)
                    }
                }
                
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }

                if viewModel.reachedEnd && !viewModel.followingPosts.isEmpty {
                    FeedEndBanner(message: FeedEndMessage.following, celebration: celebration)
                }
            }
            .padding(.top)
        }
        .celebratesEndOfList(celebration, reachedEnd: viewModel.reachedEnd)
        .refreshable {
            // Pull-to-refresh: reload the newest posts from the backend.
            // Run the reload in an unstructured Task so SwiftUI cancelling
            // the refreshable task on a re-render can't cancel the request.
            await Task { await viewModel.refreshFeed() }.value
        }
        // Add .onAppear to trigger the *initial* fetch
        .onAppear {
            if viewModel.followingPosts.isEmpty {
                viewModel.fetchFollowingFeed()
            }
        }
    }
}


/// The "Top" feed: a Posts board of the most-liked public posts across the app
/// over a chosen period (issue #558), and a Profiles board of the accounts with
/// the most followers (issue #588), each numbered by rank.
struct TopFeedView: View {
    @ObservedObject var viewModel: TopPostsViewModel
    @ObservedObject var profilesViewModel: TopProfilesViewModel
    @Binding var board: TopBoard
    @ObservedObject var postActions: PostActionsViewModel
    @StateObject private var celebration = EndOfListCelebration()

    var body: some View {
        VStack(spacing: 0) {
            Picker("Top board", selection: $board) {
                ForEach(TopBoard.allCases) { board in
                    Text(board.displayName).tag(board).accessibilityIdentifier(board.displayName)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.top, 8)
            .accessibilityIdentifier("TopBoardPicker")

            switch board {
            case .posts:
                postsBoard
            case .profiles:
                TopProfilesListView(viewModel: profilesViewModel,
                                    currentUsername: postActions.currentUsername)
            }
        }
    }

    private var postsBoard: some View {
        VStack(spacing: 0) {
            Picker("Period", selection: Binding(
                get: { viewModel.selectedPeriod },
                set: { viewModel.selectPeriod($0) }
            )) {
                ForEach(TopPostPeriod.allCases) { period in
                    Text(period.displayName).tag(period)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.top, 8)
            .accessibilityIdentifier("TopPeriodPicker")

            feedScroll
        }
    }

    private var feedScroll: some View {
        ScrollView {
            LazyVStack(spacing: 25) {
                ForEach(Array(viewModel.topPosts.enumerated()), id: \.element.id) { index, post in
                    VStack(alignment: .leading, spacing: 10) {

                        HStack(spacing: 8) {
                            // The scoreboard position.
                            Text("#\(index + 1)")
                                .font(.headline)
                                .monospacedDigit()
                                .foregroundStyle(Color.accentColor)
                                .accessibilityLabel("Rank \(index + 1)")
                                .accessibilityIdentifier("TopPostRank")
                            ProfileAvatarView(
                                imageUrl: post.authorProfileImageUrl,
                                originalImageUrl: post.authorProfileImageOriginalUrl,
                                blurHash: post.authorProfileImageBlurHash,
                                size: 32
                            )
                            AuthorNameLink(
                                username: post.authorUsername,
                                isCurrentUser: postActions.state(for: post).isOwn
                            ) {
                                Text(post.authorUsername)
                                    .font(.headline)
                                    .fontWeight(.bold)
                            }
                            Spacer()
                        }
                        .padding(.horizontal)

                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        blurHash: post.blurHash,
                                        caption: postActions.caption(for: post),
                                        captionFont: post.captionFont,
                                        backgroundColor: post.backgroundColor,
                                        placeholderColor: Color(.systemGray5)
                                    )
                                }
                                .clipped()
                                .border(Color.gray, width: 0.5)
                                .cornerRadius(15)
                                .shadow(color: Color.black.opacity(0.4), radius: 10, x: 0, y: 0)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            if post.id == viewModel.topPosts.last?.id {
                                viewModel.fetchTopPosts()
                            }
                        }
                        .accessibilityIdentifier("TopPostImage")

                        if post.imageUrl != nil {
                            Text(postActions.caption(for: post))
                                .font(TextFormatting.captionFont(post.captionFont, size: UIFont.preferredFont(forTextStyle: .body).pointSize))
                                .padding(.horizontal)
                                .accessibilityIdentifier("PostCaption")
                        }

                        PostActionBar(post: post, postActions: postActions, showsPostDetails: true)
                            .padding(.horizontal)
                    }
                }

                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }

                if viewModel.reachedEnd && !viewModel.topPosts.isEmpty {
                    FeedEndBanner(message: FeedEndMessage.top(viewModel.selectedPeriod), celebration: celebration)
                }
            }
            .padding(.top)
        }
        .celebratesEndOfList(celebration, reachedEnd: viewModel.reachedEnd)
        .refreshable {
            await Task { await viewModel.refreshFeed() }.value
        }
        .onAppear {
            if viewModel.topPosts.isEmpty {
                viewModel.fetchTopPosts()
            }
        }
    }
}


/// The Profiles board of the Top feed (issue #588): public accounts ranked by
/// followers, all-time, each row opening that profile.
struct TopProfilesListView: View {
    @ObservedObject var viewModel: TopProfilesViewModel
    let currentUsername: String?
    @StateObject private var celebration = EndOfListCelebration()

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                if viewModel.topProfiles.isEmpty && !viewModel.isLoadingNextPage {
                    Text("No profiles here yet.")
                        .foregroundColor(.gray)
                        .padding()
                }
                ForEach(Array(viewModel.topProfiles.enumerated()), id: \.element.id) { index, profile in
                    AuthorNameLink(username: profile.username,
                                   isCurrentUser: profile.username == currentUsername) {
                        HStack(spacing: 10) {
                            Text("#\(index + 1)")
                                .font(.headline)
                                .monospacedDigit()
                                .foregroundStyle(Color.accentColor)
                                .frame(minWidth: 36, alignment: .leading)
                                .accessibilityLabel("Rank \(index + 1)")
                                .accessibilityIdentifier("TopProfileRank")
                            ProfileAvatarView(
                                imageUrl: profile.authorProfileImageUrl,
                                originalImageUrl: profile.authorProfileImageOriginalUrl,
                                blurHash: profile.authorProfileImageBlurHash,
                                size: 32
                            )
                            // Truncates rather than squeezing out the follower total.
                            Text(profile.username)
                                .font(.headline)
                                .lineLimit(1)
                                .truncationMode(.tail)
                            if profile.identityIsVerified {
                                Image(systemName: "checkmark.seal.fill")
                                    .foregroundColor(.blue)
                                    .accessibilityLabel("Verified")
                            }
                            Spacer()
                            Text(profile.followerCountLabel)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                                .fixedSize()
                        }
                        .padding(.horizontal)
                        .padding(.vertical, 10)
                        .contentShape(Rectangle())
                    }
                    .accessibilityIdentifier(profile.username)
                    // Trigger for infinite scrolling. Keyed to the list's end and
                    // to each refresh as well as appearance: a refresh can make an
                    // already-visible row the last one, or return the identical
                    // page, and onAppear alone would never fire again for it.
                    .task(id: "\(viewModel.topProfiles.count)|\(viewModel.topProfiles.last?.id ?? "")|\(viewModel.refreshRevision)") {
                        if profile.id == viewModel.topProfiles.last?.id {
                            viewModel.fetchTopProfiles()
                        }
                    }
                    Divider()
                }

                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }

                if viewModel.reachedEnd && !viewModel.topProfiles.isEmpty {
                    FeedEndBanner(message: FeedEndMessage.topProfiles, celebration: celebration)
                }
            }
            .padding(.top)
        }
        .celebratesEndOfList(celebration, reachedEnd: viewModel.reachedEnd)
        .refreshable {
            await Task { await viewModel.refresh() }.value
        }
        .onAppear {
            if viewModel.topProfiles.isEmpty {
                viewModel.fetchTopProfiles()
            }
        }
    }
}


// MARK: - Preview
#Preview {
    // Assuming KeychainHelper() is a valid initializer
    // If not, you may need to use your mock
    FeedView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
