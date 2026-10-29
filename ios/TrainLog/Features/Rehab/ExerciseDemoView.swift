import SwiftUI

/// The animated figure for one rehab exercise. Same poses and timing as the web demo, drawn with
/// more care: tapered limbs with rounded joints, the working muscle glowing with the effort, a
/// floor shadow that follows the body, and cue chips that fill while their phase runs.
/// Reduce Motion shows the hardest pose as a still.
struct ExerciseDemoView: View {
    let demo: ExerciseDemo
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var start = Date.now
    private let box: CGRect
    private let movers: [String]
    private let cues: [DemoCue]

    init(demo: ExerciseDemo) {
        self.demo = demo
        // A little more room than the web's frame, for the motion arrows.
        box = ExerciseDemos.viewBox(demo, pad: 16)
        movers = ExerciseDemos.movers(demo)
        cues = ExerciseDemos.cues(demo)
    }

    var body: some View {
        TimelineView(.animation(paused: reduceMotion)) { context in
            let seconds = context.date.timeIntervalSince(start)
            let frame = reduceMotion
                ? DemoFrame(pose: ExerciseDemos.peakPose(demo), effort: 1, step: -1)
                : ExerciseDemos.frame(demo, at: seconds)
            VStack(alignment: .leading, spacing: 10) {
                Canvas { context, size in
                    draw(frame, seconds: seconds, in: &context, size: size)
                }
                .aspectRatio(box.width / box.height, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.cardBorder))
                if !reduceMotion {
                    cueChips(step: frame.step, seconds: seconds)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(demo.title): \(cues.map(\.label).joined(separator: ", "))")
    }

    // MARK: Drawing

    /// Start and end widths of each bone, in demo units: thick at the body, thin at the tips.
    private static let widths: [String: (Double, Double)] = [
        "torso": (8.6, 7.2), "Thigh": (6.4, 5), "Shin": (5, 3.8), "Foot": (3.6, 2.8),
        "UpperArm": (4.4, 3.6), "Forearm": (3.6, 2.8),
    ]

    private func width(_ id: String) -> (Double, Double) {
        if id == "torso" { return Self.widths["torso"]! }
        return Self.widths.first { id.hasSuffix($0.key) }?.value ?? (6, 6)
    }

    private func draw(_ frame: DemoFrame, seconds: Double, in context: inout GraphicsContext, size: CGSize) {
        let scale = size.width / box.width
        context.scaleBy(x: scale, y: scale)
        context.translateBy(x: -box.minX, y: -box.minY)
        let skeleton = ExerciseDemos.skeleton(frame.pose)
        let muted = Color.muted.opacity(0.22)

        // Floor, then the props as muted scenery.
        context.fill(Path(CGRect(x: box.minX, y: ExerciseDemos.floor, width: box.width, height: 1.5)), with: .color(.outline))
        for prop in demo.props {
            switch prop {
            case let .rect(x, y, width, height, radius):
                context.fill(Path(roundedRect: CGRect(x: x, y: y, width: width, height: height), cornerRadius: radius), with: .color(muted))
            case let .line(x1, y1, x2, y2):
                var path = Path()
                path.move(to: CGPoint(x: x1, y: y1))
                path.addLine(to: CGPoint(x: x2, y: y2))
                context.stroke(path, with: .color(muted), style: StrokeStyle(lineWidth: 3, lineCap: .round))
            }
        }

        // A soft contact shadow under the body: wider and darker the closer it is to the floor.
        let lowest = skeleton.segments.map { max($0.from.y, $0.to.y) }.max() ?? ExerciseDemos.floor
        let xs = skeleton.segments.flatMap { [$0.from.x, $0.to.x] }
        let spread = (xs.max() ?? 0) - (xs.min() ?? 0)
        let lift = max(0, ExerciseDemos.floor - lowest)
        context.drawLayer { layer in
            layer.addFilter(.blur(radius: 3))
            let width = spread + 10
            layer.fill(
                Path(ellipseIn: CGRect(x: (xs.min() ?? 0) - 5, y: ExerciseDemos.floor - 2, width: width, height: 5)),
                with: .color(.black.opacity(max(0.15, 0.55 - lift / 60)))
            )
        }

        // The working muscle glows, brighter at the hard part of the move.
        let glow = 0.12 + 0.45 * frame.effort
        context.drawLayer { layer in
            layer.addFilter(.blur(radius: 4))
            for segment in skeleton.segments where demo.focus.contains(segment.id) {
                let (from, to) = width(segment.id)
                layer.fill(bone(segment.from, segment.to, from + 6, to + 6), with: .color(Color.mobility.opacity(glow)))
            }
            if demo.focus.contains("hip") {
                layer.fill(Path(ellipseIn: CGRect(x: skeleton.hip.x - 8, y: skeleton.hip.y - 8, width: 16, height: 16)),
                           with: .color(Color.mobility.opacity(glow)))
            }
        }

        for segment in skeleton.segments {
            let far = segment.layer == .far && !demo.solid
            let focused = demo.focus.contains(segment.id)
            let base: Color = focused ? .mobility : .ink
            let (from, to) = width(segment.id)
            context.fill(bone(segment.from, segment.to, from, to), with: .color(far ? base.opacity(focused ? 0.5 : 0.32) : base))
        }
        // Head, a touch smaller than the web's and with a neck gap so it reads as separate.
        let radius = ExerciseDemos.headRadius - 1
        let headRect = CGRect(x: skeleton.head.x - radius, y: skeleton.head.y - radius, width: radius * 2, height: radius * 2)
        context.fill(Path(ellipseIn: headRect.insetBy(dx: -1.5, dy: -1.5)), with: .color(.inset))
        context.fill(Path(ellipseIn: headRect), with: .color(.ink))

        if !reduceMotion {
            for arrow in ExerciseDemos.arrows(demo, movers: movers, at: seconds) {
                var path = Path()
                for line in arrow.lines {
                    path.move(to: line[0])
                    line.dropFirst().forEach { path.addLine(to: $0) }
                }
                context.stroke(path, with: .color(Color.volt.opacity(arrow.opacity)),
                               style: StrokeStyle(lineWidth: 2.6, lineCap: .round, lineJoin: .round))
            }
        }
    }

    /// A tapered capsule from `a` (width `wa`) to `b` (width `wb`), so joints are round.
    private func bone(_ a: CGPoint, _ b: CGPoint, _ wa: Double, _ wb: Double) -> Path {
        let ra = wa / 2, rb = wb / 2
        let dx = b.x - a.x, dy = b.y - a.y
        let length = max(0.001, hypot(dx, dy))
        let nx = -dy / length, ny = dx / length
        var side = Path()
        side.move(to: CGPoint(x: a.x + nx * ra, y: a.y + ny * ra))
        side.addLine(to: CGPoint(x: b.x + nx * rb, y: b.y + ny * rb))
        side.addLine(to: CGPoint(x: b.x - nx * rb, y: b.y - ny * rb))
        side.addLine(to: CGPoint(x: a.x - nx * ra, y: a.y - ny * ra))
        side.closeSubpath()
        // A union, not one path of subpaths: opposite windings would punch holes at the joints.
        return side
            .union(Path(ellipseIn: CGRect(x: a.x - ra, y: a.y - ra, width: wa, height: wa)))
            .union(Path(ellipseIn: CGRect(x: b.x - rb, y: b.y - rb, width: wb, height: wb)))
    }

    // MARK: Cues

    private func cueChips(step: Int, seconds: Double) -> some View {
        FlowLayout(spacing: 6) {
            ForEach(Array(cues.enumerated()), id: \.offset) { _, cue in
                let active = cue.steps.contains(step)
                HStack(alignment: .firstTextBaseline, spacing: 5) {
                    Text(cue.label).font(AppFont.body(12, weight: .semibold))
                    Text(Self.secondsLabel(cue.seconds)).font(AppFont.body(11)).foregroundStyle(Color.muted).monospacedDigit()
                }
                .foregroundStyle(active ? Color.ink : Color.muted)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(alignment: .leading) {
                    // The active chip fills left to right over its phase.
                    GeometryReader { proxy in
                        Color.mobility.opacity(0.18)
                            .frame(width: active ? proxy.size.width * progress(of: cue, at: seconds) : 0)
                    }
                }
                .clipShape(Capsule())
                .overlay(Capsule().strokeBorder(active ? Color.mobility.opacity(0.5) : Color.cardBorder))
            }
        }
    }

    private static func secondsLabel(_ value: Double) -> String {
        value.rounded() == value ? "\(Int(value))s" : String(format: "%.1fs", value)
    }

    /// How far into this cue's steps the loop is, 0–1.
    private func progress(of cue: DemoCue, at seconds: Double) -> Double {
        let total = ExerciseDemos.cycleLength(demo)
        let time = (seconds.truncatingRemainder(dividingBy: total) + total).truncatingRemainder(dividingBy: total)
        let starts = demo.steps.indices.map { index in demo.steps[..<index].reduce(0) { $0 + $1.seconds } }
        guard let first = cue.steps.first else { return 0 }
        return min(1, max(0, (time - starts[first]) / cue.seconds))
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
