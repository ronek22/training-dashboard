import SwiftUI
import UIKit

/// Words and numbers for the after-session recap (unit-tested).
enum SummaryLogic {
    enum Change: Equatable {
        case up(String)
        case reps(String)
        case hold
        case down(String)

        var label: String {
            switch self {
            case .up(let delta), .reps(let delta), .down(let delta): delta
            case .hold: "Hold"
            }
        }

        var color: Color {
            switch self {
            case .up, .reps: .mobility
            case .hold: .inkSoft
            case .down: .warning
            }
        }

        var symbol: String {
            switch self {
            case .up, .reps: "arrow.up.right"
            case .hold: "equal"
            case .down: "arrow.down.right"
            }
        }
    }

    /// Held reasons that apply to the whole next session rather than one lift.
    static let dayWide: Set<String> = ["life_load", "phase", "mountain_reentry"]

    /// The recap from the session alone, for when the server can't be reached.
    static func local(_ session: StrengthSession, now: Date = .now) -> StrengthSummary {
        let exercises: [StrengthSummary.Exercise] = session.exercises.compactMap { exercise in
            let done = exercise.workingSets.filter(\.isCompleted)
            guard let top = done.max(by: { ($0.actualWeightKg ?? 0, $0.actualReps ?? 0) < ($1.actualWeightKg ?? 0, $1.actualReps ?? 0) })
            else { return nil }
            let timed = done.contains(where: \.isTimed)
            return .init(
                exerciseName: exercise.exerciseName,
                setCount: done.count,
                reps: timed ? nil : done.reduce(0) { $0 + ($1.actualReps ?? 0) },
                volumeKg: volume(done),
                topSet: .init(weightKg: top.actualWeightKg, reps: top.actualReps, seconds: top.actualSeconds),
                seconds: timed ? done.reduce(0) { $0 + ($1.actualSeconds ?? 0) } : nil
            )
        }
        let done = session.exercises.flatMap(\.workingSets).filter(\.isCompleted)
        let minutes = StrengthFormat.parseMoment(session.startedAt).map { max(0, Int((now.timeIntervalSince($0) / 60).rounded())) }
        return StrengthSummary(
            sessionId: session.id,
            name: session.templateName,
            date: String(session.startedAt.prefix(10)),
            durationMinutes: minutes,
            volumeKg: volume(done),
            setCount: done.count,
            repCount: done.filter { !$0.isTimed }.reduce(0) { $0 + ($1.actualReps ?? 0) },
            exercises: exercises,
            fromServer: false
        )
    }

    private static func volume(_ sets: [StrengthSession.WorkoutSet]) -> Double {
        sets.reduce(0) { $0 + ($1.actualWeightKg ?? 0) * Double($1.actualReps ?? 0) }
    }

    /// Volume against the last time this workout was done, in percent.
    static func versusLast(_ summary: StrengthSummary) -> Int? {
        guard let previous = summary.previous?.volumeKg, previous > 0, summary.volumeKg > 0 else { return nil }
        return Int(((summary.volumeKg - previous) / previous * 100).rounded())
    }

    /// The kicker over the big number.
    static func headline(_ summary: StrengthSummary) -> String {
        if summary.bestCount > 0 { return summary.bestCount == 1 ? "Workout done · a new best" : "Workout done · \(summary.bestCount) new bests" }
        if let delta = versusLast(summary), delta > 0 { return "Workout done · more than last time" }
        return "Workout done"
    }

    static func change(_ exercise: StrengthSummary.Exercise) -> Change? {
        guard let next = exercise.next, let change = next.change else { return nil }
        let today = exercise.topSet.weightKg ?? 0
        let target = next.targetWeightKg ?? 0
        switch change {
        case "up": return .up("+\(TodayFormat.number(target - today)) kg")
        case "down": return .down("−\(TodayFormat.number(today - target)) kg")
        case "reps":
            let delta = (next.targetReps ?? 0) - (exercise.topSet.reps ?? 0)
            return .reps(delta > 1 ? "+\(delta) reps" : "+1 rep")
        default: return .hold
        }
    }

    /// "4,172": grouped the same way whatever the phone's region, so it never reads as a decimal.
    static func grouped(_ value: Double) -> String {
        Int(value.rounded()).formatted(.number.locale(Locale(identifier: "en_US")))
    }

    /// A lift's own hint; a hold for the whole session is said once, under "Next time".
    static func rowHint(_ next: StrengthSummary.Next?) -> String? {
        guard let next, next.held.map(dayWide.contains) != true else { return nil }
        return next.hint
    }

