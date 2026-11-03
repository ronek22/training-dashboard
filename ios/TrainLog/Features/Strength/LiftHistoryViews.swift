import SwiftUI

/// The line under the lift name: a tiny ladder of the last sessions with today's target as a pink
/// ring, and "Last 77.5 × 6 · 3 sets · Oct 15". Tapping it opens `LiftHistorySheet`.
struct LiftHistoryLine: View {
    let history: LiftHistory
    let target: Double?
    let action: () -> Void

    var body: some View {
        if let line = LiftLogic.lastLine(history) {
            Button(action: action) {
                HStack(spacing: 10) {
                    if LiftLogic.plotted(history).count > 1 {
                        Sparkladder(values: values, target: target).frame(width: 56, height: 18)
                    }
                    (Text("Last ") + Text(line.top).foregroundColor(.ink).fontWeight(.semibold) + Text(" · \(line.rest)"))
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.inkSoft)
                        .lineLimit(1)
                    Image(systemName: "chevron.right")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Color(hex: 0x5A6375))
                }
                .padding(.leading, 8)
                .padding(.trailing, 10)
                .frame(height: 30)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.cardBorder))
                .frame(minHeight: 44)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .padding(.leading, -8)
            .accessibilityLabel("Last time \(line.top), \(line.rest). Show history")
        }
    }

    private var values: [Double] {
        let metric = LiftLogic.metric(of: history)
        return LiftLogic.plotted(history).suffix(4).compactMap { LiftLogic.value(of: $0, metric) }
    }
}

/// Dots joined by a line, oldest first, with an optional dashed step to today's target.
private struct Sparkladder: View {
    let values: [Double]
    let target: Double?

    var body: some View {
        Canvas { context, size in
            let all = values + (target.map { [$0] } ?? [])
            guard let low = all.min(), let high = all.max() else { return }
            let span = max(high - low, 0.0001)
            let step = size.width / CGFloat(max(all.count - 1, 1))
            func point(_ index: Int, _ value: Double) -> CGPoint {
                let x = all.count == 1 ? size.width / 2 : CGFloat(index) * step
                let y = 2.5 + (1 - CGFloat((value - low) / span)) * (size.height - 5)
                return CGPoint(x: min(max(x, 2.5), size.width - 2.5), y: y)
            }
            var line = Path()
            for (index, value) in values.enumerated() {
                index == 0 ? line.move(to: point(index, value)) : line.addLine(to: point(index, value))
            }
            context.stroke(line, with: .color(Color(hex: 0x4A5263)), lineWidth: 1.5)
            if let target, let last = values.last {
                var ghost = Path()
                ghost.move(to: point(values.count - 1, last))
                ghost.addLine(to: point(values.count, target))
                context.stroke(ghost, with: .color(.strength), style: StrokeStyle(lineWidth: 1.5, dash: [2, 2]))
                let end = point(values.count, target)
                context.stroke(Path(ellipseIn: CGRect(x: end.x - 2.5, y: end.y - 2.5, width: 5, height: 5)), with: .color(.strength), lineWidth: 1.5)
            }
            for (index, value) in values.enumerated() {
                let center = point(index, value)
                let color = index == values.count - 1 ? Color.ink : Color.inkSoft
                context.fill(Path(ellipseIn: CGRect(x: center.x - 2.5, y: center.y - 2.5, width: 5, height: 5)), with: .color(color))
            }
        }
        .accessibilityHidden(true)
    }
}

