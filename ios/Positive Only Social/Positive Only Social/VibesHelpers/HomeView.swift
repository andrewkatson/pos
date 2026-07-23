//
//  HomeView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import SwiftUI
import Kingfisher

struct HomeView: View {
    
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    // The ViewModel is the single source of truth for this view's state.
    @StateObject private var viewModel: HomeViewModel
    
    @State private var currentTab = 0
    
    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        // We use _viewModel because we are initializing a @StateObject property
        _viewModel = StateObject(wrappedValue: HomeViewModel(api: api, keychainHelper: keychainHelper))
        
        self.api = api
        self.keychainHelper = keychainHelper
    }
    
    //TabView Menu
    var body: some View {
        TabView(selection: $currentTab){
            // Tab 1: The signed-in user's own profile — the same profile view
            // other users' profiles use, plus the user-search bar (issue #347).
            MyProfileTabView(api: api, keychainHelper: keychainHelper)
                .tabItem {
                    Label("Profile", systemImage: "person.crop.circle")
                }.tag(0)
            
            // Tab 2: Global feed view
            FeedView(api: api, keychainHelper: keychainHelper)
                .tabItem {
                    Label("Feed", systemImage: "list.bullet")
                }.tag(1)
            
            // Tab 3: New post creation view
            NewPostView(api: api, keychainHelper: keychainHelper, tabSelection: $currentTab)
                .tabItem {
                    Label("Post", systemImage: "plus.square")
                }.tag(2)
            
            // Tab 4: Settings view with logout
            SettingsView(api: api, keychainHelper: keychainHelper)
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }.tag(3)
        }
        .environmentObject(viewModel)
        // Lets anything below select a tab — tapping your own username anywhere
        // in the app lands on the Profile tab (issue #347).
        .environment(\.selectTab, { currentTab = $0 })
    }
}

/// Selects one of `HomeView`'s tabs. Defaults to a no-op so a view rendered
/// outside the tab bar (a preview, a test host) can't crash for want of it.
private struct SelectTabKey: EnvironmentKey {
    static let defaultValue: (Int) -> Void = { _ in }
}

extension EnvironmentValues {
    var selectTab: (Int) -> Void {
        get { self[SelectTabKey.self] }
        set { self[SelectTabKey.self] = newValue }
    }
}

/// A tappable username. Another user's name pushes their profile, as it always
/// has; the signed-in user's own name selects the Profile tab instead, since
/// their profile lives there rather than being pushed a second time (#347).
struct AuthorNameLink<Content: View>: View {
    private let username: String
    private let isCurrentUser: Bool
    private let label: Content

    @Environment(\.selectTab) private var selectTab

    init(username: String, isCurrentUser: Bool, @ViewBuilder label: () -> Content) {
        self.username = username
        self.isCurrentUser = isCurrentUser
        self.label = label()
    }

    var body: some View {
        if isCurrentUser {
            Button {
                selectTab(GVOAppConstants.profileTabIndex)
            } label: {
                label
            }
            .buttonStyle(.plain) // Keeps the text style
        } else {
            NavigationLink(value: User(username: username, identityIsVerified: false)) {
                label
            }
            .buttonStyle(.plain) // Keeps the text style
        }
    }
}

/// The first tab: the signed-in user's own profile (issue #347).
///
/// It shows exactly what `ProfileView` shows for anyone else — the Posts /
/// Followers / Following stats above the post grid — so the stats live in one
/// implementation instead of being duplicated for "your posts". Follow and
/// Block stay hidden because `ProfileViewModel.isOwnProfile` is true here.
///
/// The user-search bar behaves exactly as it did before: typing at least three
/// characters replaces the profile body with the matching users, each of which
/// pushes that user's profile.
struct MyProfileTabView: View {
    let api: Networking
    let keychainHelper: KeychainHelperProtocol

    // Owned by HomeView and shared with this tab: it drives the user search.
    @EnvironmentObject private var homeViewModel: HomeViewModel

    @StateObject private var viewModel: ProfileViewModel
    @StateObject private var postActions: PostActionsViewModel

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.api = api
        self.keychainHelper = keychainHelper
        _viewModel = StateObject(wrappedValue: ProfileViewModel.forCurrentUser(api: api, keychainHelper: keychainHelper))
        _postActions = StateObject(wrappedValue: PostActionsViewModel(api: api, keychainHelper: keychainHelper))
    }

    var body: some View {
        NavigationStack {
            Group {
                // If the user is searching, show the user list. Otherwise, show
                // their own profile.
                if !homeViewModel.searchText.isEmpty {
                    ScrollView {
                        UserSearchResultsView()
                    }
                } else {
                    ProfileBodyView(
                        viewModel: viewModel,
                        postActions: postActions,
                        // Keep the identifier the Home grid has always used so
                        // it stays distinguishable from another user's grid.
                        postAccessibilityIdentifier: "MyPostImage"
                    )
                }
            }
            .navigationTitle("Your Profile")
            // The searchable modifier provides the search bar UI and manages its state.
            .searchable(text: $homeViewModel.searchText, prompt: "Search for Users")
            .navigationDestination(for: Post.self) { post in
                PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
            }
            .navigationDestination(for: User.self) { user in
                ProfileView(user: user, api: api, keychainHelper: keychainHelper)
            }
            .postActionDialogs(postActions)
        }
    }
}

