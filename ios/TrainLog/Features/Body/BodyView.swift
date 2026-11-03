import Charts
import SwiftUI

struct BodyView: View {
    @State private var model = BodyModel()
    /// Day (the clock) or Body (the muscle map); the screen opens on the last one used.
    @AppStorage("bodyTab") private var tab = BodyTab.day.rawValue
    /// Minutes after midnight; sets the lights-out target.
    @AppStorage("bodyWakeMinutes") private var wakeMinutes = 450
    @State private var editingWake = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if let data = model.data {
                    if model.offline, let syncedAt = model.syncedAt {
                        OfflineNote(syncedAt: syncedAt)
                    }
                    BodyTabPicker(selection: Binding(get: { BodyTab(rawValue: tab) ?? .day }, set: { tab = $0.rawValue }))
                    if BodyTab(rawValue: tab) == .body {
                        BodyMapSection(summary: BodyMapSummary(training: data.training ?? [], issues: data.issues ?? [], today: data.date), today: data.date)
                    } else {
                        daySection(data)
                    }
                } else if let error = model.error {
                    VStack(alignment: .leading, spacing: 8) {
                        Kicker("Not synced yet")
                        Text(error).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    }
                    .card()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .smoothRefreshable { await model.refresh() }
        .task { await model.load() }
        .sheet(isPresented: $editingWake) { WakeTimeSheet(minutes: $wakeMinutes) }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(model.data.map { TodayFormat.dateKicker($0.date) } ?? " ")
                Text("BODY").font(AppFont.title(44)).foregroundStyle(Color.ink)
            }
            Spacer()
            if let readiness = model.data?.readiness {
                let style = ReadinessStyle(level: readiness.level)
                Pill(text: style.headline, color: style.color).padding(.bottom, 8)
            }
        }
        .padding(.horizontal, 4)
    }

    @ViewBuilder
    private func daySection(_ data: PhoneBody) -> some View {
        let need = data.sleepDebt?.needH ?? data.sleep?.baselineH ?? 7.5
        let lightsOut = BodyClockMath.lightsOut(wakeMinutes: wakeMinutes, needH: need, debtH: data.sleepDebt?.hours ?? 0)
        TimelineView(.everyMinute) { context in
            BodyClockDial(now: context.date, sleep: data.sleep, steps: model.live?.steps ?? [], lightsOut: lightsOut) {
                VStack(spacing: 2) {
                    Kicker("Since midnight", color: .muted)
                    Text(model.steps.map(BodyFormat.steps) ?? "–").font(AppFont.number(46)).foregroundStyle(Color.ink).padding(.top, 2)
                    Text("steps").font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.run)
                    if let sleep = data.sleep, sleep.date == data.date {
                        Text("slept \(BodyFormat.duration(sleep.asleepH))")
                            .font(AppFont.body(12)).foregroundStyle(Color.inkSoft).padding(.top, 6)
                    }
                }
            }
        }
        .padding(.horizontal, 8)
        ClockLegend()
        TonightCard(lightsOut: lightsOut, wakeMinutes: wakeMinutes, needH: need, debt: data.sleepDebt,
                    nights: data.vitals.sleep?.days ?? []) { editingWake = true }
        VitalTiles(vitals: data.vitals)
        if let sleep = data.sleep {
            SleepCard(sleep: sleep, today: data.date)
        }
        ReadinessHero(readiness: data.readiness)
        HeartCard(vitals: data.vitals, live: model.live)
        TrainingLoadCard(load: data.load)
    }
}

enum BodyTab: String, CaseIterable {
    case day, body
    var label: String { rawValue.capitalized }
}

private struct BodyTabPicker: View {
    @Binding var selection: BodyTab

    var body: some View {
        HStack(spacing: 0) {
            ForEach(BodyTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(Motion.quick) { selection = tab }
                } label: {
                    Text(tab.label)
                        .font(AppFont.body(14, weight: .bold))
                        .foregroundStyle(selection == tab ? Color.bg : Color.muted)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(selection == tab ? Color.ink : .clear, in: Capsule())
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(Color.card, in: Capsule())
        .overlay(Capsule().strokeBorder(Color.cardBorder, lineWidth: 1))
        .sensoryFeedback(.selection, trigger: selection)
    }
}

// MARK: - Day

private struct ClockLegend: View {
    var body: some View {
        HStack(spacing: 14) {
            item(SleepStage.core.color, "sleep")
            item(.run, "steps / hour")
            item(Color.other.opacity(0.6), "wind-down")
        }
        .frame(maxWidth: .infinity)
    }

    private func item(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 5) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label).font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
        }
    }
}

