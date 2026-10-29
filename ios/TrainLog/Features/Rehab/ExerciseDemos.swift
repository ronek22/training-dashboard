import CoreGraphics
import Foundation

// Animated stick-figure demos for rehab exercises, matched by exercise name. A port of the web's
// frontend/src/recovery/exercise-demos.mjs; keep the two in step. Poses are drawn in a 240-wide
// frame with the floor at y=120. Legs and arms are solved with two-bone IK so limbs keep their
// length while the pose moves; a limb can instead give an explicit knee/elbow for out-of-plane
// moves (clamshell).

struct DemoLimb: Sendable {
    var foot: CGPoint?
    var hand: CGPoint?
    var handRel: CGPoint?
    var knee: CGPoint?
    var elbow: CGPoint?
    var toe: Double?
    var bend: Double?
}

struct DemoPose: Sendable {
    var hip: CGPoint
    var shoulder: CGPoint?
    var torso: Double?
    var head: Double?
    var near = DemoLimb()
    var far = DemoLimb()
    var nearArm = DemoLimb()
    var farArm = DemoLimb()

    func with(_ change: (inout DemoPose) -> Void) -> DemoPose {
        var copy = self
        change(&copy)
        return copy
    }
}

enum DemoProp: Sendable {
    case rect(x: Double, y: Double, width: Double, height: Double, radius: Double)
    case line(x1: Double, y1: Double, x2: Double, y2: Double)
}

struct ExerciseDemo: Sendable {
    struct Step: Sendable {
        let pose: String
        let seconds: Double
        let label: String
    }

    let key: String
    let title: String
    /// Case-insensitive regex tried against the exercise name.
    let match: String
    var props: [DemoProp] = []
    let focus: [String]
    var solid = false
    let poses: [String: DemoPose]
    var effort: [String: Double] = [:]
    /// Isometric holds: an arrow pressing on this joint while the effort is high.
    var press: (at: String, angle: Double)?
    var movers = 1
    let steps: [Step]
}

struct DemoSegment: Sendable {
    enum Layer: Sendable { case far, body, near }
    let id: String
    let from: CGPoint
    let to: CGPoint
    let layer: Layer
}

struct DemoSkeleton: Sendable {
    let segments: [DemoSegment]
    let head: CGPoint
    let hip: CGPoint
    let joints: [String: CGPoint]
}

struct DemoFrame: Sendable {
    let pose: DemoPose
    let effort: Double
    let step: Int
}

struct DemoCue: Equatable, Sendable {
    let label: String
    var seconds: Double
    var steps: [Int]
}

enum ExerciseDemos {
    static let floor = 120.0
    static let headRadius = 8.0
    private static let torsoLength = 38.0, thigh = 27.0, shin = 26.0, footLength = 9.0
    private static let upperArm = 19.0, forearm = 18.0, neck = 12.0

    static func demo(for name: String?) -> ExerciseDemo? {
        guard let name else { return nil }
        return all.first { name.range(of: $0.match, options: [.regularExpression, .caseInsensitive]) != nil }
    }

    // MARK: Geometry

