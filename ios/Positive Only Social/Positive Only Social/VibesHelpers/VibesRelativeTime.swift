import Foundation


/// Formats how long ago a date was, relative to `now` (defaults to the current
/// time).
///
/// Sub-minute durations collapse to "< 1 min" so the label doesn't tick on
/// every second the way SwiftUI's `.relative` style does. Larger durations
/// round down to the largest whole unit: minutes, hours, days, weeks, then
/// years. This mirrors the same helper on Android (`RelativeTime`) and the
/// website (`formatRelativeTime`) so the three clients read identically.
enum RelativeTime {
    static func string(from date: Date, now: Date = Date()) -> String {
        let seconds = max(0, Int(now.timeIntervalSince(date)))
        if seconds < 60 { return "< 1 min" }
        
        let minutes = seconds / 60
        if minutes < 60 { return "\(minutes) min" }
        
        let hours = minutes / 60
        if hours < 24 { return "\(hours) hr" }
        
        let days = hours / 24
        if days < 7 { return "\(days) \(days == 1 ? "day" : "days")" }
        
        if days < 365 {
            let weeks = days / 7
            return "\(weeks) \(weeks == 1 ? "week" : "weeks")"
        }
        
        let years = days / 365
        return "\(years) \(years == 1 ? "year" : "years")"
    }

    /// Parses an ISO8601 date string produced by Django, whose `DjangoJSONEncoder`
    /// emits a colon-separated UTC offset (e.g. "2024-01-15T10:30:45.123456+00:00"),
    /// while the in-memory stub emits a "Z" suffix. Tries colon- and omitted-separator
    /// variants, with and without fractional seconds, so both real and stubbed
    /// timestamps decode. Returns nil when nothing matches so callers can omit a
    /// relative-time label rather than showing a bogus "now".
    ///
    /// Uses `Date.ISO8601FormatStyle` (a value type) rather than an `NSObject`-backed
    /// formatter, so it's cheap and safe to call from async task groups without
    /// actor hopping or sharing non-Sendable state across isolation domains.
    static func date(from string: String) -> Date? {
        // `.colon` matches the real backend's "+00:00"; `.omitted` matches "+0000"
        // and the stub's "Z". Django usually includes fractional seconds, but older
        // rows may not, so try both.
        let separators: [Date.ISO8601FormatStyle.TimeZoneSeparator] = [.colon, .omitted]
        for separator in separators {
            for includingFractionalSeconds in [true, false] {
                let strategy = Date.ISO8601FormatStyle().year().month().day()
                    .time(includingFractionalSeconds: includingFractionalSeconds)
                    .timeZone(separator: separator)
                if let date = try? Date(string, strategy: strategy) {
                    return date
                }
            }
        }
        return nil
    }
}

