import SwiftUI

/// Ask the coach to rewrite today: four quick asks (or a session on a rest day), the wait, then
/// was → now on the same tape. The job is the Plan tab's one-day revision (`PlanCoachTask.day`).
struct ChangeTodaySheet: View {
    @Bindable var coach: PlanCoachModel
    let plan: PlanModel
    let date: String
    /// Today as it was when the sheet opened; the tape's Now (and Was once it changed).
    let now: ChangeTodayFormat.Session
    let readiness: PhoneToday.Readiness?
    /// The plan's own short version: Short on time shows it on the card without the coach.
    let fallback: String?
    let canMove: Bool
    let onShort: () -> Void
    let onMove: () -> Void
    @Environment(\.dismiss) private var dismiss
    @FocusState private var typing: Bool
    @State private var ask: ChangeTodayFormat.Ask?
    @State private var choice: ChangeTodayFormat.Choice?
    @State private var restSport: Sport?
    @State private var restMinutes = 30
    @State private var note = ""
    #if DEBUG
    var demoAfter: (ChangeTodayFormat.Session, String?)? = ChangeTodayDemo.after
    #endif

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SheetGrabber()
            switch coach.phase {
            case .compose: compose
            case .working(let stage): working(stage)
            case .done(let result): done(result)
            case .failed(let message): failed(message)
            }
        }
        .padding(.horizontal, Space.gutter)
        .padding(.top, 8)
        .padding(.bottom, 16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(Motion.quick, value: coach.phase)
        .onAppear(perform: preselect)
        .onChange(of: coach.phase) {
            // Keep the first version of the day: "Change again" shouldn't hide what the plan said.
            if case .done(let result) = coach.phase, !result.changes.isEmpty {
                let key = ChangeTodayFormat.trailKey(date)
                if UserDefaults.standard.string(forKey: key) == nil {
                    UserDefaults.standard.set(ChangeTodayFormat.trail(now), forKey: key)
                }
            }
        }
    }

    // MARK: - Compose

    private var picked: ChangeTodayFormat.Choice? {
        if now.isRest { return restSport.map { .session($0, restMinutes) } }
        return choice
    }

    private var hasFallback: Bool { fallback != nil }

    /// The plan's short version needs no coach: it shows on the card straight away.
    private var instant: Bool { picked == .planShort }

    private var canAsk: Bool {
        if instant { return true }
        guard coach.helper != .away, !isDown else { return false }
        return !ChangeTodayFormat.feedback(picked, note: note, now: now).isEmpty
    }

    private var isDown: Bool {
        if case .down = coach.helper { return true }
        return false
    }

    @ViewBuilder
    private var compose: some View {
        head(kicker: kicker, title: now.isRest ? "Add a session" : "Change today")
        if !now.isRest, readiness?.suggestsSwap == true {
            readinessLine.padding(.top, 14)
        }
        ChangeTape(rows: composeRows, scale: scale(picked)).padding(.top, 16)
        if now.isRest {
            segment(ChangeTodayFormat.restSports.map { ChangeTodayFormat.Choice.session($0, restMinutes) }, selected: picked) { pick in
                if case .session(let sport, _) = pick { restSport = restSport == sport ? nil : sport }
            }
            .padding(.top, 16)
            segment(ChangeTodayFormat.restMinutes.map { ChangeTodayFormat.Choice.minutes($0) }, selected: .minutes(restMinutes)) { pick in
                if case .minutes(let m) = pick { restMinutes = m }
            }
            .padding(.top, 8)
        } else {
            tiles.padding(.top, 16)
            if let ask {
                segment(ChangeTodayFormat.options(ask, now: now, hasFallback: hasFallback), selected: choice) { pick in
                    choice = pick
                }
                .padding(.top, 10)
            }
        }
        if !instant {
            noteField.padding(.top, 12)
        }
        Spacer(minLength: 12)
        if !instant { helperState }
        if canMove, !now.isRest {
            Button {
                dismiss()
                onMove()
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.left.arrow.right")
                    Text("Move it to another day")
                    Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold)).foregroundStyle(Color.faint)
                }
                .font(AppFont.body(14, weight: .semibold))
                .foregroundStyle(Color.inkSoft)
                .frame(maxWidth: .infinity, minHeight: 44)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        Button(instant ? "Use the short version" : "Ask coach") { send() }
            .buttonStyle(AskButtonStyle(enabled: canAsk))
            .disabled(!canAsk)
        Text(instant ? "Shows on the card · the plan stays as it is" : "Only today changes · the rest of the week stays")
            .font(AppFont.body(12))
            .foregroundStyle(Color.muted)
            .frame(maxWidth: .infinity)
            .padding(.top, 10)
    }

    private func preselect() {
        guard ask == nil, choice == nil, case .compose = coach.phase else { return }
        #if DEBUG
        if let demo = ChangeTodayDemo.pick(now) {
            ask = demo.ask
            choice = demo.choice
            note = demo.note
            if case .session(let sport, let minutes)? = demo.choice {
                restSport = sport
                restMinutes = minutes
            }
            return
        }
        #endif
        if let (ask, choice) = ChangeTodayFormat.initial(suggestsSwap: readiness?.suggestsSwap == true, now: now) {
            self.ask = ask
            self.choice = choice
        }
    }

    private func send() {
        typing = false
        if instant {
            Haptics.selection()
            dismiss()
            onShort()
            return
        }
        coach.note = ChangeTodayFormat.feedback(picked, note: note, now: now)
        coach.send()
    }

    private var kicker: String {
        let day = ActivityFormat.shortDay(date).prefix(3)
        if now.isRest { return "\(day) · Rest day" }
        return [String(day), PlanFormat.rowTitle(now.title), now.minutes > 0 ? "\(now.minutes) min" : nil]
            .compactMap { $0 }.joined(separator: " · ")
    }

    private var readinessLine: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Circle().fill(Color.alert).frame(width: 8, height: 8)
            (Text("Readiness ") + Text((readiness?.label ?? "low").lowercased()).foregroundStyle(Color.dangerStrong).bold()
             + Text(" · \(ChangeTodayFormat.readinessLine(readiness?.factors ?? [])) The coach sees this too."))
                .font(AppFont.body(13))
                .foregroundStyle(Color.inkBody)
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private var composeRows: [ChangeTape.Row] {
        var rows = [nowRow(faded: false)]
        if let ghost = ChangeTodayFormat.ghost(picked, now: now) {
            rows.append(.init(key: now.isRest ? "Add" : "Ask", minutes: ghost.minutes, color: ghost.sport.color, label: ghost.label, style: .ghost))
        }
        return rows
    }

    private func nowRow(faded: Bool) -> ChangeTape.Row {
        if now.isRest {
            return .init(key: faded ? "Was" : "Now", minutes: 0, color: .dim, label: "Rest", style: faded ? .faded : .solid)
        }
        let label = faded ? PlanFormat.rowTitle(now.title).components(separatedBy: " + ").first ?? "" : "\(now.minutes) min"
        return .init(key: faded ? "Was" : "Now", minutes: now.minutes, color: now.sport.color, label: label, style: faded ? .faded : .solid)
    }

    private func scale(_ choice: ChangeTodayFormat.Choice?) -> Int {
        ChangeTodayFormat.scale(now.minutes, ChangeTodayFormat.ghost(choice, now: now)?.minutes ?? 0)
    }

    private var tiles: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)], spacing: 8) {
            ForEach(ChangeTodayFormat.Ask.allCases) { item in
                let on = ask == item
                Button {
                    Haptics.selection()
                    if on {
                        ask = nil
                        choice = nil
                    } else {
                        ask = item
                        choice = ChangeTodayFormat.options(item, now: now, hasFallback: hasFallback).first
                    }
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: item.symbol)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(on ? Color.ink : Color.inkSoft)
                            .frame(width: 30, height: 30)
                            .background(on ? Color.outline : Color.cardBorder, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                        VStack(alignment: .leading, spacing: 1) {
                            Text(item.title).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                            Text(ChangeTodayFormat.subtitle(item, hasFallback: hasFallback))
                                .font(AppFont.body(11.5)).foregroundStyle(Color.muted)
                        }
                        .lineLimit(1)
                        .minimumScaleFactor(0.85)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, 12)
                    .frame(minHeight: 58)
                    .background(on ? Color.cardBorder : Color.inset, in: RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: Radius.tile, style: .continuous).strokeBorder(on ? Color.ink : Color.cardBorder))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }

    private func segment(_ options: [ChangeTodayFormat.Choice], selected: ChangeTodayFormat.Choice?,
                         pick: @escaping (ChangeTodayFormat.Choice) -> Void) -> some View {
        HStack(spacing: 6) {
            ForEach(options, id: \.self) { option in
                let on = option == selected
                Button {
                    Haptics.selection()
                    pick(option)
                } label: {
                    HStack(spacing: 6) {
                        if let sport = sport(of: option) {
                            Circle().fill(sport.color).frame(width: 6, height: 6)
                        }
                        Text(ChangeTodayFormat.label(option)).lineLimit(1).minimumScaleFactor(0.8)
                    }
                    .font(AppFont.body(13, weight: .semibold))
                    .foregroundStyle(on ? Color.bg : Color.inkBody)
                    .frame(maxWidth: .infinity, minHeight: 36)
                    .background(on ? Color.ink : .clear, in: Capsule())
                    .overlay(Capsule().strokeBorder(on ? Color.ink : Color.outline))
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }

    private func sport(of choice: ChangeTodayFormat.Choice) -> Sport? {
        switch choice {
        case .sport(let sport), .session(let sport, _): sport
        default: nil
        }
    }

    private var noteField: some View {
        TextField("Anything else? (optional)", text: $note, axis: .vertical)
            .font(AppFont.body(14))
            .foregroundStyle(Color.ink)
            .tint(.volt)
            .lineLimit(1...3)
            .focused($typing)
            .padding(.horizontal, 14)
            .padding(.vertical, 13)
            .frame(minHeight: 48, alignment: .leading)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: Radius.tile, style: .continuous).strokeBorder(Color.cardBorder))
    }

    @ViewBuilder
    private var helperState: some View {
        let others = [hasFallback && !now.isRest ? "Short on time" : nil, canMove && !now.isRest ? "Move day" : nil].compactMap { $0 }
        let still = others.isEmpty ? "" : " \(others.joined(separator: " and ")) still \(others.count == 1 ? "works" : "work")."
        switch coach.helper {
        case .down(let detail):
            stateCard(color: .run, title: "Coach is offline", text: detail + still).padding(.bottom, 12)
        case .away:
            stateCard(color: .faint, title: "Mac out of reach", text: "The coach runs on the Mac.\(still)").padding(.bottom, 12)
        case .unknown, .up:
            EmptyView()
        }
    }

    // MARK: - Working

    @ViewBuilder
    private func working(_ stage: String) -> some View {
        head(kicker: kicker, title: "Changing…")
        ChangeTape(rows: [nowRow(faded: false),
                          .init(key: "New", minutes: max(now.minutes, 30), color: .raised, label: "", style: .pending)],
                   scale: ChangeTodayFormat.scale(now.minutes))
            .padding(.top, 16)
        HStack(alignment: .top, spacing: 12) {
            ProgressView().tint(.volt).padding(.top, 1)
            VStack(alignment: .leading, spacing: 3) {
                Text(stage == "The coach is working" ? "Rewriting today" : stage)
                    .font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                if let startedAt = coach.startedAt {
                    Text("Coach on the Mac · started \(startedAt.formatted(date: .omitted, time: .shortened))")
                        .font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            }
            Spacer(minLength: 8)
            if let startedAt = coach.startedAt {
                TimelineView(.periodic(from: .now, by: 1)) { context in
                    Text(PlanCoachFormat.clock(Int(context.date.timeIntervalSince(startedAt))))
                        .font(AppFont.number(22))
                        .foregroundStyle(Color.ink)
                        .monospacedDigit()
                }
            }
        }
        .padding(.top, 20)
        if !coach.sent.isEmpty {
            (Text("You asked: ").foregroundStyle(Color.muted) + Text(coach.sent).foregroundStyle(Color.inkSoft))
                .font(AppFont.body(13))
                .lineSpacing(2)
                .lineLimit(4)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous).strokeBorder(Color.cardBorder))
                .padding(.top, 16)
        }
        Spacer(minLength: 12)
        Button("Close · keeps going on the Mac") { dismiss() }
            .buttonStyle(OutlineButtonStyle(height: 48))
            .font(AppFont.body(14, weight: .semibold))
    }

    // MARK: - Done

    /// Today after the job, from the reloaded plan.
    private var after: (session: ChangeTodayFormat.Session, details: String?)? {
        #if DEBUG
        if let demoAfter { return (demoAfter.0, demoAfter.1) }
        #endif
        guard let day = plan.day(date) else { return nil }
        let sport = PlanFormat.sport(day)
        return (ChangeTodayFormat.Session(sport: sport, minutes: day.targetDurationMin ?? 0, title: day.title), day.details)
    }

    @ViewBuilder
    private func done(_ result: PlanCoachResult) -> some View {
        let after = self.after
        let changed = !result.changes.isEmpty
        head(kicker: "\(changed ? "Changed" : "Checked") · \(PlanCoachFormat.clock(result.seconds))", kickerColor: .volt,
             title: doneTitle(after?.session, changed: changed))
        if let after = after?.session {
            let rows: [ChangeTape.Row] = changed
                ? [nowRow(faded: true),
                   .init(key: "Now", minutes: after.minutes, color: after.sport.color,
                         label: after.isRest ? "Rest" : "\(after.minutes) min", style: .solid)]
                : [nowRow(faded: false)]
            ChangeTape(rows: rows, scale: ChangeTodayFormat.scale(now.minutes, after.minutes)).padding(.top, 16)
            if changed, !after.isRest {
                Text(PlanFormat.rowTitle(after.title).uppercased())
                    .font(AppFont.title(24))
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                    .minimumScaleFactor(0.8)
                    .padding(.top, 18)
            }
        }
        if let text = result.summary ?? after?.details {
            ScrollView {
                Text(text).font(AppFont.body(14)).foregroundStyle(Color.inkBody).lineSpacing(3)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .scrollBounceBehavior(.basedOnSize)
            .padding(.top, 8)
        }
        Spacer(minLength: 12)
        Button("Done") { dismiss() }
            .buttonStyle(VoltButtonStyle())
        Button("Change again") {
            note = ""
            coach.open(.day(week: PlanFormat.weekStart(of: date), date: date))
        }
        .font(AppFont.body(14, weight: .semibold))
        .foregroundStyle(Color.inkSoft)
        .frame(maxWidth: .infinity, minHeight: 44)
        .padding(.top, 6)
    }

    private func doneTitle(_ after: ChangeTodayFormat.Session?, changed: Bool) -> String {
        guard changed, let after else { return "Today stays" }
        switch after.sport {
        case .rest: return "Today is rest"
        case .ride: return "Today is a ride"
        case .run: return "Today is a run"
        case .walk: return "Today is a walk"
        case .strength: return after.sport == now.sport ? "Today changed" : "Today is a lift"
        case .mobility: return "Today is mobility"
        default: return "Today changed"
        }
    }

    // MARK: - Failed

    @ViewBuilder
    private func failed(_ message: String) -> some View {
        head(kicker: kicker, title: now.isRest ? "Add a session" : "Change today")
        stateCard(color: Color.alert, title: "The coach couldn't finish", text: "\(message) Nothing was changed.").padding(.top, 18)
        Spacer(minLength: 12)
        Button("Try again") {
            coach.retry()
            note = ""
        }
        .buttonStyle(OutlineButtonStyle(height: 48))
        .font(AppFont.body(14, weight: .semibold))
    }

    // MARK: - Parts

    private func head(kicker: String, kickerColor: Color = .muted, title: String) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(kicker, color: kickerColor).lineLimit(1)
                Text(title.uppercased()).font(AppFont.title(28)).foregroundStyle(Color.ink).lineLimit(1).minimumScaleFactor(0.7)
            }
            Spacer()
            Button { dismiss() } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(Color.inkSoft)
                    .frame(width: 32, height: 32)
                    .background(Color.raised, in: Circle())
                    .frame(width: 44, height: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close")
            .padding(.top, -6)
            .padding(.trailing, -6)
        }
    }

    private func stateCard(color: Color, title: String, text: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 10) {
                Circle().fill(color).frame(width: 8, height: 8)
                Text(title).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
            }
            Text(text).font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Space.gutter)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.panel, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.panel, style: .continuous).strokeBorder(Color.cardBorder))
    }
}

