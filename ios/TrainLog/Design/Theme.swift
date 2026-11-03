import SwiftUI
import UIKit

// Tokens from docs/design/REDESIGN.md and the iOS artboard. Dark only.
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

    static let bg = Color(hex: 0x0A0C11)
    static let card = Color(hex: 0x12151C)
    static let cardBorder = Color(hex: 0x1C212B)
    static let inset = Color(hex: 0x0E1117)
    static let track = Color(hex: 0x1F242E)
    static let outline = Color(hex: 0x2A303C)
    static let raised = Color(hex: 0x232835)
    /// Chip, segment and small-control fill on a card.
    static let chip = Color(hex: 0x1A1E27)
    /// Bar tracks and unselected chips inside a card, a step darker than `chip`.
    static let well = Color(hex: 0x151922)
    /// Sheet background (`presentationBackground`) for sheets that sit over the tab bar.
    static let sheet = Color(hex: 0x161A22)
    /// Full-bleed backdrop behind maps and hero charts.
    static let deep = Color(hex: 0x0C0F15)
    /// Chart ticks and axis lines.
    static let tick = Color(hex: 0x343A47)
    /// Dashed placeholders and quiet chart lines.
    static let rule = Color(hex: 0x4A5263)

    static let ink = Color(hex: 0xF3F5F9)
    /// Long-form body copy on a card: notes, coach text, summaries.
    static let inkBody = Color(hex: 0xC9CFDA)
    static let inkSoft = Color(hex: 0xA3ABBC)
    static let muted = Color(hex: 0x8A93A6)
    static let faint = Color(hex: 0x6B7385)
    /// Chart labels and finished/past steps, between `faint` and `dim`.
    static let subtle = Color(hex: 0x5B6375)
    static let dim = Color(hex: 0x3A4150)

    static let volt = Color(hex: 0xD4FF3A)
    static let warning = Color(hex: 0xFFC76E)
    /// Stronger amber for badges and "below target" states.
    static let caution = Color(hex: 0xFFC83A)
    static let amber = Color(hex: 0xFFB547)
    static let danger = Color(hex: 0xFF8A8A)
    static let dangerStrong = Color(hex: 0xFF7A7A)
    /// Alert dots, destructive swipe tints, failed states.
    static let alert = Color(hex: 0xFF5C6C)

    static let ride = Color(hex: 0x3B8CFF)
    static let run = Color(hex: 0xFF8A2A)
    static let strength = Color(hex: 0xFF4D9A)
    static let mobility = Color(hex: 0x2ED3B0)
    static let other = Color(hex: 0x8B7BFF)

    /// Sport colors lifted for text and links on dark (the base colors are for bars and fills).
    static let rideText = Color(hex: 0x6FAEFF)
    static let strengthText = Color(hex: 0xFF7AB5)
    static let strengthSoft = Color(hex: 0xFF9AC6)
}

/// Corner radii. Cards and sheets-in-cards use `card`; anything smaller steps down.
enum Radius {
    static let card: CGFloat = 22
    static let panel: CGFloat = 18
    static let tile: CGFloat = 16
    static let row: CGFloat = 14
    static let control: CGFloat = 12
    static let chip: CGFloat = 8
}

/// Spacing scale. `gutter` is the screen edge and card padding.
enum Space {
    static let hair: CGFloat = 2
    static let xs: CGFloat = 4
    static let s: CGFloat = 8
    static let m: CGFloat = 12
    static let gutter: CGFloat = 16
    static let l: CGFloat = 24
}

enum Sport: String, Decodable, Sendable {
    case ride, run, strength, mobility, walk, hike, rest, other

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = Sport(rawValue: raw) ?? .other
    }

    var color: Color {
        switch self {
        case .ride: .ride
        case .run: .run
        case .strength: .strength
        case .mobility, .walk: .mobility
        case .hike, .other: .other
        case .rest: .dim
        }
    }

    var label: String {
        switch self {
        case .mobility: "Mobility"
        case .rest: "Rest"
        default: rawValue.capitalized
        }
    }

    var symbol: String {
        switch self {
        case .ride: "bicycle"
        case .run: "figure.run"
        case .strength: "dumbbell.fill"
        case .mobility: "figure.cooldown"
        case .walk: "figure.walk"
        case .hike: "figure.hiking"
        case .rest: "bed.double.fill"
        case .other: "figure.mixed.cardio"
        }
    }
}

// Barlow Condensed for numbers and titles, Archivo for body (Resources/Fonts, OFL). Falls back
// to SF condensed / SF if a font fails to load.
enum AppFont {
    static func title(_ size: CGFloat) -> Font {
        custom("BarlowCondensed-ExtraBoldItalic", size) ?? .system(size: size, weight: .heavy).width(.condensed).italic()
    }

    static func number(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        let name = weight == .semibold ? "BarlowCondensed-SemiBold" : "BarlowCondensed-Bold"
        return custom(name, size) ?? .system(size: size, weight: weight).width(.condensed)
    }

    /// Archivo ships as one variable font, so it's picked by family and weight.
    static func body(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        archivoAvailable ? .custom("Archivo", fixedSize: size).weight(weight) : .system(size: size, weight: weight)
    }

    private static let archivoAvailable = !UIFont.fontNames(forFamilyName: "Archivo").isEmpty

    private static func custom(_ name: String, _ size: CGFloat) -> Font? {
        UIFont(name: name, size: size) == nil ? nil : .custom(name, fixedSize: size)
    }
}

struct Kicker: View {
    let text: String
    var color: Color = .muted

    init(_ text: String, color: Color = .muted) {
        self.text = text
        self.color = color
    }

    var body: some View {
        Text(text.uppercased())
            .font(AppFont.body(11, weight: .semibold))
            .tracking(11 * 0.14)
            .foregroundStyle(color)
    }
}

struct CardModifier: ViewModifier {
    var border: Color = .cardBorder

    func body(content: Content) -> some View {
        content
            .padding(Space.gutter)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(border, lineWidth: 1))
    }
}

extension View {
    func card(border: Color = .cardBorder) -> some View {
        modifier(CardModifier(border: border))
    }
}

/// The one volt action per screen.
struct VoltButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(AppFont.body(16, weight: .bold))
            .foregroundStyle(Color.bg)
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(Color.volt.opacity(configuration.isPressed ? 0.8 : 1), in: Capsule())
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.snappy(duration: 0.15), value: configuration.isPressed) // Motion.tap; Theme.swift is also built into the widgets
    }
}

/// Secondary actions: outline pills.
struct OutlineButtonStyle: ButtonStyle {
    var height: CGFloat = 40

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(AppFont.body(13, weight: .semibold))
            .foregroundStyle(Color.ink)
            .frame(maxWidth: .infinity, minHeight: height)
            .background(configuration.isPressed ? Color.raised : .clear, in: Capsule())
            .overlay(Capsule().strokeBorder(Color.outline, lineWidth: 1))
            .contentShape(Capsule())
    }
}

struct Pill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text.uppercased())
            .font(AppFont.body(11, weight: .bold))
            .tracking(1.1)
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .frame(height: 26)
            .background(color.opacity(0.14), in: Capsule())
    }
}
