import CoreGraphics
import Foundation

// Animated figure demos for rehab exercises, matched by exercise name. A port of the web's
// frontend/src/recovery/exercise-demos.mjs; keep the two in step (TrainLogTests/Fixtures/
// demo-frames.json, written by frontend/scripts/export-demo-frames.mjs, checks the port).
// Poses are drawn in a 240-wide frame with the floor at y=120. A pose names where the hips, hands
// and feet go; each pose is resolved into joint angles once, and the animation blends those
// angles, so limbs swing on arcs and keep their length. A hand or foot that stays put between two
// poses is planted (solved with IK so it never slides), and a limb can give an explicit knee or
// elbow for out-of-plane moves (clamshell). Timing follows a minimum-jerk speed curve, arms and
// head trail the body a moment, and holds keep breathing. A few demos (straight leg raise, mini
// squat, side plank) are hand-animated with their own `rig`.

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

/// One limb of a drawable body: the middle joint (knee/elbow), the end (ankle/hand) and the toe angle.
struct DemoMixLimb: Sendable {
    var joint: CGPoint
    var end: CGPoint
    var toe = 10.0
    var contact = false
    var explicit = false
}

/// A body between poses (or built by a rig), before it becomes segments.
struct DemoMix: Sendable {
    var hip: CGPoint
    var shoulder: CGPoint
    var torso = 0.0
    var head = 0.0
    /// Rigs place the head directly.
    var headPoint: CGPoint?
    var bend = 0.0
    var near: DemoMixLimb
    var far: DemoMixLimb
    var nearArm: DemoMixLimb
    var farArm: DemoMixLimb
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
    /// The joint the path arrow follows; otherwise the one that travels furthest.
    var guide: String?
    /// Rigs: the moment that explains the move in one still.
    var peakAt = 0.0
    let poses: [String: DemoPose]
    var effort: [String: Double] = [:]
    /// Isometric holds: an arrow pressing on this joint while the effort is high.
    var press: (at: String, angle: Double)?
    let steps: [Step]
    /// Hand-animated demos build their own body at each moment.
    var rig: (@Sendable (Double) -> (mix: DemoMix, effort: Double))?
}

struct DemoSegment: Sendable {
    enum Layer: Sendable { case far, body, near }
    let id: String
    let from: CGPoint
    let to: CGPoint
    let layer: Layer
}

struct DemoBody: Sendable {
    let segments: [DemoSegment]
    let head: CGPoint
    let hip: CGPoint
    let shoulder: CGPoint
    let joints: [String: CGPoint]
    /// Trunk flexion: > 0 rounds the back, < 0 lifts the chest.
    let bend: Double
    /// Side-lying demos face the viewer, so there's no seat in profile.
    let seat: Bool

    func segment(_ id: String) -> DemoSegment? { segments.first { $0.id == id } }
}

struct DemoFrame: Sendable {
    let body: DemoBody
    let effort: Double
    let step: Int
}

struct DemoCue: Equatable, Sendable {
    let label: String
    var seconds: Double
    var steps: [Int]
    var start = 0.0
}

/// The running cue, how far into it, and whole seconds left (for the countdown).
struct DemoCuePhase: Sendable {
    let index: Int
    let cue: DemoCue
    let progress: Double
    let left: Int
    let length: Double
}

enum DemoEase: Sendable {
    case io, lift, ecc, lead, lag, settle, lin

    /// Minimum-jerk profile: the bell-shaped speed curve real lifts and reaches follow. A
    /// constant-speed middle reads as robotic. Warping it starts a move earlier or later without
    /// losing the soft ends.
    static func minJerk(_ t: Double) -> Double {
        let t = max(0, min(1, t))
        return t * t * t * (10 - 15 * t + 6 * t * t)
    }

    private static func warp(_ k: Double, _ t: Double) -> Double { minJerk(t + k * t * (1 - t)) }

    func callAsFunction(_ t: Double) -> Double {
        switch self {
        case .io: Self.minJerk(t)
        case .lift: Self.warp(0.15, t) // off the floor a touch quicker, long cushion into the top
        case .ecc: Self.warp(-0.1, t) // eases out of the top, steady and slow on the way down
        case .lead: Self.warp(0.5, t) // this channel moves early
        case .lag: Self.warp(-0.5, t) // this channel moves late
        case .settle: Self.minJerk(t) + 0.25 * pow(sin(.pi * t), 2) * t * t // a small overshoot, starting and ending at rest
        case .lin: t
        }
    }
}