/// Today as a bar on a minutes scale, with what you ask for (or what it became) under it.
struct ChangeTape: View {
    struct Row: Equatable {
        enum Style { case solid, faded, ghost, pending }
        let key: String
        let minutes: Int
        let color: Color
        let label: String
        let style: Style
    }

    let rows: [Row]
    let scale: Int
    @State private var breathe = false

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                HStack(spacing: 10) {
                    Text(row.key.uppercased())
                        .font(AppFont.body(10, weight: .semibold))
                        .tracking(1.2)
                        .foregroundStyle(row.style == .solid && rows.count > 1 && row.key == "Now" && rows.first?.style == .faded ? row.color : Color.muted)
                        .frame(width: 34, alignment: .leading)
                    track(row)
                }
            }
            HStack {
                ForEach(Array(stride(from: 0, through: scale, by: 30)), id: \.self) { tick in
                    Text("\(tick)")
                    if tick < scale { Spacer(minLength: 0) }
                }
            }
            .font(AppFont.number(10))
            .foregroundStyle(Color.dim)
            .padding(.leading, 44)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(rows.map { "\($0.key): \($0.label)" }.joined(separator: ", "))
    }

    private func track(_ row: Row) -> some View {
        GeometryReader { proxy in
            let width = proxy.size.width * min(Double(row.minutes), Double(scale)) / Double(max(scale, 1))
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Radius.chip, style: .continuous).fill(Color.chip)
                bar(row).frame(width: max(width, row.minutes > 0 ? 8 : 0))
                if !row.label.isEmpty {
                    Text(row.label)
                        .font(AppFont.number(15))
                        .strikethrough(row.style == .faded, color: Color.dim)
                        .foregroundStyle(labelColor(row))
                        .lineLimit(1)
                        .fixedSize()
                        .offset(x: labelX(width: width, total: proxy.size.width, row: row))
                }
            }
        }
        .frame(height: 26)
        .animation(Motion.enter, value: row.minutes)
    }

    @ViewBuilder
    private func bar(_ row: Row) -> some View {
        let shape = RoundedRectangle(cornerRadius: Radius.chip, style: .continuous)
        switch row.style {
        case .solid: shape.fill(row.color)
        case .faded: shape.fill(row.color.opacity(0.35))
        case .ghost:
            shape.fill(row.color.opacity(0.08))
                .overlay(shape.strokeBorder(row.color, style: StrokeStyle(lineWidth: 1.5, dash: [4, 3])))
        case .pending:
            shape.fill(row.color)
                .opacity(breathe ? 0.45 : 1)
                .onAppear {
                    withAnimation(Motion.breathe) { breathe = true }
                }
        }
    }

    private func labelColor(_ row: Row) -> Color {
        switch row.style {
        case .faded: Color.faint
        case .ghost: row.color == .dim ? Color.inkSoft : row.color
        default: Color.ink
        }
    }

    /// Right of the bar; inside it, left-aligned, when the bar leaves too little room.
    private func labelX(width: Double, total: Double, row: Row) -> Double {
        let estimate = Double(row.label.count) * 7.5
        if width + 8 + estimate <= total { return width + 8 }
        return 10
    }
}

