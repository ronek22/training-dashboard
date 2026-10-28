import SwiftUI

struct ActivitiesView: View {
    /// Tells the root to hide the tab bar while a detail page is open.
    @Binding var showingDetail: Bool
    @State private var model = ActivitiesModel()
    @State private var path = NavigationPath()
    @State private var feedbackFor: ActivitySummary?
    @State private var ratingFor: ActivitySummary?

    var body: some View {
        NavigationStack(path: $path) {
            List {
                header
                    .plainRow()
                if !model.sports.isEmpty {
                    chips.plainRow()
                }
                if model.offline, let syncedAt = model.syncedAt {
                    Text("Offline · showing \(syncedAt.formatted(date: .omitted, time: .shortened)) data")
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.muted)
                        .plainRow()
                }
                if model.loaded && model.activities.isEmpty {
                    emptyCard.plainRow()
                } else if !model.loaded {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300).plainRow()
                }
                ForEach(model.weeks) { week in
                    Section {
                        ForEach(week.activities) { activity in
                            NavigationLink(value: activity.id) {
                                ActivityRow(activity: activity)
                            }
                            .listRowBackground(Color.card)
                            .listRowSeparatorTint(Color.cardBorder)
                            .listRowInsets(EdgeInsets(top: 0, leading: 14, bottom: 0, trailing: 14))
                            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                Button("Pain") { feedbackFor = activity }.tint(Color(hex: 0xC2475A))
                                Button("Rate") { ratingFor = activity }.tint(Color.raised)
                            }
                        }
                    } header: {
                        Kicker(week.title)
                            .padding(.leading, -12)
                            .padding(.top, 2)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .listSectionSpacing(14)
            .scrollContentBackground(.hidden)
            .scrollIndicators(.hidden)
            .contentMargins(.horizontal, 16, for: .scrollContent)
            .contentMargins(.top, 0, for: .scrollContent)
            .contentMargins(.bottom, TabBar.height, for: .scrollContent)
            .background(Color.bg)
            .toolbar(.hidden, for: .navigationBar)
            .navigationTitle("Activities")
            .refreshable { await model.sync() }
            .task { await model.load() }
            .navigationDestination(for: String.self) { id in
                ActivityDetailView(id: id, summary: model.activities.first { $0.id == id }) { input in
                    Task { await model.saveFeedback(input, for: id) }
                }
            }
            .navigationDestination(for: TrendsRoute.self) { _ in TrendsView() }
        }
        .tint(.volt)
        .onChange(of: path) { showingDetail = !path.isEmpty }
        .sheet(item: $feedbackFor) { activity in
            FeedbackSheet(title: activity.title, existing: activity.feedback) { input in
                Task { await model.saveFeedback(input, for: activity.id) }
            }
        }
        .confirmationDialog("How was it?", isPresented: rating, titleVisibility: .visible, presenting: ratingFor) { activity in
            Button("Loved it") { Task { await model.rate(activity, verdict: "loved") } }
            Button("Fine") { Task { await model.rate(activity, verdict: "fine") } }
            Button("Hated it") { Task { await model.rate(activity, verdict: "hated") } }
        } message: { activity in
            Text(activity.title)
        }
    }

    private var rating: Binding<Bool> {
        Binding(get: { ratingFor != nil }, set: { if !$0 { ratingFor = nil } })
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(syncedKicker)
                Text("ACTIVITIES").font(AppFont.title(44)).foregroundStyle(Color.ink)
            }
            Spacer()
            Button {
                path.append(TrendsRoute())
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "chart.xyaxis.line")
                    Text("Trends")
                }
                .font(AppFont.body(13, weight: .semibold))
                .foregroundStyle(Color.ink)
                .padding(.horizontal, 14)
                .frame(height: 36)
                .overlay(Capsule().strokeBorder(Color.outline))
                .frame(minHeight: 44)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .padding(.bottom, 2)
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private var syncedKicker: String {
        guard let syncedAt = model.syncedAt else { return " " }
        let minutes = Int(Date.now.timeIntervalSince(syncedAt) / 60)
        switch minutes {
        case ..<1: return "Synced just now"
        case ..<60: return "Synced \(minutes) min ago"
        default: return "Synced \(syncedAt.formatted(date: .abbreviated, time: .shortened))"
        }
    }

    private var chips: some View {
        ScrollView(.horizontal) {
            HStack(spacing: 8) {
                chip(nil, "All")
                ForEach(model.sports, id: \.self) { sport in
                    chip(sport, sport.label)
                }
            }
            .padding(.horizontal, 4)
        }
        .scrollIndicators(.hidden)
        .padding(.horizontal, -4)
    }

    private func chip(_ sport: Sport?, _ title: String) -> some View {
        let selected = model.filter == sport
        return Button {
            model.filter = sport
        } label: {
            HStack(spacing: 6) {
                if let sport {
                    RoundedRectangle(cornerRadius: 2).fill(sport.color).frame(width: 8, height: 8)
                }
                Text(title).font(AppFont.body(13, weight: .semibold))
            }
            .foregroundStyle(selected ? Color.bg : Color.inkSoft)
            .padding(.horizontal, 14)
            .frame(height: 32)
            .background(selected ? Color.ink : .clear, in: Capsule())
            .overlay(Capsule().strokeBorder(selected ? .clear : Color.outline))
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var emptyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(model.error == nil ? "Nothing yet" : "Not synced yet")
            Text(model.error ?? "No activities on the server.").font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Text("Start the backend on the Mac (docker compose up) and pull to refresh.")
                .font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .card()
    }
}

/// Sport bar, title and the one thing that matters on the left; one headline number on the right.
struct ActivityRow: View {
    let activity: ActivitySummary

    var body: some View {
        let subtitle = ActivityFormat.subtitle(activity)
        let headline = ActivityFormat.headline(activity)
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 2)
                .fill(ActivityFormat.sport(activity).color)
                .frame(width: 4, height: 34)
            VStack(alignment: .leading, spacing: 3) {
                Text(activity.title)
                    .font(AppFont.body(15, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .lineLimit(1)
                let plain = Text(subtitle.plain + (subtitle.highlight == nil ? "" : " · ")).foregroundStyle(Color.muted)
                let highlight = Text(subtitle.highlight?.text ?? "").foregroundStyle(color(subtitle.highlight?.tone))
                Text("\(plain)\(highlight)")
                    .font(AppFont.body(12))
                    .lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 2) {
                let number = Text(headline.value).font(AppFont.number(20)).foregroundStyle(Color.ink)
                let unit = Text(headline.unit).font(AppFont.body(12)).foregroundStyle(Color.muted)
                Text("\(number)\(unit)")
                let detail = ActivityFormat.detail(activity)
                if !detail.isEmpty {
                    Text(detail).font(AppFont.body(11)).foregroundStyle(Color.muted)
                }
            }
        }
        .padding(.vertical, 11)
        .frame(minHeight: 60)
    }

    private func color(_ tone: ActivityFormat.Highlight.Tone?) -> Color {
        switch tone {
        case .pain: Color(hex: 0xFF7A7A)
        case .win: .volt
        case .muted, nil: .muted
        }
    }
}

private extension View {
    /// A list row with no card behind it (header, chips).
    func plainRow() -> some View {
        listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
            .listRowInsets(EdgeInsets(top: 4, leading: 0, bottom: 4, trailing: 0))
    }
}
