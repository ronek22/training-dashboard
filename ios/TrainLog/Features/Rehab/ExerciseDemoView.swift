import SwiftUI

/// The animated figure for one rehab exercise, "direction C (Coaching)" from the web's
/// docs/design/motion-study.html: a solid figure with the working muscle coloured by effort, the
/// target pose as a dashed ghost, an arrow along the moving joint's real path, and a countdown
/// with a tempo bar. Same engine and silhouette as frontend/src/components/ExerciseDemo.vue.
/// Reduce Motion shows the hardest pose as a still, without the ghost or the arrow.
struct ExerciseDemoView: View {
    let demo: ExerciseDemo
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var start = Date.now
    private let box: CGRect
    private let cues: [DemoCue]
    private let ghost: DemoBody

    init(demo: ExerciseDemo) {
        self.demo = demo
        box = ExerciseDemos.viewBox(demo, pad: 14)
        cues = ExerciseDemos.cues(demo)
        ghost = ExerciseDemos.peakFrame(demo).body
    }

    var body: some View {
        TimelineView(.animation(paused: reduceMotion)) { context in
            let seconds = context.date.timeIntervalSince(start)
            let animated = !reduceMotion
            let frame = animated ? ExerciseDemos.frame(demo, at: seconds) : ExerciseDemos.peakFrame(demo)
            let phase = ExerciseDemos.cueAt(demo, at: seconds)
            VStack(alignment: .leading, spacing: 10) {
                Canvas { context, size in
                    draw(frame, seconds: seconds, animated: animated, in: &context, size: size)
                }
                .aspectRatio(box.width / box.height, contentMode: .fit)
                .overlay(alignment: .topLeading) { if animated { tempo(phase) } }
                .overlay(alignment: .bottom) { if animated { tempoBar(phase) } }
                .background(Self.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                cueChips(active: animated ? phase.index : nil, progress: phase.progress)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(demo.title): \(cues.map(\.label).joined(separator: ", "))")
    }

    // MARK: Colour

    private static let surface = Color.card
    private static let surfaceRGB = RGB(0x12151C), bodyRGB = RGB(0xC9CFDA), tealRGB = RGB(0x2ED3B0)

    private func focused(_ id: String) -> Bool {
        demo.focus.contains(id) || (id == "seat" && demo.focus.contains { $0 == "hip" || $0 == "nearThigh" })
    }

    /// The working muscle shifts from the body colour to teal as the effort builds; the far side
    /// sinks into the background (except side-lying demos, seen from the front).
    private func colour(_ part: FigurePart, effort: Double) -> Color {
        let isFocused = focused(part.id)
        let tone = isFocused ? Self.tealRGB.mixed(with: Self.bodyRGB, 0.3 + 0.7 * effort) : Self.bodyRGB
        let far = part.layer == .far && !demo.solid
        return (far ? tone.mixed(with: Self.surfaceRGB, isFocused ? 0.45 : 0.34) : tone).color
    }

    // MARK: Drawing

    private func draw(_ frame: DemoFrame, seconds: Double, animated: Bool, in context: inout GraphicsContext, size: CGSize) {
        let scale = size.width / box.width
        context.scaleBy(x: scale, y: scale)
        context.translateBy(x: -box.minX, y: -box.minY)
        let floor = ExerciseDemos.floor
        let muted = Color.muted.opacity(0.22)

        // Floor, then the props as muted scenery.
        context.fill(Path(CGRect(x: box.minX, y: floor, width: box.width, height: 1.2)), with: .color(Color(red: 170 / 255, green: 184 / 255, blue: 210 / 255).opacity(0.2)))
        for prop in demo.props {
            var path = Path()
            switch prop {
            case let .rect(x, y, width, height, radius):
                path = Path(roundedRect: CGRect(x: x, y: y, width: width, height: height), cornerRadius: radius)
                context.fill(path, with: .color(muted))
            case let .line(x1, y1, x2, y2):
                path.move(to: CGPoint(x: x1, y: y1))
                path.addLine(to: CGPoint(x: x2, y: y2))
            }
            context.stroke(path, with: .color(muted), style: StrokeStyle(lineWidth: 3, lineCap: .round))
        }

        // The target pose as a dashed ghost.
        if animated {
            var outline = Path()
            for segment in ghost.segments {
                outline.move(to: segment.from)
                outline.addLine(to: segment.to)
            }
            let r = ExerciseDemos.headRadius
            outline.addEllipse(in: CGRect(x: ghost.head.x - r, y: ghost.head.y - r, width: r * 2, height: r * 2))
            context.stroke(outline, with: .color(Color.mobility.opacity(0.4)),
                           style: StrokeStyle(lineWidth: 1.1, lineCap: .round, dash: [2, 2.6]))
        }

        // A soft contact shadow: wider than the body, darker the closer the body is to the floor.
        let points = frame.body.segments.flatMap { [$0.from, $0.to] }
        let xs = points.map(\.x), lowest = points.map(\.y).max() ?? CGFloat(floor)
        let lo = xs.min() ?? 0, hi = xs.max() ?? 0
        let lift = max(0, floor - lowest)
        context.drawLayer { layer in
            layer.translateBy(x: (lo + hi) / 2, y: floor + 1)
            layer.scaleBy(x: (hi - lo) / 2 + 8, y: 4.2)
            layer.fill(Path(ellipseIn: CGRect(x: -1, y: -1, width: 2, height: 2)),
                       with: .radialGradient(Gradient(colors: [.black.opacity(max(0.22, 0.6 - lift / 60)), .black.opacity(0)]),
                                             center: .zero, startRadius: 0, endRadius: 1))
        }

        for part in FigureShapes.parts(frame.body) {
            let colour = colour(part, effort: frame.effort)
            switch part.kind {
            case let .head(center, radius):
                // A background-coloured ring so the neck reads as a gap.
                let ring = radius + 2.4
                context.fill(Path(ellipseIn: CGRect(x: center.x - ring, y: center.y - ring, width: ring * 2, height: ring * 2)), with: .color(Self.surface))
                context.fill(Path(ellipseIn: CGRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2)), with: .color(colour))
            case let .shoe(path):
                context.fill(path, with: .color(colour))
                context.stroke(path, with: .color(colour), style: StrokeStyle(lineWidth: 1.6, lineJoin: .round))
            case let .shape(path):
                context.fill(path, with: .color(colour))
            }
        }

        if animated, let path = ExerciseDemos.pathAt(demo, at: seconds) {
            let pts = path.points, tip = pts[pts.count - 1], from = pts[max(0, pts.count - 3)]
            let angle = atan2(tip.y - from.y, tip.x - from.x)
            let wing = { (side: Double) in
                CGPoint(x: tip.x + cos(angle + .pi + side * 0.61) * 5.5, y: tip.y + sin(angle + .pi + side * 0.61) * 5.5)
            }
            var arrow = Path()
            arrow.addLines(pts)
            arrow.addLines([wing(-1), tip, wing(1)])
            context.stroke(arrow, with: .color(Color.volt.opacity(path.opacity)), style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
        }
    }

    // MARK: Tempo

    private func tempo(_ phase: DemoCuePhase) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            if phase.length >= 1 {
                Text("\(phase.left)").font(AppFont.title(28)).foregroundStyle(Color.ink).monospacedDigit()
            }
            Text(phase.cue.label.uppercased())
                .font(AppFont.body(11, weight: .semibold)).tracking(1.1)
                .foregroundStyle(Color.mobility)
        }
        .padding(.top, 9)
        .padding(.leading, 12)
        .allowsHitTesting(false)
    }

    /// Finished cues full, the running one filling, the rest empty.
    private func tempoBar(_ phase: DemoCuePhase) -> some View {
        GeometryReader { proxy in
            let gaps = Double(cues.count - 1) * 3
            let total = cues.reduce(0) { $0 + $1.seconds }
            HStack(spacing: 3) {
                ForEach(Array(cues.enumerated()), id: \.offset) { index, cue in
                    let fill = index < phase.index ? 1 : index == phase.index ? phase.progress : 0
                    let width = (proxy.size.width - gaps) * cue.seconds / total
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.ink.opacity(0.1))
                        Capsule().fill(index == phase.index ? Color.mobility : Color.mobility.opacity(0.45))
                            .frame(width: width * fill)
                    }
                    .frame(width: width)
                }
            }
        }
        .frame(height: 3)
        .padding(.horizontal, 12)
        .padding(.bottom, 8)
        .allowsHitTesting(false)
    }

    // MARK: Cues

    private func cueChips(active: Int?, progress: Double) -> some View {
        FlowLayout(spacing: 6) {
            ForEach(Array(cues.enumerated()), id: \.offset) { index, cue in
                let isActive = index == active
                HStack(alignment: .firstTextBaseline, spacing: 5) {
                    Text(cue.label).font(AppFont.body(12, weight: .semibold))
                    Text(Self.secondsLabel(cue.seconds)).font(AppFont.body(11)).foregroundStyle(Color.muted).monospacedDigit()
                }
                .foregroundStyle(isActive ? Color.ink : Color.muted)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(isActive ? Color.mobility.opacity(0.12) : .clear)
                .clipShape(Capsule())
                .overlay(Capsule().strokeBorder(isActive ? Color.mobility.opacity(0.5) : Color.cardBorder))
            }
        }
    }

    private static func secondsLabel(_ value: Double) -> String {
        value.rounded() == value ? "\(Int(value))s" : String(format: "%.1fs", value)
    }
}