    private static func rad(_ deg: Double) -> Double { deg * .pi / 180 }
    private static func dir(_ deg: Double, _ length: Double) -> CGPoint { CGPoint(x: cos(rad(deg)) * length, y: sin(rad(deg)) * length) }
    private static func add(_ a: CGPoint, _ b: CGPoint) -> CGPoint { CGPoint(x: a.x + b.x, y: a.y + b.y) }
    private static func lerp(_ a: Double, _ b: Double, _ t: Double) -> Double { a + (b - a) * t }
    private static func lerp(_ a: CGPoint, _ b: CGPoint, _ t: Double) -> CGPoint { CGPoint(x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t)) }
    private static func lerpAngle(_ a: Double, _ b: Double, _ t: Double) -> Double {
        let diff = ((b - a).truncatingRemainder(dividingBy: 360) + 540).truncatingRemainder(dividingBy: 360) - 180
        return a + diff * t
    }

    /// Joint between root and target with fixed bone lengths; bend picks the side.
    private static func solveLimb(_ root: CGPoint, _ target: CGPoint, _ upper: Double, _ lower: Double, _ bend: Double) -> (CGPoint, CGPoint) {
        let dx = target.x - root.x, dy = target.y - root.y
        let dist = max(0.01, min(hypot(dx, dy), upper + lower - 0.01))
        let cosine = (upper * upper + dist * dist - lower * lower) / (2 * upper * dist)
        let angle = atan2(dy, dx) + bend * acos(max(-1, min(1, cosine)))
        let joint = CGPoint(x: root.x + cos(angle) * upper, y: root.y + sin(angle) * upper)
        let endAngle = atan2(target.y - joint.y, target.x - joint.x)
        return (joint, CGPoint(x: joint.x + cos(endAngle) * lower, y: joint.y + sin(endAngle) * lower))
    }

    private static func torsoAngle(_ pose: DemoPose) -> Double {
        if let shoulder = pose.shoulder { return atan2(shoulder.y - pose.hip.y, shoulder.x - pose.hip.x) * 180 / .pi }
        return pose.torso ?? -90
    }

    private static func mix(_ a: CGPoint?, _ b: CGPoint?, _ t: Double) -> CGPoint? {
        guard let start = a ?? b, let end = b ?? a else { return nil }
        return lerp(start, end, t)
    }

    private static func mixLimb(_ a: DemoLimb, _ b: DemoLimb, _ t: Double) -> DemoLimb {
        var limb = DemoLimb(bend: a.bend ?? b.bend)
        limb.foot = mix(a.foot, b.foot, t)
        limb.hand = mix(a.hand, b.hand, t)
        limb.handRel = mix(a.handRel, b.handRel, t)
        limb.knee = mix(a.knee, b.knee, t)
        limb.elbow = mix(a.elbow, b.elbow, t)
        if let start = a.toe ?? b.toe, let end = b.toe ?? a.toe { limb.toe = lerpAngle(start, end, t) }
        return limb
    }

    static func mixPose(_ a: DemoPose, _ b: DemoPose, _ t: Double) -> DemoPose {
        DemoPose(
            hip: lerp(a.hip, b.hip, t),
            torso: lerpAngle(torsoAngle(a), torsoAngle(b), t),
            head: lerpAngle(a.head ?? torsoAngle(a), b.head ?? torsoAngle(b), t),
            near: mixLimb(a.near, b.near, t), far: mixLimb(a.far, b.far, t),
            nearArm: mixLimb(a.nearArm, b.nearArm, t), farArm: mixLimb(a.farArm, b.farArm, t)
        )
    }

    /// Segments in draw order (far side first) plus the head and hip.
    static func skeleton(_ pose: DemoPose) -> DemoSkeleton {
        let torso = torsoAngle(pose)
        let hip = pose.hip
        let shoulder = add(hip, dir(torso, torsoLength))
        let head = add(shoulder, dir(pose.head ?? torso, neck))
        func leg(_ side: String, _ spec: DemoLimb, _ layer: DemoSegment.Layer) -> [DemoSegment] {
            let foot = spec.foot ?? add(hip, CGPoint(x: 0, y: thigh + shin))
            let (knee, ankle) = spec.knee.map { ($0, foot) } ?? solveLimb(hip, foot, thigh, shin, spec.bend ?? -1)
            let toe = add(ankle, dir(spec.toe ?? 10, footLength))
            return [.init(id: "\(side)Thigh", from: hip, to: knee, layer: layer),
                    .init(id: "\(side)Shin", from: knee, to: ankle, layer: layer),
                    .init(id: "\(side)Foot", from: ankle, to: toe, layer: layer)]
        }
        func arm(_ side: String, _ spec: DemoLimb, _ layer: DemoSegment.Layer) -> [DemoSegment] {
            let hand = spec.hand ?? add(shoulder, spec.handRel ?? CGPoint(x: 3, y: upperArm + forearm))
            let (elbow, wrist) = spec.elbow.map { ($0, hand) } ?? solveLimb(shoulder, hand, upperArm, forearm, spec.bend ?? 1)
            return [.init(id: "\(side)UpperArm", from: shoulder, to: elbow, layer: layer),
                    .init(id: "\(side)Forearm", from: elbow, to: wrist, layer: layer)]
        }
        let segments = arm("far", pose.farArm, .far) + leg("far", pose.far, .far)
            + [DemoSegment(id: "torso", from: hip, to: shoulder, layer: .body)]
            + leg("near", pose.near, .near) + arm("near", pose.nearArm, .near)
        let end = { (id: String) in segments.first { $0.id == id }!.to }
        let joints = ["hip": hip, "shoulder": shoulder, "head": head,
                      "nearKnee": end("nearThigh"), "nearAnkle": end("nearShin"),
                      "farKnee": end("farThigh"), "farAnkle": end("farShin"),
                      "nearHand": end("nearForearm"), "farHand": end("farForearm")]
        return DemoSkeleton(segments: segments, head: head, hip: hip, joints: joints)
    }

    // MARK: Timing

    private static func ease(_ t: Double) -> Double { 0.5 - cos(.pi * t) / 2 }

    static func cycleLength(_ demo: ExerciseDemo) -> Double { demo.steps.reduce(0) { $0 + $1.seconds } }

    /// Pose, effort and step index at `seconds` into the loop. Each step eases from the previous
    /// step's pose to its own; a step to the same pose is a hold.
    static func frame(_ demo: ExerciseDemo, at seconds: Double) -> DemoFrame {
        let total = cycleLength(demo)
        var time = (seconds.truncatingRemainder(dividingBy: total) + total).truncatingRemainder(dividingBy: total)
        var from = demo.steps[demo.steps.count - 1].pose
        for (index, step) in demo.steps.enumerated() {
            if time < step.seconds || index == demo.steps.count - 1 {
                let t = ease(min(1, time / step.seconds))
                let effort = lerp(demo.effort[from] ?? 0, demo.effort[step.pose] ?? 0, t)
                return DemoFrame(pose: mixPose(demo.poses[from]!, demo.poses[step.pose]!, t), effort: effort, step: index)
            }
            time -= step.seconds
            from = step.pose
        }
        fatalError("unreachable")
    }

    /// The pose that best explains the move in one still: the hardest one.
    static func peakPose(_ demo: ExerciseDemo) -> DemoPose {
        let key = demo.poses.keys.sorted().max { (demo.effort[$0] ?? 0) < (demo.effort[$1] ?? 0) }!
        return mixPose(demo.poses[key]!, demo.poses[key]!, 0)
    }

    /// The joints that travel furthest over the loop; they carry the motion arrows.
    static func movers(_ demo: ExerciseDemo) -> [String] {
        let start = skeleton(frame(demo, at: 0).pose).joints
        var travel = start.mapValues { _ in 0.0 }
        var seconds = 0.0
        while seconds < cycleLength(demo) {
            for (key, point) in skeleton(frame(demo, at: seconds).pose).joints {
                travel[key] = max(travel[key] ?? 0, hypot(point.x - start[key]!.x, point.y - start[key]!.y))
            }
            seconds += 0.1
        }
        let ranked = travel.filter { $0.key != "head" && $0.value > 6 }
            .sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }.map(\.key)
        let limb = { (key: String) in key.replacingOccurrences(of: #"Knee|Ankle"#, with: "Leg", options: .regularExpression) }
        var seen = Set<String>()
        return Array(ranked.filter { seen.insert(limb($0)).inserted }.prefix(demo.movers))
    }

    /// Arrows just ahead of each moving joint, pointing where it's going; they fade out during
    /// holds. Isometric demos name a `press` instead. Each arrow is a list of polylines.
    static func arrows(_ demo: ExerciseDemo, movers: [String], at seconds: Double) -> [(lines: [[CGPoint]], opacity: Double)] {
        let now = skeleton(frame(demo, at: seconds).pose).joints
        let before = skeleton(frame(demo, at: seconds - 0.06).pose).joints
        let soon = skeleton(frame(demo, at: seconds + 0.06).pose).joints
        var arrows: [(at: CGPoint, angle: Double, opacity: Double, press: Bool)] = movers.map { key in
            let dx = soon[key]!.x - before[key]!.x, dy = soon[key]!.y - before[key]!.y
            let speed = hypot(dx, dy) / 0.12
            return (now[key]!, atan2(dy, dx) * 180 / .pi, max(0, min(1, (speed - 5) / 15)), false)
        }
        if let press = demo.press {
            let effort = frame(demo, at: seconds).effort
            arrows.append((now[press.at]!, press.angle, effort > 0.6 ? (effort - 0.6) / 0.4 : 0, true))
        }
        return arrows.filter { $0.opacity > 0.02 }.map { arrow in
            // A press arrow points at the joint from outside; a motion arrow leads it.
            let (near, far) = arrow.press ? (-22.0, -11.0) : (11.0, 24.0)
            let tail = add(arrow.at, dir(arrow.angle, near)), tip = add(arrow.at, dir(arrow.angle, far))
            let wing = { (side: Double) in add(tip, dir(arrow.angle + 180 + side * 35, 6)) }
            return ([[tail, tip], [wing(-1), tip, wing(1)]], arrow.opacity)
        }
    }

    /// Adjacent steps with the same label read as one cue: "Hold 3s".
    static func cues(_ demo: ExerciseDemo) -> [DemoCue] {
        var merged: [DemoCue] = []
        for (index, step) in demo.steps.enumerated() {
            if let last = merged.last, last.label == step.label {
                merged[merged.count - 1].seconds += step.seconds
                merged[merged.count - 1].steps.append(index)
            } else {
                merged.append(DemoCue(label: step.label, seconds: step.seconds, steps: [index]))
            }
        }
        return merged.map { DemoCue(label: $0.label, seconds: ($0.seconds * 2).rounded() / 2, steps: $0.steps) }
    }

    /// Frame that fits the whole move, between 2:1 and 2.6:1 with the floor near the bottom.
    static func viewBox(_ demo: ExerciseDemo, pad: Double = 10) -> CGRect {
        var minX = Double.infinity, minY = Double.infinity, maxX = -Double.infinity, maxY = floor + 4
        var seconds = 0.0
        while seconds < cycleLength(demo) {
            let skeleton = skeleton(frame(demo, at: seconds).pose)
            for point in skeleton.segments.flatMap({ [$0.from, $0.to] }) {
                minX = min(minX, point.x - 4); maxX = max(maxX, point.x + 4); minY = min(minY, point.y - 4)
            }
            minX = min(minX, skeleton.head.x - headRadius); maxX = max(maxX, skeleton.head.x + headRadius)
            minY = min(minY, skeleton.head.y - headRadius)
            seconds += 0.1
        }
        for prop in demo.props {
            switch prop {
            case let .rect(x, _, width, _, _): minX = min(minX, x); maxX = max(maxX, x + width)
            case let .line(x1, _, x2, _): minX = min(minX, x1, x2); maxX = max(maxX, x1, x2)
            }
        }
        minX -= pad; maxX += pad; minY -= pad; maxY += pad / 2
        var width = maxX - minX, height = maxY - minY
        let aspect = max(2, min(2.6, width / height))
        if width / height < aspect {
            minX -= (height * aspect - width) / 2
            width = height * aspect
        } else {
            minY -= width / aspect - height
            height = width / aspect
        }
        return CGRect(x: minX, y: minY, width: width, height: height)
    }
}

