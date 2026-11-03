import SwiftUI

/// Plan a week, refine one, or change one day with the coach: the note, the wait, then what changed.
struct PlanCoachSheet: View {
    @Bindable var coach: PlanCoachModel
    /// The saved week the task is about (nil while planning an unsaved week).
    let week: WeeklyPlan?
    let today: String
    let onRefine: () -> Void
    @Environment(\.dismiss) private var dismiss
    @FocusState private var typing: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Capsule().fill(Color(hex: 0x3A404C)).frame(width: 36, height: 5).frame(maxWidth: .infinity).padding(.bottom, 12)
            if let task = coach.task {
                switch coach.phase {
                case .compose: compose(task)
                case .working(let stage): working(task, stage: stage)
                case .done(let result): done(result)
                case .failed(let message): failed(task, message: message)
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(.snappy(duration: 0.25), value: coach.phase)
    }

    // MARK: - Compose

    @ViewBuilder
    private func compose(_ task: PlanCoachTask) -> some View {
        head(kicker: kicker(task), title: composeTitle(task))
        if case .day(_, let date) = task {
            if let day = week?.days.first(where: { $0.date == date }) { sessionLine(day).padding(.top, 12) }
        } else {
            let dates = stripDates(task)
            Text(stripCaption(task))
                .font(AppFont.body(12))
                .foregroundStyle(Color.muted)
                .padding(.top, 12)
                .padding(.bottom, 8)
            PlanWeekStrip(days: composeStrip(task, mentioned: PlanCoachFormat.mentioned(coach.note, in: dates)), showMinutes: week != nil && !isPlan(task)) { date in
                coach.note = PlanCoachFormat.toggleDay(coach.note, date: date)
                typing = true
            }
        }
        noteField(task).padding(.top, 14)
        chips(task).padding(.top, 12)
        Spacer(minLength: 12)
        helperState
        Button(sendLabel(task)) {
            typing = false
            coach.send()
        }
        .buttonStyle(SendButtonStyle(enabled: coach.canSend))
        .disabled(!coach.canSend)
        Text(composeFoot(task))
            .font(AppFont.body(12))
            .foregroundStyle(Color.muted)
            .frame(maxWidth: .infinity)
            .padding(.top, 10)
    }

    private func noteField(_ task: PlanCoachTask) -> some View {
        TextField(placeholder(task), text: $coach.note, axis: .vertical)
            .font(AppFont.body(15))
            .foregroundStyle(Color.ink)
            .tint(.volt)
            .lineLimit(3...6)
            .focused($typing)
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(minHeight: 92, alignment: .topLeading)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func chips(_ task: PlanCoachTask) -> some View {
        let options = switch task {
        case .plan: PlanCoachFormat.planSuggestions
        case .refine: PlanCoachFormat.refineSuggestions
        case .day: PlanCoachFormat.daySuggestions
        }
        return FlowLayout(spacing: 0) {
            ForEach(options, id: \.self) { option in
                Button {
                    coach.note = PlanCoachFormat.adding(option, to: coach.note)
                } label: {
                    HStack(spacing: 6) {
                        Text("+").foregroundStyle(Color.muted).fontWeight(.semibold)
                        Text(option).foregroundStyle(Color(hex: 0xC9CFDA))
                    }
                    .font(AppFont.body(13, weight: .medium))
                    .padding(.horizontal, 12)
                    .frame(height: 32)
                    .overlay(Capsule().strokeBorder(Color.outline))
                    .padding(.trailing, 8)
                    .frame(minHeight: 40)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
    }

    @ViewBuilder
    private var helperState: some View {
        switch coach.helper {
        case .down(let detail):
            stateCard(color: .run, title: "Coach is offline", text: detail).padding(.bottom, 12)
        case .away:
            stateCard(color: .faint, title: "Mac out of reach",
                      text: "Planning runs on the Mac. Your note is kept; send it when you're back on home Wi-Fi.").padding(.bottom, 12)
        case .unknown, .up:
            EmptyView()
        }
    }

    // MARK: - Working

    @ViewBuilder
    private func working(_ task: PlanCoachTask, stage: String) -> some View {
        head(kicker: kicker(task), title: workingTitle(task))
        if case .day = task {
            EmptyView()
        } else {
            PlanWeekStrip(days: PlanCoachFormat.ghost(task.week).map { PlanWeekStrip.Day(date: $0.date, color: nil, minutes: 0, style: .normal) },
                      showMinutes: false, pending: true)
                .padding(.top, 18)
        }
        HStack(alignment: .top, spacing: 12) {
            ProgressView().tint(.volt).padding(.top, 1)
            VStack(alignment: .leading, spacing: 3) {
                Text(stage).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
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
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
                .padding(.top, 16)
        }
        Spacer(minLength: 12)
        Button("Close · keeps going on the Mac") { dismiss() }
            .buttonStyle(OutlineButtonStyle(height: 48))
            .font(AppFont.body(14, weight: .semibold))
    }

    // MARK: - Done

    @ViewBuilder
    private func done(_ result: PlanCoachResult) -> some View {
        let isPlan = isPlan(result.task)
        head(kicker: "\(isPlan ? "Planned" : "Revised") · \(PlanCoachFormat.clock(result.seconds))", kickerColor: .volt, title: doneTitle(result))
        if !result.days.isEmpty {
            PlanWeekStrip(days: result.days).padding(.top, 16)
        }
        if isPlan {
            HStack(alignment: .firstTextBaseline, spacing: 18) {
                Text(ActivityFormat.compactDuration(Double(result.totalMinutes)).replacingOccurrences(of: " ", with: ""))
                    .font(AppFont.number(34))
                    .foregroundStyle(Color.ink)
                HStack(spacing: 12) {
                    ForEach(result.mix, id: \.label) { part in
                        HStack(spacing: 5) {
                            Circle().fill(part.sport.color).frame(width: 6, height: 6)
                            Text(part.label).font(AppFont.body(11)).foregroundStyle(Color.inkSoft)
                        }
                    }
                }
            }
            .padding(.top, 16)
            if let summary = result.summary {
                ScrollView {
                    Text(summary).font(AppFont.body(14)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .scrollBounceBehavior(.basedOnSize)
                .padding(.top, 12)
            }
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(result.changes.enumerated()), id: \.element.date) { index, change in
                        changeRow(change)
                        if index < result.changes.count - 1 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                    }
                    if let summary = result.summary {
                        Text(summary).font(AppFont.body(13)).foregroundStyle(Color.muted).lineSpacing(2).padding(.top, 8)
                    }
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .padding(.top, 12)
        }
        Spacer(minLength: 12)
        Button(isPlan ? "See week \(PlanCoachFormat.weekNumber(result.task.week))" : "Done") { dismiss() }
            .buttonStyle(VoltButtonStyle())
        Button(isPlan ? "Refine" : "Refine again") { onRefine() }
            .font(AppFont.body(14, weight: .semibold))
            .foregroundStyle(Color.inkSoft)
            .frame(maxWidth: .infinity, minHeight: 44)
            .padding(.top, 6)
    }

    private func changeRow(_ change: PlanCoachFormat.Change) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(PlanCoachFormat.weekday(change.date)).font(AppFont.number(15)).foregroundStyle(Color.ink).frame(width: 32, alignment: .leading)
            VStack(alignment: .leading, spacing: 2) {
                Text(change.was ?? "Free day").font(AppFont.body(12)).foregroundStyle(Color.faint).strikethrough(color: Color.dim)
                Text(change.now ?? "Free day").font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 11)
    }

    // MARK: - Failed

    @ViewBuilder
    private func failed(_ task: PlanCoachTask, message: String) -> some View {
        head(kicker: kicker(task), title: composeTitle(task))
        stateCard(color: Color(hex: 0xFF5C6C), title: "The coach couldn't finish", text: message).padding(.top, 18)
        Spacer(minLength: 12)
        Button("Try again") { coach.retry() }
            .buttonStyle(OutlineButtonStyle(height: 48))
            .font(AppFont.body(14, weight: .semibold))
    }

    // MARK: - Parts

    private func head(kicker: String, kickerColor: Color = .muted, title: String) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(kicker, color: kickerColor)
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
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.cardBorder))
    }

    // MARK: - Copy

    private func isPlan(_ task: PlanCoachTask) -> Bool {
        if case .plan = task { return true }
        return false
    }

    private func kicker(_ task: PlanCoachTask) -> String {
        if case .day(_, let date) = task { return ActivityFormat.longDay(date) }
        return PlanFormat.weekKicker(task.week)
    }

    /// The session being changed: sport bar, title, minutes (as in Move session).
    private func sessionLine(_ day: PlanDay) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 2).fill(PlanFormat.sport(day).color).frame(width: 4, height: 32)
            VStack(alignment: .leading, spacing: 2) {
                Text(PlanFormat.rowTitle(day.title)).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                Text(PlanFormat.plannedMeta(day)).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
            }
        }
    }

