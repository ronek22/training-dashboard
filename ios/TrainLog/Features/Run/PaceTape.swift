import SwiftUI

/// The run screens' one visual: a fine tape of paces (a tick every 2 s) with the easy zone in
/// orange. With `numbers`, the band's edges stand over the zone joined by hairlines; with a
/// `marker`, a run's average pace stands on it as a white needle.
struct PaceTape: View {
    let band: RunningFitness.Band
    var range: ClosedRange<Int>?
    /// Point size of the band's edge numbers; nil hides them.
    var numbers: CGFloat? = 50
    /// A run's average pace, drawn as a needle with its value over it.
    var marker: Int?
    /// Off the left edge, e.g. "‹ 2015 · 4:32".
    var leftNote: String?
    /// Small orange labels at the zone's edges (when the big numbers are off).
    var edgeLabels = false

    private var span: ClosedRange<Int> { range ?? RunFormat.tapeRange(band) }

    private var zoneTop: CGFloat {
        if let numbers { return numbers + 46 }
        return marker != nil ? 74 : 22
    }

    private var height: CGFloat { zoneTop + 24 + 26 }

    var body: some View {
        Canvas { context, size in
            draw(in: &context, width: size.width)
        }
        .frame(height: height)
        .accessibilityElement()
        .accessibilityLabel(accessibilityText)
    }

    private var accessibilityText: String {
        var text = "Easy pace \(RunFormat.pace(band.fromS)) to \(RunFormat.pace(band.toS)) per kilometre"
        if let marker { text = "Your pace \(RunFormat.pace(marker)). " + text }
        return text
    }

    private func draw(in context: inout GraphicsContext, width: CGFloat) {
        let low = span.lowerBound, high = span.upperBound
        let x = { (value: Int) -> CGFloat in CGFloat(value - low) / CGFloat(high - low) * width }
        let z0 = x(band.fromS), z1 = x(band.toS)
        let top = zoneTop
        let base = top + 24

        if let size = numbers {
            context.draw(Text(RunFormat.pace(band.fromS)).font(AppFont.number(size)).foregroundStyle(Color.ink),
                         at: CGPoint(x: z0, y: size), anchor: .bottomLeading)
            context.draw(Text(RunFormat.pace(band.toS)).font(AppFont.number(size)).foregroundStyle(Color.ink),
                         at: CGPoint(x: z1, y: size), anchor: .bottomTrailing)
            context.draw(Text("–").font(AppFont.number(size * 0.6)).foregroundStyle(Color.dim),
                         at: CGPoint(x: (z0 + z1) / 2, y: size * 0.84), anchor: .bottom)
            context.draw(Text("MIN / KM").font(AppFont.body(11, weight: .semibold)).tracking(1.5).foregroundStyle(Color.muted),
                         at: CGPoint(x: (z0 + z1) / 2, y: size + 22), anchor: .bottom)
            for edge in [z0, z1] {
                var line = Path()
                line.move(to: CGPoint(x: edge, y: size + 9))
                line.addLine(to: CGPoint(x: edge, y: top))
                context.stroke(line, with: .color(Color.run.opacity(0.5)), lineWidth: 1)
            }
        }

        context.fill(Path(roundedRect: CGRect(x: z0, y: top, width: z1 - z0, height: 28), cornerRadius: 6),
                     with: .color(Color.run.opacity(0.10)))

        for value in stride(from: low, through: high, by: 2) {
            let inZone = (band.fromS...band.toS).contains(value)
            var length: CGFloat = value % 30 == 0 ? 16 : (value % 10 == 0 ? 11 : 6)
            if inZone { length += 5 }
            var tick = Path()
            tick.move(to: CGPoint(x: x(value), y: base - length))
            tick.addLine(to: CGPoint(x: x(value), y: base))
            context.stroke(tick, with: .color(inZone ? Color.run : Color.tick),
                           style: StrokeStyle(lineWidth: value % 10 == 0 ? 1.6 : 1, lineCap: .round))
        }

        if edgeLabels {
            for (edge, value) in [(z0, band.fromS), (z1, band.toS)] {
                context.draw(Text(RunFormat.pace(value)).font(AppFont.body(10, weight: .bold)).foregroundStyle(Color.run),
                             at: CGPoint(x: edge, y: top - 4), anchor: .bottom)
            }
        }

        if let marker {
            let mx = min(max(x(marker), 0), width)
            var needle = Path()
            needle.move(to: CGPoint(x: mx, y: top - 34))
            needle.addLine(to: CGPoint(x: mx, y: base + 2))
            context.stroke(needle, with: .color(Color.ink), style: StrokeStyle(lineWidth: 2, lineCap: .round))
            context.fill(Path(ellipseIn: CGRect(x: mx - 4, y: base - 2, width: 8, height: 8)), with: .color(Color.ink))
            context.draw(Text(RunFormat.pace(marker)).font(AppFont.number(34)).foregroundStyle(Color.ink),
                         at: CGPoint(x: mx, y: top - 36), anchor: .bottom)
        }

        // Half-minute marks under the tape; the left one gives way to the note.
        let labelY = base + 8
        for value in stride(from: (low + 29) / 30 * 30, through: high, by: 30) {
            let px = x(value)
            if leftNote != nil, px < 90 { continue }
            let anchor: UnitPoint = px > width - 14 ? .topTrailing : (px < 14 ? .topLeading : .top)
            context.draw(Text(RunFormat.pace(value)).font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.subtle),
                         at: CGPoint(x: px, y: labelY), anchor: anchor)
        }
        if let leftNote {
            context.draw(Text(leftNote).font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.muted),
                         at: CGPoint(x: 0, y: labelY), anchor: .topLeading)
        }
    }
}

#Preview {
    VStack(spacing: 30) {
        PaceTape(band: .init(fromS: 364, toS: 408), range: 350...420, leftNote: "‹ 2015 · 4:32")
        PaceTape(band: .init(fromS: 364, toS: 408), range: 350...420, numbers: nil, marker: 371, edgeLabels: true)
    }
    .padding()
    .background(Color.bg)
}
