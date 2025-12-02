//
//  NewPostView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import PhotosUI  // 1. Import the PhotosUI framework
import SwiftUI

struct NewPostView: View {
    let api: APIProtocol
    let keychainHelper: KeychainHelperProtocol
    // Create an instance of the S3Uploader
    private let s3Uploader = S3Uploader()

    @State private var selectedItem: PhotosPickerItem?
    @State private var selectedImageData: Data?
    @State private var caption = ""
    @State private var isLoading = false
    @State private var showSuccessAlert = false
    @State private var showFailureAlert = false
    @State private var failureAlertMessage = ""

    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("New Post Details")) {
                    PhotosPicker(
                        selection: $selectedItem,
                        matching: .images,
                        photoLibrary: .shared()
                    ) {
                        Text("Select a photo")
                    }.accessibilityIdentifier("SelectAPhotoPicker")

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

                    TextEditor(text: $caption).frame(height: 100).accessibilityIdentifier("CaptionTextEditor")
                }

                if isLoading {
                    HStack {
                        Spacer()
                        ProgressView()
                        Spacer()
                    }
                } else {
                    Button(action: makePost) { Text("Share Post") }
                        .disabled(selectedImageData == nil || caption.isEmpty)
                        .accessibilityIdentifier("SharePostButton")
                }
            }
            .navigationTitle("Create Post")
            // Alert for SUCCESS
            .alert("Success!", isPresented: $showSuccessAlert) {
                Button("OK") {
                    // This is the key: only dismiss when OK is tapped
                    // on the *success* alert.
                    dismiss()
                }.accessibilityIdentifier("OkButtonSuccess")
            } message: {
                Text("Your post was shared successfully!")
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
        guard let imageData = selectedImageData else {
            failureAlertMessage = "Please select an image before posting."
            showFailureAlert = true
            return
        }

        Task {
            isLoading = true
            do {
                // 1. UPLOAD IMAGE TO S3
                let uniqueFileName = "\(UUID().uuidString).jpg"
                
                var imageURL: URL! = URL(string: "https://example.com/image.jpg")!
                if !isTesting() {
                    imageURL = try await s3Uploader.upload(
                        data: imageData,
                        fileName: uniqueFileName
                    )
                }

                // 2. SEND THE S3 URL TO YOUR BACKEND
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: "userSessionToken") ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
                
                _ = try await api.makePost(
                    sessionManagementToken: userSession.sessionToken,
                    imageURL: imageURL.absoluteString,
                    caption: caption
                )

                // --- SUCCESS ---
                // Reset the form and show the success alert
                isLoading = false
                caption = ""
                selectedItem = nil
                selectedImageData = nil
                showSuccessAlert = true // This will trigger the success alert

            } catch {
                // --- FAILURE ---
                // Set the error message and show the failure alert
                failureAlertMessage =
                    "Failed to share post. Error: \(error.localizedDescription)"
                isLoading = false
                showFailureAlert = true // This will trigger the failure alert
            }
        }
    }
}

#Preview {
    NewPostView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
