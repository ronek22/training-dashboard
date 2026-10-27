import Foundation

enum APIError: LocalizedError {
    case badURL(String)
    case status(Int)
    case unreachable

    var errorDescription: String? {
        switch self {
        case .badURL(let url): "Server address \(url) isn't a valid URL."
        case .status(let code): "Server answered \(code)."
        case .unreachable: "Can't reach the TrainLog server."
        }
    }
}

/// A decoded response, and whether it came from the on-device cache because the server was unreachable.
struct Loaded<Value: Sendable>: Sendable {
    let value: Value
    let syncedAt: Date
    let fromCache: Bool
}

/// The one place that knows the base URL, decoding rules and offline cache.
struct APIClient: Sendable {
    static let baseURLKey = "serverBaseURL"
    /// The Simulator reaches the Mac directly; a phone needs the Mac's Wi-Fi address (Settings).
    static let defaultBaseURL = "http://localhost:8000"

    var baseURL: String
    var session: URLSession = .shared
    var cache = ResponseCache()

    static var current: APIClient {
        APIClient(baseURL: UserDefaults.standard.string(forKey: baseURLKey) ?? defaultBaseURL)
    }

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    /// GET that falls back to the last good response when the server is unreachable.
    func get<T: Decodable & Sendable>(_ path: String, as type: T.Type = T.self) async throws -> Loaded<T> {
        do {
            let data = try await fetch(path)
            let value = try Self.decoder.decode(T.self, from: data)
            cache.store(data, for: path)
            return Loaded(value: value, syncedAt: .now, fromCache: false)
        } catch let error as DecodingError {
            throw error
        } catch {
            guard let cached = cache.load(path) else { throw error }
            let value = try Self.decoder.decode(T.self, from: cached.data)
            return Loaded(value: value, syncedAt: cached.savedAt, fromCache: true)
        }
    }

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    /// GET without the offline fallback, for state that must be live (an active workout).
    func getLive<T: Decodable & Sendable>(_ path: String, as type: T.Type = T.self) async throws -> T {
        try Self.decoder.decode(T.self, from: try await fetch(path))
    }

    /// POST / PUT / DELETE with an already-encoded JSON body.
    @discardableResult
    func send(_ method: String, _ path: String, body: Data? = nil) async throws -> Data {
        try await fetch(path, method: method, body: body)
    }

    func send<T: Decodable & Sendable>(_ method: String, _ path: String, body: Data? = nil, as type: T.Type) async throws -> T {
        try Self.decoder.decode(T.self, from: try await fetch(path, method: method, body: body))
    }

    private func fetch(_ path: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        guard let url = URL(string: baseURL.trimmingCharacters(in: .init(charactersIn: "/")) + path) else {
            throw APIError.badURL(baseURL)
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 8
        request.httpMethod = method
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.unreachable
        }
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw APIError.status(http.statusCode)
        }
        return data
    }
}

/// Writes made while the server was unreachable, replayed in order once it's back. Kept in
/// Application Support so a logged set survives the app being killed.
struct WriteQueue: Sendable {
    struct Write: Codable, Sendable, Equatable {
        let method: String
        let path: String
        let body: Data?
    }

    var file: URL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appending(path: "write-queue.json")

    var pending: [Write] {
        (try? Data(contentsOf: file)).flatMap { try? JSONDecoder().decode([Write].self, from: $0) } ?? []
    }

    func append(_ write: Write) {
        save(pending + [write])
    }

    /// Sends queued writes in order. Stops at the first unreachable one; drops writes the server
    /// rejects (e.g. a set in a workout finished on the web) so one bad write can't block the rest.
    /// Returns whether the queue is now empty.
    @discardableResult
    func flush(with client: APIClient) async -> Bool {
        var remaining = pending
        while let write = remaining.first {
            do {
                try await client.send(write.method, write.path, body: write.body)
            } catch APIError.status(let code) where (400..<500).contains(code) {
                // Rejected for good; fall through and drop it.
            } catch {
                save(remaining)
                return false
            }
            remaining.removeFirst()
        }
        save(remaining)
        return true
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

/// Last good response per path, in Caches.
struct ResponseCache: Sendable {
    var directory: URL = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        .appending(path: "api", directoryHint: .isDirectory)

    func store(_ data: Data, for path: String) {
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try? data.write(to: file(for: path), options: .atomic)
    }

    func load(_ path: String) -> (data: Data, savedAt: Date)? {
        let url = file(for: path)
        guard let data = try? Data(contentsOf: url) else { return nil }
        let savedAt = (try? url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
        return (data, savedAt)
    }

    private func file(for path: String) -> URL {
        let name = path.replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "?", with: "_")
        return directory.appending(path: name + ".json")
    }
}
