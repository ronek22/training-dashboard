import CoreLocation
import SwiftUI

@MainActor
@Observable
final class ActivityDetailModel {
    private(set) var detail: ActivityDetail?
    private(set) var feedback: ActivityFeedback?
    /// Your usual running form and the good ranges, for runs with a FIT file.
    private(set) var form: RunningFitness.Form?
    /// Town under the route's start, for the map header.
    private(set) var place: String?
    private(set) var offline = false
    private(set) var syncedAt: Date?
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
            syncedAt = loaded.syncedAt
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        guard let detail else { return }
        if detail.runDynamics != nil { await loadForm() }
        if place == nil, detail.mountainRegion == nil, let start = ActivityDetailFormat.route(detail)?.first { await locate(start) }
    }

    private func loadForm() async {
        let path = "/running/fitness"
        if form == nil { form = client().cached(path, as: RunningFitness.self)?.value.form }
        if let loaded = try? await client().get(path, as: RunningFitness.self, timeout: 15) {
            form = loaded.value.form
        }
    }

    private func locate(_ coordinate: CLLocationCoordinate2D) async {
        let location = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        let placemark = try? await CLGeocoder().reverseGeocodeLocation(location).first
        place = placemark?.locality ?? placemark?.subAdministrativeArea
    }

    /// Queues a written analysis; the coach runner picks it up and the section shows it on reload.
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

    /// "Offline · last synced 2 h ago · pull to retry".
    var offlineLine: String? {
        guard offline, let syncedAt else { return nil }
        let ago = syncedAt.formatted(.relative(presentation: .numeric, unitsStyle: .abbreviated))
        return "Offline · last synced \(ago) · pull to retry"
    }
}

/// D2 (docs/design/artboards/iOSActivityDetailV3.dc.html): a visual leads, one title, a coloured
/// grid, then calm sections on the background with depth behind "Show more". Laps, segments and
/// the coach chat stay on the web page.
struct ActivityDetailView: View {
    let summary: ActivitySummary?
    let onSaveFeedback: (ActivityFeedbackInput) -> Void
    @State private var model: ActivityDetailModel
    @State private var editingFeedback = false
    @State private var sheet: SheetKind?
    @State private var showMap = false
    @State private var scrolled = false
    @Environment(\.dismiss) private var dismiss

    enum SheetKind: Identifiable {
        case metric(String)
        case coach(ActivityDetailFormat.CoachTake)

        var id: String {
            switch self {
            case .metric(let key): key
            case .coach: "coach"
            }
        }
    }

    init(id: String, summary: ActivitySummary?, onSaveFeedback: @escaping (ActivityFeedbackInput) -> Void) {
        self.summary = summary
        self.onSaveFeedback = onSaveFeedback
        _model = State(initialValue: ActivityDetailModel(id: id))
    }

    private var activity: ActivitySummary? { model.detail?.activity ?? summary }