enum ExerciseDemos {
    static let floor = 120.0
    // Real proportions (Drillis & Contini): trunk about 0.29 of height, head 0.13, leg 0.49.
    static let headRadius = 6.6
    static let torsoLength = 32.0, thighLength = 27.0, shinLength = 26.0, footLength = 9.0
    static let upperArmLength = 19.0, forearmLength = 17.0, neckLength = 11.5
    /// Joint names in the web's order, so ties break the same way.
    static let jointNames = ["hip", "shoulder", "head", "nearKnee", "nearAnkle", "farKnee", "farAnkle", "nearHand", "farHand", "nearToe"]

    private static let armLag = 0.2
    private static let headLag = 0.12
    private static let tau = Double.pi * 2

    static func demo(for name: String?) -> ExerciseDemo? {
        guard let name else { return nil }
        return all.first { name.range(of: $0.match, options: [.regularExpression, .caseInsensitive]) != nil }
    }

    // MARK: Geometry

    static func rad(_ deg: Double) -> Double { deg * .pi / 180 }
    static func dir(_ deg: Double, _ length: Double) -> CGPoint { CGPoint(x: cos(rad(deg)) * length, y: sin(rad(deg)) * length) }
    static func add(_ a: CGPoint, _ b: CGPoint) -> CGPoint { CGPoint(x: a.x + b.x, y: a.y + b.y) }
    static func lerp(_ a: Double, _ b: Double, _ t: Double) -> Double { a + (b - a) * t }
    static func lerp(_ a: CGPoint, _ b: CGPoint, _ t: Double) -> CGPoint { CGPoint(x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t)) }
    static func lerpAngle(_ a: Double, _ b: Double, _ t: Double) -> Double {
        let diff = ((b - a).truncatingRemainder(dividingBy: 360) + 540).truncatingRemainder(dividingBy: 360) - 180
        return a + diff * t
    }
    static func angleOf(_ from: CGPoint, _ to: CGPoint) -> Double { atan2(to.y - from.y, to.x - from.x) * 180 / .pi }
    static func clamp01(_ t: Double) -> Double { max(0, min(1, t)) }
    private static func same(_ a: CGPoint, _ b: CGPoint) -> Bool { abs(a.x - b.x) < 0.01 && abs(a.y - b.y) < 0.01 }

    /// Keyframed channel for hand-animated rigs: (seconds, value, ease into this key), looping.
    typealias Key = (Double, Double, DemoEase)
    static func track(_ keys: [Key], _ seconds: Double, _ period: Double) -> Double {
        let t = (seconds.truncatingRemainder(dividingBy: period) + period).truncatingRemainder(dividingBy: period)
        for i in 1..<keys.count {
            let (t1, v1, ease) = keys[i]
            if t <= t1 {
                let (t0, v0, _) = keys[i - 1]
                return lerp(v0, v1, ease(t1 > t0 ? (t - t0) / (t1 - t0) : 1))
            }
        }
        return keys[keys.count - 1].1
    }

    /// Joint between root and target with fixed bone lengths; bend picks the side.
    static func solveLimb(_ root: CGPoint, _ target: CGPoint, _ upper: Double, _ lower: Double, _ bend: Double) -> (CGPoint, CGPoint) {
        let dx = target.x - root.x, dy = target.y - root.y
        let dist = max(0.01, min(hypot(dx, dy), upper + lower - 0.01))
        let cosine = (upper * upper + dist * dist - lower * lower) / (2 * upper * dist)
        let angle = atan2(dy, dx) + bend * acos(max(-1, min(1, cosine)))
        let joint = CGPoint(x: root.x + cos(angle) * upper, y: root.y + sin(angle) * upper)
        let endAngle = atan2(target.y - joint.y, target.x - joint.x)
        return (joint, CGPoint(x: joint.x + cos(endAngle) * lower, y: joint.y + sin(endAngle) * lower))
    }

    /// The same, choosing the joint by a preference (for hand-animated rigs).
    static let up: @Sendable (CGPoint, CGPoint) -> Bool = { $0.y < $1.y }
    static let fwd: @Sendable (CGPoint, CGPoint) -> Bool = { $0.x > $1.x }
    static func solveToward(_ root: CGPoint, _ target: CGPoint, _ upper: Double, _ lower: Double,
                            _ prefer: (CGPoint, CGPoint) -> Bool) -> (CGPoint, CGPoint) {
        let a = solveLimb(root, target, upper, lower, 1), b = solveLimb(root, target, upper, lower, -1)
        return prefer(a.0, b.0) ? a : b
    }

    static func rigLeg(_ hip: CGPoint, _ ankle: CGPoint, _ prefer: (CGPoint, CGPoint) -> Bool, _ toe: Double) -> DemoMixLimb {
        let (joint, end) = solveToward(hip, ankle, thighLength, shinLength, prefer)
        return DemoMixLimb(joint: joint, end: end, toe: toe)
    }

    private static func torsoAngle(_ pose: DemoPose) -> Double {
        if let shoulder = pose.shoulder { return angleOf(pose.hip, shoulder) }
        return pose.torso ?? -90
    }

    // MARK: Resolving poses

    /// A limb as joint angles. It keeps its target (to spot planted hands and feet) and the toe
    /// angle relative to the shin, so a moving foot hinges with it.
    private struct ResolvedLimb {
        var target: CGPoint
        var explicit = false
        var joint: CGPoint?
        var end: CGPoint?
        var toe = 10.0
        var bend = 0.0
        var upper = 0.0, lower = 0.0, toeRel = 0.0
        var contact = false
    }

    private struct ResolvedPose {
        var hip: CGPoint
        var torso: Double
        var head: Double
        var near, far, nearArm, farArm: ResolvedLimb
    }

    private static func resolve(_ pose: DemoPose) -> ResolvedPose {
        let torso = torsoAngle(pose)
        let shoulder = add(pose.hip, dir(torso, torsoLength))
        func limb(_ root: CGPoint, _ spec: DemoLimb, _ upper: Double, _ lower: Double, _ fallback: CGPoint, _ bend: Double) -> ResolvedLimb {
            let target = spec.foot ?? spec.hand ?? add(root, spec.handRel ?? fallback)
            if let joint = spec.knee ?? spec.elbow {
                return ResolvedLimb(target: target, explicit: true, joint: joint, end: target, toe: spec.toe ?? 10)
            }
            let side = spec.bend ?? bend
            let (joint, end) = solveLimb(root, target, upper, lower, side)
            let lowerAngle = angleOf(joint, end)
            return ResolvedLimb(target: target, bend: side, upper: angleOf(root, joint), lower: lowerAngle, toeRel: (spec.toe ?? 10) - lowerAngle)
        }
        let leg = { (spec: DemoLimb) in limb(pose.hip, spec, thighLength, shinLength, CGPoint(x: 0, y: thighLength + shinLength), -1) }
        let arm = { (spec: DemoLimb) in limb(shoulder, spec, upperArmLength, forearmLength, CGPoint(x: 3, y: upperArmLength + forearmLength), 1) }
        return ResolvedPose(hip: pose.hip, torso: torso, head: pose.head ?? torso,
                            near: leg(pose.near), far: leg(pose.far), nearArm: arm(pose.nearArm), farArm: arm(pose.farArm))
    }

    /// A hand or foot that sits in the same place in every pose is a contact (on the floor, a
    /// wall, a step): it's solved with IK so it never slides. Everything else swings by its angles.
    private static func resolveAll(_ demo: ExerciseDemo) -> [String: ResolvedPose] {
        var poses = demo.poses.mapValues(resolve)
        let sides: [WritableKeyPath<ResolvedPose, ResolvedLimb>] = [\.near, \.far, \.nearArm, \.farArm]
        for side in sides {
            let limbs = poses.values.map { $0[keyPath: side] }
            let contact = limbs.allSatisfy { !$0.explicit && same($0.target, limbs[0].target) }
            for key in poses.keys { poses[key]![keyPath: side].contact = contact }
        }
        return poses
    }

    private static let resolved: [String: [String: ResolvedPose]] =
        Dictionary(uniqueKeysWithValues: all.map { ($0.key, resolveAll($0)) })

    private static func poses(_ demo: ExerciseDemo) -> [String: ResolvedPose] { resolved[demo.key] ?? resolveAll(demo) }

    /// Blend one limb between two resolved poses: planted ends stay put, free ends swing on arcs.
    private static func blendLimb(_ a: ResolvedLimb, _ b: ResolvedLimb, _ t: Double, _ root: CGPoint, _ upper: Double, _ lower: Double) -> DemoMixLimb {
        if a.explicit || b.explicit {
            return DemoMixLimb(joint: lerp(a.joint ?? a.target, b.joint ?? b.target, t), end: lerp(a.end ?? a.target, b.end ?? b.target, t),
                               toe: lerpAngle(a.toe, b.toe, t), explicit: true)
        }
        if a.contact {
            let (joint, end) = solveLimb(root, a.target, upper, lower, a.bend)
            return DemoMixLimb(joint: joint, end: end, toe: lerpAngle(a.toeRel + a.lower, b.toeRel + b.lower, t), contact: true)
        }
        let joint = add(root, dir(lerpAngle(a.upper, b.upper, t), upper))
        let lowerAngle = lerpAngle(a.lower, b.lower, t)
        return DemoMixLimb(joint: joint, end: add(joint, dir(lowerAngle, lower)), toe: lowerAngle + lerpAngle(a.toeRel, b.toeRel, t))
    }

    private static func blend(_ a: ResolvedPose, _ b: ResolvedPose, _ t: Double) -> DemoMix {
        let hip = lerp(a.hip, b.hip, t), torso = lerpAngle(a.torso, b.torso, t)
        let shoulder = add(hip, dir(torso, torsoLength))
        return DemoMix(
            hip: hip, shoulder: shoulder, torso: torso, head: lerpAngle(a.head, b.head, t),
            near: blendLimb(a.near, b.near, t, hip, thighLength, shinLength),
            far: blendLimb(a.far, b.far, t, hip, thighLength, shinLength),
            nearArm: blendLimb(a.nearArm, b.nearArm, t, shoulder, upperArmLength, forearmLength),
            farArm: blendLimb(a.farArm, b.farArm, t, shoulder, upperArmLength, forearmLength)
        )
    }

    /// Segments in draw order (far side first), plus the head, hip and named joints.
    private static func build(_ m: DemoMix, _ demo: ExerciseDemo) -> DemoBody {
        func leg(_ side: String, _ l: DemoMixLimb, _ layer: DemoSegment.Layer) -> [DemoSegment] {
            [.init(id: "\(side)Thigh", from: m.hip, to: l.joint, layer: layer),
             .init(id: "\(side)Shin", from: l.joint, to: l.end, layer: layer),
             .init(id: "\(side)Foot", from: l.end, to: add(l.end, dir(l.toe, footLength)), layer: layer)]
        }
        func arm(_ side: String, _ l: DemoMixLimb, _ layer: DemoSegment.Layer) -> [DemoSegment] {
            [.init(id: "\(side)UpperArm", from: m.shoulder, to: l.joint, layer: layer),
             .init(id: "\(side)Forearm", from: l.joint, to: l.end, layer: layer)]
        }
        let segments = arm("far", m.farArm, .far) + leg("far", m.far, .far)
            + [DemoSegment(id: "torso", from: m.hip, to: m.shoulder, layer: .body)]
            + leg("near", m.near, .near) + arm("near", m.nearArm, .near)
        let head = m.headPoint ?? add(m.shoulder, dir(m.head, neckLength))
        let joints = ["hip": m.hip, "shoulder": m.shoulder, "head": head, "nearKnee": m.near.joint, "nearAnkle": m.near.end,
                      "farKnee": m.far.joint, "farAnkle": m.far.end, "nearHand": m.nearArm.end, "farHand": m.farArm.end,
                      "nearToe": segments[segments.count - 3].to]
        return DemoBody(segments: segments, head: head, hip: m.hip, shoulder: m.shoulder, joints: joints, bend: m.bend, seat: !demo.solid)
    }

    // MARK: Timing

    static func cycleLength(_ demo: ExerciseDemo) -> Double { demo.steps.reduce(0) { $0 + $1.seconds } }

    private static func wrapped(_ seconds: Double, _ total: Double) -> Double {
        (seconds.truncatingRemainder(dividingBy: total) + total).truncatingRemainder(dividingBy: total)
    }

    /// Where the loop is: the step, how far into it, and the blend between its two poses.
    private static func stepAt(_ demo: ExerciseDemo, _ seconds: Double) -> (index: Int, from: String, to: String, progress: Double) {
        var time = wrapped(seconds, cycleLength(demo))
        var from = demo.steps[demo.steps.count - 1].pose
        for (index, step) in demo.steps.enumerated() {
            if time < step.seconds || index == demo.steps.count - 1 { return (index, from, step.pose, min(1, time / step.seconds)) }
            time -= step.seconds
            from = step.pose
        }
        fatalError("unreachable")
    }

    /// The step's own curve: lifting into effort eases off the floor and cushions in, lowering out
    /// of effort is slow and even, anything else is a plain minimum-jerk move.
    private static func poseAt(_ demo: ExerciseDemo, _ seconds: Double) -> (mix: DemoMix, effort: Double, step: Int) {
        let (index, from, to, progress) = stepAt(demo, seconds)
        let effortFrom = demo.effort[from] ?? 0, effortTo = demo.effort[to] ?? 0
        let curve: DemoEase = effortTo > effortFrom ? .lift : effortTo < effortFrom ? .ecc : .io
        let t = curve(progress)
        let poses = poses(demo)
        return (blend(poses[from]!, poses[to]!, t), lerp(effortFrom, effortTo, t), index)
    }

    /// Pose, effort and step index at `seconds` into the loop, as a drawable body.
    static func frame(_ demo: ExerciseDemo, at seconds: Double) -> DemoFrame {
        if let rig = demo.rig {
            let (mix, effort) = rig(seconds)
            return DemoFrame(body: build(mix, demo), effort: effort, step: stepAt(demo, seconds).index)
        }
        let current = poseAt(demo, seconds)
        var mix = current.mix
        // Arms and head trail the body a moment (overlap); planted hands stay where they are.
        let late = poseAt(demo, seconds - armLag).mix
        for side in [\DemoMix.nearArm, \DemoMix.farArm] {
            let now = mix[keyPath: side], lagged = late[keyPath: side]
            if now.contact || now.explicit { continue }
            let joint = add(mix.shoulder, dir(angleOf(late.shoulder, lagged.joint), upperArmLength))
            mix[keyPath: side].joint = joint
            mix[keyPath: side].end = add(joint, dir(angleOf(lagged.joint, lagged.end), forearmLength))
        }
        mix.head = poseAt(demo, seconds - headLag).mix.head
        // A moving hold: the chest rises with each breath, and a held effort wobbles a little.
        let breath = sin(tau * seconds / 3.7)
        mix.bend = -0.35 * (1 + breath)
        mix.head += 0.8 * breath
        return DemoFrame(body: build(mix, demo), effort: current.effort, step: current.step)
    }

    /// The pose that best explains the move in one still: the hardest one.
    static func peakFrame(_ demo: ExerciseDemo) -> DemoFrame {
        if demo.rig != nil { return frame(demo, at: demo.peakAt) }
        let key = demo.poses.keys.sorted().max { (demo.effort[$0] ?? 0) < (demo.effort[$1] ?? 0) }!
        let pose = poses(demo)[key]!
        return DemoFrame(body: build(blend(pose, pose, 0), demo), effort: demo.effort[key] ?? 0, step: -1)
    }

    private static let guides: [String: String] = Dictionary(uniqueKeysWithValues: all.compactMap { demo in
        travelledFurthest(demo).map { (demo.key, $0) }
    })

    private static func travelledFurthest(_ demo: ExerciseDemo) -> String? {
        let start = frame(demo, at: 0).body.joints
        var travel = start.mapValues { _ in 0.0 }
        var seconds = 0.0
        while seconds < cycleLength(demo) {
            for (key, point) in frame(demo, at: seconds).body.joints {
                travel[key] = max(travel[key]!, hypot(point.x - start[key]!.x, point.y - start[key]!.y))
            }
            seconds += 0.1
        }
        var best: String?
        for key in jointNames where key != "head" && key != "nearToe" {
            if best == nil || travel[key]! > travel[best!]! { best = key }
        }
        return best.flatMap { travel[$0]! > 6 ? $0 : nil }
    }

    /// The joint the path arrow follows: a demo can name it, otherwise the one that travels furthest.
    static func guideJoint(_ demo: ExerciseDemo) -> String? {
        demo.guide ?? (resolved[demo.key] != nil ? guides[demo.key] : travelledFurthest(demo))
    }

    /// Where the guide joint goes in the next 0.6 s, along its real arc, fading out when it barely
    /// moves (holds). Isometric demos name a `press` instead: an arrow pushing on a joint while held.
    static func pathAt(_ demo: ExerciseDemo, at seconds: Double) -> (points: [CGPoint], opacity: Double)? {
        guard let guide = guideJoint(demo) else {
            guard let press = demo.press else { return nil }
            let frame = frame(demo, at: seconds)
            let at = frame.body.joints[press.at]!, opacity = frame.effort > 0.6 ? (frame.effort - 0.6) / 0.4 : 0
            if opacity < 0.02 { return nil }
            return ([add(at, dir(press.angle, -22)), add(at, dir(press.angle, -11))], opacity)
        }
        var points: [CGPoint] = []
        var ahead = 0.08
        while ahead <= 0.7 {
            points.append(frame(demo, at: seconds + ahead).body.joints[guide]!)
            ahead += 0.04
        }
        var length = 0.0
        for i in 1..<points.count { length += hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y) }
        let opacity = clamp01((length - 3) / 8)
        return opacity > 0.02 ? (points, opacity) : nil
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
        var start = 0.0
        return merged.map { cue in
            defer { start += cue.seconds }
            return DemoCue(label: cue.label, seconds: (cue.seconds * 2).rounded() / 2, steps: cue.steps, start: start)
        }
    }

    static func cueAt(_ demo: ExerciseDemo, at seconds: Double) -> DemoCuePhase {
        let list = cues(demo)
        let time = wrapped(seconds, cycleLength(demo))
        let index = max(0, list.lastIndex { time >= $0.start - 1e-9 } ?? 0)
        let cue = list[index], length = cue.steps.reduce(0) { $0 + demo.steps[$1].seconds }
        return DemoCuePhase(index: index, cue: cue, progress: clamp01((time - cue.start) / length),
                            left: Int((length - (time - cue.start) - 1e-6).rounded(.up)), length: length)
    }

    /// Frame that fits the whole move, between 2:1 and 2.6:1 with the floor near the bottom, so
    /// lying moves fill the card instead of hugging its bottom edge.
    static func viewBox(_ demo: ExerciseDemo, pad: Double = 10) -> CGRect {
        var minX = Double.infinity, minY = Double.infinity, maxX = -Double.infinity, maxY = floor + 4
        var seconds = 0.0
        while seconds < cycleLength(demo) {
            let body = frame(demo, at: seconds).body
            for point in body.segments.flatMap({ [$0.from, $0.to] }) {
                minX = min(minX, point.x - 5); maxX = max(maxX, point.x + 5); minY = min(minY, point.y - 5)
            }
            minX = min(minX, body.head.x - headRadius - 2); maxX = max(maxX, body.head.x + headRadius + 2)
            minY = min(minY, body.head.y - headRadius - 2)
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
        let round = { (value: Double) in (value * 10).rounded() / 10 }
        return CGRect(x: round(minX), y: round(minY), width: round(width), height: round(height))
    }
}