    private func composeTitle(_ task: PlanCoachTask) -> String {
        switch task {
        case .plan: "Plan the week"
        case .refine: "Refine the week"
        case .day: "Change this day"
        }
    }

    private func workingTitle(_ task: PlanCoachTask) -> String {
        switch task {
        case .plan: "Planning…"
        case .refine: "Refining…"
        case .day(_, let date): "Changing \(PlanCoachFormat.weekday(date))…"
        }
    }

    private func doneTitle(_ result: PlanCoachResult) -> String {
        switch result.task {
        case .plan(let week): return "Week \(PlanCoachFormat.weekNumber(week)) is ready"
        case .day(_, let date): return result.changes.isEmpty ? "\(PlanCoachFormat.weekday(date)) stays" : "\(PlanCoachFormat.weekday(date)) changed"
        case .refine:
            switch result.changes.count {
            case 0: return "Nothing changed"
            case 1: return "1 day changed"
            case let n: return "\(n) days changed"
            }
        }
    }

    private func sendLabel(_ task: PlanCoachTask) -> String {
        switch task {
        case .plan(let week): "Plan week \(PlanCoachFormat.weekNumber(week))"
        case .refine: "Send to coach"
        case .day: "Ask coach"
        }
    }

    private func placeholder(_ task: PlanCoachTask) -> String {
        switch task {
        case .plan: "Anything different next week? Optional"
        case .refine: "What should change?"
        case .day: "What should this day be instead?"
        }
    }

