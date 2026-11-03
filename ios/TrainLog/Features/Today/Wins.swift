import SwiftUI

/// Today's small wins. Check-in and protein sit in a row under the title (neither has another home
/// on Today); the workout and rehab are celebrated in the session card's parts, where they already
/// live. Each win is celebrated once per day, even when it was reached on the web.
enum Wins {
    enum Key: String, CaseIterable, Sendable {
        case checkin, protein, main, rehab, clean
    }

    /// What's done right now. `sessionDone` is the session card's "all done" (true on rest days).
    static func done(checkinDone: Bool, protein: PhoneToday.Protein?, mainDone: Bool, rehabDone: Bool,
                     sessionDone: Bool) -> Set<Key> {
        var keys: Set<Key> = []
        if checkinDone { keys.insert(.checkin) }
        if protein?.hit == true { keys.insert(.protein) }
        if mainDone { keys.insert(.main) }
        if rehabDone { keys.insert(.rehab) }
        // Without a protein target the row is check-in alone, so a clean day doesn't wait on it.
        if checkinDone, protein.map(\.hit) ?? true, sessionDone { keys.insert(.clean) }
        return keys
    }

    /// The volt pill: what's in, or the clean day with its count this week.
    static func pillText(done: Set<Key>, cleanThisWeek: Int) -> String? {
        if done.contains(.clean) { return "All done · \(ordinal(cleanThisWeek)) clean day this week" }
        let labels = [(Key.checkin, "Check-in"), (.protein, "Protein")].filter { done.contains($0.0) }.map(\.1)
        return labels.isEmpty ? nil : labels.joined(separator: " · ")
    }

    static func ordinal(_ n: Int) -> String {
        let suffix = (11...13).contains(n % 100) ? "th" : [1: "st", 2: "nd", 3: "rd"][n % 10] ?? "th"
        return "\(n)\(suffix)"
    }

    /// "97/130 g protein".
    static func proteinLabel(_ protein: PhoneToday.Protein) -> (value: String, rest: String) {
        (String(Int(protein.eatenG.rounded())), "/\(protein.targetG) g protein")
    }
}

/// Which wins have been celebrated today, and which days were clean (kept on the phone).
struct WinLedger {
    static let celebratedKey = "wins.celebrated"
    static let cleanDaysKey = "wins.cleanDays"

    var defaults: UserDefaults = .standard

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        #if DEBUG
        // Screenshots of the wins replay their celebration on every launch.
        if defaults.string(forKey: "winsDemo") != nil { defaults.removeObject(forKey: Self.celebratedKey) }
        #endif
    }

    /// The wins in `done` not yet celebrated on `date`, now marked as celebrated.
    mutating func claim(_ done: Set<Wins.Key>, on date: String) -> Set<Wins.Key> {
        let stored = defaults.dictionary(forKey: Self.celebratedKey) as? [String: [String]] ?? [:]
        let seen = Set((stored[date] ?? []).compactMap(Wins.Key.init(rawValue:)))
        let fresh = done.subtracting(seen)
        guard !fresh.isEmpty else { return [] }
        // Only today is kept: yesterday's wins never celebrate again anyway.
        defaults.set([date: seen.union(fresh).map(\.rawValue).sorted()], forKey: Self.celebratedKey)
        if fresh.contains(.clean) { addCleanDay(date) }
        return fresh
    }

    /// Clean days in the Monday-to-Sunday week holding `date`, `date` included.
    func cleanDays(weekOf date: String) -> Int {
        guard let day = TodayFormat.parse(date) else { return 0 }
        var calendar = Calendar(identifier: .gregorian)
        calendar.firstWeekday = 2
        let week = calendar.dateInterval(of: .weekOfYear, for: day)
        let days = defaults.stringArray(forKey: Self.cleanDaysKey) ?? []
        return days.compactMap(TodayFormat.parse).filter { day in
            // DateInterval.contains includes its end, which is next Monday's midnight.
            week.map { $0.start <= day && day < $0.end } ?? false
        }.count
    }

    private func addCleanDay(_ date: String) {
        var days = defaults.stringArray(forKey: Self.cleanDaysKey) ?? []
        guard !days.contains(date) else { return }
        days.append(date)
        defaults.set(Array(days.suffix(14)), forKey: Self.cleanDaysKey)
    }
}

