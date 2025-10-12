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
    // Create an instance of the S3Uploader
    private let s3Uploader = S3Uploader()

    @State private var selectedItem: PhotosPickerItem?
    @State private var selectedImageData: Data?
    @State private var caption = ""
    @State private var isLoading = false
    @State private var showingAlert = false
    @State private var alertMessage = ""

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

                    TextEditor(text: $caption).frame(height: 100)
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
                }
            }
            .navigationTitle("Create Post")
            .alert("Post Status", isPresented: $showingAlert) {
                Button("OK") {}
            } message: {
                Text(alertMessage)
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
            alertMessage = "Please select an image before posting."
            showingAlert = true
            return
        }

        Task {
            isLoading = true
            do {
                // 1. UPLOAD IMAGE TO S3
                // Create a unique file name to avoid collisions
                let uniqueFileName = "\(UUID().uuidString).jpg"
                let imageURL = try await s3Uploader.upload(
                    data: imageData,
                    fileName: uniqueFileName
                )

                // 2. SEND THE S3 URL TO YOUR BACKEND
                let token =
                    try KeychainHelper.shared.load(
                        String.self,
                        from: "positive-only-social.Positive-Only-Social",
                        account: "userSessionToken"
                    ) ?? ""

                // Call your original API, but now with the URL from S3
                _ = try await api.makePost(
                    sessionManagementToken: token,
                    imageURL: imageURL.absoluteString,  // Use the URL from S3
                    caption: caption
                )

                alertMessage = "Your post was shared successfully!"
                caption = ""
                selectedItem = nil
                selectedImageData = nil

            } catch {
                alertMessage =
                    "Failed to share post. Error: \(error.localizedDescription)"
            }

            isLoading = false
            showingAlert = true
        }
    }
}

#Preview {
    NewPostView(api: StatefulStubbedAPI())
}