// MARK: - Catalog

private func pt(_ x: Double, _ y: Double) -> CGPoint { CGPoint(x: x, y: y) }
private func step(_ pose: String, _ seconds: Double, _ label: String) -> ExerciseDemo.Step { .init(pose: pose, seconds: seconds, label: label) }

// Props are muted scenery: a chair, a wall, a step.
private let chair: [DemoProp] = [
    .rect(x: 40, y: 88, width: 42, height: 5, radius: 2),
    .line(x1: 44, y1: 93, x2: 44, y2: 120), .line(x1: 78, y1: 93, x2: 78, y2: 120),
    .line(x1: 44, y1: 88, x2: 44, y2: 44),
]
private func wall(_ x: Double) -> [DemoProp] { [.rect(x: x, y: -14, width: 7, height: 134, radius: 1)] }
private func box(_ x: Double, _ width: Double, _ height: Double) -> [DemoProp] {
    [.rect(x: x, y: ExerciseDemos.floor - height, width: width, height: height, radius: 3)]
}

/// Lying on the back, head to the left.
private let supine = DemoPose(hip: pt(112, 116), torso: 180, head: 200, nearArm: DemoLimb(hand: pt(113, 117)), farArm: DemoLimb(hand: pt(112, 117)))
/// Lying on the side, facing the viewer, head propped on the bottom hand, top arm along the body.
/// Side demos are `solid` (no dimmed far side): from the front both arms show and the legs stack.
private let sideLying = DemoPose(hip: pt(112, 110), shoulder: pt(76, 105), head: 222,
                                 nearArm: DemoLimb(hand: pt(112, 104)), farArm: DemoLimb(hand: pt(58, 98), elbow: pt(62, 116)))
