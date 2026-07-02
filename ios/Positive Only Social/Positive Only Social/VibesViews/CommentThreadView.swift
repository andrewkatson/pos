
import SwiftUI

struct CommentThreadView: View {
       @EnvironmentObject var viewModel: PostDetailViewModel
       let thread: CommentThreadViewData
       let onAuthorTap: (String) -> Void

       /// Hide every comment that sits below the first collapsed one in the
       /// thread, so tapping a comment's header folds away the comments under it
       /// (issue #243).
       private var visibleComments: [CommentViewData] {
           if let collapseIndex = thread.comments.firstIndex(where: {
               viewModel.collapsedCommentIds.contains($0.id)
           }) {
               return Array(thread.comments.prefix(collapseIndex + 1))
           }
           return thread.comments
       }

       var body: some View {
           VStack(alignment: .leading, spacing: 0) {
               if let rootComment = visibleComments.first {
                   // Show the root comment
                   CommentRowView(comment: rootComment,
                                  isReported: viewModel.reportedCommentIds.contains(rootComment.id),
                                  isOwn: viewModel.isOwnComment(rootComment),
                                  isCollapsed: viewModel.collapsedCommentIds.contains(rootComment.id),
                                  onToggleCollapse: {
                                      viewModel.toggleCommentCollapsed(rootComment.id)
                                  },
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
                   // Tapping "Reply" opens the shared composer sheet, the same
                   // dialog used for a new comment on the post.
                   Button("Reply") {
                       viewModel.threadToReplyTo = thread
                   }
                   .font(.caption)
                   .fontWeight(.bold)
                   .padding(.leading, 50) // Aligns with comment text
                   .padding(.vertical, 8)
                   .accessibilityIdentifier("ReplyToCommentThreadButton")
               }

               // Show replies, if any
               if visibleComments.count > 1 {
                   // Indent replies
                   VStack(alignment: .leading, spacing: 0) {
                       ForEach(visibleComments.dropFirst()) { reply in
                           CommentRowView(comment: reply,
                                          isReported: viewModel.reportedCommentIds.contains(reply.id),
                                          isOwn: viewModel.isOwnComment(reply),
                                          isCollapsed: viewModel.collapsedCommentIds.contains(reply.id),
                                          onToggleCollapse: {
                                              viewModel.toggleCommentCollapsed(reply.id)
                                          },
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

