import SwiftUI

// Calm detail pages (docs/design/artboards/iOSActivityDetailV3.dc.html, "Component sheet"):
// colour per metric, status lines, sections on the background, glass buttons, small meters.

/// One colour per kind of number, the same in grids, charts and tables.
enum Metric: Sendable {
    case time, distance, pace, speed, heartRate, power, elevation, cadence, volume, grade, plain

    var color: Color {
        switch self {
        case .time: Color(hex: 0xFFD24A)
        case .distance: Color(hex: 0x4FD1FF)
        case .pace, .speed: Color(hex: 0xFFA25A)
        case .heartRate: Color(hex: 0xFF6B7D)
        case .power: Color(hex: 0xA99BFF)
        case .elevation: Color(hex: 0x7DDB5A)
        case .cadence: Color(hex: 0x6FAEFF)
        case .volume: Color(hex: 0xFF7AB4)
        case .grade: Color.inkSoft
        case .plain: Color.ink
        }
    }
}

/// Heart-rate and power zone colours, Zone 1 first.
enum ZonePalette {
    static let hex: [UInt32] = [0x49A6FF, 0x43D17C, 0xF5B742, 0xFF8B3D, 0xFF5C6F, 0xC77DFF, 0xA99BFF]

    static func color(_ index: Int) -> Color {
        Color(hex: hex[min(max(index, 0), hex.count - 1)])
    }
}

/// A colour ramp: stops at positions 0...1, interpolated in sRGB.
struct ColorScale: Sendable {
    let stops: [(at: Double, hex: UInt32)]

    /// Slower or lower (cyan) to faster or higher (red): the glowing route.
    static let route = ColorScale(stops: [(0, 0x4FD1FF), (0.25, 0x7DDB5A), (0.5, 0xFFD24A), (0.75, 0xFFA25A), (1, 0xFF5C6F)])
    /// Share of the all-time best: power bests bars.
    static let share = ColorScale(stops: [(0, 0x4FD1FF), (0.35, 0x7DDB5A), (0.55, 0xFFD24A), (0.75, 0xFFA25A), (1, 0xFF5C6F)])

    func color(_ value: Double) -> Color {
        let v = min(max(value, 0), 1)
        guard let upper = stops.firstIndex(where: { $0.at >= v }) else { return Color(hex: stops.last?.hex ?? 0) }
        if upper == 0 { return Color(hex: stops[0].hex) }
        let (a, b) = (stops[upper - 1], stops[upper])
        let t = (v - a.at) / max(b.at - a.at, 0.0001)
        func channel(_ hex: UInt32, _ shift: UInt32) -> Double { Double((hex >> shift) & 0xFF) / 255 }
        func mix(_ shift: UInt32) -> Double { channel(a.hex, shift) + (channel(b.hex, shift) - channel(a.hex, shift)) * t }
        return Color(.sRGB, red: mix(16), green: mix(8), blue: mix(0))
    }
}

// MARK: Status lines

enum StatusTone: Equatable, Sendable {
    case good, warn, info

    var color: Color {
        switch self {
        case .good: .mobility
        case .warn: Color(hex: 0xFFC83A)
        case .info: Color(hex: 0x5B6478)
        }
    }

    init(_ tone: String?) {
        switch tone {
        case "good": self = .good
        case "warn", "bad": self = .warn
        default: self = .info
        }
    }
}

/// Teal tick = good, amber ! = watch, grey ring = info.
struct StatusIcon: View {
    let tone: StatusTone
    var size: CGFloat = 14