/// Turns the week's sleep debt into one target: lights out tonight.
private struct TonightCard: View {
    let lightsOut: Int
    let wakeMinutes: Int
    let needH: Double
    let debt: PhoneBody.SleepDebt?
    let nights: [PhoneBody.Day]
    let editWake: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Kicker("Tonight", color: .other)
                Spacer()
                if let debt, debt.hours >= 0.5 {
                    Text("debt \(BodyFormat.duration(debt.hours))").font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.muted)
                }
            }
            Text("LIGHTS OUT \(BodyClockMath.clock(minutes: lightsOut))").font(AppFont.title(34)).foregroundStyle(Color.ink)
            Button(action: editWake) {
                HStack(spacing: 4) {
                    Text(line).font(AppFont.body(14)).foregroundStyle(Color.inkSoft).multilineTextAlignment(.leading)
                    Image(systemName: "pencil").font(.system(size: 11, weight: .semibold)).foregroundStyle(Color.muted)
                }
                .frame(minHeight: 44, alignment: .leading)
            }
            .buttonStyle(.plain)
            if nights.count > 1 {
                NightBars(nights: nights, needH: needH)
            }
        }
        .card()
    }

    private var line: String {
        let hours = BodyClockMath.sleepHours(lightsOut: lightsOut, wakeMinutes: wakeMinutes)
        let base = "\(BodyFormat.duration(hours)) of sleep before your \(BodyClockMath.clock(minutes: wakeMinutes)) wake-up"
        guard let debt, debt.hours >= 1 else { return base + "." }
        return base + ", to start paying back the week."
    }
}

/// The last nights against the sleep need, last night solid.
private struct NightBars: View {
    let nights: [PhoneBody.Day]
    let needH: Double