// MARK: - Hand-animated rigs

extension ExerciseDemos {
    /// The leg rises and lowers about the hip, so the foot draws an arc and the knee stays locked.
    static func straightLegRaise(_ seconds: Double) -> (mix: DemoMix, effort: Double) {
        let period = 7.4
        let tr = { (keys: [Key], lag: Double) in track(keys, seconds - lag, period) }
        let breath = sin(tau * seconds / 3.7), hip = CGPoint(x: 112, y: 116)
        let lift: [Key] = [(0, 0, .io), (0.6, 0, .io), (2.6, -38, .lift), (3.6, -39.5, .io), (6.6, 0, .ecc), (7.4, 0, .lin)]
        let thigh = tr(lift, 0)
        // Quad set before the lift (knee locks); it relaxes only after the heel is down.
        let flex = tr([(0, 5, .io), (0.45, 0, .io), (6.75, 0, .lin), (7.2, 5, .io), (7.4, 5, .lin)], 0)
        // Toes pull up first (anticipation) and flop out after landing (follow-through).
        let footRel = tr([(0, -60, .io), (0.5, -94, .io), (6.65, -94, .lin), (7.25, -60, .settle), (7.4, -60, .lin)], 0)
        let thighAngle = thigh - flex * 0.5, shinAngle = thighAngle + flex
        let knee = add(hip, dir(thighAngle, thighLength)), ankle = add(knee, dir(shinAngle, shinLength))
        let effort = clamp01(-thigh / 38) * 0.85 + (1 - flex / 5) * 0.15
        let shoulder = add(hip, dir(180 + breath * 0.8, torsoLength))
        let headPoint = add(shoulder, dir(198 + 5 * clamp01(-tr(lift, 0.25) / 38), neckLength))
        // Hands press into the floor a moment after the lift starts.
        func arm(_ bias: Double, _ lag: Double) -> DemoMixLimb {
            let press = clamp01(-tr(lift, lag) / 38), up = 1.2 + bias + press * 1.6
            let elbow = add(shoulder, dir(up, upperArmLength))
            return DemoMixLimb(joint: elbow, end: add(elbow, dir(up - 5 - press * 2, forearmLength)))
        }
        let mix = DemoMix(hip: hip, shoulder: shoulder, headPoint: headPoint, bend: -0.4 * (1 + breath),
                          near: DemoMixLimb(joint: knee, end: ankle, toe: shinAngle + footRel),
                          far: rigLeg(hip, CGPoint(x: 146, y: 115.5), up, 0), nearArm: arm(0, 0.2), farArm: arm(-0.8, 0.28))
        return (mix, effort)
    }

