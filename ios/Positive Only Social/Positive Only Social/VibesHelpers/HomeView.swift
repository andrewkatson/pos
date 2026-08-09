//
//  HomeView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import SwiftUI
import Kingfisher
import UIKit
import Combine

struct HomeView: View {

    let api: Networking
    let keychainHelper: KeychainHelperProtocol

    // The ViewModel is the single source of truth for this view's state.
    @StateObject private var viewModel: HomeViewModel

    @State private var currentTab = 0
    // The Profile tab's navigation stack path. A tapped push notification pushes
    // the rejected post onto it (issues #342/#343). NavigationPath (not [String])
    // because that stack already navigates by other value types — Post, User,
    // FollowListMode — and a homogeneous typed path would break those pushes.
    @State private var profilePath = NavigationPath()
    @ObservedObject private var pushRouter = PushRouter.shared

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
            MyProfileTabView(api: api, keychainHelper: keychainHelper, path: $profilePath)
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
        // Now that a session exists (this view only shows when logged in), ask
        // for notification permission and register this device (issues
        // #342/#343). Best-effort; the OS prompts at most once.
        .task {
            PushNotifications.shared.requestAuthorizationAndRegister()
            PushNotifications.shared.uploadCachedTokenIfAvailable()
        }
        // A tapped "post rejected" notification asks us to open that post: jump
        // to the Profile tab and push its detail. onReceive fires with the
        // current (nil) value on subscribe too, hence the guard.
        .onReceive(pushRouter.$pendingPostIdentifier) { postIdentifier in
            guard let postIdentifier else { return }
            currentTab = GVOAppConstants.profileTabIndex
            var newPath = NavigationPath()
            newPath.append(postIdentifier)
            profilePath = newPath
            pushRouter.pendingPostIdentifier = nil
        }
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

    // The navigation path, owned by HomeView so a tapped push notification can
    // push the rejected post's detail onto this stack (issues #342/#343).
    @Binding private var path: NavigationPath

    @StateObject private var viewModel: ProfileViewModel
    @StateObject private var postActions: PostActionsViewModel

    init(api: Networking, keychainHelper: KeychainHelperProtocol, path: Binding<NavigationPath>) {
        self.api = api
        self.keychainHelper = keychainHelper
        _path = path
        _viewModel = StateObject(wrappedValue: ProfileViewModel.forCurrentUser(api: api, keychainHelper: keychainHelper))
        _postActions = StateObject(wrappedValue: PostActionsViewModel(api: api, keychainHelper: keychainHelper))
    }