/// Check-in and protein under the title. What's done folds into one volt pill; what's left is a
/// small ring and a number. Tapping opens the check-in sheet or the Food tab.
struct WinsRow: View {
    let checkinDone: Bool
    let protein: PhoneToday.Protein?
    let done: Set<Wins.Key>
    let cleanThisWeek: Int
    /// The pill pops when a row win (or the clean day) has just landed.
    let celebrate: Bool
    let onCheckin: () -> Void
    let onFood: () -> Void

    var body: some View {
        HStack(spacing: 14) {
            if let text = Wins.pillText(done: done, cleanThisWeek: cleanThisWeek) {
                Button(action: done.contains(.checkin) ? onCheckin : onFood) {
                    HStack(spacing: 6) {
                        ZStack {
                            Circle().fill(Color.bg)
                            Image(systemName: "checkmark").font(.system(size: 10, weight: .heavy)).foregroundStyle(Color.volt)
                        }
                        .frame(width: 22, height: 22)
                        Text(text).font(AppFont.body(13, weight: .bold)).foregroundStyle(Color.bg).lineLimit(1)
                    }
                    .padding(.leading, 3)
                    .padding(.trailing, 11)
                    .frame(height: 28)
                    .background(Color.volt, in: Capsule())
                    .overlay { WinBurst(trigger: celebrate) }
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .transition(.scale(scale: 0.8, anchor: .leading).combined(with: .opacity))
                .accessibilityLabel(text)
            }
            if !checkinDone {
                open(icon: "sun.max.fill", progress: 0, value: "Check in", rest: nil, action: onCheckin)
                    .accessibilityLabel("Check in")
            }
            if let protein, !protein.hit {
                let label = Wins.proteinLabel(protein)
                open(icon: "fish.fill", progress: protein.eatenG / Double(max(protein.targetG, 1)),
                     value: label.value, rest: label.rest, action: onFood)
                    .accessibilityLabel("Protein \(label.value) of \(protein.targetG) grams")
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 2)
        .frame(height: 30)
        .animation(.spring(duration: 0.5, bounce: 0.3), value: done)
    }

    private func open(icon: String, progress: Double, value: String, rest: String?, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 6) {
                WinRing(progress: progress, icon: icon)
                (Text(value).font(AppFont.number(15)).foregroundStyle(Color.inkSoft)
                    + Text(rest ?? "").font(AppFont.number(11)).foregroundStyle(Color.faint))
                    .lineLimit(1)
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

/// A 22 pt ring with an icon inside; white progress on the track.
private struct WinRing: View {
    let progress: Double
    let icon: String

    var body: some View {
        ZStack {
            Circle().stroke(Color.raised, lineWidth: 2.2)
            Circle()
                .trim(from: 0, to: min(max(progress, 0), 1))
                .stroke(Color.ink, style: StrokeStyle(lineWidth: 2.2, lineCap: .round))
                .rotationEffect(.degrees(-90))
            Image(systemName: icon)
                .font(.system(size: 9, weight: .semibold))
                .imageScale(.small)
                .foregroundStyle(progress > 0 ? Color.ink : Color.muted)
        }
        .frame(width: 22, height: 22)
    }
}

/// Ten volt dots that pop out of a win and fade, on an ellipse just outside the view, so the same
/// burst rings a 28 pt badge or a wide pill. Nothing moves with Reduce Motion.
struct WinBurst: View {
    let trigger: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var out = false

    var body: some View {
        GeometryReader { geometry in
            let rx = geometry.size.width / 2, ry = geometry.size.height / 2
            let grow: Double = out ? 1 : 0.55
            let gap: Double = out ? 10 : 0
            ForEach(0..<10, id: \.self) { index in
                let angle = Double(index) * .pi / 5 - .pi / 2
                Circle()
                    .fill(Color.volt)
                    .frame(width: 4, height: 4)
                    .opacity(out ? 0 : (index.isMultiple(of: 2) ? 0.6 : 0.95))
                    .position(x: rx + cos(angle) * (rx * grow + gap), y: ry + sin(angle) * (ry * grow + gap))
            }
        }
        .opacity(trigger && !reduceMotion ? 1 : 0)
        .allowsHitTesting(false)
        .onChange(of: trigger) {
            guard trigger, !reduceMotion else { return }
            out = false
            withAnimation(.easeOut(duration: 0.8)) { out = true }
        }
        .accessibilityHidden(true)
    }
}
