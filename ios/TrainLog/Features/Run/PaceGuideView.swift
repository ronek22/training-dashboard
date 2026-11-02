import SwiftUI

/// Today's easy pace and why: the tape as the page header, the way back to the peak VDOT, every
/// pace in its colour, and how recent runs felt. Pushed from the Today run card.
struct PaceGuideView: View {
    let model: RunModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Button { dismiss() } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(Color.ink)
                        .frame(width: 40, height: 40)
                        .background(Color.card, in: Circle())
                        .overlay(Circle().strokeBorder(Color.cardBorder))
                        .frame(width: 44, height: 44)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Back")

                if let fitness = model.fitness, let paces = fitness.paces, let vdot = fitness.vdot {
                    VStack(alignment: .leading, spacing: 4) {
                        Kicker("Running · VDOT \(TodayFormat.number(vdot.current))")
                        Text("EASY PACE").font(AppFont.title(44)).foregroundStyle(Color.ink)
                    }
                    .padding(.horizontal, 4)

                    let easy = paces.zones.easy
                    PaceTape(band: easy, range: (easy.fromS - 9) / 5 * 5...(easy.toS + 11) / 5 * 5, numbers: 66,
                             leftNote: paces.peakEasy.map { "‹ 2015 · \(RunFormat.pace($0.fromS))" })
                        .padding(.top, 6)
                    rules(paces)
                    WayBackCard(vdot: vdot, lastRunDays: fitness.summary?.lastRun?.daysAgo)
                    PacesCard(paces: paces)
                    FeltCard(runs: Array(model.feltRuns.suffix(7)), eased: paces.easedS ?? 0)
                } else {
                    Text("Running data isn't here yet. Pull to refresh on Today once the Mac is reachable.")
                        .font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                        .card()
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .overlay(alignment: .top) {
            // Keeps scrolled cards from running under the status bar (same as Today).
            Color.bg.frame(height: 0).background(Color.bg).allowsHitTesting(false)
        }
        .background(Color.bg)
        .toolbar(.hidden, for: .navigationBar)
        .task { await model.load() }
    }

    private func rules(_ paces: RunningFitness.Paces) -> some View {
        (Text("Talk in full sentences. Walk when your heart rate passes ")
         + Text("\(paces.hrCapBpm ?? 162)").font(AppFont.number(17)).foregroundStyle(Color.ink)
         + Text(". On hills, follow heart rate, not pace."))
            .font(AppFont.body(14))
            .foregroundStyle(Color.inkSoft)
            .lineSpacing(3)
            .padding(.horizontal, 4)
            .padding(.bottom, 6)
    }
}

/// VDOT on a ruler: now, the 8-week projection and the peak standing on it.
private struct WayBackCard: View {
    let vdot: RunningFitness.Vdot
    let lastRunDays: Int?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("The way back")
                Spacer()
                if let share = vdot.shareOfPeakPct { Kicker("\(share)% of peak", color: .run) }
            }
            ruler.frame(height: 124).padding(.top, 16)
            Text(note).font(AppFont.body(12)).foregroundStyle(Color.muted).lineSpacing(2).padding(.top, 10)
        }
        .card()
    }

    private var note: String {
        let basis = vdot.basis == "heart_rate" ? "VDOT from heart rate on your recent runs." : "VDOT from your best recent effort."
        guard let days = lastRunDays, days > 7 else { return basis }
        return basis + " Last run \(days) days ago."
    }

    private var ruler: some View {
        let peak = vdot.peak?.vdot
        let low = floor(min(vdot.current, 40) / 10) * 10 - (vdot.current < 32 ? 10 : 0)
        let high = max(peak ?? vdot.projected, vdot.projected) + 2
        let peakYear = vdot.peak.flatMap { TodayFormat.parse($0.date) }.map { String(Calendar(identifier: .gregorian).component(.year, from: $0)) }
        return Canvas { context, size in
            let x = { (value: Double) -> CGFloat in CGFloat((value - low) / (high - low)) * size.width }
            let now = x(vdot.current), ahead = x(vdot.projected)
            context.fill(Path(roundedRect: CGRect(x: now, y: 82, width: max(0, ahead - now), height: 18), cornerRadius: 4),
                         with: .color(Color.run.opacity(0.18)))
            for value in Int(low)...Int(high) {
                let tall = value % 10 == 0
                var tick = Path()
                tick.move(to: CGPoint(x: x(Double(value)), y: 96 - (tall ? 10 : 5)))
                tick.addLine(to: CGPoint(x: x(Double(value)), y: 96))
                context.stroke(tick, with: .color(Double(value) <= vdot.current ? Color.run : Color(hex: 0x343A47)),
                               style: StrokeStyle(lineWidth: tall ? 1.4 : 1, lineCap: .round))
                // Tens under the ruler, except where the projection note runs.
                let px = x(Double(value))
                if tall, !(now - 8...now + 110).contains(px) {
                    let anchor: UnitPoint = px < 10 ? .topLeading : (px > size.width - 10 ? .topTrailing : .top)
                    context.draw(Text("\(value)").font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color(hex: 0x5B6375)),
                                 at: CGPoint(x: px, y: 106), anchor: anchor)
                }
            }
            func stand(_ at: CGFloat, value: String, label: String, size: CGFloat, color: Color) {
                var line = Path()
                line.move(to: CGPoint(x: at, y: 68))
                line.addLine(to: CGPoint(x: at, y: 100))
                context.stroke(line, with: .color(color), style: StrokeStyle(lineWidth: 2, lineCap: .round))
                context.draw(Text(value).font(AppFont.number(size)).foregroundStyle(color), at: CGPoint(x: at, y: 42), anchor: .bottom)
                context.draw(Text(label).font(AppFont.body(10, weight: .bold)).tracking(1.2).foregroundStyle(color == .ink ? Color.muted : color),
                             at: CGPoint(x: at, y: 50), anchor: .top)
            }
            stand(now, value: TodayFormat.number(vdot.current), label: "NOW", size: 44, color: .ink)
            if let peak {
                stand(x(peak), value: TodayFormat.number(peak), label: peakYear ?? "PEAK", size: 28, color: Color(hex: 0x5B6375))
            }
            context.draw(Text("→ \(Int(vdot.projected.rounded())) in \(vdot.projectionWeeks) weeks").font(AppFont.body(10, weight: .bold)).foregroundStyle(Color.run),
                         at: CGPoint(x: now + 6, y: 112), anchor: .leading)
        }
        .accessibilityElement()
        .accessibilityLabel("VDOT \(TodayFormat.number(vdot.current)) now, about \(Int(vdot.projected.rounded())) in \(vdot.projectionWeeks) weeks" + (peak.map { ", peak \(TodayFormat.number($0))" } ?? ""))
    }
}

