import SwiftUI

@MainActor
@Observable
final class ActivityDetailModel {
    private(set) var detail: ActivityDetail?
    private(set) var feedback: ActivityFeedback?
    private(set) var paces: RunningPaces.Paces.Zones?
    private(set) var offline = false
    private(set) var error: String?
    private(set) var asking = false
    private(set) var askError: String?

    let id: String
    private let client: () -> APIClient

    init(id: String, client: @escaping () -> APIClient = { .current }) {
        self.id = id
        self.client = client
    }

    func load() async {
        if detail == nil, let cached = client().cached("/activities/\(id)", as: ActivityDetail.self) {
            detail = cached.value
            feedback = cached.value.feedback
        }
        do {
            // The first open of an activity can fetch streams from Strava, so allow longer.
            let loaded = try await client().get("/activities/\(id)", as: ActivityDetail.self, timeout: 30)
            detail = loaded.value
            feedback = loaded.value.feedback
            offline = loaded.fromCache
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        if let detail, ActivityFormat.sport(detail.activity) == .run {
            await loadPaces()
        }
    }

    /// Training paces for the run pace gauge; the gauge goes plain without them.
    private func loadPaces() async {
        let path = "/running/fitness"
        if paces == nil { paces = client().cached(path, as: RunningPaces.self)?.value.paces?.zones }
        if let loaded = try? await client().get(path, as: RunningPaces.self, timeout: 15) {
            paces = loaded.value.paces?.zones
        }
    }

    /// Queues a written analysis; the coach runner picks it up and the card shows it on reload.
    func askCoach() async {
        asking = true
        askError = nil
        defer { asking = false }
        do {
            let body = try JSONSerialization.data(withJSONObject: ["force_refresh": false])
            let analysis = try await client().send("POST", "/activities/\(id)/analysis", body: body, as: ActivityDetail.Analysis.self, timeout: 30)
            detail?.analysis = analysis
        } catch {
            askError = "Couldn't reach the coach. Try again at home."
        }
    }

    /// Shows saved feedback straight away; the list model sends it.
    func showFeedback(_ input: ActivityFeedbackInput) {
        feedback = ActivityFeedback(rpe: input.rpe, energy: input.energy, muscleSoreness: input.muscleSoreness,
                                    painLevel: input.painLevel, note: input.note)
    }
}

/// Read-only, phone-sized: one skeleton for every sport, with cards that appear when the backend
/// has the data (docs/design/artboards/iOSActivityDetail.dc.html). Laps, segments and the coach
/// chat stay on the web page.
struct ActivityDetailView: View {
    let summary: ActivitySummary?
    let onSaveFeedback: (ActivityFeedbackInput) -> Void
    @State private var model: ActivityDetailModel
    @State private var editingFeedback = false

    init(id: String, summary: ActivitySummary?, onSaveFeedback: @escaping (ActivityFeedbackInput) -> Void) {
        self.summary = summary
        self.onSaveFeedback = onSaveFeedback
        _model = State(initialValue: ActivityDetailModel(id: id))
    }