/// Top load (or reps, or hold) per session, with today's target as the next step.
struct LiftHistorySheet: View {
    let history: LiftHistory
    let target: Double?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Kicker("\(history.exerciseName) · last \(plotted.count) \(plotted.count == 1 ? "session" : "sessions")")
                LadderChart(sessions: plotted, metric: metric, target: target, best: bestValue)
                    .frame(height: 204)
                    .padding(.top, 10)
                VStack(spacing: 0) {
                    ForEach(Array(history.sessions.enumerated()), id: \.offset) { index, session in
                        if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                        HStack(spacing: 12) {
                            Text(LiftLogic.shortDate(session.date))
                                .font(AppFont.body(13))
                                .foregroundStyle(Color.muted)
                                .frame(width: 56, alignment: .leading)
                            Text(LiftLogic.setsLine(session))
                                .font(AppFont.number(18))
                                .foregroundStyle(Color.ink)
                                .lineLimit(1)
                                .minimumScaleFactor(0.7)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Text(LiftLogic.feel(session) ?? "")
                                .font(AppFont.body(12))
                                .foregroundStyle(Color.muted)
                        }
                        .frame(minHeight: 44)
                        .accessibilityElement(children: .combine)
                    }
                }
                .padding(.top, 8)
                if let best = LiftLogic.bestLine(history, target: target) {
                    (Text("Best ") + Text(best.best).foregroundColor(.volt).fontWeight(.semibold) + Text(" \(best.tail)"))
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.muted)
                        .padding(.top, 10)
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 22)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
    }

    private var metric: LiftLogic.Metric { LiftLogic.metric(of: history) }
    private var plotted: [LiftHistory.Session] { LiftLogic.plotted(history) }

    private var bestValue: Double? {
        guard let best = history.best else { return nil }
        switch metric {
        case .load: return best.weightKg
        case .reps: return best.weightKg == nil ? best.reps.map(Double.init) : nil
        case .seconds: return best.seconds.map(Double.init)
        }
    }
}

private struct LadderChart: View {
    let sessions: [LiftHistory.Session]
    let metric: LiftLogic.Metric
    let target: Double?
    let best: Double?

