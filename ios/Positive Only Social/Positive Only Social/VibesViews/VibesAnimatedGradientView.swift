//
//  VibesAnimatedGradientView.swift
//  Vibes
//
//  Created by Andrew Katson & Eblen Macari on 2026-09-20.
//

import SwiftUI

// MARK: - Animated Gradient Background
struct AnimatedGradientBackground: View {
    
    @State private var animateGradient: Bool = false
    @State private var top: Color
    @State private var middle: Color
    @State private var centre: Color
    @State private var bottom: Color
    
    // Example Colour for this view
    static let exampleTop = SwiftUICore.Color.blue.opacity(0.7)
    static let exampleMiddle = SwiftUICore.Color.purple.opacity(0.8)
    static let exampleCentre = SwiftUICore.Color.indigo.opacity(0.7)
    static let exampleBottom = SwiftUICore.Color.pink.opacity(0.6)
    
    
    // Use this to init the gradient with custom coulor, else
    // Use the designated init "()" and will create
    // one with defualt values
    
    init(
        animateGradient: Bool = false,
        top: Color = exampleTop,
        middle: Color = exampleMiddle,
        centre: Color = exampleCentre,
        bottom: Color = exampleBottom
    ) {
        _animateGradient = State(initialValue: animateGradient)
        _top = State(initialValue: top)
        _middle = State(initialValue: middle)
        _centre = State(initialValue: centre)
        _bottom = State(initialValue: bottom)
    }
    
    // The gradient color array we use to show as animated background image.
    private var gradientColors: [Color] {
        [top, middle, centre, bottom]
    }

    // Animated Gradient background Image
    var body: some View {
        LinearGradient(
            colors: gradientColors,
            startPoint: animateGradient ? .topLeading : .bottomLeading,
            endPoint: animateGradient ? .bottomTrailing : .topTrailing
        )
        .ignoresSafeArea()
        .onAppear {
            // Hold the gradient still under UI tests: this view is the root of
            // the navigation stack, so a repeatForever animation keeps running
            // under every pushed screen and XCUITest never sees the app idle
            // (snapshot and accessibility timeouts). Checked inline (same arg
            // as isUITesting()) to avoid referencing that free function across
            // the test-target membership boundary.
            if CommandLine.arguments.contains("--ui_testing") { return }
            withAnimation(.easeInOut(duration: 6.0).repeatForever(autoreverses: true)) {
                animateGradient.toggle()
            }
        }
    }
}

#Preview {
    AnimatedGradientBackground(
        animateGradient: true,
        top: AnimatedGradientBackground.exampleTop,
        middle: AnimatedGradientBackground.exampleMiddle,
        centre: AnimatedGradientBackground.exampleCentre,
        bottom: AnimatedGradientBackground.exampleBottom
    )
}
