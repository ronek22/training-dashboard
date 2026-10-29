import SwiftUI

/// What today's workout asks of each lift compared with last time (unit-tested).
enum BriefLogic {
    enum Change: Equatable {
        case up(String)
        case down(String)
        case hold
        case repeatLast
        case new

        var label: String {
            switch self {
            case .up(let delta), .down(let delta): delta
            case .hold: "Hold"
            case .repeatLast: "Repeat"
            case .new: "New"
            }
        }

        var color: Color {
            switch self {
            case .up: .mobility
            case .down: .warning
            case .hold, .repeatLast: .inkSoft
            case .new: .other
            }
        }
    }

    struct Lift: Equatable, Identifiable {
        var id: String { name }
        let name: String
        let target: String
        let change: Change
        let hint: String?
        let notes: String?
        let last: StrengthTemplate.Last?
    }

    /// Held reasons that apply to the whole day rather than one lift.
    private static let dayWide: Set<String> = ["life_load", "phase", "mountain_reentry"]

    static func lifts(_ template: StrengthTemplate) -> [Lift] {
        template.exercises.map { exercise in
            let weight = exercise.next?.targetWeightKg ?? (exercise.next == nil ? exercise.targetWeightKg : nil)
            let reps = exercise.next?.targetReps ?? exercise.targetReps ?? 0
            let sets = exercise.setCount ?? 0
            let load = weight.map { "\(TodayFormat.number($0)) kg" } ?? "BW"
            return Lift(
                name: exercise.exerciseName,
                target: "\(sets) × \(reps) · \(load)",
                change: change(exercise.next),
                hint: exercise.next?.hint,
                notes: exercise.notes,
                last: exercise.next?.last
            )
        }
    }

    static func change(_ next: StrengthTemplate.Next?) -> Change {
        guard let next, let last = next.last else { return .new }
        let target = next.targetWeightKg ?? 0
        let previous = last.weightKg ?? 0
        if target > previous { return .up("+\(TodayFormat.number(target - previous)) kg") }
        if target < previous { return .down("−\(TodayFormat.number(previous - target)) kg") }
        let reps = next.targetReps ?? last.reps
        if reps > last.reps { return .up(reps - last.reps == 1 ? "+1 rep" : "+\(reps - last.reps) reps") }
        return next.held == nil ? .repeatLast : .hold
    }

    /// "Deadline today", "Deload week until 3 Nov": the day-wide reason loads are held, if any.
    static func dayNote(_ template: StrengthTemplate) -> String? {
        let held = template.exercises.compactMap(\.next).first { $0.held.map(dayWide.contains) == true }
        guard let hint = held?.hint else { return nil }
        return hint.split(separator: ":", maxSplits: 1).first.map(String.init) ?? hint
    }

    /// "2 going up · 3 holding · 1 new".
    static func summary(_ lifts: [Lift]) -> String {
        var up = 0, hold = 0, new = 0
        for lift in lifts {
            switch lift.change {
            case .up: up += 1
            case .new: new += 1
            case .hold, .repeatLast, .down: hold += 1
            }
        }
        return [
            up > 0 ? "\(up) going up" : nil,
            hold > 0 ? "\(hold) holding" : nil,
            new > 0 ? "\(new) new" : nil,
        ].compactMap { $0 }.joined(separator: " · ")
    }

    /// "Last 77.5 kg × 6 · Thu 15 Oct".
    static func lastLine(_ last: StrengthTemplate.Last, today: String) -> String {
        let load = StrengthFormat.load(weight: last.weightKg, reps: last.reps)
        return "Last \(load) · \(TodayFormat.shortDay(last.date, relativeTo: today))"
    }
}

/// Shown before a planned workout starts: today's lifts, targets and what changed.
struct SessionBriefView: View {
    let template: StrengthTemplate
    let starting: Bool
    let onStart: () -> Void

    private var lifts: [BriefLogic.Lift] { BriefLogic.lifts(template) }
    private var today: String {
        Date.now.formatted(.iso8601.year().month().day().dateSeparator(.dash))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                header
                if let note = BriefLogic.dayNote(template) {
                    dayNote(note)
                }
                liftList
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            Button(action: onStart) {
                if starting {
                    ProgressView().tint(Color.bg)
                } else {
                    Label("Start workout", systemImage: "play.fill")
                }
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(starting)
            .padding(.horizontal, 16)
            .padding(.top, 10)
            .padding(.bottom, 8)
            .background(Color.bg)
        }
    }

    private var header: some View {
        let sets = template.exercises.reduce(0) { $0 + ($1.setCount ?? 0) }
        let meta = ["\(template.exercises.count) lifts", "\(sets) sets", template.estimatedDurationMinutes.map { "~\($0) min" }]
            .compactMap { $0 }
            .joined(separator: " · ")
        return VStack(alignment: .leading, spacing: 6) {
            Kicker("Session brief", color: Color(hex: 0xFF7AB5))
            Text(template.name.uppercased())
                .font(AppFont.title(36))
                .foregroundStyle(Color.ink)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
            Text(meta).font(AppFont.body(13)).foregroundStyle(Color.muted)
            let summary = BriefLogic.summary(lifts)
            if !summary.isEmpty {
                Text(summary).font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.inkSoft)
            }
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private func dayNote(_ note: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: "pause.circle.fill").foregroundStyle(Color.warning)
            VStack(alignment: .leading, spacing: 2) {
                Text(note).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                Text("No load jumps today. Match last time and leave a rep or two in reserve.")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
            }
        }
        .card(border: Color.warning.opacity(0.35))
    }

    private var liftList: some View {
        VStack(spacing: 0) {
            ForEach(Array(lifts.enumerated()), id: \.element.id) { index, lift in
                if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                row(lift)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
    }

    private func row(_ lift: BriefLogic.Lift) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(lift.name)
                    .font(AppFont.body(15, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                Spacer(minLength: 8)
                Text(lift.change.label.uppercased())
                    .font(AppFont.body(10, weight: .bold))
                    .tracking(1)
                    .foregroundStyle(lift.change.color)
                    .padding(.horizontal, 8)
                    .frame(height: 22)
                    .background(lift.change.color.opacity(0.14), in: Capsule())
            }
            Text(lift.target)
                .font(AppFont.number(22))
                .foregroundStyle(Color.ink)
                .monospacedDigit()
            if let hint = lift.hint {
                Text(hint).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            if let notes = lift.notes, !notes.isEmpty {
                Text(notes).font(AppFont.body(12)).foregroundStyle(Color.inkSoft)
            }
            if let last = lift.last {
                Text(BriefLogic.lastLine(last, today: today))
                    .font(AppFont.body(11, weight: .medium))
                    .foregroundStyle(Color.faint)
            }
        }
        .padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }
}
