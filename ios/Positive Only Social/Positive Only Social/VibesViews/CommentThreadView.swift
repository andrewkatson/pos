
import SwiftUI

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
                                  onUnlike: {
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
                           CommentRowView(comment: reply,
                                          isReported: viewModel.reportedCommentIds.contains(reply.id),
                                          isOwn: viewModel.isOwnComment(reply),
                                          onLike: {
                                              viewModel.likeComment(reply)
                                          },
                                          onUnlike: {
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

