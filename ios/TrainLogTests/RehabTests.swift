import Foundation
import Testing
@testable import TrainLog

struct RehabTests {
    private let sample = """
    {"session": {"key": "rehab", "title": "Rehab routine", "type": "Workout", "watch_workout": "Core Training",
      "context": "rehab", "context_label": "Rehab", "layout": "sets", "rounds": 1, "rest_seconds": 30,
      "issues": ["Left knee"], "duration_min": 14, "steps": ["Quad isometric 2 × 30 s"],
      "exercises": [
        {"issue_id": 2, "issue_title": "Left knee", "index": 0, "name": "Quad isometric", "dose": "2 x 30 sec, daily",
         "cue": "Press the knee down.", "sets": 2, "per_side": false, "frequency": {"kind": "daily", "label": "daily"},
         "seconds": 30, "done": false, "due": true},
        {"issue_id": 2, "issue_title": "Left knee", "index": 3, "name": "Clamshell", "dose": "1 x 8-10/side",
         "cue": "", "sets": 1, "per_side": true, "frequency": {"kind": "daily", "label": "daily"},
         "reps": 8, "range": "8–10", "done": false, "due": true}
      ]}}
    """

    private func session() throws -> GuidedSession {
        try APIClient.decoder.decode(GuidedSessionEnvelope.self, from: Data(sample.utf8)).session
    }

    @Test func buildsStraightSetsWithRestsAndSides() throws {
        let steps = RehabFormat.steps(try session())
        #expect(steps.map(\.kind) == [.exercise, .rest, .exercise, .exercise, .exercise])
        #expect(steps[1].seconds == 30)
        #expect(steps[3].side == "Left side")
        #expect(steps[4].side == "Right side")
        // Only an exercise's last step ticks it, with the routine's own index.
        #expect(steps[2].completes == .init(issueId: 2, index: 0))
        #expect(steps[4].completes == .init(issueId: 2, index: 3))
        #expect(steps.filter { $0.completes != nil }.count == 2)
    }

    @Test func formatsDoseAndKicker() throws {
        let steps = RehabFormat.steps(try session())
        #expect(RehabFormat.dose(steps[0]) == "0:30")
        #expect(RehabFormat.dose(steps[3]) == "×8–10")
        #expect(RehabFormat.kicker(steps[0]) == "Exercise 1 of 2 · Set 1 of 2")
        #expect(RehabFormat.kicker(steps[1]) == "Rest")
        #expect(RehabFormat.kicker(steps[3]) == "Exercise 2 of 2")
        #expect(RehabFormat.upNext(steps[2], after: steps[0]) == "Set 2 of 2 · 0:30")
        #expect(RehabFormat.upNext(steps[3], after: steps[2]) == "Clamshell · left side ×8–10")
        #expect(RehabFormat.upNext(steps[4], after: steps[3]) == "Same set · right side · ×8–10")
    }

    @Test func todayCardFollowsTheNextPart() {
        // Ride + rehab: the ride's steps until the Watch workout syncs, then the rehab.
        #expect(TodayFormat.next(isStrength: false, rehabOnly: false, mainDone: false, rehabLeft: 8) == .openSession)
        #expect(TodayFormat.next(isStrength: false, rehabOnly: false, mainDone: true, rehabLeft: 8) == .startRehab)
        #expect(TodayFormat.next(isStrength: false, rehabOnly: false, mainDone: true, rehabLeft: 0) == .allDone)
        #expect(TodayFormat.next(isStrength: true, rehabOnly: false, mainDone: false, rehabLeft: nil) == .startStrength)
        #expect(TodayFormat.next(isStrength: true, rehabOnly: false, mainDone: true, rehabLeft: nil) == .allDone)
        #expect(TodayFormat.next(isStrength: false, rehabOnly: true, mainDone: false, rehabLeft: 5) == .startRehab)
    }
}