    var body: some View {
        ZStack {
            switch tone {
            case .good:
                Circle().fill(tone.color)
                Image(systemName: "checkmark").font(.system(size: size * 0.5, weight: .heavy)).foregroundStyle(Color.bg)
            case .warn:
                Circle().fill(tone.color)
                Text("!").font(.system(size: size * 0.72, weight: .heavy)).foregroundStyle(Color.bg)
            case .info:
                Circle().strokeBorder(tone.color, lineWidth: 2)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

struct StatusLine: View {
    let tone: StatusTone
    let text: String
    var size: CGFloat = 13
    var color: Color = .inkSoft

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            StatusIcon(tone: tone).alignmentGuide(.firstTextBaseline) { $0[.bottom] - 2.5 }
            Text(text).font(AppFont.body(size)).foregroundStyle(color).lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: Numbers

/// "43m 36s" style: Barlow numbers in the metric colour, units at 58% of the size in a soft white.
struct MetricValue: View {
    let parts: [(value: String, unit: String)]
    var size: CGFloat = 34
    var color: Color = .ink
    var unitColor: Color = Color(hex: 0xC9CFDA)
    var unitUppercase = false

    var body: some View {
        parts.enumerated().reduce(Text("")) { text, item in
            let (index, part) = item
            let unit = unitUppercase ? part.unit.uppercased() : part.unit
            return Text("\(text)\(Text(index > 0 ? " " : "").font(AppFont.number(size * 0.58)))\(Text(part.value).font(AppFont.number(size)).foregroundStyle(color))\(Text(unit).font(AppFont.number(size * 0.58)).foregroundStyle(unitColor))")
        }
        .lineLimit(1)
        .minimumScaleFactor(0.6)
    }
}

// MARK: Sections

/// A section on the background: 32 above, a hairline, 24 below it, a Barlow 22 title.
struct DetailSection<Trailing: View, Content: View>: View {
    let title: String?
    @ViewBuilder let trailing: Trailing
    @ViewBuilder let content: Content

    init(_ title: String?, @ViewBuilder trailing: () -> Trailing = { EmptyView() }, @ViewBuilder content: () -> Content) {
        self.title = title
        self.trailing = trailing()
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            if let title {
                HStack(alignment: .center) {
                    Text(title).font(AppFont.number(22)).foregroundStyle(Color.ink)
                    Spacer(minLength: 8)
                    trailing
                }
                .frame(height: 32)
                .padding(.top, 20)
            }
            content
        }
        .padding(.top, 32)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct ShowMoreButton: View {
    var title = "Show more ›"
    let action: () -> Void

    var body: some View {
        Button(title, action: action)
            .font(AppFont.body(14, weight: .semibold))
            .foregroundStyle(Color(hex: 0x6FAEFF))
            .frame(minHeight: 44)
            .contentShape(Rectangle())
    }
}

/// "Edit": a quiet filled pill, 32 high with a 44 hit area.
struct QuietPillButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(AppFont.body(14, weight: .semibold))
                .foregroundStyle(Color.ink)
                .padding(.horizontal, 14)
                .frame(height: 32)
                .background(Color(hex: 0x1A1E27), in: Capsule())
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
    }
}

/// Uppercase tinted badge ("On intent").
struct ToneBadge: View {
    let text: String
    let color: Color
    var fill: Color?

    var body: some View {
        Text(text.uppercased())
            .font(AppFont.body(11, weight: .bold))
            .tracking(1.1)
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .frame(height: 24)
            .background(fill ?? color.opacity(0.12), in: Capsule())
    }
}

/// 44 pt glass circle over a map or trace.
struct GlassCircleButton: View {
    let symbol: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Color.ink)
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial, in: Circle())
                .background(Color(hex: 0x12151C).opacity(0.72), in: Circle())
                .overlay(Circle().strokeBorder(Color.white.opacity(0.08)))
                .environment(\.colorScheme, .dark)
        }
        .accessibilityLabel(label)
    }
}

/// Low · good · high with today's step lit; nil lights nothing.
struct ThreeStepMeter: View {
    let step: Int?
    let lit: Color

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<3, id: \.self) { index in
                RoundedRectangle(cornerRadius: 2).fill(index == step ? lit : Color(hex: 0x1A1F29)).frame(height: 4)
            }
        }
        .accessibilityHidden(true)
    }
}

/// Flat loading block with a slow opacity pulse (still under Reduce Motion).
struct Skeleton: View {
    var width: CGFloat?
    let height: CGFloat
    var radius: CGFloat = 8
    @State private var dim = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        RoundedRectangle(cornerRadius: radius, style: .continuous)
            .fill(Color(hex: 0x161A22))
            .frame(width: width, height: height)
            .opacity(dim ? 0.55 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.1).repeatForever(autoreverses: true)) { dim = true }
            }
    }
}

/// The fade from a header visual into the page: clear, then the background by 92%.
struct BackgroundFade: View {
    var body: some View {
        LinearGradient(stops: [.init(color: Color.bg.opacity(0), location: 0), .init(color: Color.bg.opacity(0.78), location: 0.45),
                               .init(color: Color.bg, location: 0.92)], startPoint: .top, endPoint: .bottom)
            .allowsHitTesting(false)
    }
}
