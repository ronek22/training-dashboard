import Foundation
import Observation
import UIKit

/// `/running/fitness` for the Today run card and the pace guide, plus the after-run felt tap.
@MainActor
@Observable
final class RunModel {
    static let path = "/running/fitness"
    static let answeredKey = "runFeelAnswered"
    static let dismissedKey = "runFeelDismissed"

    private(set) var fitness: RunningFitness?
    /// Felt taps made here, so the sheet doesn't come back before the server has them.
    private(set) var answered: [String: RunFeel]
    private var dismissed: Set<String>

    private let client: () -> APIClient
    private let queue: WriteQueue
    private let defaults: UserDefaults

    init(client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue(), defaults: UserDefaults = .standard) {
        self.client = client
        self.queue = queue
        self.defaults = defaults
        let stored = defaults.dictionary(forKey: Self.answeredKey) as? [String: String] ?? [:]
        answered = stored.compactMapValues(RunFeel.init(rawValue:))
        dismissed = Set(defaults.stringArray(forKey: Self.dismissedKey) ?? [])
    }

    func load() async {
        let api = client()
        if fitness == nil, let cached = api.cached(Self.path, as: RunningFitness.self) {
            fitness = Self.demo(cached.value)
        }
        guard let loaded = try? await api.get(Self.path, as: RunningFitness.self) else { return }
        guard !Task.isCancelled else { return }
        fitness = Self.demo(loaded.value)
    }

    /// The last runs with this phone's taps folded in (the server may not have them yet).
    var feltRuns: [RunningFitness.FeltRun] {
        (fitness?.felt ?? []).map { run in
            var run = run
            if run.felt == nil { run.felt = answered[run.activityId] }
            return run
        }
    }

    func pendingFeel(today: String) -> RunningFitness.FeltRun? {
        #if DEBUG
        if UserDefaults.standard.bool(forKey: "runDemoFelt"), let last = fitness?.felt?.last { return last }
        #endif
        return RunFormat.pendingFeel(fitness?.felt ?? [], today: today, answered: Set(answered.keys), dismissed: dismissed)
    }

    func dismiss(_ run: RunningFitness.FeltRun) {
        dismissed.insert(run.activityId)
        defaults.set(Array(dismissed.suffix(30)), forKey: Self.dismissedKey)
    }

    /// Saves the tap (and the pain score when asked), queued when the Mac is away.
    func save(_ feel: RunFeel, pain: Int?, for run: RunningFitness.FeltRun) async {
        answered[run.activityId] = feel
        defaults.set(answered.mapValues(\.rawValue), forKey: Self.answeredKey)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        let encodedID = run.activityId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? run.activityId
        var writes: [WriteQueue.Write] = [
            .init(method: "PUT", path: "/activities/\(encodedID)/felt", body: try? APIClient.encoder.encode(RunFeelInput(felt: feel))),
        ]
        if let pain {
            writes.append(.init(method: "PUT", path: "/activities/\(encodedID)/symptoms", body: try? APIClient.encoder.encode(RunSymptomInput(during: pain))))
        }
        #if DEBUG
        // Screenshots of the sheet shouldn't write to the real server.
        if UserDefaults.standard.bool(forKey: "runDemoFelt") { return }
        #endif
        let api = client()
        await queue.flush(with: api)
        for (index, write) in writes.enumerated() {
            do {
                try await api.send(write.method, write.path, body: write.body)
            } catch APIError.unreachable {
                writes[index...].forEach(queue.append)
                return
            } catch {
                // Refused (an activity merged away since): the tap is kept here, nothing to retry.
                return
            }
        }
        await load()
    }

    /// `-runDemo rtr` previews the Return-to-run card on a stage 3 program.
    private static func demo(_ fitness: RunningFitness) -> RunningFitness {
        #if DEBUG
        if UserDefaults.standard.string(forKey: "runDemo") == "rtr" {
            var fitness = fitness
            let names = ["Run/walk 1:2", "Run/walk 2:1", "Run/walk 5:1", "Continuous 20 min", "Continuous 30–40 min", "Back to normal running"]
            var blocks = [RunningFitness.Block(kind: "walk", minutes: 5)]
            for _ in 0..<4 { blocks += [.init(kind: "jog", minutes: 5), .init(kind: "walk", minutes: 1)] }
            fitness.returnToRun = .init(active: true, stage: 3, stageName: names[2], stages: 6, stageNames: names,
                                        minutes: 30, blocks: blocks, paceTarget: false, symptom: "Knee")
            return fitness
        }
        #endif
        return fitness
    }
}
