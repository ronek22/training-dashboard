import SwiftUI

/// Opens on Today once a new run has synced: your pace on the easy tape, an optional pain score,
/// then one tap for how it felt. The tap saves and the sheet says what it means for the next run.
struct AfterRunSheet: View {
    let run: RunningFitness.FeltRun
    let model: RunModel
    /// The injury the pain row asks about; nil hides the row.
    let painLabel: String?
    var startingPain = 0
    @Environment(\.dismiss) private var dismiss
    @State private var pain = 0
    @State private var saved: RunFeel?
    @State private var detent: PresentationDetent = .height(470)

    /// Sized to the content: the question (taller with the pain row), then the answer.
    private var askDetent: PresentationDetent { .height(painLabel == nil ? 470 : 560) }
    private static let resultDetent = PresentationDetent.height(560)

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let saved {
                result(saved).transition(.opacity.combined(with: .move(edge: .trailing)))
            } else {
                ask.transition(.opacity)
            }
        }
        .padding(.horizontal, Space.gutter)
        .padding(.top, 22)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.card)
        .animation(Motion.enter, value: saved)
        .presentationDetents([askDetent, Self.resultDetent, .large], selection: $detent)
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.card)
        .onAppear {
            pain = startingPain
            detent = askDetent
        }
        .onChange(of: saved) { if saved != nil { detent = Self.resultDetent } }
    }

    private var paces: RunningFitness.Paces? { model.fitness?.paces }

    // MARK: Ask

    private var ask: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Just synced")
                Spacer()
                Kicker(RunFormat.shortDate(run.date))
            }
            Text(run.name.uppercased()).font(AppFont.title(30)).foregroundStyle(Color.ink).lineLimit(1).padding(.top, 6)
            HStack(spacing: 18) {
                stat(TodayFormat.number((run.distanceKm * 10).rounded() / 10), unit: "km")
                stat(clock(run.durationMin), unit: nil)
                if let hr = run.avgHr { stat("\(Int(hr.rounded()))", unit: "bpm") }
            }
            .padding(.top, 8)

            if let pace = run.paceS, let easy = paces?.zones.easy {
                let verdict = RunFormat.verdict(pace, band: easy)
                PaceTape(band: easy, range: RunFormat.tapeRange(easy, room: max(12, abs(pace - (easy.fromS + easy.toS) / 2) - 10)),
                         numbers: nil, marker: pace, edgeLabels: true)
                    .padding(.top, 8)
                HStack(spacing: 8) {
                    Circle().fill(verdict == .faster ? Color.warning : Color.mobility).frame(width: 8, height: 8)
                    Text(RunFormat.verdictText(verdict)).font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink)
                    if let cap = paces?.hrCapBpm, let hr = run.avgHr, hr > Double(cap) {
                        Text("· avg HR over \(cap)").font(AppFont.body(13)).foregroundStyle(Color.muted)
                    }
                }
                .padding(.top, 4)
            }

            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.vertical, 16)

            if let painLabel {
                Kicker(painLabel)
                painPicker.padding(.top, 8).padding(.bottom, 18)
            }
            Kicker("How did it feel?", color: .ink)
            HStack {
                ForEach(RunFeel.allCases, id: \.self) { feel in
                    Button {
                        saved = feel
                        Task { await model.save(feel, pain: painLabel == nil ? nil : pain, for: run) }
                    } label: {
                        face(feel)
                    }
                    .buttonStyle(PressableStyle())
                    .frame(maxWidth: .infinity)
                    .accessibilityLabel("Felt \(feel.label)")
                }
            }
            .padding(.top, 12)
        }
    }

    private var painPicker: some View {
        HStack(spacing: 4) {
            ForEach(0...5, id: \.self) { value in
                Button {
                    pain = value
                    Haptics.selection()
                } label: {
                    Text(value == 5 ? "5+" : "\(value)")
                        .font(AppFont.number(17))
                        .foregroundStyle(pain == value ? Color.bg : Color.muted)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(pain == value ? TodayFormat.painColor(value) : .clear, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Pain \(value)")
                .accessibilityAddTraits(pain == value ? .isSelected : [])
            }
        }
        .padding(4)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func face(_ feel: RunFeel) -> some View {
        let color = feel == .ok ? Color.inkSoft : RunFormat.feelColor(feel)
        return VStack(spacing: 8) {
            FaceGlyph(feel: feel, color: color)
                .frame(width: 40, height: 40)
                .frame(width: 76, height: 76)
                .overlay(Circle().strokeBorder(feel == .ok ? Color.dim : color, lineWidth: 2))
            Text(feel.label).font(AppFont.body(13, weight: .semibold)).foregroundStyle(color)
        }
    }

    // MARK: Result

    private func result(_ feel: RunFeel) -> some View {
        let verdict = run.paceS.flatMap { pace in paces.map { RunFormat.verdict(pace, band: $0.zones.easy) } } ?? .inside
        let previous = model.feltRuns.dropLast().compactMap(\.felt)
        let next = paces.map { RunFormat.nextBand(after: feel, previous: previous, current: $0.zones.easy, easedNow: $0.easedS ?? 0) }
        let win = feel != .hard && verdict == .inside
        var runs = Array(model.feltRuns.suffix(8))
        if let last = runs.indices.last, runs[last].activityId == run.activityId { runs[last].felt = feel }
        return VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 14) {
                ZStack {
                    Circle().fill(win ? Color.volt : RunFormat.feelColor(feel))
                    Image(systemName: win ? "checkmark" : "figure.walk")
                        .font(.system(size: 22, weight: .heavy))
                        .foregroundStyle(Color.bg)
                }
                .frame(width: 56, height: 56)
                VStack(alignment: .leading, spacing: 4) {
                    Text(RunFormat.nextHeadline(feel, verdict: verdict).uppercased()).font(AppFont.title(30)).foregroundStyle(Color.ink)
                    Text(RunFormat.nextLine(feel, verdict: verdict) + (painLabel.map { " \($0) \(pain)/10." } ?? ""))
                        .font(AppFont.body(13)).foregroundStyle(Color.inkSoft).fixedSize(horizontal: false, vertical: true)
                }
            }
            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 18)
            if let next {
                HStack {
                    Kicker("Next easy run")
                    Spacer()
                    Kicker(next.eased > 0 ? "Eased 10 s" : "Holds", color: next.eased > 0 ? .warning : .mobility)
                }
                .padding(.top, 16)
                PaceTape(band: next.band, numbers: 40).padding(.top, 12)
            }
            HStack {
                Kicker("Last \(runs.count) runs")
                Spacer()
                Kicker("\(runs.filter { $0.felt == .easy }.count) felt easy")
            }
            .padding(.top, 18)
            FeltDots(runs: runs, highlightLast: true).padding(.top, 14)
            Text("Two hard runs in a row ease the band by 10 s/km. A tap never makes it faster; only VDOT does.")
                .font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineSpacing(2)
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous).strokeBorder(Color.cardBorder))
                .padding(.top, 18)
            Button("Done") { dismiss() }
                .buttonStyle(OutlineButtonStyle(height: 50))
                .padding(.top, 16)
        }
    }

    private func stat(_ value: String, unit: String?) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 2) {
            Text(value).font(AppFont.number(22)).foregroundStyle(Color.ink)
            if let unit { Text(unit).font(AppFont.number(11, weight: .semibold)).foregroundStyle(Color.muted) }
        }
    }

    private func clock(_ minutes: Double) -> String {
        let seconds = Int((minutes * 60).rounded())
        return seconds >= 3600
            ? "\(seconds / 3600):" + String(format: "%02d:%02d", seconds / 60 % 60, seconds % 60)
            : "\(seconds / 60):" + String(format: "%02d", seconds % 60)
    }
}