    /// "22.5 kg × 8 · 3 sets" or "3 × 0:45" for a hold.
    static func todayLine(_ exercise: StrengthSummary.Exercise) -> String {
        if let seconds = exercise.topSet.seconds {
            let load = exercise.topSet.weightKg.map { " · \(TodayFormat.number($0)) kg" } ?? ""
            return "\(exercise.setCount) × \(StrengthFormat.hold(seconds))\(load)"
        }
        let load = StrengthFormat.load(weight: exercise.topSet.weightKg, reps: exercise.topSet.reps ?? 0)
        return "\(load) · \(exercise.setCount) \(exercise.setCount == 1 ? "set" : "sets")"
    }

    /// "25 kg × 8": next time's target.
    static func targetLine(_ next: StrengthSummary.Next) -> String? {
        guard let reps = next.targetReps else { return nil }
        return StrengthFormat.load(weight: next.targetWeightKg, reps: reps)
    }

    /// The best beaten today and the number behind it.
    static func best(_ exercise: StrengthSummary.Exercise) -> (title: String, detail: String)? {
        let top = StrengthFormat.load(weight: exercise.topSet.weightKg, reps: exercise.topSet.reps ?? 0)
        switch exercise.bests.first {
        case "heaviest": return ("Heaviest ever", top)
        case "e1rm": return ("Strongest set ever", "\(top) · best estimated max")
        case "volume": return ("Most volume ever", "\(TodayFormat.number(exercise.volumeKg.rounded())) kg over \(exercise.setCount) sets")
        case "reps": return ("Most reps ever", "\(exercise.topSet.reps ?? 0) reps in a set")
        default: return nil
        }
    }

    /// The line under "Next time" that explains the pace: steady, never pushy.
    static func pace(_ summary: StrengthSummary) -> String? {
        let nexts = summary.exercises.compactMap(\.next)
        guard !nexts.isEmpty else { return nil }
        if let held = nexts.first(where: { $0.held.map(dayWide.contains) == true }), let hint = held.hint {
            let reason = hint.split(separator: ":", maxSplits: 1).first.map(String.init) ?? hint
            return "\(reason): no load jumps. Match today and keep the streak going."
        }
        let up = summary.goingUp
        let holding = summary.holding
        let reps = nexts.filter { $0.change == "reps" }.count
        switch (up, holding) {
        case (0, 0): return reps > 0 ? "A rep more where you hit every target. Same weights." : nil
        case (0, _): return "Every load holds. Own these first; the jump comes when the sets feel easy."
        case (_, 0): return up == 1 ? "One lift goes up. Small step, same reps." : "\(up) lifts go up. Small steps, same reps."
        default: return "\(up) up, \(holding) holding. One or two jumps a session keeps progress steady."
        }
    }
}

/// The recap that ends a strength workout: big numbers, new bests, then what next time asks.
struct SessionSummaryView: View {
    let summary: StrengthSummary
    let onDone: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header.reveal(0)
                HeroCard(summary: summary).reveal(1)
                let wins = summary.exercises.filter { SummaryLogic.best($0) != nil }
                if !wins.isEmpty {
                    BestsCard(exercises: wins).reveal(2)
                }
                NextCard(summary: summary).reveal(3)
                if !summary.fromServer {
                    Text("Bests and next targets show once the Mac has your sets.")
                        .font(AppFont.body(12))
                        .foregroundStyle(Color.faint)
                        .padding(.horizontal, 4)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            Button("Done", action: onDone)
                .buttonStyle(VoltButtonStyle())
                .padding(.horizontal, 16)
                .padding(.top, 10)
                .padding(.bottom, 8)
                .background(Color.bg)
        }
        .onAppear {
            Haptics.success()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker(SummaryLogic.headline(summary), color: .volt)
            Text(summary.name.uppercased())
                .font(AppFont.title(34))
                .foregroundStyle(Color.ink)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
        }
        .padding(.horizontal, 4)
    }
}

/// Giant volume (reps on a bodyweight day), against last time, then time, sets and reps.
private struct HeroCard: View {
    let summary: StrengthSummary

