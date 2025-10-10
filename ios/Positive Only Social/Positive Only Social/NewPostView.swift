//
//  PostView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI

struct NewPostView: View {
    let api: APIProtocol
    
    @State private var imageUrl = ""
    @State private var caption = ""
    @State private var isLoading = false
    @State private var showingAlert = false
    @State private var alertMessage = ""
    
    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("New Post Details")) {
                    TextField("Image URL", text: $imageUrl)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                    
                    TextEditor(text: $caption)
                        .frame(height: 100)
                }
                
                if isLoading {
                    HStack {
                        Spacer()
                        ProgressView()
                        Spacer()
                    }
                } else {
                    Button(action: makePost) {
                        Text("Share Post")
                    }
                    .disabled(imageUrl.isEmpty || caption.isEmpty)
                }
            }
            .navigationTitle("Create Post")
            .alert("Post Status", isPresented: $showingAlert) {
                Button("OK") {}
            } message: {
                Text(alertMessage)
            }
        }
    }
    
    private func makePost() {
        Task {
            isLoading = true
            do {
                let token = try KeychainHelper.shared.load(String.self, from: "com.yourapp.bundleid", account: "userSessionToken") ?? ""
                
                _ = try await api.makePost(
                    sessionManagementToken: token,
                    imageURL: imageUrl,
                    caption: caption
                )
                
                alertMessage = "Your post was shared successfully!"
                // Clear the fields after success
                imageUrl = ""
                caption = ""
                
            } catch {
                alertMessage = "Failed to share post. Please try again."
            }
            
            isLoading = false
            showingAlert = true
        }
    }
}

#Preview {
    NewPostView(api: StatefulStubbedAPI())
}
