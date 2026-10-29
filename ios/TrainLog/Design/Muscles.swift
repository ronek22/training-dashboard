import Foundation

/// The web's muscle keys (frontend/src/activity-detail/muscles.mjs). Name-based estimates, not
/// measured activation.
enum Muscle: String, CaseIterable, Sendable, Codable {
    case chest, shoulders, triceps, biceps, forearms
    case upperBack = "upper_back", lats, lowerBack = "lower_back"
    case abs, obliques
    case glutes, quads, hamstrings, adductors, calves

    var label: String {
        switch self {
        case .upperBack: "Upper back"
        case .lowerBack: "Lower back"
        default: rawValue.capitalized
        }
    }

    var isCore: Bool { self == .abs || self == .obliques }

    /// Chip groups on the Add exercises sheet.
    enum Group: String, CaseIterable, Sendable {
        case back = "Back", chest = "Chest", shoulders = "Shoulders", arms = "Arms", legs = "Legs", core = "Core"

        var muscles: Set<Muscle> {
            switch self {
            case .back: [.upperBack, .lats, .lowerBack]
            case .chest: [.chest]
            case .shoulders: [.shoulders]
            case .arms: [.biceps, .triceps, .forearms]
            case .legs: [.glutes, .quads, .hamstrings, .adductors, .calves]
            case .core: [.abs, .obliques]
            }
        }
    }
}

struct MuscleMapping: Equatable, Sendable {
    let primary: [Muscle]
    let secondary: [Muscle]
}

/// Port of `classifyExercise` in muscles.mjs. Specific variants come before broad movement names
/// (leg curl before curl). Keep the two in sync.
enum MuscleRules {
    private static let rules: [(pattern: String, primary: [Muscle], secondary: [Muscle])] = [
        (#"\b(?:calf|calves)\b"#, [.calves], []),
        (#"\b(?:leg|hamstring) curls?\b|\bnordic\b"#, [.hamstrings], [.calves]),
        (#"\bleg extensions?\b"#, [.quads], []),
        (#"\b(?:hip|thigh) adductions?\b|\badductor\b"#, [.adductors], []),
        (#"\b(?:hip|thigh) abductions?\b|\b(?:glute kickback|hip thrust|glute bridge)\b"#, [.glutes], [.hamstrings]),
        (#"\b(?:romanian|stiff leg|straight leg) deadlift\b|\brdl\b|\bgood mornings?\b"#, [.hamstrings, .glutes], [.lowerBack]),
        (#"\bdeadlift\b"#, [.glutes, .hamstrings, .quads], [.lowerBack, .upperBack, .forearms]),
        (#"\bsquat\b|\blunges?\b|\bleg press\b|\bstep ups?\b"#, [.quads, .glutes], [.hamstrings, .adductors]),
        (#"\b(?:back|lumbar) extensions?\b|\bhyperextensions?\b"#, [.lowerBack], [.glutes, .hamstrings]),
        (#"\b(?:reverse|rear delt) (?:fly|flyes|flys|flies|raises?)\b|\bface pulls?\b"#, [.shoulders], [.upperBack]),
        (#"\bshrugs?\b"#, [.upperBack], []),
        (#"\bupright rows?\b"#, [.shoulders, .upperBack], [.biceps]),
        (#"\b(?:straight arm|stiff arm) (?:pull ?downs?|pullovers?)\b"#, [.lats], []),
        (#"\bpull ?ups?\b|\bchin ?ups?\b|\bpull ?downs?\b"#, [.lats], [.biceps, .upperBack]),
        (#"\brows?\b"#, [.upperBack, .lats], [.biceps, .shoulders]),
        (#"\b(?:wrist|reverse wrist) curls?\b|\bfarmer(?:s)? (?:walk|carry)\b"#, [.forearms], []),
        (#"\b(?:bicep|biceps|hammer|preacher|concentration|reverse|barbell|dumbbell|cable|incline dumbbell) curls?\b"#, [.biceps], [.forearms]),
        (#"\b(?:tricep|triceps)\b|\bskull ?crushers?\b|\bpush ?downs?\b|\bclose grip (?:bench )?press\b|\bbench dips?\b"#, [.triceps], []),
        (#"\b(?:shoulder|overhead|military|arnold) press\b|\b(?:lateral|front|scaption) raises?\b|\bpike push ups?\b"#, [.shoulders], []),
        (#"\bbench press\b|\bchest press\b|\bfloor press\b|\bpush ?ups?\b|\bdips?\b"#, [.chest], [.triceps, .shoulders]),
        (#"\b(?:chest|dumbbell|cable|incline|decline|machine) (?:fly|flyes|flys|flies)\b|\bpec deck\b|\bcable crossover\b"#, [.chest], [.shoulders]),
        (#"\bside plank\b|\brussian twist\b|\bwood ?chop\b|\bpallof\b|\bside bends?\b"#, [.obliques], [.abs]),
        (#"\bplank\b|\bcrunch(?:es)?\b|\bsit ?ups?\b|\bleg raises?\b|\bknee raises?\b|\bdead bug\b|\bab (?:wheel|rollout)\b"#, [.abs], [.obliques]),
    ]

    private static let compiled = rules.map { rule in
        (regex: try! NSRegularExpression(pattern: rule.pattern), mapping: MuscleMapping(primary: rule.primary, secondary: rule.secondary))
    }
    private static let excluded = try! NSRegularExpression(pattern: #"\bstretch|\bwarm up\b|\browing\b|\bclean\b|\bsnatch\b|\bto\b|\band\b"#)

    static func classify(_ name: String) -> MuscleMapping? {
        var words = name.lowercased()
            .replacingOccurrences(of: "[-_–—]", with: " ", options: .regularExpression)
            .replacingOccurrences(of: "[^a-z0-9 ]", with: "", options: .regularExpression)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
        words = words.trimmingCharacters(in: .whitespaces)
        let range = NSRange(words.startIndex..., in: words)
        if excluded.firstMatch(in: words, range: range) != nil { return nil }
        return compiled.first { $0.regex.firstMatch(in: words, range: range) != nil }?.mapping
    }
}

/// Work sets per muscle for a list of (exercise name, set count), like `summarizeMuscles`.
struct MuscleSummary: Equatable, Sendable {
    struct Count: Equatable, Sendable {
        let muscle: Muscle
        var primary: Int
        var secondary: Int
    }

    let counts: [Count]

    init(_ exercises: [(name: String, sets: Int)]) {
        var byMuscle: [Muscle: Count] = [:]
        for exercise in exercises where exercise.sets > 0 {
            guard let mapping = MuscleRules.classify(exercise.name) else { continue }
            for muscle in mapping.primary {
                byMuscle[muscle, default: Count(muscle: muscle, primary: 0, secondary: 0)].primary += exercise.sets
            }
            for muscle in mapping.secondary {
                byMuscle[muscle, default: Count(muscle: muscle, primary: 0, secondary: 0)].secondary += exercise.sets
            }
        }
        counts = byMuscle.values.sorted {
            ($0.primary, $0.secondary, $1.muscle.label) > ($1.primary, $1.secondary, $0.muscle.label)
        }
    }

    var primary: Set<Muscle> { Set(counts.filter { $0.primary > 0 }.map(\.muscle)) }
    var secondary: Set<Muscle> { Set(counts.filter { $0.primary == 0 && $0.secondary > 0 }.map(\.muscle)) }
    var hasCore: Bool { counts.contains { $0.muscle.isCore && $0.primary > 0 } }
}