    var body: some View {
        let visual = model.detail.map(ActivityDetailFormat.visual)
        let headerHeight = DetailHeaderView.height(visual) ?? 300
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if let activity {
                    DetailHeaderView(header: ActivityDetailFormat.header(activity, detail: model.detail, place: model.place),
                                     visual: visual, offlineLine: model.offlineLine,
                                     placeholderHeight: model.detail == nil ? 220 : nil)
                }
                Group {
                    if let detail = model.detail {
                        content(detail)
                    } else if let error = model.error {
                        DetailSection(nil) {
                            StatusLine(tone: .warn, text: "Not loaded: \(error)").padding(.top, 24)
                        }
                    } else {
                        loading
                    }
                }
                .padding(.horizontal, 16)
            }
            .padding(.bottom, 40)
        }
        .onScrollGeometryChange(for: Bool.self) { geometry in
            geometry.contentOffset.y + geometry.contentInsets.top > headerHeight - 150
        } action: { _, value in
            withAnimation(.easeOut(duration: 0.2)) { scrolled = value }
        }
        .scrollIndicators(.hidden)
        .ignoresSafeArea(edges: .top)
        .background(Color.bg)
        .overlay(alignment: .top) { topBar(visual) }
        .toolbar(.hidden, for: .navigationBar)
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
        .sheet(item: $sheet) { kind in
            switch kind {
            case .metric(let key):
                if let detail = model.detail { MetricSheet(detail: detail, key: key) }
            case .coach(let take):
                CoachSheet(take: take)
            }
        }
        .fullScreenCover(isPresented: $showMap) {
            if case let .route(coordinates, fractions)? = visual {
                RouteMapScreen(coordinates: coordinates, fractions: fractions)
            }
        }
    }

    // MARK: Top bar

    private func topBar(_ visual: ActivityDetailFormat.Visual?) -> some View {
        HStack(spacing: 12) {
            GlassCircleButton(symbol: "chevron.left", label: "Back") { dismiss() }
            Spacer(minLength: 0)
            if case .route? = visual {
                GlassCircleButton(symbol: "map", label: "Full-screen map") { showMap = true }
            }
            if let url = ActivityDetailFormat.stravaURL(model.id) {
                ShareLink(item: url) {
                    Image(systemName: "square.and.arrow.up")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(Color.ink)
                        .frame(width: 44, height: 44)
                        .background(.ultraThinMaterial, in: Circle())
                        .background(Color(hex: 0x12151C).opacity(0.72), in: Circle())
                        .overlay(Circle().strokeBorder(Color.white.opacity(0.08)))
                        .environment(\.colorScheme, .dark)
                }
                .accessibilityLabel("Share")
            }
        }
        .overlay {
            if scrolled, let activity {
                Text(activity.title)
                    .font(AppFont.body(16, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .lineLimit(1)
                    .padding(.horizontal, 120)
                    .transition(.opacity)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 8)
        .background {
            if scrolled {
                Color.bg.opacity(0.92).background(.ultraThinMaterial).ignoresSafeArea(edges: .top)
                    .overlay(alignment: .bottom) { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                    .transition(.opacity)
            }
        }
    }

    // MARK: Content

    private var loading: some View {
        VStack(alignment: .leading, spacing: 0) {
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 16), GridItem(.flexible())], alignment: .leading, spacing: 24) {
                ForEach(0..<4, id: \.self) { _ in
                    VStack(alignment: .leading, spacing: 8) {
                        Skeleton(width: 70, height: 10)
                        Skeleton(width: 90, height: 28)
                        Skeleton(width: 110, height: 10)
                    }
                }
            }
            .padding(.top, 32)
            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 32)
            Skeleton(width: 120, height: 14).padding(.top, 24)
            Skeleton(height: 140, radius: 14).padding(.top, 16)
        }
    }

    @ViewBuilder
    private func content(_ detail: ActivityDetail) -> some View {
        let sport = ActivityFormat.sport(detail.activity)
        let pain = ActivityDetailFormat.painAlert(model.feedback)
        let streams = ActivityDetailFormat.hasStreams(detail)
        let cells = ActivityDetailFormat.grid(detail)
        let hasVisual = DetailHeaderView.height(ActivityDetailFormat.visual(detail)) != nil

        if let pain { PainBlock(pain: pain.pain, note: pain.note) }
        if !cells.isEmpty {
            MetricGrid(cells: cells) { sheet = .metric("watts") }
                .padding(.top, pain == nil ? (hasVisual ? 12 : 28) : 24)
                .reveal(0)
        }
        if model.feedback == nil {
            LogFeelPrompt { editingFeedback = true }
        }
        if [.run, .ride, .strength].contains(sport), let read = ActivityDetailFormat.sessionRead(detail) {
            SessionReadSection(read: read)
        }
        if sport == .strength {
            let lifts = ActivityDetailFormat.liftRows(detail)
            if !lifts.isEmpty { LiftsSection(rows: lifts, comparedTo: ActivityDetailFormat.liftsComparedTo(detail)) }
        }
        if !streams {
            NoStreamsPlaceholder()
        } else if sport != .mobility && sport != .other {
            let chips = ActivityDetailFormat.chips(detail)
            if sport == .strength {
                MainChartSection(detail: detail, chips: chips, fixedTitle: "Heart rate") { sheet = .metric($0) }
            } else if !chips.isEmpty {
                MainChartSection(detail: detail, chips: chips) { sheet = .metric($0) }
            }
        }
        if sport == .run {
            let splits = ActivityDetailFormat.splits(detail)
            if !splits.isEmpty {
                SplitsSection(rows: splits, lines: ActivityDetailFormat.splitLines(splits)) { sheet = .metric("pace") }
            }
            let form = ActivityDetailFormat.form(detail, fitness: model.form)
            if !form.isEmpty {
                RunningFormSection(cells: form, summary: ActivityDetailFormat.formSummary(form)) { sheet = .metric("pace") }
            }
        }
        if [.run, .ride].contains(sport) {
            let hr = ActivityDetailFormat.zoneRows(detail.heartRateZones)
            let power = sport == .ride ? ActivityDetailFormat.zoneRows(detail.powerZones) : []
            if !hr.isEmpty || !power.isEmpty {
                ZonesSection(heartRate: hr, power: power, summary: ActivityDetailFormat.zoneSummary(detail)) {
                    sheet = .metric(hr.isEmpty ? "watts" : "heartrate")
                }
            }
        }
        if sport == .ride {
            let compared = ActivityDetailFormat.compared(detail)
            if !compared.isEmpty { ComparedSection(cells: compared) }
            let bests = ActivityDetailFormat.powerBests(detail)
            if !bests.isEmpty { PowerBestsSection(rows: bests) }
        }
        if sport == .run {
            let efforts = ActivityDetailFormat.bestEfforts(detail)
            if !efforts.isEmpty { BestEffortsSection(rows: efforts) }
        }
        let feel = ActivityDetailFormat.feel(model.feedback)
        if !feel.isEmpty {
            FeelSection(cells: feel, note: pain?.note == nil ? model.feedback?.note?.nilIfEmpty : nil) { editingFeedback = true }
        }
        if let win = ActivityDetailFormat.win(detail) { WinRow(win: win) }
        let coach = ActivityDetailFormat.coachState(detail.analysis)
        if coach != .none && sport != .mobility && sport != .other {
            CoachSection(state: coach, asking: model.asking, offline: model.offline, sport: coachNoun(sport)) {
                Task { await model.askCoach() }
            } onMore: {
                if case .take(let take) = coach { sheet = .coach(take) }
            }
            if let askError = model.askError {
                Text(askError).font(AppFont.body(12)).foregroundStyle(Color.danger).padding(.top, 8)
            }
        }
    }

    private func coachNoun(_ sport: Sport) -> String {
        switch sport {
        case .ride: "ride"
        case .run: "run"
        case .hike: "hike"
        case .walk: "walk"
        case .strength: "lift"
        default: "session"
        }
    }
}

extension UINavigationController: @retroactive UIGestureRecognizerDelegate {
    /// Keeps swipe-back working on pages that hide the navigation bar for their own back button.
    override open func viewDidLoad() {
        super.viewDidLoad()
        interactivePopGestureRecognizer?.delegate = self
    }

    public func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        viewControllers.count > 1
    }
}
