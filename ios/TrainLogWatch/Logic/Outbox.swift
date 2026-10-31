import Foundation

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

    var pending: [Write] {
        (try? Data(contentsOf: file)).flatMap { try? JSONDecoder().decode([Write].self, from: $0) } ?? []
    }

    func append(_ write: Write) {
        save(pending + [write])
    }

    /// Hands writes over oldest first and stops at the first one the phone didn't take, so they
    /// never arrive out of order. `deliver` returns whether the phone accepted it. Returns what's left.
    @discardableResult
    func flush(isolation: isolated (any Actor)? = #isolation, _ deliver: (Write) async -> Bool) async -> Int {
        var remaining = pending
        while let write = remaining.first {
            guard await deliver(write) else { break }
            remaining.removeFirst()
            save(remaining)
        }
        return remaining.count
    }

    private func save(_ writes: [Write]) {
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        if writes.isEmpty {
            try? FileManager.default.removeItem(at: file)
        } else if let data = try? JSONEncoder().encode(writes) {
            try? data.write(to: file, options: .atomic)
        }
    }
}
