import SwiftUI

/// Front or back body with muscles lit by role: the web's `MuscleSilhouette` on the phone.
/// `gap` muscles get an amber dashed outline (a muscle the workout is missing).
struct MuscleSilhouette: View {
    enum Side { case front, back }

    let side: Side
    var primary: Set<Muscle> = []
    var secondary: Set<Muscle> = []
    var gap: Set<Muscle> = []
    /// Outline between regions; matches whatever the figure sits on.
    var background: Color = .card

    static let primaryFill = Color(hex: 0xF2588F)
    static let secondaryFill = Color(hex: 0x8C5674)
    private static let restFill = Color(hex: 0x343B4A)
    private static let bodyFill = Color(hex: 0x1A1E27)
    /// The artwork's crop inside the web's 240 × 460 viewBox.
    private static let crop = CGRect(x: 14, y: 4, width: 212, height: 448)
    private static let bodyPath = SVGPath.parse(SilhouettePaths.body)
    private static let frontPaths = SilhouettePaths.front.map { ($0.muscle, SVGPath.parse($0.path)) }
    private static let backPaths = SilhouettePaths.back.map { ($0.muscle, SVGPath.parse($0.path)) }

    var body: some View {
        Canvas { context, size in
            let scale = min(size.width / Self.crop.width, size.height / Self.crop.height)
            let dx = (size.width - Self.crop.width * scale) / 2 - Self.crop.minX * scale
            let dy = (size.height - Self.crop.height * scale) / 2 - Self.crop.minY * scale
            let place = CGAffineTransform(a: scale, b: 0, c: 0, d: scale, tx: dx, ty: dy)
            let mirror = CGAffineTransform(a: -1, b: 0, c: 0, d: 1, tx: 240, ty: 0).concatenating(place)
            let line = max(0.8, 2 * scale)

            context.fill(Self.bodyPath.applying(place), with: .color(Self.bodyFill))
            for (muscle, path) in side == .front ? Self.frontPaths : Self.backPaths {
                for transform in [place, mirror] {
                    let shape = path.applying(transform)
                    if let muscle, gap.contains(muscle) {
                        context.fill(shape, with: .color(Color.warning.opacity(0.14)))
                        context.stroke(shape, with: .color(.warning), style: StrokeStyle(lineWidth: line * 1.2, lineJoin: .round, dash: [line * 3, line * 2]))
                    } else {
                        context.fill(shape, with: .color(fill(muscle)))
                        context.stroke(shape, with: .color(background), style: StrokeStyle(lineWidth: line, lineJoin: .round))
                    }
                }
            }
        }
        .aspectRatio(Self.crop.width / Self.crop.height, contentMode: .fit)
        .accessibilityElement()
        .accessibilityLabel(accessibilityText)
    }

    private func fill(_ muscle: Muscle?) -> Color {
        guard let muscle else { return Self.restFill }
        if primary.contains(muscle) { return Self.primaryFill }
        if secondary.contains(muscle) { return Self.secondaryFill }
        return Self.restFill
    }

    private var accessibilityText: String {
        let names = primary.map(\.label).sorted()
        let view = side == .front ? "Front" : "Back"
        return names.isEmpty ? "\(view) body" : "\(view) body, works \(names.joined(separator: ", "))"
    }
}

/// Front and back side by side.
struct MusclePair: View {
    let summary: MuscleSummary
    var gap: Set<Muscle> = []
    var background: Color = .card

    var body: some View {
        HStack(spacing: 4) {
            MuscleSilhouette(side: .front, primary: summary.primary, secondary: summary.secondary, gap: gap, background: background)
            MuscleSilhouette(side: .back, primary: summary.primary, secondary: summary.secondary, gap: gap, background: background)
        }
    }
}

extension MuscleSummary {
    /// The side that shows more of the workout's main muscles: thumbnails show only one.
    var bestSide: MuscleSilhouette.Side {
        let front = Set(SilhouettePaths.front.compactMap(\.muscle))
        let back = Set(SilhouettePaths.back.compactMap(\.muscle))
        func weight(_ side: Set<Muscle>) -> Int {
            counts.filter { side.contains($0.muscle) }.reduce(0) { $0 + $1.primary * 2 + $1.secondary }
        }
        return weight(back) > weight(front) ? .back : .front
    }
}

/// Absolute M / L / Q / C / Z path data, which is all the silhouette uses.
enum SVGPath {
    static func parse(_ data: String) -> Path {
        var path = Path()
        let scanner = Scanner(string: data)
        scanner.charactersToBeSkipped = CharacterSet(charactersIn: " ,\n\t")
        var command: Character = "M"
        func number() -> CGFloat? { scanner.scanDouble().map { CGFloat($0) } }
        func point() -> CGPoint? {
            guard let x = number(), let y = number() else { return nil }
            return CGPoint(x: x, y: y)
        }
        while !scanner.isAtEnd {
            if let letter = scanner.scanCharacter(), letter.isLetter {
                command = letter
                if letter == "Z" || letter == "z" {
                    path.closeSubpath()
                    continue
                }
            } else {
                // A repeated command without its letter: step back over the number.
                scanner.currentIndex = data.index(before: scanner.currentIndex)
            }
            switch command {
            case "M":
                guard let p = point() else { return path }
                path.move(to: p)
                command = "L"
            case "L":
                guard let p = point() else { return path }
                path.addLine(to: p)
            case "Q":
                guard let c = point(), let p = point() else { return path }
                path.addQuadCurve(to: p, control: c)
            case "C":
                guard let c1 = point(), let c2 = point(), let p = point() else { return path }
                path.addCurve(to: p, control1: c1, control2: c2)
            default:
                return path
            }
        }
        return path
    }
}