    var body: some View {
        let top = max(9, (nights.map(\.value).max() ?? 0) + 0.5)
        VStack(spacing: 4) {
            GeometryReader { geometry in
                let height = geometry.size.height
                ZStack(alignment: .bottomLeading) {
                    HStack(alignment: .bottom, spacing: 8) {
                        ForEach(nights.indices, id: \.self) { index in
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .fill(index == nights.count - 1 ? Color.other : Color.other.opacity(0.38))
                                .frame(height: max(4, nights[index].value / top * height))
                                .frame(maxWidth: .infinity)
                        }
                    }
                    Rectangle()
                        .stroke(style: StrokeStyle(lineWidth: 1.5, dash: [4, 4]))
                        .foregroundStyle(Color.ink)
                        .frame(height: 1)
                        .offset(y: -needH / top * height)
                    Text("need \(String(format: "%.1f", needH)) h")
                        .font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.ink)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                        .offset(y: -needH / top * height - 10)
                }
            }
            .frame(height: 72)
            HStack(spacing: 8) {
                ForEach(nights.indices, id: \.self) { index in
                    Text(BodyFormat.weekday(nights[index].date))
                        .font(AppFont.body(10, weight: .semibold))
                        .foregroundStyle(index == nights.count - 1 ? Color.ink : Color.faint)
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(.top, 6)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Last \(nights.count) nights against your \(String(format: "%.1f", needH)) hour need")
    }
}

/// HRV, resting HR and sleep: big number, what it means this week, a 7-day line.
private struct VitalTiles: View {
    let vitals: PhoneBody.Vitals

    var body: some View {
        HStack(spacing: 8) {
            ForEach([VitalKind.hrv, .restingHr, .sleep], id: \.self) { kind in
                if let vital = vital(kind) { tile(kind, vital) }
            }
        }
    }

    private func vital(_ kind: VitalKind) -> PhoneBody.Vital? {
        switch kind {
        case .hrv: vitals.hrv
        case .restingHr: vitals.restingHr
        case .sleep: vitals.sleep
        case .steps: vitals.steps
        }
    }

    private func tile(_ kind: VitalKind, _ vital: PhoneBody.Vital) -> some View {
        let note = VitalNote.make(kind: kind, vital: vital)
        return VStack(alignment: .leading, spacing: 4) {
            Kicker(kind.label, color: kind.color)
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(kind.format(vital.value)).font(AppFont.number(30)).foregroundStyle(Color.ink)
                Text(kind.unit).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
            }
            Text(note.text).font(AppFont.body(11, weight: .bold)).foregroundStyle(note.tone.color)
                .lineLimit(1).minimumScaleFactor(0.8)
            Sparkline(values: (vital.days ?? []).map(\.value), baseline: vital.baseline, color: kind.color)
                .frame(height: 26)
                .padding(.top, 4)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.panel, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.panel, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(kind.label) \(kind.format(vital.value)) \(kind.unit), \(note.text)")
    }
}

/// One line on what a vital means this week (unit-tested).
struct VitalNote: Equatable {
    enum Tone: Equatable {
        case good, bad, neutral
        var color: Color {
            switch self {
            case .good: .mobility
            case .bad: .danger
            case .neutral: .muted
            }
        }
    }

    let text: String
    let tone: Tone

    static func make(kind: VitalKind, vital: PhoneBody.Vital) -> VitalNote {
        let week = (vital.days ?? []).map(\.value)
        if week.count >= 4 {
            let best = kind.higherIsBetter ? week.max() : week.min()
            if vital.value == best { return VitalNote(text: kind.higherIsBetter ? "▲ best this week" : "▼ lowest this week", tone: .good) }
        }
        guard let baseline = vital.baseline else { return VitalNote(text: "no baseline yet", tone: .neutral) }
        let delta = vital.value - baseline
        let small = kind == .sleep ? 0.25 : kind == .restingHr ? 3 : baseline * 0.08
        if abs(delta) < small { return VitalNote(text: "normal", tone: .neutral) }
        let better = (delta > 0) == kind.higherIsBetter
        let amount = kind == .sleep ? String(format: "%.1f h", abs(delta)) : "\(Int(abs(delta).rounded()))"
        return VitalNote(text: "\(delta > 0 ? "▲ +" : "▼ −")\(amount) vs normal", tone: better ? .good : .bad)
    }
}

private struct Sparkline: View {
    let values: [Double]
    let baseline: Double?
    let color: Color

    var body: some View {
        GeometryReader { geometry in
            let all = values + (baseline.map { [$0] } ?? [])
            if values.count > 1, let low = all.min(), let high = all.max() {
                let range = max(high - low, 0.001)
                let w = geometry.size.width, h = geometry.size.height
                let points = values.indices.map { index in
                    CGPoint(x: 4 + CGFloat(index) / CGFloat(values.count - 1) * (w - 8),
                            y: 4 + (1 - (values[index] - low) / range) * (h - 8))
                }
                ZStack {
                    if let baseline {
                        let y = 4 + (1 - (baseline - low) / range) * (h - 8)
                        Path { $0.move(to: CGPoint(x: 0, y: y)); $0.addLine(to: CGPoint(x: w, y: y)) }
                            .stroke(Color.faint, style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                    }
                    Path { path in path.addLines(points) }
                        .stroke(color, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                    Circle().fill(color).frame(width: 9, height: 9)
                        .overlay(Circle().stroke(Color.card, lineWidth: 2))
                        .position(points.last!)
                }
            }
        }
    }
}

struct WakeTimeSheet: View {
    @Binding var minutes: Int
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Kicker("Lights-out target")
            Text("WHEN DO YOU WAKE UP?").font(AppFont.title(30)).foregroundStyle(Color.ink)
            DatePicker("Wake-up", selection: Binding(
                get: { Calendar.current.startOfDay(for: .now).addingTimeInterval(Double(minutes) * 60) },
                set: { minutes = Calendar.current.component(.hour, from: $0) * 60 + Calendar.current.component(.minute, from: $0) }
            ), displayedComponents: .hourAndMinute)
            .datePickerStyle(.wheel)
            .labelsHidden()
            .frame(maxWidth: .infinity)
            Button("Done") { dismiss() }.buttonStyle(VoltButtonStyle())
        }
        .padding(20)
        .presentationDetents([.medium])
        .presentationBackground(Color.card)
        .colorScheme(.dark)
    }
}

// MARK: - Body map

private struct BodyMapSection: View {
    let summary: BodyMapSummary
    let today: String

    var body: some View {
        let tint = Dictionary(uniqueKeysWithValues: summary.states.map { ($0.key, $0.value.color) })
        let pins = summary.issues.flatMap(BodyMapSummary.pins)
        VStack(spacing: 12) {
            HStack(spacing: 4) {
                figure(.front, tint: tint, pins: pins)
                figure(.back, tint: tint, pins: pins)
            }
            .frame(height: 300)
            .overlay(alignment: .center) { issueLabel }
            legend
            readyCard
            WorkCard(summary: summary)
        }
    }

    private func figure(_ side: MuscleSilhouette.Side, tint: [Muscle: Color], pins: [BodyPin]) -> some View {
        VStack(spacing: 2) {
            MuscleSilhouette(side: side, tint: tint, pins: pins.filter { $0.side == side }.map(\.point), background: .bg)
            Text(side == .front ? "FRONT" : "BACK").font(AppFont.body(10, weight: .semibold)).tracking(1.4).foregroundStyle(Color.faint)
        }
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder
    private var issueLabel: some View {
        if let issue = summary.issues.first {
            let day = BodyMapSummary.issueDay(issue, today: today).map { " · DAY \($0)" } ?? ""
            Text("\(BodyMapSummary.issueName(issue).uppercased())\(day)")
                .font(AppFont.body(11, weight: .heavy))
                .foregroundStyle(Color.bg)
                .padding(.horizontal, 8)
                .frame(height: 22)
                .background(Color.danger, in: RoundedRectangle(cornerRadius: Radius.chip, style: .continuous))
                .offset(y: 118)
        }
    }

    private var legend: some View {
        HStack(spacing: 6) {
            ForEach(MuscleState.allCases.filter { summary.count($0) > 0 }, id: \.self) { state in
                chip(state.color, "\(state.label) \(summary.count(state))")
            }
            if !summary.issues.isEmpty {
                chip(.danger, "Protect \(summary.issues.count)")
            }
        }
        .frame(maxWidth: .infinity)
    }

    private func chip(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 5) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(text).font(AppFont.body(11.5, weight: .semibold)).foregroundStyle(Color.inkSoft)
        }
        .padding(.horizontal, 9)
        .frame(height: 28)
        .background(Color.card, in: Capsule())
        .overlay(Capsule().strokeBorder(Color.cardBorder, lineWidth: 1))
    }

    private var readyCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Kicker("Ready to train", color: .mobility)
            Text(summary.headline).font(AppFont.body(17, weight: .semibold)).foregroundStyle(Color.ink)
            if let detail = summary.detail {
                Text(detail).font(AppFont.body(14)).foregroundStyle(Color.inkSoft).fixedSize(horizontal: false, vertical: true)
            }
        }
        .card()
    }
}