    private func composeFoot(_ task: PlanCoachTask) -> String {
        switch task {
        case .plan: "Takes 2–5 min on the Mac · you can close this"
        case .refine: "Done and past days stay as they are"
        case .day(_, let date): "Only \(ActivityFormat.longDay(date).components(separatedBy: " ").first ?? "this day") changes · the rest of the week stays"
        }
    }

    private func stripDates(_ task: PlanCoachTask) -> [String] {
        (0..<7).map { PlanFormat.addingDays($0, to: task.week) }
    }

    private func stripCaption(_ task: PlanCoachTask) -> String {
        guard case .refine = task, let week else { return "Tap a day to mention it" }
        let range = PlanCoachFormat.range(PlanCoachFormat.editableDates(week, today: today))
        return "The coach can change \(range) · tap a day to mention it"
    }

    private func composeStrip(_ task: PlanCoachTask, mentioned: Set<String>) -> [PlanWeekStrip.Day] {
        if case .refine = task, let week {
            return PlanCoachFormat.strip(week, today: today, selected: mentioned, editable: Set(PlanCoachFormat.editableDates(week, today: today)))
        }
        return PlanCoachFormat.ghost(task.week, selected: mentioned)
    }
}

/// The volt send button, flat grey while there's nothing to send or the coach can't be reached.
private struct SendButtonStyle: ButtonStyle {
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
