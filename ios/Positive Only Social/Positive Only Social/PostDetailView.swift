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

    // Public init
    init(postIdentifier: String, api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: PostDetailViewModel(postIdentifier: postIdentifier, api: api, keychainHelper: keychainHelper))
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
                        viewModel.showReportSheetForPost = true
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
                        
                        Text(post.authorUsername)
                            .fontWeight(.bold)
                        + Text(" ") +
                        Text(post.caption)
                    }
                    .padding(.horizontal)

                    Divider()
                    
                    Section {
                        HStack {
                            TextField("Add a comment...", text: $viewModel.newCommentText)
                                .accessibilityIdentifier("AddACommentTextFieldToPost")

                            Button("Post") {
                                viewModel.commentOnPost(commentText: viewModel.newCommentText)
                            }
                            .disabled(viewModel.newCommentText.isEmpty)
                            .accessibilityIdentifier("PostCommentButton")
                        }
                    }
                    .padding()
                    
                    // --- COMMENTS SECTION ---
                    Text("Comments")
                        .font(.headline)
                        .padding(.horizontal)
                    
                    LazyVStack(spacing: 16) {
                        ForEach(viewModel.commentThreads) { thread in
                            CommentThreadView(thread: thread)
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
        .scrollDismissesKeyboard(.immediately)
        .onSubmit { hideKeyboard() }
        .refreshable {
            // Pull-to-refresh: reload the post details and comments from the backend.
            await viewModel.refresh()
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
                .onSubmit { hideKeyboard() }
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
        let onReport: () -> Void
        
        var body: some View {
            HStack(alignment: .top, spacing: 10) {
                // Placeholder for profile picture
                Image(systemName: "person.circle.fill")
                    .font(.title)
                    .foregroundColor(.secondary)
                
                VStack(alignment: .leading, spacing: 4) {
                    // Comment body with author
                    Text(comment.authorUsername)
                        .fontWeight(.bold)
                        .font(.subheadline)
                        .accessibilityIdentifier("CommentAuthor")
                    Text(" ") 
                    Text(comment.body)
                        .font(.subheadline)
                        .accessibilityIdentifier("CommentText")
                        .accessibilityLabel(comment.body)
                    
                    // Info row
                    HStack(spacing: 16) {
                        Text(comment.createdDate, style: .relative)
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
                onReport()
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("CommentStack")
            .accessibilityAddTraits(.isButton) 
        }
    }
    
    struct CommentThreadView: View {
        @EnvironmentObject var viewModel: PostDetailViewModel
        let thread: CommentThreadViewData
        
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
                                   onReport: {
                                       viewModel.commentToReport = rootComment
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
                                           onReport: {
                                               viewModel.commentToReport = reply
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
                        .disabled(replyText.isEmpty)
                    }
                }
            }
        }
    }
}


#Preview {
    PostDetailView(postIdentifier: "123", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