/// Sessions per body area over the last week, split by sport, so rides and rehab count too.
private struct WorkCard: View {
    let summary: BodyMapSummary

    var body: some View {
        let peak = max(6, summary.work.map(\.total).max() ?? 0)
        VStack(alignment: .leading, spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Kicker("Last 7 days · every sport")
                Text("WHAT WORKED WHAT").font(AppFont.title(24)).foregroundStyle(Color.ink)
            }
            .padding(.horizontal, 4)
            .padding(.top, 8)
            VStack(spacing: 11) {
                ForEach(summary.work, id: \.area) { row in
                    HStack(spacing: 12) {
                        Text(row.area.label).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink).frame(width: 84, alignment: .leading)
                        GeometryReader { geometry in
                            HStack(spacing: 2) {
                                ForEach(WorkSport.allCases, id: \.self) { sport in
                                    if let count = row.sessions[sport], count > 0 {
                                        Rectangle().fill(sport.color).frame(width: CGFloat(count) / CGFloat(peak) * geometry.size.width)
                                    }
                                }
                                Spacer(minLength: 0)
                            }
                            .background(Color.inset)
                            .clipShape(Capsule())
                        }
                        .frame(height: 10)
                        Text("\(row.total)").font(AppFont.number(18)).foregroundStyle(row.total > 0 ? Color.ink : Color.faint).frame(width: 24, alignment: .trailing)
                    }
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(row.area.label): \(row.total) sessions")
                }
                Rectangle().fill(Color.cardBorder).frame(height: 1)
                HStack(spacing: 12) {
                    ForEach(WorkSport.allCases.filter { (summary.sportCounts[$0] ?? 0) > 0 }, id: \.self) { sport in
                        HStack(spacing: 4) {
                            Circle().fill(sport.color).frame(width: 7, height: 7)
                            Text("\(summary.sportCounts[sport] ?? 0) \(sport.label.lowercased())")
                                .font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                        }
                    }
                    Spacer()
                    Text("sessions").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.faint)
                }
            }
            .card()
        }
    }
}

// MARK: - Readiness

private struct ReadinessHero: View {
    let readiness: PhoneBody.Readiness

