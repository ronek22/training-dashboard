import SwiftUI

/// How a readiness level reads on the phone: a headline word and its colour.
struct ReadinessStyle {
    let headline: String
    let label: String
    let color: Color

    init(level: String) {
        let status = TodayFormat.readiness(level)
        label = status.label
        color = status.color
        switch level {
        case "green": headline = "Ready"
        case "amber": headline = "Ease in"
        case "red": headline = "Recover"
        default: headline = "No read"
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
