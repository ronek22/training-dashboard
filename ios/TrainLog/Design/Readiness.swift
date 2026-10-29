import Charts
import SwiftUI

/// How a readiness level reads on the phone: a headline word, an icon and a spot on the gauge.
struct ReadinessStyle {
    let headline: String
    let label: String
    let color: Color
    let icon: String
    /// Where the marker sits on the gauge, 0 (red end) to 1 (green end); nil without a read.
    let position: Double?

    init(level: String, points: Int?) {
        let status = TodayFormat.readiness(level)
        label = status.label
        color = status.color
        switch level {
        case "green": headline = "Ready"; icon = "bolt.fill"
        case "amber": headline = "Ease in"; icon = "gauge.with.dots.needle.33percent"
        case "red": headline = "Recover"; icon = "bed.double.fill"
        default: headline = "No read"; icon = "questionmark"
        }
        // Points count against readiness: 0 sits at the green end, 6 or more at the red end.
        // Without points (an older cached response) the marker sits mid-zone.
        let fallback: [String: Double] = ["green": 0.88, "amber": 0.56, "red": 0.2]
        if level == "unknown" || fallback[level] == nil {
            position = nil
        } else if let points {
            position = min(max(1 - Double(points) / 6, 0.04), 0.96)
        } else {
            position = fallback[level]
        }
    }

    static func icon(forFactor key: String) -> String {
        switch key {
        case "sleep": "moon.fill"
        case "sleep_debt": "moon.zzz.fill"
        case "hrv": "waveform.path.ecg"
        case "resting_hr": "heart.fill"
        case "check_in", "checkin": "face.smiling"
        case "life_load": "briefcase.fill"
        case "sick": "thermometer.medium"
        case "illness_return": "cross.case.fill"
        case "mountain_reentry": "mountain.2.fill"
        case "load": "flame.fill"
        case "ramp": "chart.line.uptrend.xyaxis"
        default: "circle.fill"
        }
    }
}

/// A 240° arc in three zones (red, amber, green), the current zone lit and a knob at the read.
struct ReadinessGauge: View {
    let style: ReadinessStyle
    var size: CGFloat = 96
    var lineWidth: CGFloat = 9

    @State private var shown = false

    private static let sweep = 240.0
    private static let start = 150.0
    private static let zones: [(from: Double, to: Double, color: Color)] = [
        (0, 0.375, .danger), (0.375, 0.75, .warning), (0.75, 1, .mobility),
    ]

    var body: some View {
        ZStack {
            ForEach(Self.zones.indices, id: \.self) { index in
                let zone = Self.zones[index]
                let lit = style.position.map { $0 >= zone.from && $0 <= zone.to } ?? false
                arc(from: zone.from + (index == 0 ? 0 : 0.012), to: zone.to - (index == 2 ? 0 : 0.012))
                    .stroke(style.position == nil ? Color.track : zone.color.opacity(lit ? 1 : 0.18),
                            style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
            }
            if let position = style.position {
                knob
                    .rotationEffect(.degrees(Self.sweep * (shown ? position : 0)))
            }
            Image(systemName: style.icon)
                .font(.system(size: size * 0.24, weight: .bold))
                .foregroundStyle(style.color)
                .offset(y: size * 0.02)
        }
        .frame(width: size, height: size)
        .onAppear {
            withAnimation(.spring(response: 0.9, dampingFraction: 0.75).delay(0.1)) { shown = true }
        }
        .accessibilityElement()
        .accessibilityLabel("Readiness \(style.headline), \(style.label)")
    }

    private func arc(from: Double, to: Double) -> some Shape {
        Circle()
            .inset(by: lineWidth / 2)
            .trim(from: from * Self.sweep / 360, to: to * Self.sweep / 360)
            .rotation(.degrees(Self.start))
    }

    /// Sits at the gauge's start angle; rotating the whole frame moves it along the arc.
    private var knob: some View {
        let radius = (size - lineWidth) / 2
        let angle = Self.start * .pi / 180
        return Circle()
            .fill(Color.card)
            .overlay(Circle().strokeBorder(style.color, lineWidth: 3))
            .frame(width: lineWidth + 7, height: lineWidth + 7)
            .offset(x: radius * cos(angle), y: radius * sin(angle))
            .frame(width: size, height: size)
    }
}

/// One readiness signal as a small tinted icon: green steady, amber caution, red risk.
struct SignalChip: View {
    let key: String
    let tone: String
    var size: CGFloat = 26

    var body: some View {
        let color = BodyFormat.toneColor(tone)
        Image(systemName: ReadinessStyle.icon(forFactor: key))
            .font(.system(size: size * 0.46, weight: .semibold))
            .foregroundStyle(color)
            .frame(width: size, height: size)
            .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: size * 0.32, style: .continuous))
    }
}

/// A week of readings as a thin line with the latest one dotted.
struct TrendLine: View {
    let values: [Double]
    let color: Color

    var body: some View {
        let low = values.min() ?? 0
        let high = values.max() ?? 1
        let pad = max((high - low) * 0.25, 0.5)
        Chart {
            ForEach(Array(values.enumerated()), id: \.offset) { index, value in
                AreaMark(x: .value("Day", index), yStart: .value("Floor", low - pad), yEnd: .value("Value", value))
                    .foregroundStyle(color.opacity(0.1))
                    .interpolationMethod(.monotone)
                LineMark(x: .value("Day", index), y: .value("Value", value))
                    .foregroundStyle(color)
                    .lineStyle(StrokeStyle(lineWidth: 1.6, lineCap: .round))
                    .interpolationMethod(.monotone)
            }
            if let last = values.last {
                PointMark(x: .value("Day", values.count - 1), y: .value("Value", last))
                    .symbol { Circle().fill(color).frame(width: 5, height: 5) }
            }
        }
        .chartXScale(domain: 0...max(values.count - 1, 1))
        .chartYScale(domain: (low - pad)...(high + pad))
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .accessibilityHidden(true)
    }
}