    var body: some View {
        let style = ReadinessStyle(level: readiness.level)
        VStack(alignment: .leading, spacing: 16) {
            Kicker("Readiness", color: style.color)
            VStack(alignment: .leading, spacing: 2) {
                Text(style.headline.uppercased())
                    .font(AppFont.title(46))
                    .foregroundStyle(style.color)
                Text(readiness.factors.isEmpty ? style.label : "\(style.label) · \(steady.count) of \(readiness.factors.count) signals steady")
                    .font(AppFont.body(13, weight: .medium))
                    .foregroundStyle(Color.inkSoft)
            }
            if !readiness.factors.isEmpty {
                balance
            }
            if let advice = readiness.advice {
                Text(advice).font(AppFont.body(14)).foregroundStyle(Color.inkSoft).lineSpacing(3)
            }
            if !drivers.isEmpty {
                group("Pulling it down", drivers)
            }
            if !steady.isEmpty {
                group("On your side", steady)
            }
        }
        .card()
    }

    private var drivers: [PhoneBody.Factor] {
        readiness.factors.filter { ($0.points ?? 0) > 0 || Self.tone($0) != "steady" }
            .sorted { ($0.points ?? 0) > ($1.points ?? 0) }
    }

    private var steady: [PhoneBody.Factor] {
        readiness.factors.filter { !drivers.contains($0) }
    }

    /// Every signal as one slice: green steady, amber caution, red risk.
    private var balance: some View {
        let tones = ["steady", "caution", "risk"]
        let sorted = readiness.factors.map { Self.tone($0) }.sorted { tones.firstIndex(of: $0)! < tones.firstIndex(of: $1)! }
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 3) {
                ForEach(sorted.indices, id: \.self) { index in
                    Capsule().fill(BodyFormat.toneColor(sorted[index]))
                }
            }
            .frame(height: 8)
            HStack(spacing: 14) {
                ForEach(tones, id: \.self) { tone in
                    let count = sorted.filter { $0 == tone }.count
                    if count > 0 {
                        HStack(spacing: 5) {
                            Circle().fill(BodyFormat.toneColor(tone)).frame(width: 7, height: 7)
                            Text("\(count) \(tone)").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                        }
                    }
                }
            }
        }
    }

    /// Neutral and quiet signals count as steady.
    private static func tone(_ factor: PhoneBody.Factor) -> String {
        ["caution", "risk"].contains(factor.tone) ? factor.tone : "steady"
    }

    private func group(_ title: String, _ factors: [PhoneBody.Factor]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(title)
            VStack(spacing: 0) {
                ForEach(factors) { factor in
                    row(factor)
                    if factor != factors.last {
                        Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.leading, 48)
                    }
                }
            }
            .padding(.horizontal, 12)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
        }
    }

    private func row(_ factor: PhoneBody.Factor) -> some View {
        let color = BodyFormat.toneColor(factor.tone)
        return HStack(spacing: 12) {
            SignalChip(key: factor.key, tone: factor.tone, size: 36)
            VStack(alignment: .leading, spacing: 2) {
                Text(factor.label).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                Text(factor.detail.prefix(1).uppercased() + factor.detail.dropFirst())
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            if Self.tone(factor) != "steady" || (factor.points ?? 0) > 0 {
                let points = factor.points ?? 0
                // How hard this signal pulls: one bar per point, up to four.
                HStack(alignment: .bottom, spacing: 3) {
                    ForEach(0..<max(points, 2), id: \.self) { index in
                        Capsule()
                            .fill(index < points ? color : Color.track)
                            .frame(width: 4, height: 8 + CGFloat(index) * 4)
                    }
                }
                .accessibilityLabel("\(points) point\(points == 1 ? "" : "s") against readiness")
            } else {
                Image(systemName: "checkmark")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(color.opacity(0.8))
            }
        }
        .padding(.vertical, 10)
    }
}

// MARK: - Sleep

private struct SleepCard: View {
    let sleep: PhoneBody.Sleep
    let today: String

    private let laneHeight: CGFloat = 26

