import SwiftUI

struct PlanView: View {
    /// Tells the root to hide the tab bar while a day page is open.
    @Binding var showingDetail: Bool
    let onStartStrength: (Int?) -> Void
    @State private var model = PlanModel()
    @State private var path: [String] = []
    @State private var moving: PlanDay?

    var body: some View {
        NavigationStack(path: $path) {
            List {
                header.plainRow()
                if model.offline, let syncedAt = model.syncedAt {
                    Text("Offline · showing \(syncedAt.formatted(date: .omitted, time: .shortened)) data")
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.muted)
                        .plainRow()
                }
                if let week = model.week {
                    WeekSummaryCard(week: week, today: model.today).plainRow()
                    Section {
                        ForEach(PlanFormat.slots(week)) { slot in
                            row(slot)
                        }
                    }
                    if model.nextWeekMissing && week.weekStart == model.weeks.last?.weekStart {
                        Text("Next week isn't planned yet · plan it on the Mac")
                            .font(AppFont.body(12))
                            .foregroundStyle(Color.muted)
                            .frame(maxWidth: .infinity)
                            .plainRow()
                    }
                } else if model.loaded {
                    emptyCard.plainRow()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300).plainRow()
                }
            }
            .listStyle(.insetGrouped)
            .listSectionSpacing(12)
            .scrollContentBackground(.hidden)
            .scrollIndicators(.hidden)
            .contentMargins(.horizontal, 16, for: .scrollContent)
            .contentMargins(.top, 0, for: .scrollContent)
            .contentMargins(.bottom, TabBar.height, for: .scrollContent)
            .background(Color.bg)
            .toolbar(.hidden, for: .navigationBar)
            .navigationTitle("Plan")
            .refreshable {
                await APIClient.current.reconnect()
                await model.load()
            }
            .task { await model.load() }
            .navigationDestination(for: String.self) { date in
                PlanDayView(model: model, date: date, onMove: { moving = $0 }, onStartStrength: onStartStrength)
            }
        }
        .tint(.volt)
        .onChange(of: path) { showingDetail = !path.isEmpty }
        .sheet(item: $moving) { day in
            if let week = model.week {
                MoveDaySheet(source: day, slots: PlanFormat.slots(week), today: model.today) { target in
                    let error = await model.move(from: day.date, to: target)
                    if error == nil, path.last == day.date { path.removeLast() }
                    return error
                }
                .presentationDetents([.height(470)])
                .presentationBackground(Color(hex: 0x161A22))
            }
        }
    }

    @ViewBuilder
    private func row(_ slot: PlanSlot) -> some View {
        // A button rather than a NavigationLink: the artboard's rows have the ring, not a chevron.
        Button {
            path.append(slot.date)
        } label: {
            PlanRow(slot: slot, today: model.today).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(slot.day == nil)
        .listRowBackground(Color.card)
        .listRowSeparatorTint(Color.cardBorder)
        .listRowInsets(EdgeInsets(top: 0, leading: 14, bottom: 0, trailing: 14))
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            if PlanFormat.canMove(slot.day, today: model.today), let day = slot.day {
                Button {
                    moving = day
                } label: {
                    Label("Move", systemImage: "arrow.left.arrow.right")
                }
                .tint(Color.other)
            }
        }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(model.week.map { PlanFormat.weekKicker($0.weekStart) } ?? " ")
                Text("PLAN").font(AppFont.title(44)).foregroundStyle(Color.ink)
            }
            Spacer()
            HStack(spacing: 8) {
                pageButton("chevron.left", enabled: model.hasPrevious, label: "Previous week") { model.page(-1) }
                pageButton("chevron.right", enabled: model.hasNext, label: "Next week") { model.page(1) }
            }
            .padding(.bottom, 4)
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private func pageButton(_ icon: String, enabled: Bool, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(enabled ? Color.ink : Color.dim)
                .frame(width: 36, height: 36)
                .overlay(Circle().strokeBorder(enabled ? Color.outline : Color.cardBorder))
                .frame(width: 44, height: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
    }

    private var emptyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(model.error == nil ? "No plan yet" : "Not synced yet")
            Text(model.error ?? "There's no weekly plan on the server.").font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Text("Plans are written on the Mac. Pull to refresh once one is saved.")
                .font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .card()
    }
}

/// The week's headline, focus and how much of it is done.
private struct WeekSummaryCard: View {
    let week: WeeklyPlan
    let today: String

