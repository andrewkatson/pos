//
//  TagFeedView.swift
//  Positive Only Social
//
//  Hashtag support (issue #379): the tag feed a user opens by tapping a
//  #hashtag in a caption, plus the caption view that makes those tags tappable.
//

import Foundation
import SwiftUI

/// A value identifying a tag feed, used as a navigation destination (#379).
struct TagRoute: Hashable {
    let name: String
}

/// A caption segment: literal text, or a #hashtag with its normalized name.
enum CaptionSegment: Equatable {
    case text(String)
    case tag(text: String, name: String)
}

/// Caps mirroring the backend (`backend/user_system/constants.py`), so a #token
/// is only linkified when the backend would actually store it as a tag.
private let maxTagLength = 100
private let maxTagsPerPost = 30

/// Splits a caption into text and #hashtag segments, mirroring the backend's
/// extraction (`backend/user_system/tags.py`): a '#' followed by unicode
/// letters, numbers, or underscore (\p{L}\p{N}_). That class is exactly
/// equivalent to the backend's Python `\w` on a `str` (both are alphanumerics
/// plus underscore and exclude combining marks / connector punctuation), so the
/// two tokenize a caption identically. `.lowercased()` is locale-independent,
/// matching the backend's str.lower(). The tag `name` is lowercased; `text`
/// keeps the original casing.
/// Only tags the backend would store are emitted as `.tag` — overlong tags and
/// anything past the first `maxTagsPerPost` unique names stay as plain text, so
/// a tapped tag always resolves and the caption still reads verbatim.
func captionSegments(_ caption: String) -> [CaptionSegment] {
    if caption.isEmpty { return [] }
    guard let regex = try? NSRegularExpression(pattern: "#([\\p{L}\\p{N}_]+)") else {
        return [.text(caption)]
    }
    let nsRange = NSRange(caption.startIndex..., in: caption)
    var segments: [CaptionSegment] = []
    var linkable = Set<String>()
    var lastEnd = caption.startIndex
    regex.enumerateMatches(in: caption, range: nsRange) { match, _, _ in
        guard let match,
              let full = Range(match.range, in: caption),
              let nameRange = Range(match.range(at: 1), in: caption) else { return }
        let name = caption[nameRange].lowercased()
        let canLink = name.count <= maxTagLength
            && (linkable.contains(name) || linkable.count < maxTagsPerPost)
        guard canLink else { return }  // leave as plain text
        linkable.insert(name)
        if full.lowerBound > lastEnd {
            segments.append(.text(String(caption[lastEnd..<full.lowerBound])))
        }
        segments.append(.tag(text: String(caption[full]), name: name))
        lastEnd = full.upperBound
    }
    if lastEnd < caption.endIndex {
        segments.append(.text(String(caption[lastEnd...])))
    }
    return segments
}

/// A post caption whose #hashtags are tappable (issue #379). Rendered as a
/// single Text using link runs (a custom `vibestag:` scheme) so the tags wrap
/// inline with the caption; taps are intercepted and reported via
/// `onTagTapped` with the normalized tag name, so the host can push the tag
/// feed onto its NavigationStack.
struct TaggedCaptionText: View {
    let caption: String
    let onTagTapped: (String) -> Void

    private static let tagScheme = "vibestag"

    var body: some View {
        Text(attributed)
            .tint(.accentColor)
            .environment(\.openURL, OpenURLAction { url in
                guard url.scheme == Self.tagScheme else { return .systemAction }
                let raw = String(url.absoluteString.dropFirst(Self.tagScheme.count + 1))
                let name = raw.removingPercentEncoding ?? raw
                if !name.isEmpty { onTagTapped(name) }
                return .handled
            })
    }

    private var attributed: AttributedString {
        var result = AttributedString()
        for segment in captionSegments(caption) {
            switch segment {
            case .text(let text):
                result.append(AttributedString(text))
            case .tag(let text, let name):
                var run = AttributedString(text)
                let encoded = name.addingPercentEncoding(withAllowedCharacters: .urlHostAllowed) ?? name
                if let url = URL(string: "\(Self.tagScheme):\(encoded)") {
                    run.link = url
                }
                result.append(run)
            }
        }
        return result
    }
}

/// The tag feed (issue #379): the posts carrying a given #hashtag, newest
/// first, paginated. Pushed onto an existing NavigationStack, so it inherits
/// that stack's Post/User destinations for opening a post or an author.
struct TagFeedView: View {
    @StateObject private var viewModel: TagFeedViewModel
    @StateObject private var postActions: PostActionsViewModel

    let tag: String
    let api: Networking
    let keychainHelper: KeychainHelperProtocol

    init(tag: String, api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.tag = tag
        self.api = api
        self.keychainHelper = keychainHelper
        _viewModel = StateObject(wrappedValue: TagFeedViewModel(tag: tag, api: api, keychainHelper: keychainHelper))
        _postActions = StateObject(wrappedValue: PostActionsViewModel(api: api, keychainHelper: keychainHelper))
    }

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 25) {
                if viewModel.posts.isEmpty && !viewModel.isLoadingNextPage {
                    Text("No posts with #\(tag) yet.")
                        .foregroundColor(.secondary)
                        .padding()
                        .accessibilityIdentifier("TagFeedEmpty")
                }
                ForEach(viewModel.posts) { post in
                    VStack(alignment: .leading, spacing: 10) {
                        // Tapping the author opens their profile — or the
                        // Profile tab when it's you (issue #347).
                        AuthorNameLink(
                            username: post.authorUsername,
                            isCurrentUser: postActions.state(for: post).isOwn
                        ) {
                            Text(post.authorUsername)
                                .font(.headline)
                                .fontWeight(.bold)
                                .padding(.horizontal)
                        }
                        .accessibilityIdentifier("PostAuthor")

                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        blurHash: post.blurHash,
                                        caption: post.caption,
                                        placeholderColor: Color(.systemGray5)
                                    )
                                }
                                .clipped()
                                .cornerRadius(15)
                        }
                        .onAppear {
                            if post.id == viewModel.posts.last?.id {
                                viewModel.fetchNextPage()
                            }
                        }
                        .accessibilityIdentifier("TagPostImage")

                        PostActionBar(post: post, postActions: postActions, showsPostDetails: true)
                            .padding(.horizontal)
                    }
                }
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }
            }
            .padding(.top)
        }
        .navigationTitle("#\(tag)")
        .navigationBarTitleDisplayMode(.inline)
        .postActionDialogs(postActions)
        .refreshable {
            await Task { await viewModel.refresh() }.value
        }
        .onAppear {
            if viewModel.posts.isEmpty {
                viewModel.fetchNextPage()
            }
        }
    }
}
