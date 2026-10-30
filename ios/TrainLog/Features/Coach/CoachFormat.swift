import SwiftUI

/// Labels, colours and Markdown blocks for coach chats; pure so it can be tested.
enum CoachFormat {
    enum Block: Equatable {
        case heading(String)
        case bullet(String, String)
        case paragraph(String)
    }

    static func kind(_ conversation: CoachConversation) -> CoachContext.Kind? {
        conversation.contextKind.flatMap(CoachContext.Kind.init(rawValue:))
    }

    static func color(_ kind: CoachContext.Kind?) -> Color {
        switch kind {
        case .activity: .run
        case .day: .mobility
        case .week: .ride
        case nil: .muted
        }
    }

    static func symbol(_ kind: CoachContext.Kind?) -> String {
        switch kind {
        case .activity: "waveform.path.ecg"
        case .day: "sun.max.fill"
        case .week: "calendar"
        case nil: "bubble.left.fill"
        }
    }

    static func kicker(_ context: CoachContext?, conversation: CoachConversation?) -> String {
        switch context?.kind ?? conversation.flatMap(kind) {
        case .activity: "Coach · this session"
        case .day: "Coach · this day"
        case .week: "Coach · this week"
        case nil: "Coach"
        }
    }

    static func intro(_ context: CoachContext?) -> String {
        switch context?.kind {
        case .activity: "Ask about this session. The coach reads it next to your earlier ones."
        case .day: "Ask about this day. The coach sees your plan, check-in and recovery."
        case .week: "Ask about this week. The coach sees the plan and what's done so far."
        case nil: "Ask anything about your training. The coach reads your recent context first."
        }
    }

    /// 0:42, 1:05: replies take a minute or two.
    static func elapsed(_ seconds: Int) -> String {
        String(format: "%d:%02d", seconds / 60, seconds % 60)
    }

    // MARK: Context titles, as the web names these chats

    static func dayContext(_ date: String, title: String? = nil) -> CoachContext {
        let label = FoodFormat.parse(date).map { $0.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated)) } ?? date
        let detail = title.map { " · \(PlanFormat.rowTitle($0))" } ?? ""
        return CoachContext(kind: .day, id: date, title: "\(label)\(detail)")
    }

    static func weekContext(_ weekStart: String) -> CoachContext {
        let label = FoodFormat.parse(weekStart).map { $0.formatted(.dateTime.day().month(.abbreviated)) } ?? weekStart
        return CoachContext(kind: .week, id: weekStart, title: "Week of \(label)")
    }

    static func activityContext(_ id: String, title: String?) -> CoachContext {
        CoachContext(kind: .activity, id: id, title: title?.nilIfEmpty ?? "Activity")
    }

    // MARK: List

    /// "14:05" today, "Tue" this week, "12 Oct" before that.
    static func updated(_ value: String?, now: Date = .now) -> String {
        guard let value, let date = parseTimestamp(value) else { return "" }
        let calendar = Calendar.current
        if calendar.isDate(date, inSameDayAs: now) { return date.formatted(date: .omitted, time: .shortened) }
        if let days = calendar.dateComponents([.day], from: date, to: now).day, days < 7 {
            return date.formatted(.dateTime.weekday(.abbreviated))
        }
        return date.formatted(.dateTime.day().month(.abbreviated))
    }

    /// SQLite's CURRENT_TIMESTAMP: "2026-10-30 14:05:00", in UTC.
    static func parseTimestamp(_ value: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.date(from: value) ?? ISO8601DateFormatter().date(from: value)
    }

    // MARK: Markdown

    static func blocks(_ text: String) -> [Block] {
        var blocks: [Block] = []
        var paragraph: [String] = []
        func flush() {
            if !paragraph.isEmpty { blocks.append(.paragraph(paragraph.joined(separator: " "))) }
            paragraph = []
        }
        for raw in text.components(separatedBy: .newlines) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty {
                flush()
            } else if line.hasPrefix("#") {
                flush()
                blocks.append(.heading(line.drop { $0 == "#" }.trimmingCharacters(in: .whitespaces)))
            } else if line.hasPrefix("- ") || line.hasPrefix("* ") || line.hasPrefix("• ") {
                flush()
                blocks.append(.bullet("•", String(line.dropFirst(2))))
            } else if let match = line.firstMatch(of: /^(\d+)[.)]\s+(.*)$/) {
                flush()
                blocks.append(.bullet("\(match.1).", String(match.2)))
            } else {
                paragraph.append(line)
            }
        }
        flush()
        return blocks
    }

    static func inline(_ line: String) -> AttributedString {
        (try? AttributedString(markdown: line, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(line)
    }
}