    var body: some View {
        let summary = PlanFormat.summary(week, today: today)
        VStack(alignment: .leading, spacing: 0) {
            if let title = PlanFormat.shortTitle(week.title) {
                Text(title.uppercased()).font(AppFont.title(22)).foregroundStyle(Color.ink)
            }
            if let focus = week.focus, !focus.isEmpty {
                Text(focus)
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.muted)
                    .lineSpacing(2)
                    .lineLimit(3)
                    .padding(.top, 5)
            }
            HStack(alignment: .firstTextBaseline) {
                Text("\(Text("\(summary.done)").foregroundStyle(Color.ink).bold()) of \(summary.sessions) done")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                Spacer()
                let done = Text(TodayFormat.duration(summary.doneMinutes)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                let planned = Text(" of \(TodayFormat.duration(summary.plannedMinutes))").font(AppFont.body(12)).foregroundStyle(Color.muted)
                Text("\(done)\(planned)")
            }
            .padding(.top, 12)
            progressBar(summary).padding(.top, 8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func progressBar(_ summary: PlanFormat.Summary) -> some View {
        GeometryReader { geo in
            let total = Double(max(summary.plannedMinutes, summary.doneMinutes, 1))
            HStack(spacing: 2) {
                ForEach(summary.bySport, id: \.sport) { part in
                    Rectangle().fill(part.sport.color).frame(width: geo.size.width * Double(part.minutes) / total)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(height: 6)
        .background(Color.track)
        .clipShape(Capsule())
    }
}

/// Day column, sport bar, title and meta, then the same ring as Today's week.
struct PlanRow: View {
    let slot: PlanSlot
    let today: String

    var body: some View {
        let status = PlanFormat.status(slot.day, today: today)
        let isToday = slot.date == today
        let sport = slot.day.map(PlanFormat.sport) ?? .rest
        HStack(spacing: 12) {
            VStack(spacing: 2) {
                Text(weekday)
                    .font(AppFont.body(10, weight: isToday ? .bold : .semibold))
                    .tracking(1)
                    .foregroundStyle(isToday ? Color.volt : Color.muted)
                Text(dayNumber).font(AppFont.number(20)).foregroundStyle(isToday ? Color.volt : Color.ink)
            }
            .frame(width: 30)
            RoundedRectangle(cornerRadius: 2).fill(sport.color).frame(width: 4, height: 34)
            VStack(alignment: .leading, spacing: 3) {
                Text(slot.day.map { PlanFormat.rowTitle($0.title) } ?? "Free day")
                    .font(AppFont.body(15, weight: .semibold))
                    .foregroundStyle(slot.day == nil ? Color.muted : Color.ink)
                    .lineLimit(1)
                if let day = slot.day {
                    Text(PlanFormat.meta(day, today: today))
                        .font(AppFont.body(12))
                        .foregroundStyle(status == .missed ? Color.warning : Color.muted)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            PlanRing(status: status, sport: sport, isToday: isToday)
        }
        .padding(.vertical, 10)
        .frame(minHeight: 58)
        // Past finished days step back so the rest of the week reads first.
        .opacity(slot.date < today && status != .missed ? 0.62 : 1)
        .accessibilityElement(children: .combine)
    }

    private var weekday: String {
        FoodFormat.parse(slot.date)?.formatted(.dateTime.weekday(.abbreviated).locale(Locale(identifier: "en_GB"))).uppercased() ?? ""
    }

    private var dayNumber: String {
        FoodFormat.parse(slot.date).map { "\(ActivityFormat.mondayCalendar.component(.day, from: $0))" } ?? ""
    }
}

/// Filled = done, outline = planned, volt ring around it = today.
struct PlanRing: View {
    let status: PlanDayStatus
    let sport: Sport
    let isToday: Bool

    var body: some View {
        ZStack {
            switch status {
            case .done:
                Circle().fill(sport.color)
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.bg)
            case .replaced:
                Circle().fill(Color.raised)
                Image(systemName: "arrow.left.arrow.right").font(.system(size: 10, weight: .bold)).foregroundStyle(Color.muted)
            case .skipped, .missed:
                Circle().strokeBorder(Color.dim, lineWidth: 2)
                Image(systemName: "xmark").font(.system(size: 9, weight: .bold)).foregroundStyle(Color.faint)
            case .planned:
                Circle().strokeBorder(sport.color.opacity(0.45), lineWidth: 2)
            case .rest:
                Circle().fill(Color.dim).frame(width: 5, height: 5)
            }
        }
        .frame(width: 26, height: 26)
        .padding(4)
        .overlay {
            if isToday { Circle().strokeBorder(Color.volt, lineWidth: 2) }
        }
    }
}

private extension View {
    /// A list row with no card behind it (header, summary).
    func plainRow() -> some View {
        listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
            .listRowInsets(EdgeInsets(top: 4, leading: 0, bottom: 4, trailing: 0))
    }
}
