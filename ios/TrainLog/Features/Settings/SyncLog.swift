import SwiftUI

/// What the write queue holds and what its last replays did, kept current for Today's pill and
/// Settings' Sync section.
@MainActor @Observable
final class SyncStatus {
    static let shared = SyncStatus()
    static let seenKey = "syncLogSeenAt"

    private(set) var pending: [WriteQueue.Write] = []
    private(set) var log: [WriteQueue.Outcome] = []
    private(set) var sending = false
    /// When Settings last showed the log; rejected writes after it are flagged on Today.
    private(set) var seenAt: Date

    private let queue: WriteQueue
    private let defaults: UserDefaults

    init(queue: WriteQueue = WriteQueue(), defaults: UserDefaults = .standard) {
        self.queue = queue
        self.defaults = defaults
        seenAt = defaults.object(forKey: Self.seenKey) as? Date ?? .distantPast
        refresh()
        let file = queue.file
        NotificationCenter.default.addObserver(forName: WriteQueue.changed, object: nil, queue: .main) { [weak self] note in
            guard (note.object as? URL) == file else { return }
            MainActor.assumeIsolated { self?.refresh() }
        }
    }

    /// Writes the server refused since the log was last looked at: those logs are gone.
    var unseenRejections: Int {
        log.filter { $0.rejected != nil && $0.at > seenAt }.count
    }

    func refresh() {
        pending = queue.pending
        log = queue.log
    }

    func markSeen() {
        seenAt = .now
        defaults.set(seenAt, forKey: Self.seenKey)
    }

    func sendNow(with client: APIClient = .current) async {
        guard !sending else { return }
        sending = true
        defer { sending = false }
        client.reachability.retry()
        await queue.flush(with: client)
        refresh()
    }
}

enum SyncFormat {
    /// A person's name for a queued request, from its path.
    static func label(method: String, path: String) -> String {
        let parts = path.split(separator: "/").map(String.init)
        func has(_ part: String) -> Bool { parts.contains(part) }
        switch true {
        case has("sets") && path.hasSuffix("/complete"): return "Strength set"
        case has("sets") && path.hasSuffix("/effort"): return "Set effort"
        case has("sessions") && path.hasSuffix("/position"): return "Workout position"
        case has("sessions") && path.hasSuffix("/finish"): return "Finish workout"
        case has("sessions") && path.hasSuffix("/abandon"): return "End workout"
        case has("templates"): return method == "POST" ? "New workout" : "Workout edit"
        case has("food") && method == "PUT": return "Meal edit"
        case has("food") && method == "DELETE": return "Meal removed"
        case has("food"): return "Meal"
        case path == "/checkins": return "Check-in"
        case path == "/sick-mode": return "Sick day"
        case path == "/sick-mode/end": return "Sick day ended"
        case has("life-load"): return "Busy day"
        case path == "/metrics": return "Weight"
        case has("ticks"): return "Rehab ticks"
        case has("guided-sessions"): return "Rehab session"
        case has("recovery") && path.hasSuffix("/checkins"): return "Rehab check-in"
        case has("activities") && path.hasSuffix("/felt"): return "Run feel"
        case has("activities") && path.hasSuffix("/symptoms"): return "Run pain"
        case has("activities") && path.hasSuffix("/feedback"): return "Activity feedback"
        case has("activities") && path.hasSuffix("/tags"): return "Activity tags"
        default: return parts.last.map { $0.prefix(1).uppercased() + $0.dropFirst() } ?? path
        }
    }

    /// "10:42" today, "Tue 10:42" this week, "28 Oct" before that.
    static func when(_ date: Date, now: Date = .now, calendar: Calendar = .current) -> String {
        let time = date.formatted(date: .omitted, time: .shortened)
        if calendar.isDate(date, inSameDayAs: now) { return time }
        if let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date), to: calendar.startOfDay(for: now)).day, days < 7 {
            return date.formatted(.dateTime.weekday(.abbreviated)) + " " + time
        }
        return date.formatted(.dateTime.day().month(.abbreviated))
    }

    /// Repeated writes of one kind fold into one row: five sets read "Strength set ×5".
    static func grouped(_ writes: [WriteQueue.Write]) -> [(label: String, count: Int, since: Date?)] {
        var rows: [(label: String, count: Int, since: Date?)] = []
        for write in writes {
            let label = label(method: write.method, path: write.path)
            if let last = rows.last, last.label == label {
                rows[rows.count - 1].count += 1
            } else {
                rows.append((label, 1, write.queuedAt))
            }
        }
        return rows
    }
}

