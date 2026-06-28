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
}

