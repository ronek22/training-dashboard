import Foundation

/// The Running form and Splits sheets: each form metric against its good range and your usual,
/// with how it moved kilometre by kilometre (from the HealthFit FIT file's `run_dynamics`).
extension ActivityDetailFormat {
    struct FormDetail: Equatable {
        let cell: FormCell
        let value: Double
        let usual: Double?
        let good: ClosedRange<Double>?
        /// Where the range bar starts and ends, wide enough for the range, today and usual.
        let scale: ClosedRange<Double>
        let note: String?
        let perKm: [Double]
        /// "152 → 155 spm" over the run, when the splits have it.
        let drift: String?
    }

    private struct FormMetric {
        let label: String
        let key: String
        let unit: String
        let decimals: Int
        let today: KeyPath<ActivityDetail.RunDynamics, Double?>
        let usual: KeyPath<RunningFitness.Form.Values, Double?>
        let split: KeyPath<ActivityDetail.RunDynamics.Split, Double?>
        let note: String?
    }

    private static var formMetrics: [FormMetric] { [
        FormMetric(label: "Cadence", key: "cadenceSpm", unit: "spm", decimals: 0, today: \.cadenceSpm, usual: \.cadenceSpm, split: \.cadenceSpm, note: nil),
        FormMetric(label: "Ground contact", key: "stanceTimeMs", unit: "ms", decimals: 0, today: \.stanceTimeMs, usual: \.stanceTimeMs, split: \.stanceTimeMs, note: nil),
        FormMetric(label: "Step length", key: "stepLengthM", unit: "m", decimals: 2, today: \.stepLengthM, usual: \.stepLengthM, split: \.stepLengthM,
                   note: "How far each step carries you. It grows with speed, so compare it with runs at a similar pace."),
        FormMetric(label: "Vert. oscillation", key: "verticalOscillationCm", unit: "cm", decimals: 1, today: \.verticalOscillationCm, usual: \.verticalOscillationCm, split: \.verticalOscillationCm, note: nil),
        FormMetric(label: "Vert. ratio", key: "verticalRatioPct", unit: "%", decimals: 1, today: \.verticalRatioPct, usual: \.verticalRatioPct, split: \.verticalRatioPct, note: nil),
        FormMetric(label: "Power", key: "avgPowerW", unit: "W", decimals: 0, today: \.avgPowerW, usual: \.avgPowerW, split: \.powerW,
                   note: "Running power from the watch. It follows pace and hills, so it's a read on effort rather than form."),
    ] }

    static func formDetails(_ detail: ActivityDetail, fitness: RunningFitness.Form?) -> [FormDetail] {
        guard let run = detail.runDynamics else { return [] }
        let cells = form(detail, fitness: fitness)
        return formMetrics.compactMap { metric in
            guard let value = run[keyPath: metric.today], let cell = cells.first(where: { $0.label == metric.label }) else { return nil }
            let usual = fitness?.baseline?[keyPath: metric.usual]
            // Dictionary keys keep their snake_case through the decoder.
            let snake = metric.key.replacingOccurrences(of: "([A-Z])", with: "_$1", options: .regularExpression).lowercased()
            let range = fitness?.ranges?[snake] ?? fitness?.ranges?[metric.key]
            let good = range.flatMap { $0.good.count == 2 ? $0.good[0]...$0.good[1] : nil }
            let points = [value, usual, good?.lowerBound, good?.upperBound].compactMap { $0 }
            let (lo, hi) = (points.min() ?? value, points.max() ?? value)
            let pad = Swift.max((hi - lo) * 0.25, Swift.abs(value) * 0.03)
            let perKm = run.splits.compactMap { $0[keyPath: metric.split] }
            var drift: String?
            if perKm.count >= 2, let first = perKm.first, let last = perKm.last {
                let format = { (v: Double) in metric.decimals == 0 ? "\(Int(v.rounded()))" : String(format: "%.\(metric.decimals)f", v) }
                drift = "\(format(first)) → \(format(last)) \(metric.unit) from the first km to the last"
            }
            return FormDetail(cell: cell, value: value, usual: usual, good: good, scale: (lo - pad)...(hi + pad),
                              note: range?.note ?? metric.note, perKm: perKm.count >= 2 ? perKm : [], drift: drift)
        }
    }

    // MARK: Splits sheet

    struct SplitColumn: Equatable {
        let title: String
        let metric: Metric
        let values: [String]
    }

    /// Pace, then every metric the FIT file has for each kilometre; columns with nothing in them are dropped.
    static func splitColumns(_ detail: ActivityDetail) -> [SplitColumn] {
        let splits = detail.runDynamics?.splits.filter { $0.seconds > 0 } ?? []
        guard splits.count >= 2 else { return [] }
        func column(_ title: String, _ metric: Metric, _ path: KeyPath<ActivityDetail.RunDynamics.Split, Double?>, decimals: Int = 0) -> SplitColumn? {
            let values = splits.map { split in split[keyPath: path].map { decimals == 0 ? "\(Int($0.rounded()))" : String(format: "%.\(decimals)f", $0) } ?? "–" }
            return values.allSatisfy { $0 == "–" } ? nil : SplitColumn(title: title, metric: metric, values: values)
        }
        return [
            SplitColumn(title: "Pace", metric: .pace, values: splits.map { paceText($0.seconds) }),
            column("HR", .heartRate, \.heartRate),
            column("Cad", .cadence, \.cadenceSpm),
            column("W", .power, \.powerW),
            column("GCT", .time, \.stanceTimeMs),
            column("VO", .elevation, \.verticalOscillationCm, decimals: 1),
            column("Step", .distance, \.stepLengthM, decimals: 2),
        ].compactMap { $0 }
    }
}
