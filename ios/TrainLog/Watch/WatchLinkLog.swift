import Observation
import SwiftUI

/// Each step of waking and linking the Watch (launch asked, launched, linked, failed and why,
/// with the Watch's own steps relayed over), newest first, for Settings: shows where pairing stalls.
@MainActor
@Observable
final class WatchLinkLog {
    static let shared = WatchLinkLog()
    static let key = "watchLinkLog"
    static let limit = 40

    struct Entry: Codable, Equatable, Identifiable, Sendable {
        let id: UUID
        let at: Date
        let text: String
    }

    private(set) var entries: [Entry]
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        entries = defaults.data(forKey: Self.key).flatMap { try? JSONDecoder().decode([Entry].self, from: $0) } ?? []
    }

    func add(_ text: String, at date: Date = .now) {
        entries.insert(Entry(id: UUID(), at: date, text: text), at: 0)
        entries = Array(entries.prefix(Self.limit))
        defaults.set(try? JSONEncoder().encode(entries), forKey: Self.key)
    }
}

/// Settings: the last steps of waking and linking the Watch, so a pairing that stalled shows where.
struct WatchLinkSection: View {
    let log: WatchLinkLog

    var body: some View {
        if !log.entries.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Kicker("Apple Watch link").padding(.horizontal, 4).padding(.top, 6)
                SettingsCard {
                    ForEach(Array(log.entries.prefix(12).enumerated()), id: \.element.id) { index, entry in
                        if index > 0 { Divider().overlay(Color.cardBorder) }
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Text(entry.at.formatted(.dateTime.hour().minute().second()))
                                .font(AppFont.number(15))
                                .foregroundStyle(Color.muted)
                                .monospacedDigit()
                            Text(entry.text).font(AppFont.body(14)).foregroundStyle(Color.ink)
                            Spacer(minLength: 0)
                        }
                        .settingsRow()
                    }
                }
                Text("Each step of waking the Watch for a workout opened here, newest first. Lines starting with Watch come from the Watch itself.")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .lineSpacing(2)
                    .padding(.horizontal, 4)
            }
        }
    }
}