    /// The body pivots about the feet and the elbow: the hips swing up on an arc around the ankles
    /// with straight legs, and the shoulder finds its place over the planted elbow (nothing slides).
    static func sidePlank(_ seconds: Double) -> (mix: DemoMix, effort: Double) {
        let period = 7.2
        let tr = { (keys: [Key], lag: Double) in track(keys, seconds - lag, period) }
        let ankle = CGPoint(x: 153, y: 115.1), elbow = CGPoint(x: 70, y: 117)
        let lift: [Key] = [(0, 181.8, .io), (0.6, 181.8, .io), (1.8, 192.3, .lift), (3.6, 191, .io), (4.8, 192.2, .io), (6.3, 181.8, .ecc), (7.2, 181.8, .lin)]
        let effort = clamp01((tr(lift, 0) - 181.8) / 10.5)
        // The hold sags a touch, re-braces, and wobbles a little.
        let hipAt = { (lag: Double) in add(ankle, dir(tr(lift, lag) + 0.45 * sin(tau * (seconds - lag) / 1.6) * pow(effort, 3), 52.8)) }
        let hip = hipAt(0)
        let shoulder = solveToward(elbow, hip, upperArmLength, torsoLength, up).0
        // Head stays in line with the trunk, a moment behind it, lifting slightly under effort.
        let lateHip = hipAt(0.15), lateShoulder = solveToward(elbow, lateHip, upperArmLength, torsoLength, up).0
        let headPoint = add(shoulder, dir(angleOf(lateHip, lateShoulder) + 6 + 4 * effort + 0.6 * sin(tau * seconds / 3.7), neckLength))
        // Top hand rests on the hip and follows it a beat late.
        let hand = add(hipAt(0.12), CGPoint(x: -3, y: -5))
        let topElbow = solveToward(shoulder, hand, upperArmLength, forearmLength, up).0
        let mix = DemoMix(hip: hip, shoulder: shoulder, headPoint: headPoint,
                          near: rigLeg(hip, ankle, up, -62), far: rigLeg(hip, CGPoint(x: 151.5, y: 116.6), up, -62),
                          nearArm: DemoMixLimb(joint: elbow, end: CGPoint(x: elbow.x + forearmLength, y: 117)),
                          farArm: DemoMixLimb(joint: topElbow, end: hand))
        return (mix, effort)
    }