    private var activity: ActivitySummary? { model.detail?.activity ?? summary }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let activity {
                    header(activity)
                }
                if let detail = model.detail {
                    content(detail)
                } else if let error = model.error {
                    VStack(alignment: .leading, spacing: 8) {
                        Kicker("Not loaded")
                        Text(error).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    }
                    .card()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 240)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let url = ActivityDetailFormat.stravaURL(model.id) {
                ToolbarItem(placement: .topBarTrailing) {
                    ShareLink(item: url) { Image(systemName: "square.and.arrow.up") }
                        .tint(.inkSoft)
                }
            }
        }
        .smoothRefreshable {
            await APIClient.current.reconnect()
            await model.load()
        }
        .task { await model.load() }
        .sheet(isPresented: $editingFeedback) {
            FeedbackSheet(title: activity?.title ?? "", existing: model.feedback) { input in
                model.showFeedback(input)
                onSaveFeedback(input)
            }
        }
    }

    private func header(_ activity: ActivitySummary) -> some View {
        let sport = ActivityFormat.sport(activity)
        let chips = model.detail.map(ActivityDetailFormat.chips) ?? []
        return VStack(alignment: .leading, spacing: 6) {
            Kicker(ActivityDetailFormat.kicker(activity), color: sport.color)
            Text(activity.title.uppercased())
                .font(AppFont.title(36))
                .foregroundStyle(Color.ink)
                .fixedSize(horizontal: false, vertical: true)
            if !chips.isEmpty {
                FlowLayout(spacing: 6) {
                    ForEach(chips, id: \.self) { chip in
                        Text(chip)
                            .font(AppFont.body(12, weight: .semibold))
                            .foregroundStyle(Color.inkSoft)
                            .padding(.horizontal, 10)
                            .frame(height: 24)
                            .overlay(Capsule().strokeBorder(Color.outline))
                    }
                }
                .padding(.top, 4)
            }
        }
        .padding(.horizontal, 4)
    }

    @ViewBuilder
    private func content(_ detail: ActivityDetail) -> some View {
        let sport = ActivityFormat.sport(detail.activity)
        let pain = ActivityDetailFormat.painAlert(model.feedback)
        if let pain {
            PainAlertCard(pain: pain.pain, note: pain.note)
        }
        // Virtual rides carry the game world's route; it isn't where you were.
        if detail.cycling?.environment != "indoor", let polyline = detail.route?.polyline, case let coordinates = ActivityDetailFormat.decodePolyline(polyline), coordinates.count >= 2 {
            RouteMapCard(coordinates: coordinates, color: sport.color, tags: mapTags(detail))
        }
        StatBlockCard(block: ActivityDetailFormat.statBlock(detail, paces: model.paces))
        if let win = detail.win, win.headline?.nilIfEmpty != nil {
            WinStrip(win: win)
        }
        if let read = ActivityDetailFormat.sessionRead(detail) {
            SessionReadView(read: read)
        }
        let lifts = ActivityDetailFormat.liftRows(detail)
        if !lifts.isEmpty {
            LiftsCard(rows: lifts, comparedTo: liftsComparedTo(detail))
        }
        if let charts = ActivityDetailFormat.chartSet(detail) {
            StreamChartCard(charts: charts)
        }
        let hrZones = ActivityDetailFormat.zoneRows(detail.heartRateZones, unit: "bpm")
        let powerZones = ActivityDetailFormat.zoneRows(detail.powerZones, unit: "W")
        if !hrZones.isEmpty || !powerZones.isEmpty {
            ZonesCard(heartRate: hrZones, power: powerZones)
        }
        if let load = ActivityDetailFormat.loadTiles(detail.cycling) {
            LoadCard(note: load.note, tiles: load.tiles)
        }
        if let efforts = detail.cycling?.powerEfforts, !efforts.isEmpty {
            BestPowerCard(efforts: efforts)
        }
        if sport == .run, let efforts = detail.bestEfforts?.efforts, !efforts.isEmpty {
            BestEffortsCard(efforts: efforts)
        }
        FeelCard(feedback: model.feedback, showNote: pain?.note == nil) { editingFeedback = true }
        let coach = ActivityDetailFormat.coachState(detail.analysis)
        if coach != .none {
            CoachCard(state: coach, asking: model.asking) {
                Task { await model.askCoach() }
            }
            if let askError = model.askError {
                Text(askError).font(AppFont.body(12)).foregroundStyle(Color.danger).padding(.horizontal, 4)
            }
        }
    }

    private func mapTags(_ detail: ActivityDetail) -> [String] {
        var tags: [String] = []
        if let km = ActivityDetailFormat.number(detail, "distance_km") {
            tags.append("\(km.formatted(ActivityFormat.oneDecimal)) km")
        }
        if let climb = ActivityDetailFormat.number(detail, "elevation_m"), climb >= 10 {
            tags.append("↑ \(Int(climb.rounded())) m")
        }
        return tags
    }

    /// "vs 10 Oct" when every lift was compared with the same session.
    private func liftsComparedTo(_ detail: ActivityDetail) -> String? {
        let dates = Set(detail.strengthDetail?.progression?.exercises.values.compactMap { $0.previous?.date } ?? [])
        guard dates.count == 1, let date = dates.first else { return dates.isEmpty ? nil : "vs last time" }
        return "vs \(ActivityFormat.longDay(date).split(separator: " ").dropFirst().joined(separator: " "))"
    }
}