struct ExerciseDemoTests {
    @Test func matchesTodaysRoutineByName() {
        #expect(ExerciseDemos.demo(for: "Quad isometric")?.key == "quad-set")
        #expect(ExerciseDemos.demo(for: "Side-lying hip abduction")?.key == "hip-abduction")
        #expect(ExerciseDemos.demo(for: "Side plank (knees bent if needed)")?.key == "side-plank")
        #expect(ExerciseDemos.demo(for: "Shallow wall sit isometric")?.key == "wall-sit")
        #expect(ExerciseDemos.demo(for: "Sit-to-stand to a high chair")?.key == "sit-to-stand")
        #expect(ExerciseDemos.demo(for: "Hamstring and glute stretch (gentle)")?.key == "hamstring-stretch")
        #expect(ExerciseDemos.demo(for: "Breathing") == nil)
    }

    @Test func limbsKeepTheirLength() throws {
        let demo = try #require(ExerciseDemos.demo(for: "Glute bridge"))
        for seconds in stride(from: 0.0, to: ExerciseDemos.cycleLength(demo), by: 0.37) {
            let thigh = try #require(ExerciseDemos.frame(demo, at: seconds).body.segment("nearThigh"))
            #expect(abs(hypot(thigh.to.x - thigh.from.x, thigh.to.y - thigh.from.y) - 27) < 0.05)
        }
    }

    @Test func mergesCuesAndFramesTheMove() throws {
        let demo = try #require(ExerciseDemos.demo(for: "Quad isometric"))
        #expect(ExerciseDemos.cues(demo).map(\.label) == ["Tighten thigh", "Press knee down", "Relax"])
        #expect(ExerciseDemos.cues(demo).last?.seconds == 2)
        let box = ExerciseDemos.viewBox(demo)
        #expect(box.width / box.height >= 2 - 0.001 && box.width / box.height <= 2.6 + 0.001)
        // Every demo's poses resolve and its peak pose draws.
        for demo in ExerciseDemos.all {
            #expect(!FigureShapes.parts(ExerciseDemos.peakFrame(demo).body).isEmpty)
        }
    }

    @Test func countsDownTheRunningCue() throws {
        let demo = try #require(ExerciseDemos.demo(for: "Straight leg raise"))
        let hold = ExerciseDemos.cueAt(demo, at: 2.7)
        #expect(hold.cue.label == "Hold")
        #expect(hold.left == 1)
        #expect(abs(hold.progress - 0.1) < 0.001)
        #expect(ExerciseDemos.cueAt(demo, at: ExerciseDemos.cycleLength(demo) + 0.1).index == 0)
    }

    @Test func plantedFeetNeverSlide() throws {
        let demo = try #require(ExerciseDemos.demo(for: "Glute bridge"))
        let start = try #require(ExerciseDemos.frame(demo, at: 0).body.joints["nearAnkle"])
        for seconds in stride(from: 0.0, to: ExerciseDemos.cycleLength(demo), by: 0.13) {
            let ankle = try #require(ExerciseDemos.frame(demo, at: seconds).body.joints["nearAnkle"])
            #expect(hypot(ankle.x - start.x, ankle.y - start.y) < 0.01)
        }
    }

    // The web engine's own samples (frontend/scripts/export-demo-frames.mjs): the port must draw
    // the same body at the same moment, so the two apps animate alike.
    private struct Fixture: Decodable {
        struct Sample: Decodable {
            let joints: [String: [Double]]
            let bend: Double
            let effort: Double
            let step: Int
        }
        struct Frame: Decodable {
            let seconds: Double
            let joints: [String: [Double]]
            let bend: Double
            let effort: Double
            let step: Int
            let cue: Int
            let left: Int
        }
        struct Demo: Decodable {
            let key: String
            let cycle: Double
            let guide: String?
            let peak: Sample
            let frames: [Frame]
        }
        let demos: [Demo]
    }

