
import Foundation
import SwiftUI
import Kingfisher

struct PostDetailView: View {
    // Use @StateObject to create and own the ViewModel
    @StateObject private var viewModel: PostDetailViewModel
    
    // Used to pop this view once the user deletes the post being shown.
    @Environment(\.dismiss) private var dismiss
    
    // Kept to build the ProfileView pushed when an author's name is tapped.
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    
    // Set when a comment author's name is tapped to push their profile.
    // Comment rows navigate programmatically (rather than via NavigationLink)
    // so the row's long-press (report/delete menu) and double-tap (like)
    // gestures aren't swallowed by a Button in the row.
    @State private var profileUser: User? = nil
    
    // Public init
    init(postIdentifier: String, api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: PostDetailViewModel(postIdentifier: postIdentifier, api: api, keychainHelper: keychainHelper))
        self.api = api
        self.keychainHelper = keychainHelper
    }
    
    var body: some View {
        ScrollView {
            if viewModel.isLoading && viewModel.postDetail == nil {
                ProgressView()
                    .padding()
            } else if let post = viewModel.postDetail {
                VStack(alignment: .center, spacing: 12) {
                    PostDetailImage(
                        imageUrl: post.imageURL,
                        originalImageUrl: post.originalImageURL
                    )
                    .accessibilityElement(children: .ignore)  // Treat as single element
                    .accessibilityIdentifier("PostImage")
                    .accessibilityLabel("Post image")
                    .accessibilityAddTraits(.isImage)
                    .accessibilityAddTraits(.isButton)  // Makes it clear it's tappable
                    // --- Image Interactions ---
                    .onTapGesture(count: 2) {
                        // The backend rejects liking your own post, so double-tap
                        // is a no-op on the current user's own post.
                        guard !viewModel.isOwnPost else { return }
                        // Drive the action from the server-backed like state
                        if post.isLiked {
                            viewModel.unlikePost()
                        } else {
                            viewModel.likePost()
                        }
                    }
                    .onLongPressGesture {
                        viewModel.showActionSheetForPost = true
                    }
                    
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            // Hide the like heart on the current user's own post;
                            // they can't like it.
                            if !viewModel.isOwnPost {
                                Button {
                                    if post.isLiked { viewModel.unlikePost() } else { viewModel.likePost() }
                                } label: {
                                    Image(systemName: post.isLiked ? "heart.fill" : "heart")
                                        .foregroundColor(Color(UIColor.systemRed))
                                }
                                .accessibilityLabel(post.isLiked ? "Unlike post" : "Like post")
                            }
                            Text("\(post.likeCount) likes")
                                .font(.headline)
                                .accessibilityIdentifier("PostLikesText")
                            if viewModel.isPostReported {
                                Image(systemName: "flag.fill")
                                    .foregroundColor(.red)
                                    .font(.caption) // Make it a bit smaller
                                    .accessibilityIdentifier("ReportedPostIcon")
                                Spacer()
                            }
                        }
                        HStack(alignment: .firstTextBaseline, spacing: 4) {
                            // Tap the author's name to open their profile, same
                            // as in the feed. The User destination is registered
                            // on the parent NavigationStack.
                            NavigationLink(value: User(username: post.authorUsername, identityIsVerified: false)) {
                                Text(post.authorUsername)
                                    .fontWeight(.bold)
                            }
                            .buttonStyle(.plain) // Keeps the text style
                            .accessibilityIdentifier("PostAuthor")
                            Text(post.caption)
                        }
                    }
                    .padding(.horizontal)
                    Divider()
                    // Tapping this opens the shared comment composer sheet (which
                    // shows the character counter) rather than typing inline, so
                    // commenting on a post and replying to a thread work the same
                    // way (issues #266, #289, #290).
                    Button {
                        viewModel.showAddCommentSheet = true
                    } label: {
                        Text("Add a comment...")
                            .foregroundColor(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(Color.secondary.opacity(0.4), lineWidth: 1)
                            )
                            .contentShape(Rectangle())
                    }
                    .accessibilityIdentifier("AddACommentButton")
                    .padding()
                    
                    Text("Comments")
                        .font(.headline)
                        .padding(.horizontal)
                    
                    LazyVStack(spacing: 16) {
                        ForEach(viewModel.commentThreads) { thread in
                            CommentThreadView(thread: thread, onAuthorTap: { username in
                                profileUser = User(username: username, identityIsVerified: false)
                            })
                           
                            .padding(.horizontal)
                        }
                    }
                }
            } else {
                Text("Post not found.")
            }
        }
        .navigationTitle("Post")
        .navigationBarTitleDisplayMode(.inline)
        // Pushes the profile of a tapped comment author. Driven by state
        // instead of an inline NavigationLink — see the profileUser comment.
        .navigationDestination(isPresented: Binding(
            get: { profileUser != nil },
            set: { if !$0 { profileUser = nil } }
        )) {
            if let user = profileUser {
                ProfileView(user: user, api: api, keychainHelper: keychainHelper)
            }
        }
        .scrollDismissesKeyboard(.immediately)
        .refreshable {
            // Pull-to-refresh: reload the post details and comments from the backend.
            // Run the reload in an unstructured Task so SwiftUI cancelling the
            // refreshable task on a state-driven re-render (isLoading flips as the
            // refresh starts) can't cancel the in-flight network requests.
            await Task { await viewModel.refresh() }.value
        }
        // --- Action menus (long-press) ---
        // The post's menu offers Delete on the user's own post and Report on
        // everyone else's — so you can never report your own post.
        .confirmationDialog("Post", isPresented: $viewModel.showActionSheetForPost, titleVisibility: .hidden) {
            if viewModel.isOwnPost {
                Button("Delete Post", role: .destructive) {
                    viewModel.deletePost()
                }
                .accessibilityIdentifier("DeletePostActionButton")
            } else {
                Button("Report Post") {
                    viewModel.showReportSheetForPost = true
                }
                .accessibilityIdentifier("ReportPostActionButton")
            }
        }
        // The comment menu mirrors the post menu: Delete for the user's own
        // comments, Report for everyone else's.
        .confirmationDialog(
            "Comment",
            isPresented: Binding(
                get: { viewModel.commentForAction != nil },
                set: { if !$0 { viewModel.commentForAction = nil } }
            ),
            titleVisibility: .hidden,
            presenting: viewModel.commentForAction
        ) { comment in
            if viewModel.isOwnComment(comment) {
                Button("Delete Comment", role: .destructive) {
                    viewModel.deleteComment(comment)
                }
                .accessibilityIdentifier("DeleteCommentActionButton")
            } else {
                Button("Report Comment") {
                    viewModel.commentToReport = comment
                }
                .accessibilityIdentifier("ReportCommentActionButton")
            }
        }
        // --- Modals and Sheets ---
        .sheet(isPresented: $viewModel.showReportSheetForPost) {
            ReportView { reason in
                viewModel.reportPost(reason: reason)
            }
        }
        .sheet(item: $viewModel.commentToReport) { comment in
            ReportView { reason in
                viewModel.reportComment(comment, reason: reason)
            }
        }
        // The "Add a comment" composer for a brand new comment on the post.
        .sheet(isPresented: $viewModel.showAddCommentSheet) {
            CommentComposerView(title: "Add Comment") { commentText in
                viewModel.commentOnPost(commentText: commentText)
            }
        }
        // The same composer, reused for replying to an existing thread.
        .sheet(item: $viewModel.threadToReplyTo) { thread in
            CommentComposerView(title: "Post Reply") { commentText in
                viewModel.replyToCommentThread(thread: thread, commentText: commentText)
            }
        }
        .alert(isPresented: .constant(viewModel.alertMessage != nil), content: {
            Alert(
                title: Text("Error"),
                message: Text(viewModel.alertMessage ?? "An unknown error occurred."),
                dismissButton: .default(Text("OK")) {
                    viewModel.alertMessage = nil
                }
            )
        })
        //TODO: eBlender remove this deprecated code.
        .onChange(of: viewModel.postWasDeleted) { wasDeleted in
            // The post was deleted out from under this view; pop back to the feed.
            if wasDeleted { dismiss() }
        }
        .environmentObject(viewModel) // Pass VM to subviews
    }
}

