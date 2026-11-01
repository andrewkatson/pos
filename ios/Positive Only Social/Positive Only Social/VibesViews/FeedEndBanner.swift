//
//  FeedEndBanner.swift
//  Vibes
//
//  The "you finished!" banner and confetti shown at the end of a feed or
//  profile once every post has loaded (issue #528).
//

import SwiftUI
import Combine

/// Decides when the end-of-list confetti plays, for one feed or profile.
///
/// It plays once, the first time the banner scrolls into view — and only when
/// the viewer scrolled to get there, so a profile with a handful of posts that
/// fits on one screen just shows the banner rather than throwing confetti every
/// time it opens — and never with Reduce Motion on. `reset()` (when the list
/// reloads) lets finishing it again celebrate again.
@MainActor
final class EndOfListCelebration: ObservableObject {
    /// How long a burst stays on screen; covers the slowest piece's fall.
    static let confettiDuration: TimeInterval = 4.2

    /// When the current burst started; nil while no confetti is showing.
    @Published private(set) var confettiStart: Date?
    /// Whether the list is scrolled away from its top, kept up to date by
    /// `celebratesEndOfList`.
    var isScrolled = false

    private var hasCelebrated = false
    private var clearTask: Task<Void, Never>?

    /// Called when the banner comes on screen.
    func bannerBecameVisible(reduceMotion: Bool) {
        // Seen once is enough, whether or not it earned confetti.
        guard !hasCelebrated else { return }
        hasCelebrated = true
        guard isScrolled, !reduceMotion else { return }

        let start = Date()
        confettiStart = start
        clearTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(Self.confettiDuration))
            guard !Task.isCancelled, let self, self.confettiStart == start else { return }
            self.confettiStart = nil
        }
    }

    /// The list reloaded, so reaching its end again is a fresh finish.
    func reset() {
        hasCelebrated = false
        clearTask?.cancel()
        clearTask = nil
        confettiStart = nil
    }
}

/// What the banner says the viewer just finished; the same wording as the
/// website and Android.
enum FeedEndMessage {
    static let forYou = "You've seen every post in your feed. Check back soon for more good vibes!"
    static let following = "You've seen every post from the people you follow."
    static let ownProfile = "That's every post you've shared."

    static func top(_ period: TopPostPeriod) -> String {
        let span: String
        switch period {
        case .day: span = "today"
        case .week: span = "this week"
        case .month: span = "this month"
        case .year: span = "this year"
        }
        return "That's the whole Top board for \(span)."
    }

    static func profile(of username: String) -> String {
        "You've seen all of \(username)'s posts."
    }
}

/// The banner itself, placed after the last post.
struct FeedEndBanner: View {
    let message: String
    let celebration: EndOfListCelebration

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 6) {
            Text("🎉")
                .font(.largeTitle)
                .accessibilityHidden(true)
            Text("You finished!")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(
            LinearGradient(
                colors: [Color.accentColor.opacity(0.18), Color.pink.opacity(0.14)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 14)
        )
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.accentColor.opacity(0.45)))
        .padding(.horizontal)
        .padding(.vertical, 8)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("FeedEndBanner")
        // Visibility within the scroll view rather than onAppear: on a profile
        // the banner sits in the eager stack under the lazy grid, where
        // onAppear fires as soon as it exists, off screen or not.
        .onScrollVisibilityChange(threshold: 0.5) { visible in
            if visible { celebration.bannerBecameVisible(reduceMotion: reduceMotion) }
        }
    }
}

extension View {
    /// Attach to the feed's or profile's ScrollView: tracks whether it has been
    /// scrolled, resets the celebration when the list stops being finished
    /// (a refresh, a new feed), and lays the confetti over the whole list.
    func celebratesEndOfList(_ celebration: EndOfListCelebration, reachedEnd: Bool) -> some View {
        modifier(EndOfListCelebrationModifier(celebration: celebration, reachedEnd: reachedEnd))
    }
}

private struct EndOfListCelebrationModifier: ViewModifier {
    @ObservedObject var celebration: EndOfListCelebration
    let reachedEnd: Bool

    func body(content: Content) -> some View {
        content
            .onScrollGeometryChange(for: Bool.self) { geometry in
                geometry.contentOffset.y + geometry.contentInsets.top > 1
            } action: { _, scrolled in
                celebration.isScrolled = scrolled
            }
            .onChange(of: reachedEnd) { _, reached in
                if !reached { celebration.reset() }
            }
            .overlay {
                if let start = celebration.confettiStart {
                    ConfettiView(startDate: start)
                }
            }
    }
}

/// One piece of confetti. Its spread is derived from its index rather than
/// random, so the burst is the same every time and needs no stored state;
/// multipliers coprime with 100 walk every column without bunching.
private struct ConfettiPiece {
    let x: Double
    let delay: Double
    let duration: Double
    let drift: Double
    let spin: Double
    let color: Color
    let isRound: Bool

    private static let colors: [Color] = [
        Color(red: 0.36, green: 0.64, blue: 0.86),
        Color(red: 0.97, green: 0.79, blue: 0.28),
        Color(red: 1.00, green: 0.49, blue: 0.71),
        Color(red: 0.49, green: 0.88, blue: 0.51),
        Color(red: 0.70, green: 0.55, blue: 1.00),
        Color(red: 1.00, green: 0.62, blue: 0.35),
    ]

    init(index i: Int) {
        x = Double((i * 37) % 100) / 100
        delay = Double((i * 53) % 40) / 40
        duration = 2.2 + Double((i * 29) % 10) / 10
        drift = Double((i * 71) % 17) * 6 - 48
        spin = 360 + Double((i * 43) % 5) * 180
        color = Self.colors[i % Self.colors.count]
        isRound = i % 4 == 0
    }

    static let all = (0..<72).map(ConfettiPiece.init(index:))
}

/// The confetti burst: pieces falling from above the top edge to below the
/// bottom, drifting and spinning, drawn per frame from the time since
/// `startDate`. Decorative only — it takes no touches and is hidden from
/// VoiceOver.
private struct ConfettiView: View {
    let startDate: Date

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let elapsed = timeline.date.timeIntervalSince(startDate)
                for piece in ConfettiPiece.all {
                    let t = elapsed - piece.delay
                    guard t > 0, t < piece.duration else { continue }
                    let progress = t / piece.duration
                    // Eases out, like the website's fall.
                    let fall = 1 - pow(1 - progress, 1.6)
                    let x = piece.x * size.width + piece.drift * progress + sin(t * 4) * 10
                    let y = -16 + fall * (size.height + 32)

                    var pieceContext = context
                    pieceContext.opacity = progress > 0.85 ? (1 - progress) / 0.15 : 1
                    pieceContext.translateBy(x: x, y: y)
                    pieceContext.rotate(by: .degrees(piece.spin * progress))
                    let path = piece.isRound
                        ? Path(ellipseIn: CGRect(x: -5, y: -5, width: 10, height: 10))
                        : Path(roundedRect: CGRect(x: -4, y: -7, width: 8, height: 14), cornerRadius: 2)
                    pieceContext.fill(path, with: .color(piece.color))
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}