    var body: some View {
        let blocks = BodyFormat.blocks(sleep)
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Kicker(sleep.date == today ? "Last night" : "Sleep · \(TodayFormat.shortDay(sleep.date, relativeTo: today))", color: SleepStage.deep.color)
                    Text(BodyFormat.duration(sleep.asleepH)).font(AppFont.title(46)).foregroundStyle(Color.ink)
                    Text(subtitle).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer(minLength: 8)
                if let delta = BodyFormat.sleepDelta(sleep) {
                    Pill(text: delta.text, color: delta.good.map { $0 ? Color.mobility : Color.danger } ?? .muted)
                }
            }
            if !blocks.isEmpty {
                hypnogram(blocks)
            }
            stageBar
            stageLegend
        }
        .card()
    }

    private var subtitle: String {
        var parts = ["\(BodyFormat.clock(sleep.start)) – \(BodyFormat.clock(sleep.end))"]
        if let baseline = sleep.baselineH { parts.append("30-day avg \(BodyFormat.duration(baseline))") }
        return parts.joined(separator: " · ")
    }

    /// Four lanes like Apple Health: awake on top, deep at the bottom, each stretch a rounded block,
    /// with a faint line joining one stage to the next.
    private func hypnogram(_ blocks: [SleepBlock]) -> some View {
        VStack(spacing: 6) {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(SleepStage.allCases) { stage in
                        Text(stage.title)
                            .font(AppFont.body(10, weight: .semibold))
                            .foregroundStyle(stage.color.opacity(0.9))
                            .frame(height: laneHeight)
                    }
                }
                .frame(width: 38, alignment: .leading)
                GeometryReader { geometry in
                    let width = geometry.size.width
                    ZStack(alignment: .topLeading) {
                        ForEach(SleepStage.allCases) { stage in
                            RoundedRectangle(cornerRadius: 4).fill(Color.inset)
                                .frame(height: laneHeight - 6)
                                .offset(y: CGFloat(stage.lane) * laneHeight + 3)
                        }
                        Path { path in
                            for (index, block) in blocks.enumerated() where index > 0 {
                                let previous = blocks[index - 1]
                                let x = block.from * width
                                path.move(to: CGPoint(x: x, y: mid(previous.stage)))
                                path.addLine(to: CGPoint(x: x, y: mid(block.stage)))
                            }
                        }
                        .stroke(Color.faint.opacity(0.5), lineWidth: 1)
                        ForEach(blocks) { block in
                            let blockWidth = max(2, (block.to - block.from) * width)
                            RoundedRectangle(cornerRadius: 3, style: .continuous)
                                .fill(block.stage.color)
                                .frame(width: blockWidth, height: laneHeight - 10)
                                .offset(x: min(block.from * width, width - blockWidth), y: CGFloat(block.stage.lane) * laneHeight + 5)
                        }
                    }
                }
                .frame(height: laneHeight * 4)
            }
            HStack {
                Text(BodyFormat.clock(sleep.start))
                Spacer()
                Text(BodyFormat.clock(sleep.end))
            }
            .font(AppFont.body(10, weight: .medium))
            .foregroundStyle(Color.faint)
            .padding(.leading, 46)
        }
    }

    private func mid(_ stage: SleepStage) -> CGFloat {
        CGFloat(stage.lane) * laneHeight + laneHeight / 2
    }

    private var total: Double {
        SleepStage.allCases.map { BodyFormat.hours($0, sleep.stages) }.reduce(0, +)
    }

    private var stageBar: some View {
        GeometryReader { geometry in
            HStack(spacing: 2) {
                ForEach(SleepStage.allCases.reversed()) { stage in
                    let share = total > 0 ? BodyFormat.hours(stage, sleep.stages) / total : 0
                    if share > 0 {
                        Rectangle().fill(stage.color).frame(width: max(2, share * (geometry.size.width - 6)))
                    }
                }
            }
        }
        .frame(height: 8)
        .clipShape(Capsule())
    }

    private var stageLegend: some View {
        HStack(alignment: .top, spacing: 0) {
            ForEach(SleepStage.allCases.reversed()) { stage in
                let hours = BodyFormat.hours(stage, sleep.stages)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 5) {
                        Circle().fill(stage.color).frame(width: 7, height: 7)
                        Text(stage.title).font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                    }
                    Text(BodyFormat.duration(hours)).font(AppFont.number(19)).foregroundStyle(Color.ink)
                    Text(total > 0 ? "\(Int((hours / total * 100).rounded()))%" : "–")
                        .font(AppFont.body(11)).foregroundStyle(Color.faint)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

/// 00 · 06 · 12 · 18 along the bottom of today's hourly charts.
@AxisContentBuilder
private var hourAxis: some AxisContent {
    AxisMarks(values: .stride(by: .hour, count: 6)) { _ in
        AxisGridLine().foregroundStyle(Color.cardBorder)
        AxisValueLabel(format: .dateTime.hour(.twoDigits(amPM: .omitted)).locale(Locale(identifier: "en_GB")))
            .font(AppFont.body(10))
            .foregroundStyle(Color.faint)
    }
}

// MARK: - Heart

/// Today's heart rate like the Watch's Heart Rate app: the latest reading, each hour's range,
/// and resting rate as a dashed line through it.
private struct HeartCard: View {
    let vitals: PhoneBody.Vitals
    let live: LiveDay?

    private let color = Color.danger

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 3) {
                    Kicker("Heart rate", color: color)
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Text(headline.map { "\(Int($0.rounded()))" } ?? "–").font(AppFont.title(44)).foregroundStyle(Color.ink)
                        Text("bpm").font(AppFont.body(14)).foregroundStyle(Color.muted)
                    }
                    Text(caption).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer()
                Image(systemName: "heart.fill")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(color)
                    .symbolEffect(.pulse, options: .repeating, isActive: live?.latestHeartRate != nil)
                    .frame(width: 40, height: 40)
                    .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
            }
            if let heart = live?.heart, !heart.isEmpty {
                chart(heart).frame(height: 120)
            }
            HStack(spacing: 0) {
                if let range = dayRange {
                    stat("Range today", "\(Int(range.low.rounded()))–\(Int(range.high.rounded()))")
                }
                if live?.latestHeartRate != nil {
                    stat("Resting", vitals.restingHr.map { "\(Int($0.value.rounded()))" } ?? "–")
                }
                stat("HRV", vitals.hrv.map { "\(Int($0.value.rounded())) ms" } ?? "–")
            }
        }
        .card()
    }

    /// The latest reading when the phone has today's, otherwise the resting rate.
    private var headline: Double? { live?.latestHeartRate ?? vitals.restingHr?.value }

    private var caption: String {
        if let at = live?.latestHeartRateAt { return "Latest · \(at.formatted(date: .omitted, time: .shortened))" }
        return vitals.restingHr == nil ? "No heart rate yet" : "Resting · from your Watch"
    }

    private var dayRange: (low: Double, high: Double)? {
        guard let heart = live?.heart, let low = heart.map(\.low).min(), let high = heart.map(\.high).max() else { return nil }
        return (low, high)
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
            Text(value).font(AppFont.number(22)).foregroundStyle(Color.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Each hour's lowest to highest heart rate as a capsule, resting rate dashed behind.
    private func chart(_ hours: [LiveDay.HeartHour]) -> some View {
        let start = Calendar.current.startOfDay(for: .now)
        let resting = vitals.restingHr?.value
        let low = min(hours.map(\.low).min() ?? 40, resting ?? .infinity)
        let high = hours.map(\.high).max() ?? 160
        return Chart {
            if let resting {
                RuleMark(y: .value("Resting", resting))
                    .foregroundStyle(Color.faint)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
            }
            ForEach(hours) { hour in
                RectangleMark(
                    x: .value("Hour", hour.start, unit: .hour),
                    yStart: .value("Low", hour.low),
                    yEnd: .value("High", max(hour.high, hour.low + 2)),
                    width: .ratio(0.55)
                )
                .foregroundStyle(color.opacity(hour == hours.last ? 1 : 0.6))
                .clipShape(Capsule())
            }
            if let latest = live?.latestHeartRate, let at = live?.latestHeartRateAt {
                PointMark(x: .value("Hour", at), y: .value("Latest", latest))
                    .symbol { Circle().fill(Color.ink).overlay(Circle().strokeBorder(color, lineWidth: 2)).frame(width: 9, height: 9) }
            }
        }
        .chartXScale(domain: start...start.addingTimeInterval(86_400))
        .chartYScale(domain: (low - 8)...(high + 8))
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine().foregroundStyle(Color.cardBorder)
                AxisValueLabel("\(Int(value.as(Double.self) ?? 0))").font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
        .chartXAxis { hourAxis }
    }
}

// MARK: - Training load

private struct TrainingLoadCard: View {
    let load: PhoneBody.Load

    private let fitnessColor = Color.ride
    private let fatigueColor = Color.strength

    var body: some View {
        let zone = BodyFormat.formZone(load.form)
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Kicker("Training load")
                Spacer()
                Pill(text: zone.label, color: zone.color)
            }
            HStack(alignment: .top, spacing: 0) {
                number("Fitness", "\(Int(load.fitness.rounded()))", fitnessColor)
                number("Fatigue", "\(Int(load.fatigue.rounded()))", fatigueColor)
                number("Form", BodyFormat.signed(load.form), zone.color)
            }
            chart.frame(height: 130)
            formChart.frame(height: 44)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            VStack(alignment: .leading, spacing: 4) {
                Text(zone.note).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                Text("Load ratio \(load.ratio.formatted(.number.precision(.fractionLength(2)).locale(Locale(identifier: "en_US")))) · \(load.ratioStatus) · last 42 days")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
        }
        .card()
    }

    private var days: [(date: Date, day: PhoneBody.LoadDay)] {
        load.chart.compactMap { day in FoodFormat.parse(day.date).map { ($0, day) } }
    }

    private func number(_ label: String, _ value: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 5) {
                Capsule().fill(color).frame(width: 10, height: 3)
                Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            Text(value).font(AppFont.title(36)).foregroundStyle(Color.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Fitness as a filled area, fatigue as a line over it, daily load as faint bars underneath.
    private var chart: some View {
        let days = days
        let top = (days.map { max($0.day.fitness, $0.day.fatigue) }.max() ?? 1) * 1.12
        let maxLoad = days.map(\.day.load).max() ?? 1
        return Chart {
            ForEach(days, id: \.date) { item in
                BarMark(x: .value("Day", item.date, unit: .day), y: .value("Load", maxLoad > 0 ? item.day.load / maxLoad * top * 0.35 : 0))
                    .foregroundStyle(Color.dim.opacity(0.7))
                    .cornerRadius(1)
                AreaMark(x: .value("Day", item.date, unit: .day), y: .value("Fitness", item.day.fitness), series: .value("Series", "Fitness"))
                    .foregroundStyle(fitnessColor.opacity(0.1))
                    .interpolationMethod(.monotone)
                LineMark(x: .value("Day", item.date, unit: .day), y: .value("Fitness", item.day.fitness), series: .value("Series", "Fitness"))
                    .foregroundStyle(fitnessColor)
                    .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    .interpolationMethod(.monotone)
                LineMark(x: .value("Day", item.date, unit: .day), y: .value("Fatigue", item.day.fatigue), series: .value("Series", "Fatigue"))
                    .foregroundStyle(fatigueColor)
                    .lineStyle(StrokeStyle(lineWidth: 1.8, lineCap: .round))
                    .interpolationMethod(.monotone)
            }
            if let last = days.last {
                PointMark(x: .value("Day", last.date, unit: .day), y: .value("Fitness", last.day.fitness))
                    .symbol { Circle().fill(Color.bg).stroke(fitnessColor, lineWidth: 2.5).frame(width: 9, height: 9) }
                PointMark(x: .value("Day", last.date, unit: .day), y: .value("Fatigue", last.day.fatigue))
                    .symbol { Circle().fill(Color.bg).stroke(fatigueColor, lineWidth: 2).frame(width: 8, height: 8) }
            }
        }
        .chartYScale(domain: 0...max(top, 1))
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine().foregroundStyle(Color.cardBorder)
                AxisValueLabel("\(Int(value.as(Double.self) ?? 0))").font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
        .chartXAxis(.hidden)
    }

    /// Form per day: above zero fresh, below zero carrying fatigue.
    private var formChart: some View {
        let days = days
        let reach = max(days.map { abs($0.day.form) }.max() ?? 10, 10)
        return Chart {
            RuleMark(y: .value("Zero", 0)).foregroundStyle(Color.outline)
            ForEach(days, id: \.date) { item in
                BarMark(x: .value("Day", item.date, unit: .day), y: .value("Form", item.day.form))
                    .foregroundStyle(BodyFormat.formZone(item.day.form).color.opacity(item.date == days.last?.date ? 1 : 0.55))
                    .cornerRadius(1.5)
            }
        }
        .chartYScale(domain: -reach...reach)
        .chartYAxis(.hidden)
        .chartXAxis {
            // First, middle and last day, the ends anchored inward so they don't clip.
            let ticks = days.isEmpty ? [] : [days[0].date, days[days.count / 2].date, days[days.count - 1].date]
            AxisMarks(values: ticks) { value in
                let date = value.as(Date.self)
                AxisValueLabel(
                    format: .dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB")),
                    anchor: date == ticks.first ? .topLeading : date == ticks.last ? .topTrailing : .top
                )
                .font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
    }
}
