import CoreGraphics
import Foundation
import SwiftUI

/// How ready a muscle is, from the last week of training (any sport).
enum MuscleState: String, CaseIterable, Sendable {
    /// A main muscle of a lift in the last 48 h, or legs after a long ride, run or hike yesterday or today.
    case recovering
    /// Worked this week and recovered.
    case ready
    /// Not worked in the last 7 days.
    case rested

    var label: String {
        switch self {
        case .recovering: "Recovering"
        case .ready: "Ready"
        case .rested: "Rested"
        }
    }

    var color: Color {
        switch self {
        case .recovering: .warning
        case .ready: .mobility
        case .rested: Color(hex: 0x343B4A)
        }
    }
}

/// The groups the Body tab talks in.
enum BodyArea: String, CaseIterable, Sendable {
    case shoulders, arms, chest, back, core, legs

    var label: String { rawValue.capitalized }

    var muscles: [Muscle] {
        switch self {
        case .shoulders: [.shoulders]
        case .arms: [.biceps, .triceps, .forearms]
        case .chest: [.chest]
        case .back: [.upperBack, .lats, .lowerBack]
        case .core: [.abs, .obliques]
        case .legs: [.glutes, .quads, .hamstrings, .adductors, .calves]
        }
    }

    static func of(_ muscle: Muscle) -> BodyArea {
        allCases.first { $0.muscles.contains(muscle) } ?? .core
    }
}

/// The sport colours the "What worked what" bars use.
enum WorkSport: String, CaseIterable, Sendable {
    case strength, ride, run, rehab

    var label: String { rawValue.capitalized }

    var color: Color {
        switch self {
        case .strength: .strength
        case .ride: .ride
        case .run: .run
        case .rehab: .mobility
        }
    }
}

/// An active injury pinned on the silhouette.
struct BodyPin: Equatable, Sendable {
    let side: MuscleSilhouette.Side
    /// In the web's 240 × 460 viewBox.
    let point: CGPoint
}

/// Pure: the last week of training turned into the Body tab (unit-tested).
struct BodyMapSummary: Equatable, Sendable {
    struct AreaWork: Equatable, Sendable {
        let area: BodyArea
        var sessions: [WorkSport: Int]
        var total: Int { sessions.values.reduce(0, +) }
    }

    let states: [Muscle: MuscleState]
    let work: [AreaWork]
    let sportCounts: [WorkSport: Int]
    let issues: [PhoneBody.Issue]

    static let legAreas: Set<String> = ["knee", "heel", "hip"]
    private static let cardioLegs: [Muscle] = [.quads, .glutes, .hamstrings, .calves]

    init(training: [PhoneBody.TrainingSession], issues: [PhoneBody.Issue], today: String) {
        self.issues = issues
        var worked: Set<Muscle> = []
        var tired: Set<Muscle> = []
        var work = Dictionary(uniqueKeysWithValues: BodyArea.allCases.map { ($0, [WorkSport: Int]()) })
        var sportCounts: [WorkSport: Int] = [:]
        let rehabArea: BodyArea = issues.contains { !Set($0.areas).isDisjoint(with: Self.legAreas) } ? .legs : .core

        func mark(_ muscle: Muscle, hard: Bool) {
            worked.insert(muscle)
            if hard { tired.insert(muscle) }
        }

        for session in training {
            guard let days = Self.days(from: session.date, to: today), (0..<7).contains(days) else { continue }
            switch session.sport {
            case "strength":
                let summary = MuscleSummary((session.exercises ?? []).map { ($0.name, $0.sets) })
                // Lifts with no mapped exercise (an Apple Workout import) still count as a session.
                let primary = summary.primary
                for muscle in primary { mark(muscle, hard: days < 2) }
                // Helpers (triceps on a press) count as worked, never as tired.
                for muscle in summary.secondary { mark(muscle, hard: false) }
                for area in Set(primary.map(BodyArea.of)) { work[area, default: [:]][.strength, default: 0] += 1 }
                sportCounts[.strength, default: 0] += 1
            case "ride", "run", "hike":
                // A long effort tires the legs for a day; a short spin just counts as worked.
                let long = (session.minutes ?? 0) >= 75 && days <= 1
                for muscle in Self.cardioLegs { mark(muscle, hard: long) }
                let sport: WorkSport = session.sport == "ride" ? .ride : .run
                work[.legs, default: [:]][sport, default: 0] += 1
                sportCounts[sport, default: 0] += 1
            case "rehab":
                work[rehabArea, default: [:]][.rehab, default: 0] += 1
                sportCounts[.rehab, default: 0] += 1
            default:
                continue
            }
        }

        states = Dictionary(uniqueKeysWithValues: Muscle.allCases.map { muscle in
            (muscle, tired.contains(muscle) ? MuscleState.recovering : worked.contains(muscle) ? .ready : .rested)
        })
        self.work = BodyArea.allCases.map { AreaWork(area: $0, sessions: work[$0] ?? [:]) }
        self.sportCounts = sportCounts
    }