    private func expectClose(_ joints: [String: CGPoint], _ expected: [String: [Double]], _ label: String) {
        #expect(Set(joints.keys) == Set(expected.keys), "\(label)")
        for (key, value) in expected {
            guard let point = joints[key] else { continue }
            #expect(abs(point.x - value[0]) < 0.05 && abs(point.y - value[1]) < 0.05,
                    "\(label) \(key): \(point.x), \(point.y) vs \(value[0]), \(value[1])")
        }
    }

    @Test func matchesTheWebEngine() throws {
        let url = try #require(Bundle(for: FixtureToken.self).url(forResource: "demo-frames", withExtension: "json"))
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: url))
        #expect(fixture.demos.map(\.key) == ExerciseDemos.all.map(\.key))
        for expected in fixture.demos {
            let demo = try #require(ExerciseDemos.all.first { $0.key == expected.key })
            #expect(abs(ExerciseDemos.cycleLength(demo) - expected.cycle) < 1e-9, "\(expected.key) cycle")
            #expect(ExerciseDemos.guideJoint(demo) == expected.guide, "\(expected.key) guide")
            let peak = ExerciseDemos.peakFrame(demo)
            expectClose(peak.body.joints, expected.peak.joints, "\(expected.key) peak")
            #expect(abs(peak.effort - expected.peak.effort) < 0.05, "\(expected.key) peak effort")
            for sample in expected.frames {
                let frame = ExerciseDemos.frame(demo, at: sample.seconds)
                let label = "\(expected.key) @\(sample.seconds)"
                expectClose(frame.body.joints, sample.joints, label)
                #expect(abs(frame.body.bend - sample.bend) < 0.05, "\(label) bend")
                #expect(abs(frame.effort - sample.effort) < 0.05, "\(label) effort")
                #expect(frame.step == sample.step, "\(label) step")
                let cue = ExerciseDemos.cueAt(demo, at: sample.seconds)
                #expect(cue.index == sample.cue && cue.left == sample.left, "\(label) cue")
            }
        }
    }
}

private final class FixtureToken {}

@MainActor
struct RehabDiscardTests {
    /// Records every write and answers 200, without a server.
    final class Recorder: URLProtocol, @unchecked Sendable {
        nonisolated(unsafe) static var writes: [(String, String, Data?)] = []
        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func startLoading() {
            let body = request.httpBodyStream.map { stream -> Data in
                stream.open(); defer { stream.close() }
                var data = Data(); var buffer = [UInt8](repeating: 0, count: 4096)
                while stream.hasBytesAvailable { let n = stream.read(&buffer, maxLength: 4096); if n <= 0 { break }; data.append(buffer, count: n) }
                return data
            } ?? request.httpBody
            Self.writes.append((request.httpMethod ?? "", request.url?.path ?? "", body))
            client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data("{}".utf8))
            client?.urlProtocolDidFinishLoading(self)
        }
        override func stopLoading() {}
    }

    @Test func discardUnticksWhatTheSessionTicked() async throws {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [Recorder.self]
        var api = APIClient(baseURL: "http://test.local")
        api.session = URLSession(configuration: config)
        let queue = WriteQueue(file: FileManager.default.temporaryDirectory.appending(path: "discard-\(UUID()).json"))
        let model = RehabSessionModel(client: { api }, queue: queue, today: "2026-10-29")
        let session = try APIClient.decoder.decode(GuidedSessionEnvelope.self, from: Data("""
        {"session": {"key": "rehab", "title": "Rehab routine", "rest_seconds": 0, "duration_min": 1,
          "exercises": [{"issue_id": 2, "issue_title": "Knee", "index": 4, "name": "Glute bridge", "sets": 1, "per_side": false, "reps": 12},
                        {"issue_id": 2, "issue_title": "Knee", "index": 5, "name": "Calf raise", "sets": 1, "per_side": false, "reps": 12}]}}
        """.utf8)).session
        Recorder.writes = []
        model.prepare(session)
        model.start()
        model.next()   // passes the glute bridge: ticks index 4
        await model.discard()
        let ticks = Recorder.writes.filter { $0.1 == "/recovery/issues/2/ticks" }
        #expect(!Recorder.writes.contains { $0.1 == "/guided-sessions/complete" })
        #expect(ticks.count == 2)
        let last = try JSONSerialization.jsonObject(with: try #require(ticks.last?.2)) as? [String: Any]
        #expect(last?["done"] as? Bool == false)
        #expect(last?["index"] as? Int == 4)
    }
}
