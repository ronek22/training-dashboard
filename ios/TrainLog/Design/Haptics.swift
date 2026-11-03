import UIKit

/// One place for haptics so the same kind of moment feels the same everywhere. Views that react
/// to a value can use `.sensoryFeedback` instead; models and button actions call these.
@MainActor
enum Haptics {
    /// Picking an option: a chip, a stepper value, a segment.
    static func selection() {
        UISelectionFeedbackGenerator().selectionChanged()
    }

    /// Something saved or finished: a set logged, a meal added, a plan applied.
    static func success() {
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    static func warning() {
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
    }

    static func error() {
        UINotificationFeedbackGenerator().notificationOccurred(.error)
    }

    /// A light physical tick: a swipe action, a row moved.
    static func tick() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }

    /// A heavier thud for a step forward: the next set, the next exercise.
    static func thud() {
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }
}