private func stand(_ hipX: Double) -> DemoPose {
    DemoPose(hip: pt(hipX, 61), torso: -90, near: DemoLimb(foot: pt(hipX, 114)), far: DemoLimb(foot: pt(hipX - 2, 114)))
}
private let seated = DemoPose(hip: pt(70, 84), torso: -90, near: DemoLimb(foot: pt(99, 114)), far: DemoLimb(foot: pt(97, 114)))

extension ExerciseDemos {
    static let all: [ExerciseDemo] = [
        ExerciseDemo(
            key: "quad-set", title: "Quad isometric",
            match: #"quad(riceps)?\s*(set|isometric|squeeze|tighten|contraction)|(static|isometric) quad"#,
            focus: ["nearThigh"],
            poses: [
                "rest": supine.with { $0.near = DemoLimb(foot: pt(165, 116), toe: -70); $0.far = DemoLimb(foot: pt(157, 116), toe: 0) },
                "squeeze": supine.with { $0.near = DemoLimb(foot: pt(165, 113), toe: -88); $0.far = DemoLimb(foot: pt(157, 116), toe: 0) },
            ],
            effort: ["squeeze": 1], press: ("nearKnee", 90),
            steps: [step("squeeze", 0.8, "Tighten thigh"), step("squeeze", 3, "Press knee down"), step("rest", 0.8, "Relax"), step("rest", 1, "Relax")]
        ),
        ExerciseDemo(
            key: "straight-leg-raise", title: "Straight leg raise", match: #"straight[- ]leg raise|\bslr\b"#,
            focus: ["nearThigh"],
            poses: [
                "down": supine.with { $0.near = DemoLimb(foot: pt(165, 116), toe: -88); $0.far = DemoLimb(foot: pt(150, 116), toe: 0) },
                "up": supine.with { $0.near = DemoLimb(foot: pt(155, 86), toe: -122); $0.far = DemoLimb(foot: pt(150, 116), toe: 0) },
            ],
            effort: ["up": 1],
            steps: [step("up", 1.5, "Lift straight leg"), step("up", 1, "Hold"), step("down", 2, "Lower slowly"), step("down", 0.8, "Rest")]
        ),
        ExerciseDemo(
            key: "heel-slide", title: "Heel slide", match: #"heel slide"#,
            focus: ["nearThigh", "nearShin"],
            poses: [
                "straight": supine.with { $0.near = DemoLimb(foot: pt(165, 116), toe: -80); $0.far = DemoLimb(foot: pt(150, 116), toe: 0) },
                "bent": supine.with { $0.near = DemoLimb(foot: pt(140, 116), toe: 0); $0.far = DemoLimb(foot: pt(150, 116), toe: 0) },
            ],
            effort: ["bent": 1],
            steps: [step("bent", 2, "Slide heel in"), step("bent", 1, "Pause"), step("straight", 2, "Slide out"), step("straight", 0.8, "Rest")]
        ),
        ExerciseDemo(
            key: "glute-bridge", title: "Glute bridge", match: #"bridge|hip thrust"#,
            focus: ["hip", "nearThigh"],
            poses: [
                "down": supine.with { $0.near = DemoLimb(foot: pt(150, 116), toe: 0); $0.far = DemoLimb(foot: pt(147, 116), toe: 0) },
                "up": supine.with {
                    $0.hip = pt(106, 96); $0.shoulder = pt(74, 116)
                    $0.near = DemoLimb(foot: pt(150, 116), toe: 0); $0.far = DemoLimb(foot: pt(147, 116), toe: 0)
                },
            ],
            effort: ["up": 1],
            steps: [step("up", 1.2, "Push through heels"), step("up", 1.5, "Squeeze glutes"), step("down", 2, "Lower slowly"), step("down", 0.6, "Rest")]
        ),
        ExerciseDemo(
            key: "side-plank", title: "Side plank", match: #"side plank"#,
            focus: ["hip"], solid: true,
            poses: [
                "down": DemoPose(hip: pt(106, 114), shoulder: pt(70, 98),
                                 near: DemoLimb(foot: pt(160, 114), toe: -70), far: DemoLimb(foot: pt(158, 117), toe: -70),
                                 nearArm: DemoLimb(hand: pt(80, 117), elbow: pt(70, 116)), farArm: DemoLimb(handRel: pt(31, 4), bend: -1)),
                "up": DemoPose(hip: pt(107, 105), shoulder: pt(70, 98),
                               near: DemoLimb(foot: pt(160, 114), toe: -70), far: DemoLimb(foot: pt(158, 117), toe: -70),
                               nearArm: DemoLimb(hand: pt(80, 117), elbow: pt(70, 116)), farArm: DemoLimb(handRel: pt(31, 4), bend: -1)),
            ],
            effort: ["up": 1],
            steps: [step("up", 1, "Lift hips"), step("up", 3, "Hold, body in line"), step("down", 1, "Lower"), step("down", 1, "Rest")]
        ),
        ExerciseDemo(
            key: "plank", title: "Plank", match: #"\bplank\b"#,
            focus: ["torso", "hip"],
            poses: [
                "down": DemoPose(hip: pt(113, 113), shoulder: pt(76, 104), head: 175,
                                 near: DemoLimb(foot: pt(165, 112), toe: 75), far: DemoLimb(foot: pt(163, 112), toe: 75),
                                 nearArm: DemoLimb(hand: pt(94, 116), elbow: pt(76, 116)), farArm: DemoLimb(hand: pt(92, 116), elbow: pt(74, 116))),
                "up": DemoPose(hip: pt(113, 101.6), shoulder: pt(76, 97), head: 185,
                               near: DemoLimb(foot: pt(165, 108), toe: 75), far: DemoLimb(foot: pt(163, 108), toe: 75),
                               nearArm: DemoLimb(hand: pt(94, 116), elbow: pt(76, 116)), farArm: DemoLimb(hand: pt(92, 116), elbow: pt(74, 116))),
            ],
            effort: ["up": 1],
            steps: [step("up", 1, "Lift into line"), step("up", 4, "Hold, brace"), step("down", 1, "Lower"), step("down", 1, "Rest")]
        ),
        ExerciseDemo(
            key: "clamshell", title: "Clamshell", match: #"clam"#,
            focus: ["hip", "nearThigh"], solid: true,
            poses: [
                "closed": sideLying.with {
                    $0.near = DemoLimb(foot: pt(142, 112), knee: pt(130, 109), toe: 20); $0.far = DemoLimb(foot: pt(143, 116), knee: pt(130, 116), toe: 20)
                },
                "open": sideLying.with {
                    $0.near = DemoLimb(foot: pt(142, 112), knee: pt(126, 88), toe: 20); $0.far = DemoLimb(foot: pt(143, 116), knee: pt(130, 116), toe: 20)
                },
            ],
            effort: ["open": 1],
            steps: [step("open", 1.2, "Open top knee"), step("open", 1, "Hold"), step("closed", 2, "Close slowly"), step("closed", 0.6, "Rest")]
        ),
        ExerciseDemo(
            key: "hip-abduction", title: "Side-lying hip abduction", match: #"abduct|side[- ]lying leg|side leg (lift|raise)"#,
            focus: ["hip", "nearThigh"], solid: true,
            poses: [
                "down": sideLying.with { $0.near = DemoLimb(foot: pt(165, 112), toe: -25); $0.far = DemoLimb(foot: pt(164, 116), toe: -25) },
                "up": sideLying.with { $0.near = DemoLimb(foot: pt(157, 82), toe: -55); $0.far = DemoLimb(foot: pt(164, 116), toe: -25) },
            ],
            effort: ["up": 1],
            steps: [step("up", 1.2, "Lift top leg"), step("up", 1, "Hold"), step("down", 2, "Lower slowly"), step("down", 0.6, "Rest")]
        ),
        ExerciseDemo(
            key: "wall-sit", title: "Wall sit", match: #"wall (sit|squat)|spanish squat"#,
            props: wall(55), focus: ["nearThigh", "farThigh"],
            poses: [
                "top": DemoPose(hip: pt(66, 68), torso: -90, near: DemoLimb(foot: pt(93, 114)), far: DemoLimb(foot: pt(91, 114)),
                                nearArm: DemoLimb(handRel: pt(8, 34)), farArm: DemoLimb(handRel: pt(6, 34))),
                "sit": DemoPose(hip: pt(66, 78), torso: -90, near: DemoLimb(foot: pt(93, 114)), far: DemoLimb(foot: pt(91, 114)),
                                nearArm: DemoLimb(handRel: pt(10, 34)), farArm: DemoLimb(handRel: pt(8, 34))),
            ],
            effort: ["sit": 1],
            steps: [step("sit", 1.5, "Slide down a little"), step("sit", 4, "Hold, weight even"), step("top", 1.5, "Slide up"), step("top", 1, "Rest")]
        ),
        ExerciseDemo(
            key: "sit-to-stand", title: "Sit-to-stand", match: #"sit[- ]to[- ]stand|chair (squat|stand)|box squat"#,
            props: chair, focus: ["nearThigh", "hip"],
            poses: [
                "sit": seated.with { $0.nearArm = DemoLimb(handRel: pt(22, 18)); $0.farArm = DemoLimb(handRel: pt(20, 18)) },
                "lean": seated.with {
                    $0.hip = pt(72, 84); $0.torso = -52
                    $0.nearArm = DemoLimb(handRel: pt(24, 14)); $0.farArm = DemoLimb(handRel: pt(22, 14))
                },
                "stand": DemoPose(hip: pt(94, 62), torso: -88, near: DemoLimb(foot: pt(99, 114)), far: DemoLimb(foot: pt(97, 114)),
                                  nearArm: DemoLimb(handRel: pt(22, 18)), farArm: DemoLimb(handRel: pt(20, 18))),
            ],
            effort: ["lean": 0.6, "stand": 1],
            steps: [step("lean", 0.8, "Lean forward"), step("stand", 1.2, "Stand up"), step("stand", 0.8, "Stand tall"),
                    step("lean", 1.6, "Lower in 3 s"), step("sit", 1.4, "Lower in 3 s"), step("sit", 0.8, "Sit")]
        ),
        ExerciseDemo(
            key: "calf-stretch", title: "Calf stretch", match: #"(calf|gastroc|soleus) stretch"#,
            props: wall(170), focus: ["nearShin"],
            poses: [
                "start": DemoPose(hip: pt(114, 66), shoulder: pt(136, 34), near: DemoLimb(foot: pt(92, 114), toe: 5), far: DemoLimb(foot: pt(132, 114)),
                                  nearArm: DemoLimb(hand: pt(168, 30)), farArm: DemoLimb(hand: pt(167, 32))),
                "stretch": DemoPose(hip: pt(118, 68), shoulder: pt(140, 36), near: DemoLimb(foot: pt(92, 114), toe: 5), far: DemoLimb(foot: pt(132, 114)),
                                    nearArm: DemoLimb(hand: pt(168, 30)), farArm: DemoLimb(hand: pt(167, 32))),
            ],
            effort: ["stretch": 1],
            steps: [step("stretch", 2, "Lean in, back heel down"), step("stretch", 4, "Hold"), step("start", 1.5, "Ease off"), step("start", 0.5, "Ease off")]
        ),
        ExerciseDemo(
            key: "calf-raise", title: "Calf raise", match: #"(calf|heel) (raise|rise)"#,
            focus: ["nearShin", "farShin"],
            poses: [
                "down": DemoPose(hip: pt(110, 61), torso: -90, near: DemoLimb(foot: pt(110, 114), toe: 10), far: DemoLimb(foot: pt(108, 114), toe: 10)),
                "up": DemoPose(hip: pt(113, 55), torso: -90, near: DemoLimb(foot: pt(113.4, 108), toe: 50), far: DemoLimb(foot: pt(111.4, 108), toe: 50)),
            ],
            effort: ["up": 1],
            steps: [step("up", 1, "Rise up"), step("up", 0.8, "Hold"), step("down", 2, "Lower slowly"), step("down", 0.6, "Rest")]
        ),
        ExerciseDemo(
            key: "hamstring-stretch", title: "Hamstring stretch", match: #"hamstring.*stretch|stretch.*hamstring"#,
            focus: ["nearThigh"],
            poses: [
                "rest": supine.with { $0.near = DemoLimb(foot: pt(150, 116), toe: 0); $0.far = DemoLimb(foot: pt(165, 116), toe: -85) },
                "stretch": supine.with {
                    $0.near = DemoLimb(foot: pt(128, 67), toe: -160); $0.far = DemoLimb(foot: pt(165, 116), toe: -85)
                    $0.nearArm = DemoLimb(hand: pt(117, 96), bend: -1); $0.farArm = DemoLimb(hand: pt(116, 98), bend: -1)
                },
            ],
            effort: ["stretch": 1],
            steps: [step("stretch", 2, "Raise leg gently"), step("stretch", 4, "Hold, mild stretch"), step("rest", 2, "Lower"), step("rest", 1, "Rest")]
        ),
        ExerciseDemo(
            key: "step-down", title: "Step-down", match: #"step[- ]?down|eccentric step"#,
            props: box(64, 46, 12), focus: ["nearThigh"],
            poses: [
                "top": DemoPose(hip: pt(100, 53), torso: -88, near: DemoLimb(foot: pt(100, 106)), far: DemoLimb(foot: pt(118, 104)),
                                nearArm: DemoLimb(handRel: pt(20, 22)), farArm: DemoLimb(handRel: pt(18, 22))),
                "low": DemoPose(hip: pt(97, 66), torso: -80, near: DemoLimb(foot: pt(100, 106)), far: DemoLimb(foot: pt(118, 114)),
                                nearArm: DemoLimb(handRel: pt(24, 18)), farArm: DemoLimb(handRel: pt(22, 18))),
            ],
            effort: ["low": 1],
            steps: [step("low", 2.5, "Lower heel slowly"), step("low", 0.4, "Tap"), step("top", 1.2, "Push back up"), step("top", 0.8, "Reset")]
        ),
        ExerciseDemo(
            key: "step-up", title: "Step-up", match: #"step[- ]?up"#,
            props: box(112, 50, 20), focus: ["nearThigh"],
            poses: [
                "stand": stand(96).with {
                    $0.near = DemoLimb(foot: pt(98, 114)); $0.nearArm = DemoLimb(handRel: pt(4, 36)); $0.farArm = DemoLimb(handRel: pt(2, 36))
                },
                "place": DemoPose(hip: pt(102, 62), torso: -84, near: DemoLimb(foot: pt(128, 94)), far: DemoLimb(foot: pt(96, 114)),
                                  nearArm: DemoLimb(handRel: pt(8, 34)), farArm: DemoLimb(handRel: pt(-4, 34))),
                "lift": DemoPose(hip: pt(126, 42), torso: -88, near: DemoLimb(foot: pt(128, 94)), far: DemoLimb(foot: pt(118, 84)),
                                 nearArm: DemoLimb(handRel: pt(4, 36)), farArm: DemoLimb(handRel: pt(2, 36))),
                "up": DemoPose(hip: pt(126, 41), torso: -90, near: DemoLimb(foot: pt(128, 94)), far: DemoLimb(foot: pt(124, 94)),
                               nearArm: DemoLimb(handRel: pt(4, 36)), farArm: DemoLimb(handRel: pt(2, 36))),
            ],
            effort: ["place": 0.5, "lift": 1, "up": 0.6],
            steps: [step("place", 1, "Step onto box"), step("lift", 1.2, "Drive up"), step("up", 0.5, "Stand tall"), step("lift", 0.6, "Step down"),
                    step("place", 1, "Step down"), step("stand", 1, "Step down"), step("stand", 0.6, "Reset")]
        ),
        ExerciseDemo(
            key: "split-squat", title: "Split squat", match: #"split squat|lunge"#,
            focus: ["nearThigh", "hip"],
            poses: [
                "top": DemoPose(hip: pt(106, 67), torso: -88, near: DemoLimb(foot: pt(130, 114)), far: DemoLimb(foot: pt(83, 109), toe: 45),
                                nearArm: DemoLimb(handRel: pt(3, 36)), farArm: DemoLimb(handRel: pt(1, 36))),
                "low": DemoPose(hip: pt(106, 78), torso: -88, near: DemoLimb(foot: pt(130, 114)), far: DemoLimb(foot: pt(83, 109), toe: 45),
                                nearArm: DemoLimb(handRel: pt(3, 36)), farArm: DemoLimb(handRel: pt(1, 36))),
            ],
            effort: ["low": 1],
            steps: [step("low", 1.5, "Lower a little"), step("low", 0.6, "Pause"), step("top", 1.2, "Drive up"), step("top", 0.6, "Reset")]
        ),
        ExerciseDemo(
            key: "hip-flexor-stretch", title: "Hip flexor stretch", match: #"hip flexor|kneeling.*stretch|couch stretch"#,
            focus: ["nearThigh", "hip"],
            poses: [
                "start": DemoPose(hip: pt(96, 90), torso: -90, near: DemoLimb(foot: pt(70, 114), knee: pt(94, 116), toe: 100), far: DemoLimb(foot: pt(134, 114)),
                                  nearArm: DemoLimb(handRel: pt(6, 30)), farArm: DemoLimb(handRel: pt(4, 30))),
                "stretch": DemoPose(hip: pt(104, 92), torso: -92, near: DemoLimb(foot: pt(70, 114), knee: pt(96, 116), toe: 100), far: DemoLimb(foot: pt(134, 114)),
                                    nearArm: DemoLimb(handRel: pt(6, 30)), farArm: DemoLimb(handRel: pt(4, 30))),
            ],
            effort: ["stretch": 1],
            steps: [step("stretch", 2, "Shift hips forward"), step("stretch", 4, "Hold, squeeze glute"), step("start", 1.5, "Ease back"), step("start", 0.6, "Ease back")]
        ),
        ExerciseDemo(
            key: "quad-stretch", title: "Quad stretch", match: #"quad(riceps)? stretch"#,
            focus: ["nearThigh"],
            poses: [
                "start": DemoPose(hip: pt(110, 61), torso: -90, near: DemoLimb(foot: pt(111, 114), knee: pt(111, 88), toe: 10), far: DemoLimb(foot: pt(108, 114)),
                                  nearArm: DemoLimb(hand: pt(112, 59)), farArm: DemoLimb(hand: pt(118, 58))),
                "stretch": DemoPose(hip: pt(110, 61), torso: -90, near: DemoLimb(foot: pt(94, 70), knee: pt(112, 88), toe: 200), far: DemoLimb(foot: pt(108, 114)),
                                    nearArm: DemoLimb(hand: pt(93, 72), bend: -1), farArm: DemoLimb(hand: pt(142, 42))),
            ],
            effort: ["stretch": 1],
            steps: [step("stretch", 1.5, "Heel to glute"), step("stretch", 4, "Hold, knees together"), step("start", 1.5, "Lower"), step("start", 0.6, "Lower")]
        ),
        ExerciseDemo(
            key: "knee-extension", title: "Seated knee extension",
            match: #"knee extension|leg extension|long arc quad|seated.*(kick|extension)"#,
            props: chair, focus: ["nearThigh"],
            poses: [
                "bend": seated.with { $0.nearArm = DemoLimb(handRel: pt(14, 32)); $0.farArm = DemoLimb(handRel: pt(12, 32)) },
                "extend": seated.with {
                    $0.near = DemoLimb(foot: pt(122, 80), toe: -90); $0.nearArm = DemoLimb(handRel: pt(14, 32)); $0.farArm = DemoLimb(handRel: pt(12, 32))
                },
            ],
            effort: ["extend": 1],
            steps: [step("extend", 1.5, "Straighten knee"), step("extend", 2, "Hold, squeeze thigh"), step("bend", 2, "Lower slowly"), step("bend", 0.6, "Rest")]
        ),
        ExerciseDemo(
            key: "bird-dog", title: "Bird dog", match: #"bird[- ]?dog"#,
            focus: ["torso", "hip"],
            poses: [
                "start": DemoPose(hip: pt(130, 78), torso: 180, head: 192,
                                  near: DemoLimb(foot: pt(156, 114), toe: 90, bend: 1), far: DemoLimb(foot: pt(154, 114), toe: 90, bend: 1),
                                  nearArm: DemoLimb(hand: pt(93, 116)), farArm: DemoLimb(hand: pt(91, 116))),
                "reach": DemoPose(hip: pt(130, 78), torso: 180, head: 192,
                                  near: DemoLimb(foot: pt(156, 114), toe: 90, bend: 1), far: DemoLimb(foot: pt(182, 76), toe: 90, bend: 1),
                                  nearArm: DemoLimb(hand: pt(56, 80)), farArm: DemoLimb(hand: pt(91, 116))),
            ],
            effort: ["reach": 1], movers: 2,
            steps: [step("reach", 1.5, "Reach opposite arm and leg"), step("reach", 2, "Hold, hips level"), step("start", 1.5, "Return"), step("start", 0.6, "Return")]
        ),
        ExerciseDemo(
            key: "dead-bug", title: "Dead bug", match: #"dead[- ]?bug"#,
            focus: ["torso"],
            poses: [
                "start": supine.with {
                    $0.near = DemoLimb(foot: pt(138, 89), toe: -10); $0.far = DemoLimb(foot: pt(136, 90), toe: -10)
                    $0.nearArm = DemoLimb(hand: pt(76, 79)); $0.farArm = DemoLimb(hand: pt(74, 79))
                },
                "reach": supine.with {
                    $0.near = DemoLimb(foot: pt(162, 102), toe: -30); $0.far = DemoLimb(foot: pt(136, 90), toe: -10)
                    $0.nearArm = DemoLimb(hand: pt(76, 79)); $0.farArm = DemoLimb(hand: pt(40, 106))
                },
            ],
            effort: ["reach": 1], movers: 2,
            steps: [step("reach", 2, "Extend slowly"), step("reach", 0.8, "Low back down"), step("start", 1.5, "Return"), step("start", 0.6, "Switch sides")]
        ),
        ExerciseDemo(
            key: "single-leg-balance", title: "Single-leg balance", match: #"balance|single[- ]leg stand|stork"#,
            focus: ["nearShin", "hip"],
            poses: [
                "both": stand(110).with { $0.nearArm = DemoLimb(handRel: pt(6, 34)); $0.farArm = DemoLimb(handRel: pt(2, 34)) },
                "lift": DemoPose(hip: pt(110, 61), torso: -90, near: DemoLimb(foot: pt(110, 114)), far: DemoLimb(foot: pt(112, 92)),
                                 nearArm: DemoLimb(handRel: pt(14, 30)), farArm: DemoLimb(handRel: pt(-8, 30))),
                "sway": DemoPose(hip: pt(111.5, 61), torso: -89, near: DemoLimb(foot: pt(110, 114)), far: DemoLimb(foot: pt(113, 92)),
                                 nearArm: DemoLimb(handRel: pt(16, 28)), farArm: DemoLimb(handRel: pt(-10, 30))),
            ],
            effort: ["lift": 1, "sway": 1],
            steps: [step("lift", 1, "Lift one foot"), step("sway", 1.5, "Hold steady"), step("lift", 1.5, "Hold steady"), step("both", 1, "Lower")]
        ),
        ExerciseDemo(
            key: "squat", title: "Mini squat", match: #"squat"#,
            focus: ["nearThigh", "hip"],
            poses: [
                "top": stand(108).with {
                    $0.near = DemoLimb(foot: pt(110, 114)); $0.far = DemoLimb(foot: pt(108, 114))
                    $0.nearArm = DemoLimb(handRel: pt(22, 18)); $0.farArm = DemoLimb(handRel: pt(20, 18))
                },
                "low": DemoPose(hip: pt(96, 76), torso: -65, near: DemoLimb(foot: pt(110, 114)), far: DemoLimb(foot: pt(108, 114)),
                                nearArm: DemoLimb(handRel: pt(26, 6)), farArm: DemoLimb(handRel: pt(24, 6))),
            ],
            effort: ["low": 1],
            steps: [step("low", 1.5, "Sit hips back"), step("low", 0.6, "Pause"), step("top", 1.2, "Stand up"), step("top", 0.6, "Reset")]
        ),
    ]
}