/// An sRGB colour that mixes like CSS `color-mix(in srgb, a p%, b)`.
private struct RGB {
    let r, g, b: Double
    init(_ hex: UInt32) { self.init(r: Double((hex >> 16) & 0xFF) / 255, g: Double((hex >> 8) & 0xFF) / 255, b: Double(hex & 0xFF) / 255) }
    init(r: Double, g: Double, b: Double) { self.r = r; self.g = g; self.b = b }
    /// `share` of self, the rest of `other`.
    func mixed(with other: RGB, _ share: Double) -> RGB {
        RGB(r: r * share + other.r * (1 - share), g: g * share + other.g * (1 - share), b: b * share + other.b * (1 - share))
    }
    var color: Color { Color(.sRGB, red: r, green: g, blue: b) }
}

// MARK: - Silhouette

struct FigurePart {
    enum Kind {
        case shape(Path)
        /// Drawn with a rounded outline too.
        case shoe(Path)
        /// Drawn with a background-coloured ring so the neck reads as a gap.
        case head(CGPoint, Double)
    }
    let id: String
    let layer: DemoSegment.Layer
    let kind: Kind
}

/// Filled shapes for the figure, a port of frontend/src/figure/figure-shapes.mjs: limbs that taper
/// from the body out, a trunk with a waist and a chest, a seat that belongs to the near leg, shoes
/// with a heel, fists, and a small head on a short neck.
enum FigureShapes {
    private static func unit(_ a: CGPoint, _ b: CGPoint) -> CGPoint {
        let l = hypot(b.x - a.x, b.y - a.y)
        return l == 0 ? CGPoint(x: b.x - a.x, y: b.y - a.y) : CGPoint(x: (b.x - a.x) / l, y: (b.y - a.y) / l)
    }
    private static func lerp(_ a: CGPoint, _ b: CGPoint, _ t: Double) -> CGPoint { CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t) }
    private static func at(_ origin: CGPoint, _ a: CGPoint, _ ka: Double, _ b: CGPoint = .zero, _ kb: Double = 0) -> CGPoint {
        CGPoint(x: origin.x + a.x * ka + b.x * kb, y: origin.y + a.y * ka + b.y * kb)
    }
    private static func dot(_ a: CGPoint, _ b: CGPoint) -> Double { a.x * b.x + a.y * b.y }

    /// A tapered capsule from a (width wa) to b (width wb): two circles joined by their outer
    /// tangents. Clockwise, so overlapping parts of one path fill instead of cutting holes.
    static func capsule(_ path: inout Path, _ a: CGPoint, _ b: CGPoint, _ wa: Double, _ wb: Double) {
        let ra = wa / 2, rb = wb / 2, length = max(0.001, hypot(b.x - a.x, b.y - a.y))
        let angle = atan2(b.y - a.y, b.x - a.x), s = asin(max(-1, min(1, (ra - rb) / length)))
        let on = { (c: CGPoint, r: Double, t: Double) in CGPoint(x: c.x + cos(t) * r, y: c.y + sin(t) * r) }
        path.move(to: on(a, ra, angle + .pi / 2 + s))
        path.addRelativeArc(center: a, radius: ra, startAngle: .radians(angle + .pi / 2 + s), delta: .radians(.pi - 2 * s))
        path.addLine(to: on(b, rb, angle - .pi / 2 - s))
        path.addRelativeArc(center: b, radius: rb, startAngle: .radians(angle - .pi / 2 - s), delta: .radians(.pi + 2 * s))
        path.closeSubpath()
    }

    static func circle(_ path: inout Path, _ c: CGPoint, _ r: Double) {
        path.move(to: CGPoint(x: c.x - r, y: c.y))
        path.addRelativeArc(center: c, radius: r, startAngle: .radians(.pi), delta: .radians(2 * .pi))
        path.closeSubpath()
    }

    /// A side-view shoe: the ankle sits over the rear third, a rounded heel, a sole tapering to the
    /// toe and an instep sloping back up to the ankle. The sole faces away from the knee.
    static func shoe(_ ankle: CGPoint, _ toeDir: CGPoint, _ knee: CGPoint) -> Path {
        let height = 3.0, length = 8.5, back = 3.0
        let d = unit(.zero, toeDir)
        var normal = CGPoint(x: -d.y, y: d.x)
        if dot(CGPoint(x: ankle.x - knee.x, y: ankle.y - knee.y), normal) < 0 { normal = CGPoint(x: -normal.x, y: -normal.y) }
        let sole = at(ankle, normal, height)
        let p = { (along: Double, off: Double) in at(sole, d, along, normal, off) }
        var path = Path()
        path.addLines([p(-1.8, -height * 1.05), p(-back + 0.3, -height * 0.5), p(-back, 0), p(length - 1.4, 0),
                       p(length, -1.2), p(length * 0.5, -height * 0.6), p(1.8, -height * 1.05)])
        path.closeSubpath()
        return path
    }

    /// The trunk narrows at the waist; bend > 0 rounds the back (flexion), < 0 lifts the chest.
    private static func trunk(_ path: inout Path, _ hip: CGPoint, _ shoulder: CGPoint, _ bend: Double) {
        let u = unit(hip, shoulder), back = CGPoint(x: u.y, y: -u.x)
        let waist = at(lerp(hip, shoulder, 0.45), back, bend * 0.7), chest = at(lerp(hip, shoulder, 0.76), back, bend)
        capsule(&path, hip, waist, 8.4, 7.6)
        capsule(&path, waist, chest, 7.6, 10)
        capsule(&path, chest, shoulder, 10, 7.6)
    }

    /// The seat belongs to the near leg: one shape that leaves the back just above the hip, rounds
    /// out over the buttock and runs into the back of the thigh.
    static func seat(_ hip: CGPoint, _ shoulder: CGPoint, _ knee: CGPoint, _ ankle: CGPoint) -> Path {
        let u = unit(hip, shoulder), back = CGPoint(x: u.y, y: -u.x), td = unit(hip, knee)
        var tb = CGPoint(x: -td.y, y: td.x)
        let toShin = dot(CGPoint(x: ankle.x - knee.x, y: ankle.y - knee.y), tb), toBack = dot(back, tb)
        if (abs(toShin) > 3 ? toShin : toBack) < 0 { tb = CGPoint(x: -tb.x, y: -tb.y) } // the hamstring side
        let top = at(hip, u, 3.5, back, 4.1), fold = at(hip, td, 9, tb, 3.8)
        var path = Path()
        path.move(to: at(hip, u, 3.5))
        path.addLine(to: top)
        path.addCurve(to: fold, control1: at(top, u, -3, back, 2.4), control2: at(fold, td, -5, tb, 2.4))
        path.addLine(to: at(hip, td, 9))
        path.closeSubpath()
        return path
    }

    /// Parts in draw order, each keeping its segment's id and layer so the caller can colour it.
    static func parts(_ body: DemoBody) -> [FigurePart] {
        var parts: [FigurePart] = []
        for segment in body.segments {
            let kind = segment.id.replacingOccurrences(of: #"^(near|far)"#, with: "", options: .regularExpression)
            var path = Path()
            switch kind {
            case "torso":
                trunk(&path, segment.from, segment.to, body.bend)
                capsule(&path, segment.to, body.head, 3.6, 3.2)
                parts.append(FigurePart(id: segment.id, layer: segment.layer, kind: .shape(path)))
                parts.append(FigurePart(id: "head", layer: segment.layer, kind: .head(body.head, ExerciseDemos.headRadius)))
                continue
            case "Thigh":
                if segment.id == "nearThigh", body.seat, let torso = body.segment("torso"), let shin = body.segment("nearShin") {
                    parts.append(FigurePart(id: "seat", layer: segment.layer, kind: .shape(seat(segment.from, torso.to, segment.to, shin.to))))
                }
                capsule(&path, segment.from, segment.to, 8.6, 5.4)
            case "Shin":
                let calf = lerp(segment.from, segment.to, 0.3)
                capsule(&path, segment.from, calf, 5.4, 6)
                capsule(&path, calf, segment.to, 6, 3.2)
            case "Foot":
                let knee = body.segment(segment.id.replacingOccurrences(of: "Foot", with: "Shin"))?.from ?? segment.from
                let toeDir = CGPoint(x: segment.to.x - segment.from.x, y: segment.to.y - segment.from.y)
                parts.append(FigurePart(id: segment.id, layer: segment.layer, kind: .shoe(shoe(segment.from, toeDir, knee))))
                continue
            case "UpperArm":
                capsule(&path, segment.from, segment.to, 5, 3.8)
            case "Forearm":
                capsule(&path, segment.from, segment.to, 3.8, 2.8)
                circle(&path, segment.to, 2.4)
            default:
                continue
            }
            parts.append(FigurePart(id: segment.id, layer: segment.layer, kind: .shape(path)))
        }
        return parts
    }
}

#Preview {
    ScrollView {
        VStack(spacing: 16) {
            ForEach(ExerciseDemos.all.prefix(6), id: \.key) { demo in
                ExerciseDemoView(demo: demo)
            }
        }
        .padding(16)
    }
    .background(Color.bg)
}