/// The like / reported-flag / options row shown under a post in a list, so the
/// user can act on it without opening it (issue #267). It offers exactly what
/// `PostDetailView` offers for the same post.
///
/// It sits *outside* the row's `NavigationLink` (and each control is its own
/// button with its own hit shape) so adding it can't swallow the tap that opens
/// the post — the same care the comment rows take with their gestures.
struct PostActionBar: View {
    let post: Post
    @ObservedObject var postActions: PostActionsViewModel

    /// Whether to show the comment count and the post's age alongside the
    /// actions (issue #249). The feed rows do; the square profile-grid tiles
    /// don't, because there's no room for them there.
    var showsPostDetails: Bool = false

    var body: some View {
        let state = postActions.state(for: post)
        HStack(spacing: 6) {
            // The backend rejects liking your own post, so it has no heart —
            // matching PostDetailView.
            if !state.isOwn {
                Button {
                    postActions.toggleLike(post)
                } label: {
                    Image(systemName: state.isLiked ? "heart.fill" : "heart")
                        .foregroundColor(Color(UIColor.systemRed))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("PostListLikeButton")
                .accessibilityLabel(state.isLiked ? "Unlike post" : "Like post")
            }
            Text("\(state.likeCount)")
                .foregroundColor(.secondary)
                .accessibilityIdentifier("PostListLikeCount")
            if state.isReported {
                Image(systemName: "flag.fill")
                    .foregroundColor(.red)
                    .accessibilityIdentifier("ReportedPostListIcon")
                    .accessibilityLabel("You reported this post")
            }
            if showsPostDetails {
                // Tapping the comment count opens the post, where the comments
                // are (issue #249). It's its own link so it doesn't interfere
                // with the row's image link.
                NavigationLink(value: post) {
                    HStack(spacing: 3) {
                        Image(systemName: "bubble.right")
                        Text("\(post.commentCount)")
                    }
                    .foregroundColor(.secondary)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("PostListCommentCount")
                .accessibilityLabel("\(post.commentCount) comments")
            }
            Spacer(minLength: 0)
            // How long ago the post was made, at the same coarse granularity as
            // comment times. Omitted when the backend sent no timestamp.
            if showsPostDetails, let created = post.createdDate {
                Text(RelativeTime.string(from: created))
                    .foregroundColor(.secondary)
                    .accessibilityIdentifier("PostListCreatedTime")
            }
            Button {
                postActions.postForMenu = post
            } label: {
                Image(systemName: "ellipsis")
                    .foregroundColor(.secondary)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("PostListOptionsButton")
            .accessibilityLabel("Post options")
        }
        .font(.caption)
        .padding(.horizontal, 4)
        .padding(.vertical, 4)
    }
}

/// The confirmation dialog, report sheet, retract-report alert and error alert
/// behind `PostActionBar`. They're attached once per list (rather than once per
/// row) and driven by the post the user picked.
struct PostActionDialogs: ViewModifier {
    @ObservedObject var postActions: PostActionsViewModel

    func body(content: Content) -> some View {
        content
            // Delete on your own post, Retract Report when you already reported
            // it, Report otherwise — the same menu PostDetailView shows.
            .confirmationDialog(
                "Post",
                isPresented: Binding(
                    get: { postActions.postForMenu != nil },
                    set: { if !$0 { postActions.postForMenu = nil } }
                ),
                titleVisibility: .hidden,
                presenting: postActions.postForMenu
            ) { post in
                if postActions.state(for: post).isOwn {
                    Button("Delete Post", role: .destructive) {
                        postActions.delete(post)
                    }
                    .accessibilityIdentifier("DeletePostListActionButton")
                } else if postActions.state(for: post).isReported {
                    Button("Retract Report") {
                        postActions.postToRetract = post
                    }
                    .accessibilityIdentifier("RetractReportPostListActionButton")
                } else {
                    Button("Report Post") {
                        postActions.postToReport = post
                    }
                    .accessibilityIdentifier("ReportPostListActionButton")
                }
            }
            // Shows the user's original reason so they can see what they're
            // retracting (issue #176).
            .alert(
                "Retract Report?",
                isPresented: Binding(
                    get: { postActions.postToRetract != nil },
                    set: { if !$0 { postActions.postToRetract = nil } }
                ),
                presenting: postActions.postToRetract
            ) { post in
                Button("Retract Report", role: .destructive) {
                    postActions.retractReport(post)
                }
                Button("Cancel", role: .cancel) {}
            } message: { post in
                Text("You reported this post with the reason: “\(postActions.state(for: post).reportReason ?? "")”. Retracting removes your report.")
            }
            // The same report sheet the post detail view uses.
            .sheet(item: $postActions.postToReport) { post in
                ReportView { reason in
                    postActions.report(post, reason: reason)
                }
            }
            .alert(isPresented: .constant(postActions.alertMessage != nil)) {
                Alert(
                    title: Text("Error"),
                    message: Text(postActions.alertMessage ?? "An unknown error occurred."),
                    dismissButton: .default(Text("OK")) {
                        postActions.alertMessage = nil
                    }
                )
            }
    }
}

extension View {
    /// Attaches the shared post action menus/sheets for a list of posts (#267).
    func postActionDialogs(_ postActions: PostActionsViewModel) -> some View {
        modifier(PostActionDialogs(postActions: postActions))
    }
}

/// A square grid thumbnail for a post. Loads the compressed `imageUrl` and, if
/// that fails, falls back to the full-resolution `originalImageUrl` before giving
/// up to a grey placeholder. The compressed copy is produced by an async Lambda,
/// so a just-posted or recently hidden-pending-appeal image can 403 in the
/// compressed bucket for a while — the fallback keeps those tiles from rendering
/// as empty grey boxes until the user re-logs in.
///
/// Backed by Kingfisher rather than AsyncImage: AsyncImage is one-shot, so a
/// load that fails or gets cancelled (lazy-grid scrolling, pull-to-refresh,
/// navigation transitions) parks the tile on the grey placeholder until the
/// view's identity changes — QA's "fixes itself after toggling search" on #254.
/// KFImage restarts a failed load when the tile reappears, keeps downloads
/// alive off-screen, briefly retries HTTP errors, and disk-caches the result.
/// Shared by the Home, For You, Following, and Profile grids.
/// See issues #252, #253, and #254.
struct GridPostImage: View {
    /// Nil for a text-only post (#307), which renders as a caption tile.
    let imageUrl: String?
    let originalImageUrl: String?
    /// The post caption, rendered as the tile for a text-only post.
    var caption: String = ""
    /// Shown while loading and when both the compressed and original images fail.
    /// Defaults to the grid's grey backing; callers (e.g. the feed) override it to
    /// match their own placeholder shade.
    var placeholderColor: Color = Color(.systemGray4)

    // Once the compressed URL genuinely fails, switch to the original and let
    // Kingfisher load the new URL.
    @State private var useOriginal = false

    var body: some View {
        if let imageUrl {
            let urlString = useOriginal ? (originalImageUrl ?? imageUrl) : imageUrl
            KFImage(URL(string: urlString))
                // Rides out the just-posted window where the compressed copy isn't
                // in the bucket yet; only HTTP errors are retried, not cancellations.
                .retry(maxCount: 2, interval: .seconds(1))
                .placeholder { placeholderColor }
                .onFailure { error in
                    // A cancelled load isn't a missing image — the tile reloads the
                    // same URL when it next appears, so save the fallback for real
                    // failures.
                    guard !error.isTaskCancelled else { return }
                    if !useOriginal, originalImageUrl != nil {
                        useOriginal = true
                    }
                }
                .resizable()
                .scaledToFill()
        } else {
            CaptionTileView(caption: caption)
        }
    }
}

/// The view for displaying user search results
struct UserSearchResultsView: View {
    @EnvironmentObject private var viewModel: HomeViewModel
    
    var body: some View {
        LazyVStack(alignment: .leading) {
            ForEach(viewModel.searchedUsers) { user in
                // These results only ever show on the Profile tab, so tapping
                // yourself just clears the search — you're already looking at
                // your own profile (issue #347).
                if user.username == viewModel.currentUsername {
                    Button {
                        viewModel.searchText = ""
                    } label: {
                        userRow(for: user)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier(user.username)
                } else {
                    NavigationLink(value: user) {
                        userRow(for: user)
                    }
                    .accessibilityIdentifier(user.username)
                }
                Divider()
            }
        }
    }

    private func userRow(for user: User) -> some View {
        HStack(spacing: 15) {
            // The user's profile photo (issue #7), with the neutral placeholder
            // as the fallback.
            ProfileAvatarView(
                imageUrl: user.authorProfileImageUrl,
                originalImageUrl: user.authorProfileImageOriginalUrl,
                size: 40
            )

            Text(user.username)
                .fontWeight(.bold)

            if user.identityIsVerified {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundColor(.blue)
            }
        }
    }
}


#Preview {
    HomeView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
