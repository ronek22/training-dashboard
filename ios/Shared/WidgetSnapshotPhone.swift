import Foundation

// The iPhone side of the snapshot: built from the server's DTOs, which the Watch doesn't compile.

extension WidgetSnapshot.Today {
    init(_ phone: PhoneToday) {
        self.init(
            date: phone.date,
            title: phone.today?.title,
            sport: (phone.today?.sport ?? .rest).rawValue,
            durationMin: phone.today?.durationMin,
            isDone: phone.today?.isDone ?? false,
            readiness: phone.readiness.level,
            streakDays: phone.streakDays,
            weekDoneMin: phone.weekMinutes.done,
            weekPlannedMin: phone.weekMinutes.planned,
            weekBySport: phone.weekMinutes.bySport.map { .init(sport: $0.sport.rawValue, minutes: $0.minutes) },
            intent: phone.today?.intentLabel,
            liftCount: phone.today?.strength?.exercises.count,
            sickDay: phone.sick.map { $0.day ?? 1 },
            tomorrow: phone.tomorrow.map { .init(sport: ($0.sport ?? .other).rawValue, durationMin: $0.durationMin) },
            week: phone.week.map { .init(sport: $0.sport.rawValue, status: $0.status, doneSports: $0.doneSports.map(\.rawValue)) },
            rehab: phone.rehab.map { .init(title: $0.title, done: $0.done, total: $0.total, durationMin: $0.durationMin) },
            firstLift: phone.today?.strength?.exercises.first.map(WidgetFormat.lift)
        )
    }
}

extension WidgetSnapshot.Food {
    /// `eaten` includes meals still queued on the phone.
    init(_ day: FoodDay, eaten: Macros) {
        self.init(
            date: day.date,
            eatenKcal: eaten.kcal,
            targetKcal: day.target?.kcal,
            proteinG: eaten.proteinG,
            proteinTargetG: day.proteinTargetG
        )
    }
}

extension WidgetFormat {
    /// "Row 34 kg × 10", "Plank 3 × 30 s" or "Pull-up × 6": what to rack first.
    static func lift(_ exercise: PhoneToday.Exercise) -> String {
        let name = exercise.name.replacingOccurrences(of: "Dumbbell ", with: "").replacingOccurrences(of: "Barbell ", with: "")
        if let seconds = exercise.seconds { return "\(name) \(exercise.sets) × \(seconds) s" }
        let reps = exercise.reps.map { " × \($0)" } ?? ""
        guard let kg = exercise.weightKg, kg > 0 else { return name + reps }
        let weight = kg.rounded() == kg ? String(Int(kg)) : String(format: "%.1f", kg)
        return "\(name) \(weight) kg\(reps)"
    }
}
