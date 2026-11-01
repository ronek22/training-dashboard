import HealthKit

// Shared with the Watch app (project.yml): both sides pick the same Apple Health workout.

/// The Apple Health workout a TrainLog session is saved as.
enum WatchWorkoutType {
    /// Bodyweight days (no saved workout) are functional strength.
    static func strength(templateId: Int?) -> HKWorkoutActivityType {
        templateId == nil ? .functionalStrengthTraining : .traditionalStrengthTraining
    }

    /// The backend names the Apple Workout to use (`watch_workout`); rehab defaults to recovery.
    static func rehab(_ name: String?) -> HKWorkoutActivityType {
        switch name?.lowercased() ?? "" {
        case let value where value.contains("flexibility"): .flexibility
        case let value where value.contains("core"): .coreTraining
        case let value where value.contains("mind"): .mindAndBody
        case let value where value.contains("walk"): .walking
        case let value where value.contains("strength"): .functionalStrengthTraining
        default: .preparationAndRecovery
        }
    }
}
