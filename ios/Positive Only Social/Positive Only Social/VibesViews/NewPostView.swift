//
//  NewPostView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import PhotosUI  // 1. Import the PhotosUI framework
import SwiftUI

struct NewPostView: View {
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    // Create an instance of the S3Uploader
    private let s3Uploader = S3Uploader()

    @State private var selectedItem: PhotosPickerItem?
    @State private var selectedImageData: Data?
    @State private var caption = ""
    @State private var selectedAudience: PostAudience = .public
    // Whole-caption font + whole-tile background color keys (issue #318).
    @State private var captionFont = "default"
    @State private var backgroundColor = "default"
    @State private var isLoading = false

    private let fontOptions = ["default", "serif", "monospace", "rounded", "handwriting"]
    private let backgroundOptions = ["default", "sky", "mint", "blush", "lemon", "lavender"]
    @State private var showSuccessAlert = false
    @State private var successAlertMessage = "Your post was shared successfully!"
    @State private var showFailureAlert = false
    @State private var failureAlertMessage = ""
    
    @Binding var tabSelection: Int

    // The background color is only meaningful on a text-only post; on a photo
    // post the image fills the tile and the color never shows (issue #421).
    private var showBackgroundControls: Bool { selectedImageData == nil }

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("New Post Details")) {
                    // Show the chosen photo prominently first; its "Change Photo"
                    // button sits below it and reads as a caption to the larger
                    // image (issue #305).
                    if let selectedImageData,
                       let uiImage = UIImage(data: selectedImageData)
                    {
                        Image(uiImage: uiImage)
                            .resizable().scaledToFit().frame(
                                maxWidth: .infinity,
                                maxHeight: 240
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    }

                    // A prominent, full-width button reads as the primary call to
                    // action rather than looking like plain tappable text. The
                    // label is centered so it doesn't read as left-aligned text
                    // (issue #305).
                    let pickerLabel = Label(
                        selectedImageData == nil ? "Select a Photo (Optional)" : "Change Photo",
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
                .disabled(isLoading || caption.isEmpty || !isWithinLength(caption, max: GVOAppConstants.maxCaptionLength))
                .accessibilityIdentifier("SharePostButton")

                // Text customization (issue #318): a whole-caption font, a
                // whole-tile background color, and a live preview.
                Section(header: Text("Style")) {
                    Picker("Font", selection: $captionFont) {
                        ForEach(fontOptions, id: \.self) { key in
                            Text(key.capitalized).tag(key)
                        }
                    }
                    .accessibilityIdentifier("CaptionFontPicker")

                    // On a photo post the background color never shows (the photo
                    // fills the post, not a caption tile), so hide the control to
                    // avoid promising a change that never appears (issue #421).
                    if showBackgroundControls {
                        Picker("Background", selection: $backgroundColor) {
                            ForEach(backgroundOptions, id: \.self) { key in
                                Text(key.capitalized).tag(key)
                            }
                        }
                        .accessibilityIdentifier("BackgroundColorPicker")
                    }

                    CaptionTileView(
                        caption: caption.isEmpty ? "Your caption will look like this." : caption,
                        lineLimit: nil,
                        captionFont: captionFont,
                        backgroundColor: showBackgroundControls ? backgroundColor : "default"
                    )
                    .frame(height: 120)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .accessibilityIdentifier("CaptionPreview")
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
            // Adding a photo hides the background control (issue #421); clear any
            // color already picked so a stale value isn't sent with the post.
            .onChange(of: selectedImageData) {
                if selectedImageData != nil {
                    backgroundColor = "default"
                }
            }
        }
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
                // The photo is optional (#307): with no image selected the upload
                // is skipped entirely and a text-only post is created.
                var imageURLString: String? = nil
                if let imageData = selectedImageData {
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
                    backgroundColor: backgroundColor
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

                // Reset the form and show the success alert
                isLoading = false
                caption = ""
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
