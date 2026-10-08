//
//  NewPostView.swift
//  Vibes
//
//  Created by Andrew Katson on 10/8/25.
//

import PhotosUI  // 1. Import the PhotosUI framework
import SwiftUI

struct NewPostView: View {
    /// Which kind of post is being composed (issue #520). Nested so the name
    /// stays module-qualified for the test targets that also compile this file.
    enum PostType: String, CaseIterable, Identifiable {
        case text = "Text"
        case image = "Image"
        var id: String { rawValue }
    }

    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    // Create an instance of the S3Uploader
    private let s3Uploader = S3Uploader()

    @State private var postType: PostType = .text
    // Whether the formatting controls are expanded. A text post is all about
    // its caption so they start open; on an image post they're a secondary
    // "Advanced options" that starts collapsed (issue #520).
    @State private var isFormattingExpanded = true
    @State private var selectedItem: PhotosPickerItem?
    @State private var selectedImageData: Data?
    // Decoded once when the data changes rather than on every body pass: the
    // photo is drawn in two rows, and re-decoding inside layout made each
    // pass of the Form's row sizing far more expensive (issue #549).
    @State private var selectedImage: UIImage?
    @State private var caption = ""
    @State private var selectedAudience: PostAudience = .public
    // Turn off commenting from the moment the post is created (issue #492).
    @State private var commentsDisabled = false
    // Whole-caption font + whole-tile background color keys (issue #318).
    @State private var captionFont = "default"
    @State private var backgroundColor = "default"
    @State private var isLoading = false

    /// Height of the chosen-photo row and side of the preview square. Fixed so
    /// neither row's height depends on its width (issue #549).
    private static let photoRowHeight: CGFloat = 240

    private let fontOptions = ["default", "serif", "monospace", "rounded", "handwriting"]
    private let backgroundOptions = ["default", "sky", "mint", "blush", "lemon", "lavender"]
    @State private var showSuccessAlert = false
    @State private var successAlertMessage = "Your post was shared successfully!"
    @State private var showFailureAlert = false
    @State private var failureAlertMessage = ""

    @Binding var tabSelection: Int

    private var isImagePost: Bool { postType == .image }

    // The photo only counts on the Image tab: a picked image is kept across a
    // tab switch (so flipping back doesn't lose it) but a text post never
    // sends it.
    private var photoData: Data? { isImagePost ? selectedImageData : nil }

    // The background color is only meaningful on a text post; on an image post
    // the photo fills the tile and the color never shows (issue #421), so the
    // control is hidden and `default` is sent. The user's pick survives a round
    // trip through the Image tab so it's still there if they come back to Text.
    private var showBackgroundControls: Bool { !isImagePost }
    private var effectiveBackgroundColor: String { isImagePost ? "default" : backgroundColor }

    // An image post needs its photo before it can be shared — that's what makes
    // it an image post rather than a text post with a stray picture (issue #520).
    private var canShare: Bool {
        !caption.isEmpty
            && isWithinLength(caption, max: GVOAppConstants.maxCaptionLength)
            && (!isImagePost || photoData != nil)
    }

