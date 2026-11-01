import SwiftUI

// Same tokens as the iPhone (TrainLog/Design/Theme.swift) and docs/design/artboards/Watch.dc.html.
// Pure black behind everything: OLED, and it disappears into the bezel.
extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }

    static let card = Color(hex: 0x12151C)
    static let cardBorder = Color(hex: 0x1C212B)
    static let raised = Color(hex: 0x1A1E27)
    static let track = Color(hex: 0x2A303C)

    static let ink = Color(hex: 0xF3F5F9)
    static let muted = Color(hex: 0x8A93A6)
    static let faint = Color(hex: 0x4A5263)

    static let volt = Color(hex: 0xD4FF3A)
    static let heart = Color(hex: 0xFF5A5F)
    static let strength = Color(hex: 0xFF4D9A)
    static let strengthSoft = Color(hex: 0xFF9AC6)
    static let strengthTint = Color(hex: 0x1E1219)
    static let mobility = Color(hex: 0x2ED3B0)
    static let mobilityTrack = Color(hex: 0x14302A)
    /// Started on the iPhone.
    static let ride = Color(hex: 0x3B8CFF)
    static let rideSoft = Color(hex: 0x8DBBFF)
}

enum WatchFont {
    /// Barlow Condensed Bold: every number.
    static func number(_ size: CGFloat) -> Font {
        .custom("BarlowCondensed-Bold", fixedSize: size)
    }

    /// Barlow Condensed ExtraBold Italic, uppercased by the caller: titles.
    static func title(_ size: CGFloat) -> Font {
        .custom("BarlowCondensed-ExtraBoldItalic", fixedSize: size)
    }

    static func body(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .custom("Archivo", fixedSize: size).weight(weight)
    }
}

/// 9 pt tracked uppercase label.
struct WatchKicker: View {
    let text: String
    var color: Color = .muted

    init(_ text: String, color: Color = .muted) {
        self.text = text
        self.color = color
    }

    var body: some View {
        Text(text.uppercased())
            .font(WatchFont.body(9, weight: .semibold))
            .tracking(1.2)
            .foregroundStyle(color)
            .lineLimit(1)
    }
}

struct WatchTitle: View {
    let text: String
    var size: CGFloat = 25

    init(_ text: String, size: CGFloat = 25) {
        self.text = text
        self.size = size
    }

    var body: some View {
        Text(text.uppercased())
            .font(WatchFont.title(size))
            .foregroundStyle(Color.ink)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
    }
}

/// The one primary action on a screen.
struct VoltButtonStyle: ButtonStyle {
    var height: CGFloat = 38

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(WatchFont.body(15, weight: .bold))
            .foregroundStyle(Color.black)
            .frame(maxWidth: .infinity, minHeight: height)
            .background(Color.volt, in: Capsule())
            .opacity(configuration.isPressed ? 0.8 : 1)
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
    }
}

/// Secondary actions: a filled dark capsule.
struct DarkButtonStyle: ButtonStyle {
    var height: CGFloat = 34
    var tint: Color?

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(WatchFont.body(13, weight: .semibold))
            .foregroundStyle(tint ?? .ink)
            .frame(maxWidth: .infinity, minHeight: height)
            .background(tint.map { $0.opacity(0.18) } ?? Color.raised, in: Capsule())
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
    }
}

/// ♥ 128, red; dashes before the first reading.
struct HeartRateLabel: View {
    let bpm: Double?
    var dimmed = false
    var trend: String?

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: "heart.fill")
                .font(.system(size: 11))
                .symbolEffect(.pulse, options: .repeating, isActive: bpm != nil && !dimmed)
            Text(bpm.map { String(Int($0.rounded())) } ?? "--")
                .font(WatchFont.number(16))
                .contentTransition(.numericText())
            if let trend {
                Text(trend).font(.system(size: 10, weight: .bold))
            }
        }
        .foregroundStyle(dimmed ? Color.heart.opacity(0.5) : .heart)
    }
}

/// Ring countdown used by rest and holds.
struct CountdownRing: View {
    let progress: Double
    var color: Color = .mobility
    var track: Color = .mobilityTrack
    var lineWidth: CGFloat = 9

    var body: some View {
        ZStack {
            Circle().stroke(track, lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: max(0, min(1, progress)))
                .stroke(color, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

enum WatchClock {
    /// "1:12", "18:42", "1:02:05".
    static func text(_ seconds: Int) -> String {
        let seconds = max(0, seconds)
        let hours = seconds / 3600, minutes = seconds % 3600 / 60, rest = seconds % 60
        return hours > 0 ? String(format: "%d:%02d:%02d", hours, minutes, rest) : String(format: "%d:%02d", minutes, rest)
    }
}