    func count(_ state: MuscleState) -> Int { states.values.filter { $0 == state }.count }

    /// An area is recovering if any of its muscles is, ready if any was worked.
    func state(_ area: BodyArea) -> MuscleState {
        let muscles = area.muscles.compactMap { states[$0] }
        if muscles.contains(.recovering) { return .recovering }
        return muscles.contains(.ready) ? .ready : .rested
    }

    func areas(_ state: MuscleState) -> [BodyArea] { BodyArea.allCases.filter { self.state($0) == state } }

    /// "Back, shoulders and arms are fresh."
    var headline: String {
        let ready = areas(.ready)
        if ready.isEmpty {
            return areas(.recovering).isEmpty ? "Nothing trained this week." : "Everything you trained is still recovering."
        }
        if ready.count == BodyArea.allCases.count { return "Everything is fresh." }
        return "\(Self.list(ready.map(\.label))) \(ready.count == 1 ? "is" : "are") fresh."
    }

    /// The sentence under the headline: what still needs time, what's protected, what's idle.
    var detail: String? {
        var parts: [String] = []
        let recovering = areas(.recovering)
        if !recovering.isEmpty { parts.append("\(Self.list(recovering.map(\.label))) \(recovering.count == 1 ? "needs" : "need") another day.") }
        for issue in issues {
            parts.append("\(Self.issueName(issue)) stays on rehab.")
        }
        let rested = areas(.rested)
        if !rested.isEmpty { parts.append("\(Self.list(rested.map(\.label))): nothing this week.") }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }

    /// "Left knee", "Lower back".
    static func issueName(_ issue: PhoneBody.Issue) -> String {
        let area = (issue.areas.first ?? "body").replacingOccurrences(of: "_", with: " ")
        guard let side = issue.side, side == "left" || side == "right" else { return area.prefix(1).uppercased() + area.dropFirst() }
        return "\(side.capitalized) \(area)"
    }

    /// Days of an issue so far ("day 10"), counting the start day as day 1.
    static func issueDay(_ issue: PhoneBody.Issue, today: String) -> Int? {
        guard let since = issue.since, let days = days(from: since, to: today), days >= 0 else { return nil }
        return days + 1
    }

    /// Pins on the front figure (back figure for the lower back). The front view mirrors the athlete,
    /// so their left side sits right of centre.
    static func pins(_ issue: PhoneBody.Issue) -> [BodyPin] {
        let points: [String: (MuscleSilhouette.Side, CGPoint)] = [
            "knee": (.front, CGPoint(x: 134, y: 302)),
            "heel": (.back, CGPoint(x: 107, y: 428)),
            "hip": (.front, CGPoint(x: 148, y: 198)),
            "lower_back": (.back, CGPoint(x: 120, y: 182)),
            "shoulder": (.front, CGPoint(x: 167, y: 100)),
            "elbow": (.front, CGPoint(x: 178, y: 158)),
            "wrist": (.front, CGPoint(x: 200, y: 208)),
            "neck": (.front, CGPoint(x: 120, y: 62)),
        ]
        return issue.areas.flatMap { area -> [BodyPin] in
            guard let (side, left) = points[area] else { return [] }
            if left.x == 120 { return [BodyPin(side: side, point: left)] }
            // The back view isn't mirrored: the athlete's left is on the left.
            let mirrored = CGPoint(x: 240 - left.x, y: left.y)
            let leftPoint = side == .front ? left : mirrored
            let rightPoint = side == .front ? mirrored : left
            switch issue.side {
            case "left": return [BodyPin(side: side, point: leftPoint)]
            case "right": return [BodyPin(side: side, point: rightPoint)]
            default: return [BodyPin(side: side, point: leftPoint), BodyPin(side: side, point: rightPoint)]
            }
        }
    }

    static func list(_ names: [String]) -> String {
        guard names.count > 1 else { return names.first ?? "" }
        let lower = names.enumerated().map { $0.offset == 0 ? $0.element : $0.element.lowercased() }
        return lower.dropLast().joined(separator: ", ") + " and " + lower.last!
    }

    static func days(from: String, to: String) -> Int? {
        let format = Date.ISO8601FormatStyle().year().month().day()
        guard let start = try? Date(String(from.prefix(10)), strategy: format),
              let end = try? Date(String(to.prefix(10)), strategy: format) else { return nil }
        return Int((end.timeIntervalSince(start) / 86_400).rounded())
    }
}
