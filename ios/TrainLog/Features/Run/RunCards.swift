import SwiftUI

/// The top of Today's card on a run day: today's easy pace on the tape, or the return-to-run step
/// while a program is on. The card itself (border, rehab row, menu) belongs to `SessionCard`.
struct RunCardContent: View {
    let fitness: RunningFitness
    let session: PhoneToday.Session

    var body: some View {
        if let rtr = fitness.returnToRun, rtr.active, let blocks = rtr.blocks, !blocks.isEmpty {
            ReturnToRunContent(rtr: rtr, blocks: blocks, paces: fitness.paces)
        } else if let paces = fitness.paces {
            EasyRunContent(paces: paces, minutes: session.durationMin, title: session.intentLabel)
        }
    }
}

private struct EasyRunContent: View {
    let paces: RunningFitness.Paces
    let minutes: Int?
    let title: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            RunCardHeader(left: title.map { "\($0) run" } ?? "Easy run", right: minutes.map { "\($0) min" })
            PaceTape(band: paces.zones.easy, leftNote: paces.peakEasy.map { "‹ 2015 · \(RunFormat.pace($0.fromS))" })
                .padding(.top, 18)
            RunCardFooter {
                Label { Text("Under \(paces.hrCapBpm ?? 162) bpm") } icon: { Image(systemName: "heart.fill").font(.system(size: 10)) }
                FooterPipe()
                Text(paces.easedS ?? 0 > 0 ? "Eased 10 s after hard runs" : "Talk test")
            }
        }
    }
}

private struct ReturnToRunContent: View {
    let rtr: RunningFitness.ReturnToRun
    let blocks: [RunningFitness.Block]
    let paces: RunningFitness.Paces?

    var body: some View {
        let headline = RunFormat.stageHeadline(blocks)
        VStack(alignment: .leading, spacing: 0) {
            RunCardHeader(left: "Return to run", right: rtr.stage.map { "Step \($0) of \(rtr.stages ?? 6)" })
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(headline.big).font(AppFont.number(56)).foregroundStyle(Color.ink)
                Text(blocks.dropFirst().contains { !$0.isJog } ? "jog : walk minutes\n\(headline.line)" : headline.line)
                    .font(AppFont.body(14)).foregroundStyle(Color.inkSoft).lineSpacing(2)
            }
            .padding(.top, 16)
            BlockTape(blocks: blocks).padding(.top, 16)
            if let names = rtr.stageNames, let stage = rtr.stage {
                StageBar(names: names, stage: stage).padding(.top, 16)
            }
            RunCardFooter {
                Label { Text("Under \(paces?.hrCapBpm ?? 162) bpm") } icon: { Image(systemName: "heart.fill").font(.system(size: 10)) }
                FooterPipe()
                if rtr.paceTarget == true, let easy = paces?.zones.easy {
                    Text(RunFormat.band(easy) + " /km")
                } else {
                    Text("No pace target")
                }
            }
        }
    }
}

/// The session laid out in minutes: jog blocks in orange, walks as a teal line.
private struct BlockTape: View {
    let blocks: [RunningFitness.Block]

    var body: some View {
        let total = max(1, blocks.reduce(0) { $0 + $1.minutes })
        Canvas { context, size in
            let x = { (minute: Double) -> CGFloat in CGFloat(minute / Double(total)) * size.width }
            var at = 0.0
            for block in blocks {
                let start = x(at), end = x(at + Double(block.minutes))
                if block.isJog {
                    context.fill(Path(roundedRect: CGRect(x: start + 1, y: 18, width: end - start - 2, height: 24), cornerRadius: 5),
                                 with: .color(.run))
                } else {
                    var line = Path()
                    line.move(to: CGPoint(x: start + 2, y: 30))
                    line.addLine(to: CGPoint(x: max(start + 2, end - 2), y: 30))
                    context.stroke(line, with: .color(Color.mobility.opacity(0.7)), style: StrokeStyle(lineWidth: 4, lineCap: .round))
                }
                at += Double(block.minutes)
            }
            for minute in 0..<total {
                var tick = Path()
                let length: CGFloat = minute % 5 == 0 ? 8 : 4
                tick.move(to: CGPoint(x: x(Double(minute)), y: 56 - length))
                tick.addLine(to: CGPoint(x: x(Double(minute)), y: 56))
                context.stroke(tick, with: .color(Color.tick), lineWidth: 1)
            }
            func label(_ text: String, _ minute: Double, _ anchor: UnitPoint) {
                context.draw(Text(text).font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.subtle),
                             at: CGPoint(x: x(minute), y: 62), anchor: anchor)
            }
            label("0", 0, .topLeading)
            for minute in stride(from: 10, to: total - 4, by: 10) { label("\(minute)", Double(minute), .top) }
            label("\(total) min", Double(total), .topTrailing)
            if let first = blocks.first, !first.isJog {
                context.draw(Text("WALK").font(AppFont.body(10, weight: .bold)).tracking(1).foregroundStyle(Color.mobility),
                             at: CGPoint(x: 0, y: 0), anchor: .topLeading)
            }
            if let jogIndex = blocks.firstIndex(where: \.isJog) {
                let start = blocks[..<jogIndex].reduce(0) { $0 + $1.minutes }
                let jog = blocks[jogIndex]
                context.draw(Text("JOG \(jog.minutes)").font(AppFont.body(10, weight: .bold)).tracking(1).foregroundStyle(Color.run),
                             at: CGPoint(x: x(Double(start) + Double(jog.minutes) / 2), y: 0), anchor: .top)
            }
        }
        .frame(height: 76)
        .accessibilityElement()
        .accessibilityLabel(blocks.map { "\($0.minutes) min \($0.isJog ? "jog" : "walk")" }.joined(separator: ", "))
    }
}

/// The program's steps, done ones in orange and today's ringed.
private struct StageBar: View {
    let names: [String]
    let stage: Int

    var body: some View {
        HStack(alignment: .top, spacing: 5) {
            ForEach(Array(names.enumerated()), id: \.offset) { index, name in
                let number = index + 1
                VStack(spacing: 7) {
                    Capsule()
                        .fill(number <= stage ? Color.run : Color.track)
                        .frame(height: 6)
                        .overlay {
                            if number == stage {
                                Capsule().strokeBorder(Color.run, lineWidth: 1).padding(-3)
                            }
                        }
                    Text(RunFormat.stageShort(name))
                        .font(AppFont.number(13))
                        .foregroundStyle(number == stage ? Color.ink : (number < stage ? Color.muted : Color.subtle))
                }
                .frame(maxWidth: .infinity)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Step \(stage) of \(names.count)")
    }
}

struct RunCardHeader: View {
    let left: String
    let right: String?

    var body: some View {
        HStack {
            HStack(spacing: 8) {
                Circle().fill(Color.run).frame(width: 8, height: 8)
                Kicker(left, color: .ink)
            }
            Spacer()
            if let right { Kicker(right) }
        }
    }
}

private struct RunCardFooter<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        VStack(spacing: 0) {
            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 16)
            HStack {
                HStack(spacing: 7) { content }
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineLimit(1)
                Spacer(minLength: 8)
                HStack(spacing: 6) {
                    Text("Guide").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink)
                    Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold)).foregroundStyle(Color.muted)
                }
            }
            .frame(height: 44)
        }
    }
}

private struct FooterPipe: View {
    var body: some View {
        Text("|").foregroundStyle(Color.dim).padding(.horizontal, 3)
    }
}
