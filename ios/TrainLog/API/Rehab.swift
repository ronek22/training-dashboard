import Foundation

/// `GET /guided-sessions/rehab` (backend/app/services/rehab_session.py): today's rehab routine as a
/// follow-along session. Only exercises still due today; ticked ones are already left out.
struct GuidedSession: Decodable, Sendable {
    let key: String
    let title: String
    let watchWorkout: String?
    let restSeconds: Int
    let issues: [String]?
    let exercises: [Exercise]
    let durationMin: Int

    struct Exercise: Decodable, Sendable {
        let issueId: Int?
        let issueTitle: String?
        let index: Int?
        let name: String
        let cue: String?
        let dose: String?
        let sets: Int?
        let perSide: Bool
        let reps: Int?
        let seconds: Int?
        /// "8–10" or "20–30 s" when the dose gave a range; reps/seconds hold its lower end.
        let range: String?
    }
}

/// `GET /guided-sessions/{key}` wraps the session.
struct GuidedSessionEnvelope: Decodable, Sendable {
    let session: GuidedSession
}

/// `POST /guided-sessions/complete`.
struct GuidedCompletion: Encodable, Sendable {
    let sessionKey: String
    let startedAt: String
    let elapsedSeconds: Int
    let completedSteps: Int
    var extras: [String] = []
}

/// `POST /recovery/issues/{id}/checkins`.
struct RecoveryCheckin: Encodable, Sendable {
    let pain: Int
    let didPlan: Bool
    let note: String
}