    /// Hips go back before they go down, and up before they come forward: a curved path. The gaze
    /// stays level, arms reach forward as counterbalance, and the bottom sways with small corrections.
    static func miniSquat(_ seconds: Double) -> (mix: DemoMix, effort: Double) {
        let period = 7.0
        let tr = { (keys: [Key], lag: Double) in track(keys, seconds - lag, period) }
        let depth: [Key] = [(0, 61.8, .io), (0.3, 61.2, .io), (3.3, 77, .lag), (4.3, 77.4, .io), (6.3, 61.8, .lead), (7, 61.8, .io)]
        let hold = pow(clamp01((tr(depth, 0) - 61.8) / 15.2), 4)
        let hipX = tr([(0, 107, .io), (0.3, 107.3, .io), (3.3, 94, .lead), (4.3, 93.6, .io), (6.3, 107, .lag), (7, 107, .io)], 0)
        let hip = CGPoint(x: 0.45 * sin(tau * seconds / 1.45) * hold + hipX, y: tr(depth, 0))
        let torso = tr([(0, -88, .io), (0.3, -90, .io), (3.3, -60, .lead), (4.3, -61, .io), (6.3, -91, .lag), (7, -88, .io)], 0)
        let shoulder = add(hip, dir(torso, torsoLength))
        let headPoint = add(shoulder, dir(-82 + (torso + 88) * 0.4, neckLength))
        // Forearms trail the upper arms.
        func arm(_ bias: Double, _ lag: Double) -> DemoMixLimb {
            let raise = tr([(0, 84, .io), (0.3, 86, .io), (3.3, 6, .io), (4.3, 4, .io), (6.3, 88, .settle), (7, 84, .io)], lag)
                + bias + 1.6 * sin(tau * (seconds + bias) / 2.3)
            let flex = tr([(0, 14, .io), (3.3, 4, .io), (4.3, 4, .io), (6.3, 20, .settle), (7, 14, .io)], lag + 0.12)
            let elbow = add(shoulder, dir(raise, upperArmLength))
            return DemoMixLimb(joint: elbow, end: add(elbow, dir(raise - flex, forearmLength)))
        }
        let bend = 0.35 * sin(tau * seconds / 3.7) + 0.6 * clamp01((-62 - torso) / -26)
        let mix = DemoMix(hip: hip, shoulder: shoulder, headPoint: headPoint, bend: bend,
                          near: rigLeg(hip, CGPoint(x: 109, y: 114), fwd, 8), far: rigLeg(hip, CGPoint(x: 106.5, y: 114), fwd, 8),
                          nearArm: arm(0, 0.18), farArm: arm(-3, 0.25))
        return (mix, clamp01((hip.y - 61.8) / 15.2))
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
            focus: ["nearThigh"], guide: "nearAnkle", peakAt: 3.1,
            poses: [
                "down": supine.with { $0.near = DemoLimb(foot: pt(165, 116), toe: -88); $0.far = DemoLimb(foot: pt(146, 116), toe: 0) },
                "up": supine.with { $0.near = DemoLimb(foot: pt(155, 86), toe: -122); $0.far = DemoLimb(foot: pt(146, 116), toe: 0) },
            ],
            effort: ["up": 1],
            steps: [step("down", 0.6, "Tighten thigh, toes up"), step("up", 2, "Lift straight leg"), step("up", 1, "Hold"),
                    step("down", 3, "Lower slowly"), step("down", 0.8, "Rest")],
            rig: { ExerciseDemos.straightLegRaise($0) }
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
            steps: [step("up", 2, "Push through heels"), step("up", 1.5, "Squeeze glutes"), step("down", 3, "Lower slowly"), step("down", 0.8, "Rest")]
        ),
        ExerciseDemo(
            key: "side-plank", title: "Side plank", match: #"side plank"#,
            focus: ["torso", "hip"], solid: true, guide: "hip", peakAt: 3.2,
            poses: [
                "down": DemoPose(hip: pt(100, 113), shoulder: pt(71, 98),
                                 near: DemoLimb(foot: pt(153, 115)), far: DemoLimb(foot: pt(151, 117)),
                                 nearArm: DemoLimb(hand: pt(87, 117), elbow: pt(70, 117)), farArm: DemoLimb(handRel: pt(28, 8), bend: -1)),
                "up": DemoPose(hip: pt(101, 104), shoulder: pt(70, 98),
                               near: DemoLimb(foot: pt(153, 115)), far: DemoLimb(foot: pt(151, 117)),
                               nearArm: DemoLimb(hand: pt(87, 117), elbow: pt(70, 117)), farArm: DemoLimb(handRel: pt(28, 8), bend: -1)),
            ],
            effort: ["up": 1],
            steps: [step("down", 0.6, "Brace"), step("up", 1.2, "Lift hips"), step("up", 3, "Hold, body in line"),
                    step("down", 1.5, "Lower"), step("down", 0.9, "Rest")],
            rig: { ExerciseDemos.sidePlank($0) }
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
            steps: [step("open", 1.5, "Open top knee"), step("open", 1, "Hold"), step("closed", 2.5, "Close slowly"), step("closed", 0.8, "Rest")]
        ),
        ExerciseDemo(
            key: "hip-abduction", title: "Side-lying hip abduction", match: #"abduct|side[- ]lying leg|side leg (lift|raise)"#,
            focus: ["hip", "nearThigh"], solid: true,
            poses: [
                "down": sideLying.with { $0.near = DemoLimb(foot: pt(165, 112), toe: -25); $0.far = DemoLimb(foot: pt(164, 116), toe: -25) },
                "up": sideLying.with { $0.near = DemoLimb(foot: pt(157, 82), toe: -55); $0.far = DemoLimb(foot: pt(164, 116), toe: -25) },
            ],
            effort: ["up": 1],
            steps: [step("up", 1.5, "Lift top leg"), step("up", 1, "Hold"), step("down", 2.5, "Lower slowly"), step("down", 0.8, "Rest")]
        ),
        ExerciseDemo(
            key: "wall-sit", title: "Wall sit", match: #"wall (sit|squat)|spanish squat"#,
            props: wall(55), focus: ["nearThigh", "farThigh"],
            poses: [
                "top": DemoPose(hip: pt(66, 68.6), torso: -90, near: DemoLimb(foot: pt(93, 114)), far: DemoLimb(foot: pt(91, 114)),
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
                                  nearArm: DemoLimb(hand: pt(167, 31.5)), farArm: DemoLimb(hand: pt(166, 33))),
                "stretch": DemoPose(hip: pt(118, 68), shoulder: pt(140, 36), near: DemoLimb(foot: pt(92, 114), toe: 5), far: DemoLimb(foot: pt(132, 114)),
                                    nearArm: DemoLimb(hand: pt(167, 31.5)), farArm: DemoLimb(hand: pt(166, 33))),
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
            steps: [step("up", 1.5, "Rise up"), step("up", 1, "Hold"), step("down", 3, "Lower slowly"), step("down", 0.8, "Rest")]
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
                "top": DemoPose(hip: pt(100, 54), torso: -88, near: DemoLimb(foot: pt(100, 106)), far: DemoLimb(foot: pt(118, 104)),
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
            steps: [step("low", 3, "Lower a little"), step("low", 1, "Pause"), step("top", 2, "Drive up"), step("top", 0.7, "Reset")]
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
            steps: [step("extend", 2, "Straighten knee"), step("extend", 2, "Hold, squeeze thigh"), step("bend", 3, "Lower slowly"), step("bend", 0.8, "Rest")]
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
            effort: ["reach": 1],
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
            effort: ["reach": 1],
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
            focus: ["nearThigh", "hip"], guide: "hip", peakAt: 3.8,
            poses: [
                "top": stand(107).with {
                    $0.near = DemoLimb(foot: pt(109, 114)); $0.far = DemoLimb(foot: pt(106.5, 114))
                    $0.nearArm = DemoLimb(handRel: pt(4, 36)); $0.farArm = DemoLimb(handRel: pt(2, 36))
                },
                "low": DemoPose(hip: pt(94, 77), torso: -60, near: DemoLimb(foot: pt(109, 114)), far: DemoLimb(foot: pt(106.5, 114)),
                                nearArm: DemoLimb(handRel: pt(36, 2)), farArm: DemoLimb(handRel: pt(34, 2))),
            ],
            effort: ["low": 1],
            steps: [step("top", 0.3, "Brace"), step("low", 3, "Sit hips back"), step("low", 1, "Pause"), step("top", 2, "Stand up"), step("top", 0.7, "Stand tall")],
            rig: { ExerciseDemos.miniSquat($0) }
        ),
    ]
}
