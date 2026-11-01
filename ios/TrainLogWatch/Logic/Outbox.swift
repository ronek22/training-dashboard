import Foundation
import os

private let logger = Logger(subsystem: "com.ronek22.trainlog.watchkitapp", category: "outbox")

/// Writes the Watch made while the iPhone was out of reach (in a bag, out of Bluetooth range),
/// handed to it in order once it's back. Kept on disk so a logged set survives the app restarting.
struct Outbox: Sendable {
    struct Write: Codable, Sendable, Equatable {
        let method: String
        let path: String
        var body: Data?
    }

    var file: URL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appending(path: "watch-outbox.json")

    /// A file that's there but doesn't decode is moved aside rather than read as empty, so the next
    /// `append` can't overwrite the sets in it.
    var pending: [Write] {
        guard let data = try? Data(contentsOf: file) else { return [] }
        do {
            return try JSONDecoder().decode([Write].self, from: data)
        } catch {
            let aside = file.deletingPathExtension().appendingPathExtension("unreadable-\(Int(Date.now.timeIntervalSince1970)).json")
            try? FileManager.default.moveItem(at: file, to: aside)
            logger.fault("Outbox didn't decode, kept as \(aside.lastPathComponent, privacy: .public): \(error)")
            return []
        }
    }

    func append(_ write: Write) {
        save(pending + [write])
    }

    /// Hands writes over oldest first and stops at the first one the phone didn't take, so they
    /// never arrive out of order. `deliver` returns whether the phone accepted it. Returns what's left.
    /// Reads the file again after every delivery: a write appended while one was in flight (the
    /// effort tap right after a set) is kept and sent in the same flush.
    @discardableResult
    func flush(isolation: isolated (any Actor)? = #isolation, _ deliver: (Write) async -> Bool) async -> Int {
        while let write = pending.first {
            guard await deliver(write) else {
                logger.info("Outbox flush stopped at \(write.path, privacy: .public), \(pending.count) left")
                break
            }
            var remaining = pending
            if remaining.first == write { remaining.removeFirst() }
            save(remaining)
        }
        return pending.count
    }

    private func save(_ writes: [Write]) {
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        if writes.isEmpty {
            try? FileManager.default.removeItem(at: file)
        } else {
            do {
                try JSONEncoder().encode(writes).write(to: file, options: .atomic)
            } catch {
                logger.fault("Outbox not saved (\(writes.count) writes): \(error)")
            }
        }
    }
}