    var body: some View {
        GeometryReader { proxy in
            let values = sessions.compactMap { LiftLogic.value(of: $0, metric) }
            let all = values + (target.map { [$0] } ?? [])
            let low = all.min() ?? 0
            let span = max((all.max() ?? 1) - low, 0.0001)
            let columns = all.count
            let inset: CGFloat = 30
            let step = columns > 1 ? (proxy.size.width - inset * 2) / CGFloat(columns - 1) : 0
            let x = { (index: Int) in columns > 1 ? inset + CGFloat(index) * step : proxy.size.width / 2 }
            let y = { (value: Double) in 40 + (1 - CGFloat((value - low) / span)) * 90 }

            ZStack(alignment: .topLeading) {
                Path { path in
                    for (index, value) in values.enumerated() {
                        let point = CGPoint(x: x(index), y: y(value))
                        index == 0 ? path.move(to: point) : path.addLine(to: point)
                    }
                }
                .stroke(Color.dim, style: StrokeStyle(lineWidth: 2, lineJoin: .round))
                if let target, let last = values.last {
                    Path { path in
                        path.move(to: CGPoint(x: x(values.count - 1), y: y(last)))
                        path.addLine(to: CGPoint(x: x(values.count), y: y(target)))
                    }
                    .stroke(Color.strength, style: StrokeStyle(lineWidth: 2, dash: [4, 4]))
                }
                ForEach(Array(sessions.enumerated()), id: \.offset) { index, session in
                    let value = values[index]
                    let isBest = value == best
                    let isLast = index == values.count - 1
                    dot(isBest: isBest, isLast: isLast).position(x: x(index), y: y(value))
                    Text(label(value))
                        .font(AppFont.number(20))
                        .foregroundStyle(isBest ? Color.volt : isLast ? Color.ink : Color.inkSoft)
                        .fixedSize()
                        .position(x: x(index), y: y(value) - 20)
                    footer(LiftLogic.shortDate(session.date), LiftLogic.setsLabel(session, metric), today: false)
                        .position(x: x(index), y: 182)
                }
                if let target {
                    Circle().fill(Color.card).frame(width: 14, height: 14)
                        .overlay(Circle().strokeBorder(Color.strength, lineWidth: 2))
                        .position(x: x(values.count), y: y(target))
                    Text(label(target))
                        .font(AppFont.number(20))
                        .foregroundStyle(Color(hex: 0xFF7AB5))
                        .fixedSize()
                        .position(x: x(values.count), y: y(target) - 20)
                    footer("Today", nil, today: true).position(x: x(values.count), y: 182)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(sessions.map { "\(LiftLogic.shortDate($0.date)) \(LiftLogic.top(of: $0, metric))" }.joined(separator: ", "))
    }

    @ViewBuilder private func dot(isBest: Bool, isLast: Bool) -> some View {
        if isBest {
            Circle().fill(Color.card).frame(width: 14, height: 14)
                .overlay(Circle().strokeBorder(Color.volt, lineWidth: 2))
                .overlay(Circle().fill(Color.volt).frame(width: 7, height: 7))
        } else {
            Circle().fill(isLast ? Color.ink : Color.inkSoft).frame(width: isLast ? 12 : 10, height: isLast ? 12 : 10)
        }
    }

    private func footer(_ date: String, _ detail: String?, today: Bool) -> some View {
        VStack(spacing: 4) {
            Text(date)
                .font(AppFont.body(12, weight: today ? .semibold : .regular))
                .foregroundStyle(today ? Color(hex: 0xFF7AB5) : Color.muted)
            Text(detail ?? " ").font(AppFont.body(12)).foregroundStyle(Color(hex: 0x5A6375))
        }
        .fixedSize()
    }

    private func label(_ value: Double) -> String {
        metric == .seconds ? StrengthFormat.hold(Int(value)) : StrengthFormat.number(value)
    }
}

/// The bar end as you'd load it, with the plates named beside it (barbell lifts only).
struct PlateRow: View {
    let weight: Double?
    let kit: GymKit
    let onPick: (Double) -> Void

    var body: some View {
        if let weight {
            HStack(spacing: 10) {
                switch LiftLogic.fit(weight, kit: kit) {
                case .bar:
                    PlateSleeve(plates: [])
                    (Text("Empty bar").foregroundColor(.ink).fontWeight(.semibold) + Text(" · \(StrengthFormat.number(kit.bar)) kg"))
                case .plates(let plates):
                    PlateSleeve(plates: plates)
                    (Text(plates.map(LiftLogic.kg).joined(separator: " · ")).foregroundColor(.ink).fontWeight(.semibold) + Text(" a side"))
                case .off(let lower, let upper):
                    offText(weight, lower: lower, upper: upper)
                case .belowBar:
                    Text("Under the \(StrengthFormat.number(kit.bar)) kg bar")
                }
            }
            .font(AppFont.body(13))
            .foregroundStyle(Color.inkSoft)
            .lineLimit(1)
            .minimumScaleFactor(0.8)
            .frame(maxWidth: .infinity)
            .padding(.top, 2)
            .padding(.bottom, 8)
            .accessibilityElement(children: .combine)
        }
    }

    @ViewBuilder private func offText(_ weight: Double, lower: Double?, upper: Double?) -> some View {
        if let upper, let lower {
            Text("\(StrengthFormat.number(weight)) kg can't be loaded ·")
            pick(lower)
            Text("or")
            pick(upper)
        } else if let lower {
            Text("Most you can load is")
            pick(lower)
        }
    }

    private func pick(_ value: Double) -> some View {
        Button(StrengthFormat.number(value)) { onPick(value) }
            .font(AppFont.body(13, weight: .semibold))
            .foregroundStyle(Color.ink)
            .frame(minWidth: 32, minHeight: 32)
            .buttonStyle(.plain)
    }
}

private struct PlateSleeve: View {
    let plates: [Double]

    var body: some View {
        Canvas { context, size in
            let mid = size.height / 2
            context.fill(Path(roundedRect: CGRect(x: 0, y: mid - 2, width: size.width, height: 4), cornerRadius: 1), with: .color(Color(hex: 0x4A5263)))
            context.fill(Path(roundedRect: CGRect(x: 8, y: mid - 8, width: 5, height: 16), cornerRadius: 1), with: .color(Color(hex: 0x4A5263)))
            var x: CGFloat = 16
            for kg in plates {
                let (width, height) = Self.size(kg)
                guard x + width <= size.width else { break }
                context.fill(Path(roundedRect: CGRect(x: x, y: mid - height / 2, width: width, height: height), cornerRadius: width > 6 ? 2 : 1),
                             with: .color(.inkSoft))
                x += width + 2
            }
        }
        .frame(width: max(58, CGFloat(16 + plates.map { Self.size($0).0 + 2 }.reduce(0, +) + 8)), height: 40)
        .accessibilityHidden(true)
    }

    /// Width and height by plate weight: the big ones share a diameter, small ones shrink.
    static func size(_ kg: Double) -> (CGFloat, CGFloat) {
        switch kg {
        case 15...: (9, 40)
        case 10..<15: (7, 30)
        case 5..<10: (5, 22)
        case 2.5..<5: (4, 16)
        default: (3, 12)
        }
    }
}

/// Before the first barbell lift: the climb to the working weight, ticked off without logging.
struct WarmupRampCard: View {
    let working: Double
    let reps: Int
    let steps: [LiftLogic.RampStep]
    let ticked: Set<Int>
    let kit: GymKit
    let onTick: (Int) -> Void
    let onSkip: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Kicker("Warm-up · up to \(StrengthFormat.number(working)) kg")
                Spacer()
                Text("Tap each as you go").font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            VStack(spacing: 0) {
                ForEach(steps) { step in
                    if step.index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                    Button { onTick(step.index) } label: { row(step) }
                        .buttonStyle(.plain)
                        .sensoryFeedback(.selection, trigger: ticked.contains(step.index))
                }
                Rectangle().fill(Color.cardBorder).frame(height: 1)
                goalRow
            }
            .padding(.top, 8)
            Button("Skip warm-up", action: onSkip)
                .font(AppFont.body(13, weight: .semibold))
                .foregroundStyle(Color.inkSoft)
                .padding(.horizontal, 14)
                .frame(height: 32)
                .overlay(Capsule().strokeBorder(Color.outline))
                .frame(minHeight: 44)
                .contentShape(Capsule())
                .buttonStyle(.plain)
                .padding(.top, 4)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
    }

    private var currentIndex: Int? { steps.first { !ticked.contains($0.index) }?.index }

    private func row(_ step: LiftLogic.RampStep) -> some View {
        let done = ticked.contains(step.index)
        let isCurrent = step.index == currentIndex
        return HStack(spacing: 12) {
            marker(done: done, current: isCurrent)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 6).fill(Color.inset)
                    RoundedRectangle(cornerRadius: 6)
                        .fill(done ? Color.mobility.opacity(0.16) : Color.strength.opacity(isCurrent ? 0.22 : 0.1))
                        .frame(width: proxy.size.width * CGFloat(min(1, step.weight / working)))
                    HStack(spacing: 6) {
                        Text(step.isBar ? "Bar" : "\(StrengthFormat.number(step.weight)) kg")
                            .font(AppFont.number(18))
                            .foregroundStyle(done || isCurrent ? Color.ink : Color.inkSoft)
                        Text("× \(step.reps)").font(AppFont.body(13)).foregroundStyle(Color.muted)
                    }
                    .padding(.leading, 8)
                }
            }
            .frame(height: 22)
            Text(step.isBar ? "empty bar" : step.plates.map(LiftLogic.kg).joined(separator: " · "))
                .font(AppFont.body(12))
                .foregroundStyle(Color.muted)
                .lineLimit(1)
                .frame(width: 104, alignment: .trailing)
        }
        .frame(height: 46)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(step.isBar ? "Empty bar" : "\(StrengthFormat.number(step.weight)) kilograms") times \(step.reps)")
        .accessibilityAddTraits(done ? [.isButton, .isSelected] : .isButton)
    }

    private var goalRow: some View {
        HStack(spacing: 12) {
            Circle().strokeBorder(Color.outline, style: StrokeStyle(lineWidth: 1.5, dash: [3, 3])).frame(width: 22, height: 22)
            HStack(spacing: 6) {
                Text("\(StrengthFormat.number(working)) kg").font(AppFont.number(18))
                Text("× \(reps) · set 1").font(AppFont.body(13))
            }
            .foregroundStyle(Color(hex: 0x5A6375))
            .padding(.leading, 8)
            .frame(maxWidth: .infinity, minHeight: 22, alignment: .leading)
            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Color.outline, style: StrokeStyle(lineWidth: 1, dash: [3, 3])))
            Text(goalPlates).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1).frame(width: 104, alignment: .trailing)
        }
        .frame(height: 46)
        .accessibilityElement(children: .combine)
    }

    private var goalPlates: String {
        let side = (working - kit.bar) / 2
        return side > 0 ? "\(LiftLogic.kg(side)) a side" : ""
    }

    @ViewBuilder private func marker(done: Bool, current: Bool) -> some View {
        if done {
            Image(systemName: "checkmark")
                .font(.system(size: 10, weight: .heavy))
                .foregroundStyle(Color.mobility)
                .frame(width: 22, height: 22)
                .background(Color.mobility.opacity(0.18), in: Circle())
        } else if current {
            Circle().strokeBorder(Color.strength, lineWidth: 2).frame(width: 22, height: 22)
        } else {
            Circle().strokeBorder(Color(hex: 0x4A5263), style: StrokeStyle(lineWidth: 1.5, dash: [3, 3])).frame(width: 22, height: 22)
        }
    }
}