/// The detail view's full-size post image. Loads the compressed `imageUrl` and
/// falls back to the full-resolution `originalImageUrl` when it fails — the
/// compressed copy is produced by an async Lambda, so a just-posted image can
/// 403 in the compressed bucket for a while. Kingfisher-backed for the same
/// reasons as `GridPostImage` (one-shot AsyncImage parks on the placeholder
/// after a failed or cancelled load); scaled to fit instead of fill, with the
/// detail view's spinner placeholder. See issues #252, #253, and #254.
struct PostDetailImage: View {
    let imageUrl: String
    let originalImageUrl: String?

    // Once the compressed URL genuinely fails, switch to the original and let
    // Kingfisher load the new URL.
    @State private var useOriginal = false

    var body: some View {
        let urlString = useOriginal ? (originalImageUrl ?? imageUrl) : imageUrl
        KFImage(URL(string: urlString))
            // Rides out the just-posted window where the compressed copy isn't
            // in the bucket yet; only HTTP errors are retried, not cancellations.
            .retry(maxCount: 2, interval: .seconds(1))
            .placeholder {
                Rectangle()
                    .fill(Color.secondary.opacity(0.3))
                    .aspectRatio(1, contentMode: .fit)
                    .overlay(ProgressView())
            }
            .onFailure { error in
                // A cancelled load isn't a missing image — the view reloads the
                // same URL when it next appears, so save the fallback for real
                // failures.
                guard !error.isTaskCancelled else { return }
                if !useOriginal, originalImageUrl != nil {
                    useOriginal = true
                }
            }
            .resizable()
            .scaledToFit()
            .aspectRatio(1, contentMode: .fit)
    }
}

#Preview {
    PostDetailView(postIdentifier: "123", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
