//
//  PostDetailView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 11/9/25.
//

import Foundation

import SwiftUI

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
                VStack(alignment: .leading, spacing: 12) {
                    // --- POST IMAGE ---
                    // Using AsyncImage for network URLs
                    AsyncImage(url: URL(string: post.imageURL)) { image in
                        image
                            .resizable()
                            .scaledToFit()
                            .aspectRatio(1, contentMode: .fit)
                    } placeholder: {
                        Rectangle()
                            .fill(Color.secondary.opacity(0.3))
                            .aspectRatio(1, contentMode: .fit)
                            .overlay(ProgressView())
                    }
                    .accessibilityElement(children: .ignore)  // Treat as single element
                    .accessibilityIdentifier("PostImage")
                    .accessibilityLabel("Post image")
                    .accessibilityAddTraits(.isImage)
                    .accessibilityAddTraits(.isButton)  // Makes it clear it's tappable
                    // --- Image Interactions ---
                    // --- UPDATED ---
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

                    // --- POST DETAILS (CAPTION, LIKES) ---
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
                    
                    Section {
                        VStack(alignment: .leading) {
                            HStack {
                                TextField("Add a comment...", text: $viewModel.newCommentText)
                                    .accessibilityIdentifier("AddACommentTextFieldToPost")

                                Button("Post") {
                                    viewModel.commentOnPost(commentText: viewModel.newCommentText)
                                }
                                .disabled(viewModel.newCommentText.isEmpty || !isWithinLength(viewModel.newCommentText, max: GVOAppConstants.maxCommentLength))
                                .accessibilityIdentifier("PostCommentButton")
                            }
                            CharacterCounter(text: viewModel.newCommentText, max: GVOAppConstants.maxCommentLength)
                        }
                    }
                    .padding()
                    
                    // --- COMMENTS SECTION ---
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
        .sheet(item: $viewModel.threadToReplyTo) { thread in
            ReplyView(thread: thread) { commentText in
                // This is the action that gets called when "Send" is tapped
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
        .onChange(of: viewModel.postWasDeleted) { wasDeleted in
            // The post was deleted out from under this view; pop back to the feed.
            if wasDeleted { dismiss() }
        }
        .environmentObject(viewModel) // Pass VM to subviews
    }

    struct ReportView: View {
        @Environment(\.dismiss) var dismiss
        @State private var reason: String = ""
        
        let onSubmit: (String) -> Void
        
        var body: some View {
            NavigationView {
                Form {
                    Section(header: Text("Provide a Reason")) {
                        TextField("Reason for reporting...", text: $reason)
                            .accessibilityIdentifier("ProvideAReasonTextField")
                    }

                    Button("Submit Report") {
                        if !reason.isEmpty {
                            onSubmit(reason)
                            dismiss()
                        }
                    }
                    .tint(.red)
                    .accessibilityIdentifier("SubmitReportButton")
                }
                .navigationTitle("Report Item")
                .scrollDismissesKeyboard(.immediately)
                .navigationBarItems(leading: Button("Cancel") {
                    dismiss()
                })
            }
        }
    }
    
    struct CommentRowView: View {
        let comment: CommentViewData

        let isReported: Bool

        /// Whether this comment was authored by the signed-in user. The backend
        /// rejects liking your own comment, so the like heart is hidden and the
        /// double-tap-to-like gesture is a no-op when true.
        let isOwn: Bool

        // Actions passed from the parent
        let onLike: () -> Void
        let onUnlike: () -> Void
        let onLongPress: () -> Void
        let onAuthorTap: () -> Void

        var body: some View {
            HStack(alignment: .top, spacing: 10) {
                // Placeholder for profile picture
                Image(systemName: "person.circle.fill")
                    .font(.title)
                    .foregroundColor(.secondary)
                
                VStack(alignment: .leading, spacing: 4) {
                    // Comment body with author. Tap the author's name to open
                    // their profile. A plain tap gesture (not a NavigationLink)
                    // so the row's long-press (report/delete) and double-tap
                    // (like) gestures aren't swallowed by a nested Button.
                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text(comment.authorUsername)
                            .fontWeight(.bold)
                            .font(.subheadline)
                            .contentShape(Rectangle())
                            .onTapGesture { onAuthorTap() }
                            // The tap gesture isn't visible to VoiceOver on a
                            // plain Text, so announce this as a button that
                            // opens the author's profile.
                            .accessibilityAddTraits(.isButton)
                            .accessibilityHint("Opens \(comment.authorUsername)'s profile")
                            .accessibilityIdentifier("CommentAuthor")
                        Text(comment.body)
                            .font(.subheadline)
                            .accessibilityIdentifier("CommentText")
                            .accessibilityLabel(comment.body)
                    }
                    
                    // Info row
                    HStack(spacing: 16) {
                        Text(RelativeTime.string(from: comment.createdDate))
                            .font(.caption)
                            .foregroundColor(.secondary)

                        if !isOwn {
                            Button {
                                if comment.isLiked { onUnlike() } else { onLike() }
                            } label: {
                                Image(systemName: comment.isLiked ? "heart.fill" : "heart")
                                    .foregroundColor(Color(UIColor.systemRed))
                                    .font(.caption)
                            }
                            .accessibilityLabel(comment.isLiked ? "Unlike comment" : "Like comment")
                        }

                        Text("\(comment.likeCount) likes")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .accessibilityIdentifier("CommentLikesCount")
                        
                        if isReported {
                            Image(systemName: "flag.fill")
                                .foregroundColor(.red)
                                .font(.caption) // Make it a bit smaller
                                .accessibilityIdentifier("ReportedCommentIcon")
                        }
                    }
                }
                
                Spacer()
            }
            .padding(.vertical, 8)
            // --- Interactions ---
            // --- UPDATED ---
            .onTapGesture(count: 2) {
                // The backend rejects liking your own comment, so double-tap is
                // a no-op on the current user's own comment.
                guard !isOwn else { return }
                // Drive the action from the server-backed like state
                if comment.isLiked {
                    onUnlike()
                } else {
                    onLike()
                }
            }
            .onLongPressGesture {
                onLongPress()
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("CommentStack")
            .accessibilityAddTraits(.isButton) 
        }
    }
    
    struct CommentThreadView: View {
        @EnvironmentObject var viewModel: PostDetailViewModel
        let thread: CommentThreadViewData
        let onAuthorTap: (String) -> Void

        var body: some View {
            VStack(alignment: .leading, spacing: 0) {
                if let rootComment = thread.comments.first {
                    // Show the root comment
                    CommentRowView(comment: rootComment,
                                   isReported: viewModel.reportedCommentIds.contains(rootComment.id),
                                   isOwn: viewModel.isOwnComment(rootComment),
                                   onLike: {
                                       viewModel.likeComment(rootComment)
                                   },
                                   onUnlike: { // --- ADDED ---
                                       viewModel.unlikeComment(rootComment)
                                   },
                                   onLongPress: {
                                       viewModel.commentForAction = rootComment
                                   },
                                   onAuthorTap: {
                                       onAuthorTap(rootComment.authorUsername)
                                   })
                    Section {
                        HStack {
                            TextField("Add a comment...", text: $viewModel.newCommentText)
                                .accessibilityIdentifier("AddACommentTextFieldToThread")

                            Button("Reply") {
                                // This sets the @Published var, triggering the sheet
                                viewModel.threadToReplyTo = thread
                            }
                            .font(.caption)
                            .fontWeight(.bold)
                            .padding(.leading, 50) // Aligns with comment text
                            .padding(.bottom, 8)
                            .accessibilityIdentifier("ReplyToCommentThreadButton")
                        }
                    }
                    .padding()
                }
                
                // Show replies, if any
                if thread.comments.count > 1 {
                    // Indent replies
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(thread.comments.dropFirst()) { reply in
                            // --- UPDATED ---
                            CommentRowView(comment: reply,
                                           isReported: viewModel.reportedCommentIds.contains(reply.id),
                                           isOwn: viewModel.isOwnComment(reply),
                                           onLike: {
                                               viewModel.likeComment(reply)
                                           },
                                           onUnlike: { // --- ADDED ---
                                               viewModel.unlikeComment(reply)
                                           },
                                           onLongPress: {
                                               viewModel.commentForAction = reply
                                           },
                                           onAuthorTap: {
                                               onAuthorTap(reply.authorUsername)
                                           })
                        }
                    }
                    .padding(.leading, 40) // Indentation for replies
                }
            }
        }
    }
    
    /// A view presented as a sheet for replying to a comment thread.
    struct ReplyView: View {
        @Environment(\.dismiss) var dismiss
        
        /// The thread being replied to (passed in).
        let thread: CommentThreadViewData
        
        /// The action to perform when "Send" is tapped.
        let onSubmit: (String) -> Void
        
        /// Local state to hold the text being typed.
        @State private var replyText: String = ""
        
        var body: some View {
            NavigationView {
                Form {
                    Section(header: Text("Replying to \(thread.comments.first?.authorUsername ?? "Comment")")) {
                        TextEditor(text: $replyText)
                            .frame(minHeight: 150)
                        CharacterCounter(text: replyText, max: GVOAppConstants.maxCommentLength)
                    }
                }
                .navigationTitle("Post Reply")
                .navigationBarTitleDisplayMode(.inline)
                .scrollDismissesKeyboard(.immediately)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") {
                            dismiss()
                        }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Send") {
                            onSubmit(replyText)
                            dismiss()
                        }
                        .disabled(replyText.isEmpty || !isWithinLength(replyText, max: GVOAppConstants.maxCommentLength))
                    }
                }
            }
        }
    }
}


#Preview {
    PostDetailView(postIdentifier: "123", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
