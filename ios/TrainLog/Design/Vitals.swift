import Charts
import SwiftUI

/// The overnight vitals, read like the Watch's Vitals app: each against its typical range.
enum VitalKind: String, CaseIterable, Identifiable {
    case hrv
    case restingHr = "resting_hr"
    case sleep
    case steps

    var id: String { rawValue }

    var label: String {
        switch self {
        case .hrv: "HRV"
        case .restingHr: "Resting HR"
        case .sleep: "Sleep"
        case .steps: "Steps"
        }
    }

    /// Each vital keeps its own colour, like the Watch's Vitals app.
    var color: Color {
        switch self {
        case .hrv: .ride
        case .restingHr: .danger
        case .sleep: .other
        case .steps: .warning
        }
    }

    var icon: String {
        switch self {
        case .hrv: "waveform.path.ecg"
        case .restingHr: "heart.fill"
        case .sleep: "moon.fill"
        case .steps: "figure.walk"
        }
    }

    /// For tight spots like the Today card's columns.
    var shortLabel: String { self == .restingHr ? "RHR" : label }

    var unit: String {
        switch self {
        case .hrv: "ms"
        case .restingHr: "bpm"
        case .sleep: "h"
        case .steps: "steps"
        }
    }

    var higherIsBetter: Bool { self != .restingHr }

    func format(_ value: Double) -> String {
        switch self {
        case .sleep: String(format: "%.1f", value)
        case .steps: BodyFormat.steps(value)
        default: String(Int(value.rounded()))
        }
    }
}

/// Where a reading falls against its typical range. Inside it the vital keeps its own colour;
/// outside it, green on the good side and amber on the side to watch.
enum VitalStatus: Equatable {
    case typical, low, high, unknown

    init(value: Double, low: Double?, high: Double?) {
        guard let low, let high else { self = .unknown; return }
        self = value < low ? .low : value > high ? .high : .typical
    }

    var isOutlier: Bool { self == .low || self == .high }

    var label: String {
        switch self {
        case .typical: "Typical"
        case .low: "Below typical"
        case .high: "Above typical"
        case .unknown: "Building range"
        }
    }

    func color(_ kind: VitalKind) -> Color {
        switch self {
        case .typical, .unknown: kind.color
        case .low: kind.higherIsBetter ? .warning : .mobility
        case .high: kind.higherIsBetter ? .mobility : .warning
        }
    }
}

/// The y range that fits the typical band and every reading with some air around them.
private func vitalDomain(_ values: [Double], low: Double?, high: Double?) -> ClosedRange<Double> {
    let all = values + [low, high].compactMap { $0 }
    let bottom = all.min() ?? 0
    let top = all.max() ?? 1
    let pad = max(top - bottom, abs(top) * 0.1, 1) * 0.3
    return (bottom - pad)...(top + pad)
}

/// A Watch Vitals column: a slim track, the typical range shaded in it, the latest reading as a dot.
struct VitalBar: View {
    let kind: VitalKind
    let value: Double
    let low: Double?
    let high: Double?
    var width: CGFloat = 14

    var body: some View {
        let dot = width + 4
        GeometryReader { geometry in
            let height = geometry.size.height
            let center = geometry.size.width / 2
            let domain = vitalDomain([value], low: low, high: high)
            let y = { (v: Double) in (1 - (v - domain.lowerBound) / (domain.upperBound - domain.lowerBound)) * height }
            ZStack {
                Capsule().fill(kind.color.opacity(0.14))
                    .frame(width: width, height: height)
                    .position(x: center, y: height / 2)
                if let low, let high {
                    let band = max(y(low) - y(high), width)
                    Capsule().fill(kind.color.opacity(0.4))
                        .frame(width: width, height: band)
                        .position(x: center, y: y(high) + band / 2)
                }
                Circle()
                    .fill(VitalStatus(value: value, low: low, high: high).color(kind))
                    .overlay(Circle().strokeBorder(Color.inset, lineWidth: 2))
                    .frame(width: dot, height: dot)
                    .position(x: center, y: min(max(y(value), dot / 2), height - dot / 2))
            }
        }
        .frame(width: dot)
        .accessibilityHidden(true)
    }
}

/// Seven days of readings as dots over the shaded typical range; today's dot ringed.
struct VitalWeekChart: View {
    let kind: VitalKind
    let days: [PhoneBody.Day]
    let low: Double?
    let high: Double?
    /// The last day on the axis; days before it count back from here.
    let today: String

    var body: some View {
        let points = indexed
        let domain = vitalDomain(points.map(\.value), low: low, high: high)
        Chart {
            if let low, let high {
                RectangleMark(xStart: .value("From", -0.45), xEnd: .value("To", 6.45), yStart: .value("Low", low), yEnd: .value("High", high))
                    .foregroundStyle(kind.color.opacity(0.16))
                    .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            }
            ForEach(points, id: \.index) { point in
                let status = VitalStatus(value: point.value, low: low, high: high)
                let isLast = point.index == points.last?.index
                PointMark(x: .value("Day", point.index), y: .value(kind.label, point.value))
                    .symbol {
                        Circle()
                            .fill(status.color(kind))
                            .overlay(Circle().strokeBorder(Color.card, lineWidth: isLast ? 2 : 1.5))
                            .frame(width: isLast ? 13 : 9, height: isLast ? 13 : 9)
                    }
            }
        }
        .chartXScale(domain: -0.5...6.5)
        .chartYScale(domain: domain)
        .chartXAxis {
            AxisMarks(values: Array(0...6)) { value in
                AxisValueLabel {
                    let index = value.as(Int.self) ?? 0
                    Text(letter(index))
                        .font(AppFont.body(9, weight: index == 6 ? .bold : .medium))
                        .foregroundStyle(index == 6 ? Color.inkSoft : Color.faint)
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: [low, high].compactMap { $0 }) { value in
                AxisValueLabel(kind.format(value.as(Double.self) ?? 0))
                    .font(AppFont.body(9, weight: .medium))
                    .foregroundStyle(Color.faint)
            }
        }
        .accessibilityHidden(true)
    }

    private var end: Date? { TodayFormat.parse(today) }

    /// Each reading placed by its day: 6 is today, 0 six days ago.
    private var indexed: [(index: Int, value: Double)] {
        guard let end else { return [] }
        return days.compactMap { day in
            guard let date = TodayFormat.parse(day.date) else { return nil }
            let back = Calendar.current.dateComponents([.day], from: date, to: end).day ?? 0
            return (0...6).contains(back) ? (6 - back, day.value) : nil
        }
    }

    private func letter(_ index: Int) -> String {
        guard let end, let date = Calendar.current.date(byAdding: .day, value: index - 6, to: end) else { return "" }
        return String(date.formatted(.dateTime.weekday(.narrow).locale(Locale(identifier: "en_GB"))))
    }
}