/// Settings' Sync section: what's waiting for the Mac, and what the last replays did.
struct SyncSection: View {
    @Bindable var status: SyncStatus

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker("Sync").padding(.horizontal, 4).padding(.top, 6)
            SettingsCard {
                if status.pending.isEmpty {
                    HStack(spacing: 10) {
                        Image(systemName: "checkmark.circle.fill").foregroundStyle(Color.mobility)
                        Text("Everything is on the Mac").font(AppFont.body(15)).foregroundStyle(Color.ink)
                        Spacer(minLength: 0)
                    }
                    .settingsRow()
                } else {
                    ForEach(Array(SyncFormat.grouped(status.pending).enumerated()), id: \.offset) { _, row in
                        HStack(spacing: 10) {
                            Image(systemName: "clock.arrow.circlepath").foregroundStyle(Color.warning)
                            Text(row.count > 1 ? "\(row.label) ×\(row.count)" : row.label)
                                .font(AppFont.body(15)).foregroundStyle(Color.ink)
                            Spacer(minLength: 0)
                            if let since = row.since {
                                Text(SyncFormat.when(since)).font(AppFont.body(13)).foregroundStyle(Color.muted)
                            }
                        }
                        .settingsRow()
                        Divider().overlay(Color.cardBorder)
                    }
                    Button {
                        Task { await status.sendNow() }
                    } label: {
                        HStack(spacing: 10) {
                            if status.sending {
                                ProgressView().controlSize(.small).tint(.muted)
                            } else {
                                Image(systemName: "arrow.up.circle")
                            }
                            Text(status.sending ? "Sending…" : "Send now").font(AppFont.body(15, weight: .semibold))
                            Spacer(minLength: 0)
                        }
                        .foregroundStyle(Color.ink)
                        .settingsRow()
                    }
                    .buttonStyle(.plain)
                    .disabled(status.sending)
                }
            }
            Text(status.pending.isEmpty
                ? "Logs made while the Mac is out of reach wait here and go out in order once it answers."
                : "\(status.pending.count) waiting for the Mac. They go out in order the next time it answers, or now if it's reachable.")
                .font(AppFont.body(12))
                .foregroundStyle(Color.muted)
                .lineSpacing(2)
                .padding(.horizontal, 4)

            if !status.log.isEmpty {
                Kicker("Sent after waiting").padding(.horizontal, 4).padding(.top, 6)
                SettingsCard {
                    ForEach(Array(status.log.prefix(10).enumerated()), id: \.offset) { index, outcome in
                        if index > 0 { Divider().overlay(Color.cardBorder) }
                        outcomeRow(outcome)
                    }
                }
                if status.log.contains(where: { $0.rejected != nil }) {
                    Text("Refused logs were dropped so they couldn't block the rest, usually because the workout or day had already changed on the web. Log them again if they matter.")
                        .font(AppFont.body(12))
                        .foregroundStyle(Color.muted)
                        .lineSpacing(2)
                        .padding(.horizontal, 4)
                }
            }
        }
        .onAppear { status.refresh() }
        .onDisappear { status.markSeen() }
    }

    private func outcomeRow(_ outcome: WriteQueue.Outcome) -> some View {
        HStack(spacing: 10) {
            Image(systemName: outcome.rejected == nil ? "checkmark" : "xmark")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(outcome.rejected == nil ? Color.mobility : Color.danger)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                Text(SyncFormat.label(method: outcome.method, path: outcome.path))
                    .font(AppFont.body(15)).foregroundStyle(Color.ink)
                if let code = outcome.rejected {
                    Text("Refused by the server (\(code))").font(AppFont.body(12)).foregroundStyle(Color.danger)
                }
            }
            Spacer(minLength: 0)
            Text(SyncFormat.when(outcome.at)).font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .settingsRow()
    }
}

/// Today's header pill: queued logs waiting for the Mac, or logs the server refused.
struct SyncPill: View {
    let status: SyncStatus
    let action: () -> Void

    var body: some View {
        if status.unseenRejections > 0 || !status.pending.isEmpty {
            let refused = status.unseenRejections > 0
            let color = refused ? Color.danger : Color.warning
            Button(action: action) {
                HStack(spacing: 4) {
                    Image(systemName: refused ? "exclamationmark.triangle.fill" : "arrow.up.circle")
                        .font(.system(size: 12, weight: .semibold))
                    Text(refused ? "\(status.unseenRejections)" : "\(status.pending.count)")
                        .font(AppFont.body(13, weight: .bold))
                        .contentTransition(.numericText())
                }
                .foregroundStyle(color)
                .padding(.horizontal, 10)
                .frame(height: 26)
                .background(color.opacity(0.12), in: Capsule())
                .frame(minHeight: 44)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .fixedSize()
            .accessibilityLabel(refused
                ? "\(status.unseenRejections) logs refused by the server"
                : "\(status.pending.count) logs waiting to sync")
            .accessibilityHint("Opens Sync in Settings")
        }
    }
}