/// Two eyes and a mouth: up for easy, flat for OK, down for hard.
struct FaceGlyph: View {
    let feel: RunFeel
    let color: Color

    var body: some View {
        Canvas { context, canvas in
            let s = canvas.width / 30
            for eye in [11.0, 19.0] {
                context.fill(Path(ellipseIn: CGRect(x: (eye - 1.2) * s, y: 10.8 * s, width: 2.4 * s, height: 2.4 * s)), with: .color(color))
            }
            var mouth = Path()
            switch feel {
            case .easy:
                mouth.move(to: CGPoint(x: 10 * s, y: 17.5 * s))
                mouth.addCurve(to: CGPoint(x: 20 * s, y: 17.5 * s), control1: CGPoint(x: 12.8 * s, y: 20.5 * s), control2: CGPoint(x: 17.2 * s, y: 20.5 * s))
            case .ok:
                mouth.move(to: CGPoint(x: 10.5 * s, y: 18.5 * s))
                mouth.addLine(to: CGPoint(x: 19.5 * s, y: 18.5 * s))
            case .hard:
                mouth.move(to: CGPoint(x: 10 * s, y: 20.5 * s))
                mouth.addCurve(to: CGPoint(x: 20 * s, y: 20.5 * s), control1: CGPoint(x: 12.8 * s, y: 17.5 * s), control2: CGPoint(x: 17.2 * s, y: 17.5 * s))
            }
            context.stroke(mouth, with: .color(color), style: StrokeStyle(lineWidth: 2.2 * s, lineCap: .round))
        }
        .accessibilityHidden(true)
    }
}