/// Every pace in its own colour, with what a session looks like and when it opens.
private struct PacesCard: View {
    let paces: RunningFitness.Paces

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("All paces at \(TodayFormat.number(paces.vdot))")
                Spacer()
                Kicker("min / km", color: Color(hex: 0x5B6375))
            }
            ForEach(Array(RunFormat.zones(paces).enumerated()), id: \.element.id) { index, zone in
                HStack(spacing: 14) {
                    RoundedRectangle(cornerRadius: 2).fill(zone.color).frame(width: 4)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(zone.name).font(AppFont.body(16, weight: .semibold)).foregroundStyle(Color.ink)
                        Text(zone.use).font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                    Spacer(minLength: 8)
                    VStack(alignment: .trailing, spacing: 3) {
                        Text(zone.pace).font(AppFont.number(24)).foregroundStyle(zone.color).lineLimit(1).fixedSize()
                        if index == 0 {
                            Text("TODAY").font(AppFont.body(11, weight: .bold)).tracking(0.9).foregroundStyle(zone.color)
                        } else if let opens = zone.opens {
                            Label(opens, systemImage: "lock")
                                .font(AppFont.body(11))
                                .foregroundStyle(Color.faint)
                                .labelStyle(TightLabel())
                        }
                    }
                }
                .padding(.vertical, 13)
                .overlay(alignment: .top) {
                    if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                }
                .accessibilityElement(children: .combine)
            }
        }
        .padding(.bottom, -6)
        .card()
    }
}

private struct TightLabel: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 4) {
            configuration.icon.font(.system(size: 9, weight: .semibold))
            configuration.title
        }
    }
}

/// The last easy runs as dots coloured by how they felt, the next one dashed.
private struct FeltCard: View {
    let runs: [RunningFitness.FeltRun]
    let eased: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("How easy runs felt")
                Spacer()
                HStack(spacing: 10) {
                    ForEach(RunFeel.allCases, id: \.self) { feel in
                        HStack(spacing: 4) {
                            Circle().fill(RunFormat.feelColor(feel)).frame(width: 6, height: 6)
                            Text(feel.label)
                        }
                    }
                }
                .font(AppFont.body(11))
                .foregroundStyle(Color.muted)
            }
            FeltDots(runs: runs, trailing: "next").padding(.top, 14)
            Text(eased > 0
                 ? "Two hard runs in a row, so the band is eased by \(eased) s/km until one feels easy."
                 : "The band holds while runs feel easy. Two hard in a row ease it by 10 s/km.")
                .font(AppFont.body(12)).foregroundStyle(Color.muted).lineSpacing(2).padding(.top, 14)
        }
        .card()
    }
}

/// One dot per run with its date; an untapped run is a dashed ring.
struct FeltDots: View {
    let runs: [RunningFitness.FeltRun]
    /// A dashed slot at the end ("next"); nil for none.
    var trailing: String?
    /// Rings the last dot in volt (the one just tapped).
    var highlightLast = false

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(runs.enumerated()), id: \.element.id) { index, run in
                cell(feel: run.felt, label: RunFormat.shortDate(run.date), ring: highlightLast && index == runs.count - 1, next: false)
            }
            if let trailing {
                cell(feel: nil, label: trailing, ring: false, next: true)
            }
        }
        .accessibilityElement()
        .accessibilityLabel(runs.compactMap { $0.felt?.label }.joined(separator: ", "))
    }

    /// A tapped run is a filled dot; an untapped one a faint ring; the next run a dashed ring.
    private func cell(feel: RunFeel?, label: String, ring: Bool, next: Bool) -> some View {
        VStack(spacing: 8) {
            Group {
                if let feel {
                    Circle().fill(RunFormat.feelColor(feel))
                        .overlay { if ring { Circle().strokeBorder(Color.volt, lineWidth: 1.5).padding(-4) } }
                } else if next {
                    Circle().strokeBorder(Color.dim, style: StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
                } else {
                    Circle().fill(Color.track).padding(5)
                }
            }
            .frame(width: 22, height: 22)
            Text(label).font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.faint)
        }
        .frame(maxWidth: .infinity)
    }
}
