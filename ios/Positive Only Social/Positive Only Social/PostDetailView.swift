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
    
    // --- ADDED ---
    // This state tracks the *user's action* (like or unlike)
    // for the main post.
    @State private var isPostLiked = false
    
    // Public init
    init(postIdentifier: String, api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
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
                    // --- Image Interactions ---
                    // --- UPDATED ---
                    .onTapGesture(count: 2) {
                        // Toggle the local like state
                        isPostLiked.toggle()
                        
                        // Call the correct view model function
                        if isPostLiked {
                            viewModel.likePost()
                        } else {
                            viewModel.unlikePost()
                        }
                    }
                    .onLongPressGesture {
                        viewModel.showReportSheetForPost = true
                    }
                    
                    // --- POST DETAILS (CAPTION, LIKES) ---
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            // You could add a like button here
                            Image(systemName: "heart.fill")
                                .foregroundColor(.red)
                            Text("\(post.likeCount) likes")
                                .font(.headline)
                            Spacer()
                        }
                        
                        Text(post.authorUsername)
                            .fontWeight(.bold)
                        + Text(" ") +
                        Text(post.caption)
                    }
                    .padding(.horizontal)

                    Divider()
                    
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
                    }
                    
                    Button("Submit Report") {
                        if !reason.isEmpty {
                            onSubmit(reason)
                            dismiss()
                        }
                    }
                    .tint(.red)
                }
                .navigationTitle("Report Item")
                .navigationBarItems(leading: Button("Cancel") {
                    dismiss()
                })
            }
        }
    }
    
    struct CommentRowView: View {
        let comment: CommentViewData
        
        // --- ADDED ---
        @State private var isLiked = false
        
        // Actions passed from the parent
        let onLike: () -> Void
        let onUnlike: () -> Void // --- ADDED ---
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
                    + Text(" ") +
                    Text(comment.body)
                        .font(.subheadline)
                    
                    // Info row
                    HStack(spacing: 16) {
                        Text(comment.createdDate, style: .relative)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Text("\(comment.likeCount) likes")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
            }
            .padding(.vertical, 8)
            // --- Interactions ---
            // --- UPDATED ---
            .onTapGesture(count: 2) {
                // Toggle the local like state
                isLiked.toggle()
                
                // Call the correct action
                if isLiked {
                    onLike()
                } else {
                    onUnlike()
                }
            }
            .onLongPressGesture {
                onReport()
            }
        }
    }
    
    struct CommentThreadView: View {
        @EnvironmentObject var viewModel: PostDetailViewModel
        let thread: CommentThreadViewData
        
        var body: some View {
            VStack(alignment: .leading, spacing: 0) {
                if let rootComment = thread.comments.first {
                    // Show the root comment
                    // --- UPDATED ---
                    CommentRowView(comment: rootComment,
                                   onLike: {
                                       viewModel.likeComment(rootComment)
                                   },
                                   onUnlike: { // --- ADDED ---
                                       viewModel.unlikeComment(rootComment)
                                   },
                                   onReport: {
                                       viewModel.commentToReport = rootComment
                                   })
                }
                
                // Show replies, if any
                if thread.comments.count > 1 {
                    // Indent replies
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(thread.comments.dropFirst()) { reply in
                            // --- UPDATED ---
                            CommentRowView(comment: reply,
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
}


#Preview {
    PostDetailView(postIdentifier: "123", api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
}