    var body: some View {
        NavigationStack(path: $path) {
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
            // A push notification pushes a post by its identifier (String), since
            // the payload carries only the id, not a full Post (issues #342/#343).
            .navigationDestination(for: String.self) { postIdentifier in
                PostDetailView(postIdentifier: postIdentifier, api: api, keychainHelper: keychainHelper)
            }
            .navigationDestination(for: User.self) { user in
                ProfileView(user: user, api: api, keychainHelper: keychainHelper)
            }
            // Tapping your own Followers / Following count opens that list —
            // only your own, since the endpoints take no username (issue #8).
            .navigationDestination(for: FollowListMode.self) { mode in
                FollowListView(mode: mode, api: api, keychainHelper: keychainHelper)
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
            // With no heart beside it the bare number says nothing about what it
            // counts, so your own posts spell it out the way PostDetailView does
            // (issue #476).
            Text(state.isOwn ? "\(state.likeCount) likes" : "\(state.likeCount)")
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
                // Share is offered for any post — your own and others' (issue #34).
                Button("Share Post") {
                    postActions.share(post)
                }
                .accessibilityIdentifier("SharePostListActionButton")
                // Save / Unsave, offered on any post (issue #193/#412). Web has a
                // dedicated bookmark control; on mobile it lives in this menu.
                Button(postActions.state(for: post).isSaved ? "Unsave Post" : "Save Post") {
                    postActions.toggleSave(post)
                }
                .accessibilityIdentifier("SavePostListActionButton")
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
            // Native share sheet for a post in a list (issue #34), driven by the
            // item the menu's Share button set — same pattern as the report sheet.
            .sheet(item: $postActions.postShareItem) { item in
                ShareActivityView(url: item.url)
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
    /// BlurHash for the image (issue #387): decoded into a blurred placeholder
    /// shown while the photo loads, so the tile is a soft blur of the real image
    /// instead of a flat grey square. Nil for text-only posts / older backends.
    var blurHash: String? = nil
    /// The post caption, rendered as the tile for a text-only post.
    var caption: String = ""
    /// Caption font + background color keys for a text-only tile (issue #318).
    var captionFont: String = "default"
    var backgroundColor: String = "default"
    /// Shown while loading and when both the compressed and original images fail.
    /// Defaults to the grid's grey backing; callers (e.g. the feed) override it to
    /// match their own placeholder shade.
    var placeholderColor: Color = Color(.systemGray4)

    // Once the compressed URL genuinely fails, switch to the original and let
    // Kingfisher load the new URL.
    @State private var useOriginal = false

    /// What KFImage shows while the photo loads (and if it never loads): the
    /// decoded BlurHash when the post carries one, otherwise the flat grey shade.
    /// Decoding only runs while the placeholder is on screen, and at a tiny size,
    /// so it stays cheap.
    @ViewBuilder private var blurHashPlaceholder: some View {
        if let blurHash, let image = BlurHashImage.decode(blurHash, size: BlurHashImage.decodeSize) {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
        } else {
            placeholderColor
        }
    }

    var body: some View {
        if let imageUrl {
            let urlString = useOriginal ? (originalImageUrl ?? imageUrl) : imageUrl
            KFImage(URL(string: urlString))
                // Rides out the just-posted window where the compressed copy isn't
                // in the bucket yet; only HTTP errors are retried, not cancellations.
                .retry(maxCount: 2, interval: .seconds(1))
                .placeholder { blurHashPlaceholder }
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
            CaptionTileView(caption: caption, captionFont: captionFont, backgroundColor: backgroundColor)
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

/// A minimal BlurHash decoder (issue #387) — a Swift port of the reference
/// algorithm at https://github.com/woltapp/blurhash. It turns the short BlurHash
/// string the backend attaches to a post into a small blurred `UIImage` the grid
/// shows while the real photo loads, so a loading tile isn't a flat grey box.
/// Vendored (a handful of pure functions) rather than taking a dependency just
/// to decode ~30 characters.
enum BlurHashImage {
    /// The preview is upscaled to fill the tile, so a tiny decode is plenty and
    /// keeps the per-tile cost negligible.
    static let decodeSize = CGSize(width: 32, height: 32)

    private static let digits: [Character] =
        Array("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~")
    private static let digitValues: [Character: Int] = {
        var map = [Character: Int]()
        for (index, character) in digits.enumerated() { map[character] = index }
        return map
    }()

    /// Decode `blurHash` into a blurred image of `size`, or nil if the string is
    /// malformed (bad length/characters) — callers then fall back to a flat color.
    static func decode(_ blurHash: String, size: CGSize, punch: Float = 1) -> UIImage? {
        let characters = Array(blurHash)
        guard characters.count >= 6 else { return nil }
        // Reject any character outside the BlurHash alphabet up front, so a
        // malformed string returns nil (as documented) rather than decoding to a
        // garbage bitmap — decode83 itself just skips unknown characters.
        guard characters.allSatisfy({ digitValues[$0] != nil }) else { return nil }

        let sizeFlag = decode83(characters[0 ..< 1])
        let numberOfY = (sizeFlag / 9) + 1
        let numberOfX = (sizeFlag % 9) + 1
        guard characters.count == 4 + 2 * numberOfX * numberOfY else { return nil }

        let quantisedMaximumValue = decode83(characters[1 ..< 2])
        let maximumValue = Float(quantisedMaximumValue + 1) / 166

        var colours = [(Float, Float, Float)](repeating: (0, 0, 0), count: numberOfX * numberOfY)
        for index in 0 ..< colours.count {
            if index == 0 {
                colours[index] = decodeDC(decode83(characters[2 ..< 6]))
            } else {
                let value = decode83(characters[(4 + index * 2) ..< (6 + index * 2)])
                colours[index] = decodeAC(value, maximumValue: maximumValue * punch)
            }
        }

        let width = Int(size.width)
        let height = Int(size.height)
        guard width > 0, height > 0 else { return nil }
        let bytesPerRow = width * 3
        var pixels = [UInt8](repeating: 0, count: bytesPerRow * height)

        for y in 0 ..< height {
            for x in 0 ..< width {
                var red: Float = 0, green: Float = 0, blue: Float = 0
                for j in 0 ..< numberOfY {
                    for i in 0 ..< numberOfX {
                        let basis = Float(cos(Double.pi * Double(x) * Double(i) / Double(width))
                            * cos(Double.pi * Double(y) * Double(j) / Double(height)))
                        let colour = colours[i + j * numberOfX]
                        red += colour.0 * basis
                        green += colour.1 * basis
                        blue += colour.2 * basis
                    }
                }
                let offset = 3 * x + y * bytesPerRow
                pixels[offset] = UInt8(linearTosRGB(red))
                pixels[offset + 1] = UInt8(linearTosRGB(green))
                pixels[offset + 2] = UInt8(linearTosRGB(blue))
            }
        }

        let colourSpace = CGColorSpaceCreateDeviceRGB()
        guard let provider = CGDataProvider(data: Data(pixels) as CFData) else { return nil }
        guard let cgImage = CGImage(
            width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 24,
            bytesPerRow: bytesPerRow, space: colourSpace,
            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue),
            provider: provider, decode: nil, shouldInterpolate: true, intent: .defaultIntent
        ) else { return nil }
        return UIImage(cgImage: cgImage)
    }

    private static func decode83(_ characters: ArraySlice<Character>) -> Int {
        var value = 0
        for character in characters {
            if let digit = digitValues[character] { value = value * 83 + digit }
        }
        return value
    }

    private static func decodeDC(_ value: Int) -> (Float, Float, Float) {
        (sRGBToLinear(value >> 16), sRGBToLinear((value >> 8) & 255), sRGBToLinear(value & 255))
    }

    private static func decodeAC(_ value: Int, maximumValue: Float) -> (Float, Float, Float) {
        let quantR = value / (19 * 19)
        let quantG = (value / 19) % 19
        let quantB = value % 19
        return (
            signPow((Float(quantR) - 9) / 9, 2) * maximumValue,
            signPow((Float(quantG) - 9) / 9, 2) * maximumValue,
            signPow((Float(quantB) - 9) / 9, 2) * maximumValue
        )
    }

    private static func signPow(_ value: Float, _ exponent: Float) -> Float {
        let magnitude = Float(pow(Double(abs(value)), Double(exponent)))
        return value < 0 ? -magnitude : magnitude
    }

    private static func linearTosRGB(_ value: Float) -> Int {
        let clamped = max(0, min(1, value))
        if clamped <= 0.0031308 { return Int(clamped * 12.92 * 255 + 0.5) }
        return Int((1.055 * Float(pow(Double(clamped), 1 / 2.4)) - 0.055) * 255 + 0.5)
    }

    private static func sRGBToLinear(_ value: Int) -> Float {
        let v = Float(value) / 255
        if v <= 0.04045 { return v / 12.92 }
        return Float(pow(Double((v + 0.055) / 1.055), 2.4))
    }
}