/// The volt send button, flat grey while there's nothing to ask or the coach can't be reached.
private struct AskButtonStyle: ButtonStyle {
    let enabled: Bool

    func makeBody(configuration: Configuration) -> some View {
        if enabled {
            VoltButtonStyle().makeBody(configuration: configuration)
        } else {
            configuration.label
                .font(AppFont.body(16, weight: .bold))
                .foregroundStyle(Color.faint)
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(Color.raised, in: Capsule())
        }
    }
}

#if DEBUG
/// `-changeTodayDemo sport|rough|more|short|working|done|away|rest` opens the sheet on that state
/// (simulator screenshots, never sends anything).
enum ChangeTodayDemo {
    static var stage: String? { UserDefaults.standard.string(forKey: "changeTodayDemo") }

    @MainActor
    static func start(_ coach: PlanCoachModel, date: String) {
        let task = PlanCoachTask.day(week: PlanFormat.weekStart(of: date), date: date)
        let sent = "I'd rather do a ride today instead of Bodyweight upper + core (short, travel day), about 30 min.\nSunny out, easy on the knee"
        switch stage {
        case "working": coach.demoDay(task, phase: .working(stage: "The coach is working"), helper: .up, sent: sent)
        case "done":
            let change = PlanCoachFormat.Change(date: date, was: "Bodyweight upper + core · 25 min", now: "Easy endurance ride · 45 min")
            let result = PlanCoachResult(task: task, days: [], changes: [change], totalMinutes: 0, mix: [],
                                         summary: "Z2, seated, cadence 85–90 so the knee only spins. Upper body gets a rest today; Thursday's lift stays as planned.",
                                         seconds: 112)
            coach.demoDay(task, phase: .done(result), helper: .up, sent: sent)
        case "away": coach.demoDay(task, phase: .compose, helper: .away)
        default: coach.demoDay(task, phase: .compose, helper: .up)
        }
    }

    static var isRest: Bool { stage == "rest" }

    static func pick(_ now: ChangeTodayFormat.Session) -> (ask: ChangeTodayFormat.Ask?, choice: ChangeTodayFormat.Choice?, note: String)? {
        switch stage {
        case "sport", "away": (.sport, .sport(.ride), "Sunny out, easy on the knee")
        case "more": (.more, .add(30), "Home early, have the gym")
        case "short": (.short, ChangeTodayFormat.options(.short, now: now).last, "")
        case "rest": (nil, .session(.walk, 45), "")
        default: nil
        }
    }

    static var after: (ChangeTodayFormat.Session, String?)? {
        stage == "done" ? (ChangeTodayFormat.Session(sport: .ride, minutes: 45, title: "Easy endurance ride"), nil) : nil
    }
}
#endif