    private var weighted: Bool { summary.volumeKg > 0 }
    private var today: String { Date.now.formatted(.iso8601.year().month().day().dateSeparator(.dash)) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker(weighted ? "Volume" : "Reps")
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                CountUp(value: weighted ? summary.volumeKg.rounded() : Double(summary.repCount)) { SummaryLogic.grouped($0) }
                    .font(AppFont.number(88))
                    .foregroundStyle(Color.ink)
                Text(weighted ? "kg" : "reps").font(AppFont.number(30, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.top, -4)
            versusLine.padding(.top, -2)
            HStack(spacing: 0) {
                if let minutes = summary.durationMinutes {
                    stat(Double(minutes), "minutes") { "\(Int($0))" }
                }
                stat(Double(summary.setCount), summary.setCount == 1 ? "set" : "sets") { "\(Int($0))" }
                if weighted {
                    stat(Double(summary.repCount), "reps") { "\(Int($0))" }
                } else {
                    stat(Double(summary.exercises.count), "lifts") { "\(Int($0))" }
                }
            }
            .padding(.top, 18)
        }
        .card()
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private var versusLine: some View {
        if let previous = summary.previous {
            let last = "last time \(SummaryLogic.grouped(previous.volumeKg)) kg · \(TodayFormat.shortDay(previous.date, relativeTo: today))"
            if let delta = SummaryLogic.versusLast(summary), delta > 0 {
                HStack(spacing: 8) {
                    Pill(text: "+\(delta)%", color: .volt)
                    Text(last).font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            } else {
                Text(last.prefix(1).uppercased() + last.dropFirst()).font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
        }
    }

    private func stat(_ value: Double, _ label: String, format: @escaping (Double) -> String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            CountUp(value: value, delay: 0.3, format: format)
                .font(AppFont.number(28))
                .foregroundStyle(Color.ink)
            Text(label).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Every lift that beat its own record today.
private struct BestsCard: View {
    let exercises: [StrengthSummary.Exercise]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Kicker(exercises.count == 1 ? "New best" : "\(exercises.count) new bests", color: .volt)
            ForEach(Array(exercises.enumerated()), id: \.element.id) { index, exercise in
                if let best = SummaryLogic.best(exercise) {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "trophy.fill")
                            .font(.system(size: 15, weight: .bold))
                            .foregroundStyle(Color.bg)
                            .frame(width: 36, height: 36)
                            .background(Color.volt, in: Circle())
                        VStack(alignment: .leading, spacing: 3) {
                            Text(exercise.exerciseName).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                            Text("\(best.title) · \(best.detail)").font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                        }
                        .fixedSize(horizontal: false, vertical: true)
                    }
                    .reveal(index, base: 0.45)
                }
            }
        }
        .card(border: Color.volt.opacity(0.35))
    }
}

/// Each lift: what you did today, where its target goes next and why it holds.
private struct NextCard: View {
    let summary: StrengthSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(summary.fromServer ? "Next time" : "Lifts")
                if let pace = SummaryLogic.pace(summary) {
                    Text(pace).font(AppFont.body(13, weight: .medium)).foregroundStyle(Color.inkSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(.bottom, 6)
            ForEach(Array(summary.exercises.enumerated()), id: \.element.id) { index, exercise in
                if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                row(exercise)
            }
        }
        .card()
    }

    private func row(_ exercise: StrengthSummary.Exercise) -> some View {
        let change = SummaryLogic.change(exercise)
        return VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(exercise.exerciseName)
                    .font(AppFont.body(15, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                Spacer(minLength: 8)
                if let change {
                    Label(change.label.uppercased(), systemImage: change.symbol)
                        .labelStyle(ChipLabelStyle())
                        .foregroundStyle(change.color)
                        .padding(.horizontal, 8)
                        .frame(height: 22)
                        .background(change.color.opacity(0.14), in: Capsule())
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(SummaryLogic.todayLine(exercise))
                    .font(AppFont.number(20))
                    .foregroundStyle(change == nil ? Color.ink : Color.inkSoft)
                if let next = exercise.next, let target = SummaryLogic.targetLine(next) {
                    Image(systemName: "arrow.right").font(.system(size: 11, weight: .bold)).foregroundStyle(Color.faint)
                    Text(target)
                        .font(AppFont.number(20))
                        .foregroundStyle(change.map { $0 == .hold ? Color.ink : $0.color } ?? Color.ink)
                }
            }
            .monospacedDigit()
            .lineLimit(1)
            .minimumScaleFactor(0.8)
            if let hint = SummaryLogic.rowHint(exercise.next) {
                Text(hint).font(AppFont.body(12)).foregroundStyle(Color.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }
}

private struct ChipLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 4) {
            configuration.icon.font(.system(size: 9, weight: .heavy))
            configuration.title.font(AppFont.body(10, weight: .bold)).tracking(1)
        }
    }
}

#if DEBUG
/// A finished session's recap from the server, for screenshots (`-demoSummary <id>`).
struct SummaryDemo: View {
    let sessionId: Int
    @State private var summary: StrengthSummary?

    var body: some View {
        Group {
            if let summary {
                SessionSummaryView(summary: summary) {}
            } else {
                ProgressView().tint(.muted).frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Color.bg.ignoresSafeArea())
        .task {
            summary = try? await APIClient.current.getLive("/strength/workouts/sessions/\(sessionId)/summary", as: StrengthSummary.self)
        }
    }
}
#endif