    private var previewCaption: String {
        caption.isEmpty ? "Your caption will look like this." : caption
    }

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("New Post Details")) {
                    // Text vs. image post (issue #520): the same segmented
                    // control as the feed's For You / Following switch.
                    Picker("Post Type", selection: $postType) {
                        ForEach(PostType.allCases) { type in
                            Text(type.rawValue).tag(type).accessibilityIdentifier(type.rawValue)
                        }
                    }
                    .pickerStyle(.segmented)
                    // Locked while a post is in flight so the kind of post
                    // being sent can't change under the upload.
                    .disabled(isLoading)
                    .accessibilityIdentifier("PostTypePicker")

                    // Only an image post has a photo picker (issue #520).
                    if isImagePost {
                        photoControls
                    }

                    // TextEditor has no built-in placeholder, so overlay one that
                    // shows until the user starts typing a description.
                    ZStack(alignment: .topLeading) {
                        if caption.isEmpty {
                            Text("Put a description here")
                                .foregroundColor(Color(.placeholderText))
                                .padding(.top, 8)
                                .padding(.leading, 5)
                                .allowsHitTesting(false)
                        }
                        TextEditor(text: $caption).frame(height: 100).accessibilityIdentifier("CaptionTextEditor")
                    }
                    CharacterCounter(text: caption, max: GVOAppConstants.maxCaptionLength)

                    // Who may see the post (issue #392).
                    Picker("Audience", selection: $selectedAudience) {
                        ForEach(PostAudience.allCases) { audience in
                            Text(audience.displayName).tag(audience)
                        }
                    }
                    .accessibilityIdentifier("AudiencePicker")

                    // Let the author turn off commenting from the moment the
                    // post goes up (issue #492), instead of only being able to
                    // lock it afterward.
                    Toggle("Turn off commenting", isOn: $commentsDisabled)
                        .accessibilityIdentifier("CommentsDisabledToggle")
                }

                // The Share button stays directly under the caption section so
                // it keeps its original, on-screen position (SwiftUI's Form is a
                // lazy list; pushing the button far down can make it unreachable
                // for automation). The optional style controls follow below it.
                //
                // While a post is submitting, keep the button in place and switch
                // it to a "Processing…" state rather than hiding it (issue #306).
                // A prominent style makes it read clearly as the primary action
                // (issue #280).
                Button(action: makePost) {
                    HStack {
                        Spacer()
                        if isLoading {
                            ProgressView()
                            Text("Processing…")
                        } else {
                            Text("Share Post")
                        }
                        Spacer()
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(isLoading || !canShare)
                .accessibilityIdentifier("SharePostButton")

                // Text customization (issue #318) in a collapsible group. On a
                // text post the caption *is* the post, so the controls start
                // expanded under "Text formatting"; on an image post they're a
                // secondary "Advanced options" that starts collapsed. Either way
                // the user can toggle it (issue #520).
                Section {
                    DisclosureGroup(isExpanded: $isFormattingExpanded) {
                        Picker("Font", selection: $captionFont) {
                            ForEach(fontOptions, id: \.self) { key in
                                Text(key.capitalized).tag(key)
                            }
                        }
                        .accessibilityIdentifier("CaptionFontPicker")

                        // On an image post the background color never shows (the
                        // photo fills the post, not a caption tile), so hide the
                        // control to avoid promising a change that never appears
                        // (issue #421).
                        if showBackgroundControls {
                            Picker("Background", selection: $backgroundColor) {
                                ForEach(backgroundOptions, id: \.self) { key in
                                    Text(key.capitalized).tag(key)
                                }
                            }
                            .accessibilityIdentifier("BackgroundColorPicker")
                        }
                    } label: {
                        Text(isImagePost ? "Advanced options" : "Text formatting")
                    }
                    .accessibilityIdentifier("FormattingDisclosure")
                }

                // A live preview of how the caption will read on the post: the
                // styled tile for a text post, or the caption under the photo
                // (or its placeholder) for an image post, so the styling is
                // visible before a photo is even chosen (issue #520).
                Section(header: Text("Preview")) {
                    if isImagePost {
                        imagePostPreview
                    } else {
                        CaptionTileView(
                            caption: previewCaption,
                            lineLimit: nil,
                            captionFont: captionFont,
                            backgroundColor: backgroundColor
                        )
                        .frame(height: 120)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .accessibilityIdentifier("CaptionPreview")
                    }
                }
            }
            .navigationTitle("Create Post")
            .scrollDismissesKeyboard(.immediately)
            // Alert for SUCCESS
            .alert("Success!", isPresented: $showSuccessAlert) {
                Button("OK") {
                    // Go back to HomeView
                    tabSelection = 0
                }.accessibilityIdentifier("OkButtonSuccess")
            } message: {
                Text(successAlertMessage)
            }

            // Alert for FAILURE
            .alert("Post Failed", isPresented: $showFailureAlert) {
                Button("OK") {
                    // This button does nothing, keeping the user on the view.
                }.accessibilityIdentifier("OkButtonFailure")
            } message: {
                Text(failureAlertMessage)
            }
            .onChange(of: selectedItem) {
                Task {
                    selectedImageData = try? await selectedItem?
                        .loadTransferable(type: Data.self)
                }
            }
            .onChange(of: selectedImageData) {
                selectedImage = selectedImageData.flatMap { UIImage(data: $0) }
            }
            // Each tab has its own default for the formatting group: open for
            // text, collapsed behind "Advanced options" for image (issue #520).
            .onChange(of: postType) {
                isFormattingExpanded = postType == .text
            }
        }
    }

    /// The chosen photo (shown prominently first, issue #305) and the button
    /// that picks or changes it.
    @ViewBuilder
    private var photoControls: some View {
        if let selectedImage {
            // A fixed row height, not one derived from the row's width: a Form
            // row whose height depends on its width can send the list's
            // self-sizing into an endless layout loop that freezes the app when
            // the row scrolls into view (issue #549).
            Image(uiImage: selectedImage)
                .resizable().scaledToFit()
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .frame(maxWidth: .infinity)
                .frame(height: Self.photoRowHeight)
                // The UI tests drag on this image to scroll the form (it's a
                // plain row that hands the pan to the Form, unlike the caption
                // editor or the segmented picker).
                .accessibilityIdentifier("SelectedPhotoImage")
        }

        // A prominent, full-width button reads as the primary call to action
        // rather than looking like plain tappable text. The label is centered
        // so it doesn't read as left-aligned text (issue #305).
        let pickerLabel = Label(
            selectedImageData == nil ? "Select a Photo" : "Change Photo",
            systemImage: "photo.on.rectangle.angled"
        )
        .font(.headline)
        .frame(maxWidth: .infinity, alignment: .center)

        if isUITesting() {
            // Testing mode: Use a regular button
            Button {
                // Load a test image
                if let testImage = UIImage(systemName: "photo.fill"),
                   let imageData = testImage.jpegData(compressionQuality: 0.8) {
                    selectedImageData = imageData
                }
            } label: {
                pickerLabel
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .accessibilityIdentifier("SelectAPhotoPicker")
        } else {
            // Production mode: Use real PhotosPicker
            PhotosPicker(
                selection: $selectedItem,
                matching: .images,
                photoLibrary: .shared()
            ) {
                pickerLabel
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .accessibilityIdentifier("SelectAPhotoPicker")
        }
    }

    /// An image post as the feed lays it out: the photo (or a placeholder that
    /// holds its place until one is picked) with the caption underneath in the
    /// chosen font (issue #450). The media is the same 1:1 square crop the
    /// feed uses (FeedView), for both states, so the preview matches the
    /// published post and doesn't jump when a photo is picked.
    ///
    /// The square has a fixed side rather than filling the row's width: an
    /// `aspectRatio` square makes the row's height a function of its width,
    /// which in a Form can loop the list's self-sizing forever and hang the
    /// app as soon as this row scrolls into view (issue #549).
    private var imagePostPreview: some View {
        VStack(alignment: .leading, spacing: 8) {
            Color(.secondarySystemFill)
                .frame(width: Self.photoRowHeight, height: Self.photoRowHeight)
                .overlay {
                    if let selectedImage {
                        Image(uiImage: selectedImage)
                            .resizable()
                            .scaledToFill()
                    } else {
                        Text("Your photo will appear here")
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding()
                    }
                }
                .clipped()
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .frame(maxWidth: .infinity)
            Text(previewCaption)
                .font(TextFormatting.captionFont(captionFont, size: UIFont.preferredFont(forTextStyle: .body).pointSize))
                .foregroundColor(caption.isEmpty ? .secondary : .primary)
        }
        .accessibilityIdentifier("CaptionPreview")
    }

    private func makePost() {
        Task {
            isLoading = true
            do {
                // Load session
                let userSession: UserSession
                if isTesting() {
                    userSession = try keychainHelper.load(UserSession.self, from: GVOAppConstants.keychainService, account: "userSessionToken") ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                } else {
                    guard let loaded = try keychainHelper.load(UserSession.self, from: GVOAppConstants.keychainService, account: "userSessionToken") else {
                        failureAlertMessage = "You must be logged in to post."
                        isLoading = false
                        showFailureAlert = true
                        return
                    }
                    userSession = loaded
                }

                // 2. UPLOAD IMAGE using a backend-issued presigned S3 URL (#310).
                // Only an image post carries a photo (#520): `photoData` is nil
                // for a text post, so the upload is skipped entirely and a
                // text-only post is created (#307).
                var imageURLString: String? = nil
                if let imageData = photoData {
                    var uploadedURLString = "https://picsum.photos/400/400"
                    if !isTesting() {
                        let uploadUrlData = try await api.createUploadUrl(
                            sessionManagementToken: userSession.sessionToken
                        )
                        let uploadUrlResponse = try JSONDecoder().decode(UploadUrlResponse.self, from: uploadUrlData)
                        guard let uploadURL = URL(string: uploadUrlResponse.uploadUrl) else {
                            throw ImageUploadError.invalidUploadURL
                        }
                        try await s3Uploader.upload(data: imageData, to: uploadURL)
                        uploadedURLString = uploadUrlResponse.imageUrl
                    }
                    imageURLString = uploadedURLString
                }

                // 3. SEND THE IMAGE URL (IF ANY) TO THE BACKEND

                let responseData = try await api.makePost(
                    sessionManagementToken: userSession.sessionToken,
                    imageURL: imageURLString,
                    caption: caption,
                    audience: selectedAudience.rawValue,
                    captionFont: captionFont,
                    backgroundColor: effectiveBackgroundColor,
                    commentsDisabled: commentsDisabled
                )

                // Reload the Profile tab's grid so the new post appears there
                // immediately, without waiting for a manual pull-to-refresh.
                NotificationCenter.default.post(name: .postCreated, object: nil)

                // Classification is asynchronous (issue #282): the backend
                // accepts the post in a pending state and reviews it in the
                // background, so tell the user it's under review — the Home
                // grid shows its progress and outcome. Older backends
                // classified inline; their hidden response means the post was
                // flagged but is appealable.
                let response = try? JSONDecoder().decode(MakePostResponse.self, from: responseData)
                if response?.status == "pending" || response?.hiddenReason == "pending_classification" {
                    successAlertMessage = response?.message
                        ?? "Your post is being reviewed and will be visible to others once it is approved."
                } else if response?.hidden == true {
                    successAlertMessage = response?.message
                        ?? "Your post did not pass automated review. It is hidden for now but you can appeal the decision."
                } else {
                    successAlertMessage = "Your post was shared successfully!"
                }

                // Reset the form and show the success alert. That includes the
                // Text tab and its expanded formatting group — otherwise a
                // second post would open on an empty Image tab with Share
                // disabled.
                isLoading = false
                postType = .text
                isFormattingExpanded = true
                caption = ""
                commentsDisabled = false
                captionFont = "default"
                backgroundColor = "default"
                selectedItem = nil
                selectedImageData = nil
                showSuccessAlert = true // This will trigger the success alert

            } catch {
                // Set the error message and show the failure alert
                failureAlertMessage = error.userFacingMessage
                isLoading = false
                showFailureAlert = true // This will trigger the failure alert
            }
        }
    }
}

#Preview {
    NewPostView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper, tabSelection: .constant(2))
}
