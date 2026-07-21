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
    @State private var isLoading = false
    @State private var showSuccessAlert = false
    @State private var successAlertMessage = "Your post was shared successfully!"
    @State private var showFailureAlert = false
    @State private var failureAlertMessage = ""
    
    @Binding var tabSelection: Int
    
    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("New Post Details")) {
                    // A prominent, full-width button reads as the primary call to
                    // action rather than looking like plain tappable text.
                    let pickerLabel = Label(
                        selectedImageData == nil ? "Select a Photo (Optional)" : "Change Photo",
                        systemImage: "photo.on.rectangle.angled"
                    )
                    .font(.headline)
                    .frame(maxWidth: .infinity)

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

                    if let selectedImageData,
                       let uiImage = UIImage(data: selectedImageData)
                    {
                        Image(uiImage: uiImage)
                            .resizable().scaledToFit().frame(
                                maxWidth: .infinity,
                                maxHeight: 200
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 10))
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
                }
                
                if isLoading {
                    HStack {
                        Spacer()
                        ProgressView()
                        Spacer()
                    }
                } else {
                    Button(action: makePost) { Text("Share Post") }
                        .disabled(caption.isEmpty || !isWithinLength(caption, max: GVOAppConstants.maxCaptionLength))
                        .accessibilityIdentifier("SharePostButton")
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
                    caption: caption
                )

                // Reload the Profile tab's grid so the new post appears there
                // immediately, without waiting for a manual pull-to-refresh.
                NotificationCenter.default.post(name: .postCreated, object: nil)

                // A post flagged by automated review is created hidden pending
                // appeal; tell the user it's hidden but appealable rather than
                // implying it went live.
                let response = try? JSONDecoder().decode(MakePostResponse.self, from: responseData)
                if response?.hidden == true {
                    successAlertMessage = response?.message
                        ?? "Your post did not pass automated review. It is hidden for now but you can appeal the decision."
                } else {
                    successAlertMessage = "Your post was shared successfully!"
                }

                // Reset the form and show the success alert
                isLoading = false
                caption = ""
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
