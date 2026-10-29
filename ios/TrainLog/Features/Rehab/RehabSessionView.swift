import SwiftUI

/// Full-screen follow-along for today's rehab routine. Big type and big targets: the phone sits on
/// the floor next to the mat. The screen stays awake while it's open.
struct RehabSessionView: View {
    @State private var model = RehabSessionModel()
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var confirmClose = false

    var body: some View {
        VStack(spacing: 0) {
            topBar
            switch model.phase {
            case .loading:
                ProgressView().tint(.muted).frame(maxWidth: .infinity, maxHeight: .infinity)
            case .intro:
                intro
            case .running:
                if let step = model.current { running(step) }
            case .done:
                done
            case .empty:
                message("NOTHING LEFT TODAY", "Everything due today is ticked off. The rest of the routine is on its off day.")
            case .failed(let error):
                message("NOT SYNCED", "\(error)\nThe session comes from the Mac, so it needs the server once to start.")
            }
        }
        .background(Color.bg)
        .task { await model.load() }
        .onAppear { UIApplication.shared.isIdleTimerDisabled = true }
        .onDisappear {
            UIApplication.shared.isIdleTimerDisabled = false
            RestAlarm.cancel()
        }
        .onChange(of: scenePhase) {
            if scenePhase == .background {
                model.scheduleAlarm()
            } else if scenePhase == .active {
                RestAlarm.cancel()
                // A hold that ran out while locked moves on now.
                model.timerEnded(model.index)
            }
        }
        .confirmationDialog("Leave the rehab session?", isPresented: $confirmClose, titleVisibility: .visible) {
            Button("Finish now") { model.finish() }
            Button("Leave without saving", role: .destructive) { dismiss() }
        } message: {
            Text("Exercises you finished are already ticked.")
        }
    }

    // MARK: Chrome

    private var topBar: some View {
        VStack(spacing: 10) {
            HStack {
                Button {
                    if model.phase == .running { confirmClose = true } else { dismiss() }
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(Color.ink)
                        .frame(width: 40, height: 40)
                        .background(Color.raised, in: Circle())
                        .frame(width: 44, height: 44)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Close")
                Spacer()
                Kicker("Rehab", color: .mobility)
                Spacer()
                elapsed.frame(width: 44 + 20, alignment: .trailing)
            }
            if model.phase == .running || model.phase == .done {
                GeometryReader { proxy in
                    Capsule().fill(Color.track).overlay(alignment: .leading) {
                        Capsule().fill(Color.mobility).frame(width: proxy.size.width * model.progress)
                    }
                }
                .frame(height: 4)
                .animation(.snappy, value: model.progress)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    @ViewBuilder
    private var elapsed: some View {
        if let startedAt = model.startedAt {
            TimelineView(.periodic(from: .now, by: 1)) { context in
                Text(StrengthFormat.clock(Int((model.finishedAt ?? context.date).timeIntervalSince(startedAt))))
                    .font(AppFont.number(18))
                    .foregroundStyle(Color.muted)
                    .monospacedDigit()
            }
        }
    }

    // MARK: Intro

    private var intro: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 6) {
                        Kicker(introKicker, color: .mobility)
                        Text("TODAY'S REHAB").font(AppFont.title(40)).foregroundStyle(Color.ink)
                        if let issues = model.session?.issues, !issues.isEmpty {
                            Text(issues.joined(separator: " · ")).font(AppFont.body(14)).foregroundStyle(Color.muted)
                        }
                    }
                    if let watch = model.session?.watchWorkout {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "applewatch")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundStyle(Color.mobility)
                                .frame(width: 28)
                            VStack(alignment: .leading, spacing: 3) {
                                Text("Start a \(watch) workout on your Watch")
                                    .font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                                Text("It records heart rate and syncs as this rehab session.")
                                    .font(AppFont.body(13)).foregroundStyle(Color.muted)
                            }
                        }
                        .card(border: Color.mobility.opacity(0.35))
                    }
                    VStack(spacing: 0) {
                        ForEach(Array((model.session?.exercises ?? []).enumerated()), id: \.offset) { index, exercise in
                            if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                            HStack(alignment: .firstTextBaseline, spacing: 12) {
                                Text(String(format: "%02d", index + 1))
                                    .font(AppFont.number(16)).foregroundStyle(Color.mobility)
                                    .frame(width: 22, alignment: .leading)
                                Text(exercise.name).font(AppFont.body(15)).foregroundStyle(Color.ink)
                                Spacer(minLength: 8)
                                Text(exercise.dose?.components(separatedBy: ",").first ?? "")
                                    .font(AppFont.body(13)).foregroundStyle(Color.muted)
                                    .lineLimit(1)
                            }
                            .padding(.vertical, 12)
                        }
                    }
                    .padding(.horizontal, 16)
                    .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
                }
                .padding(16)
            }
            .scrollIndicators(.hidden)
            Button {
                model.start()
            } label: {
                Label(model.session?.watchWorkout != nil ? "Watch is running · start" : "Start", systemImage: "play.fill")
            }
            .buttonStyle(VoltButtonStyle())
            .padding(16)
        }
    }

    private var introKicker: String {
        let count = model.session?.exercises.count ?? 0
        return "\(count) exercise\(count == 1 ? "" : "s") · ~\(model.session?.durationMin ?? 0) min"
    }

    // MARK: Running

    private func running(_ step: RehabStep) -> some View {
        let isRest = step.kind == .rest
        let accent: Color = isRest ? .inkSoft : .mobility
        // Rests show the next exercise's demo, so you can see what's coming.
        let demo = ExerciseDemos.demo(for: isRest ? model.upNext?.name : step.name)
        return VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Kicker(RehabFormat.kicker(step), color: accent)
                Text(step.name.uppercased())
                    .font(AppFont.title(isRest ? 44 : 36))
                    .foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .minimumScaleFactor(0.7)
                if let side = step.side {
                    Text(side.uppercased())
                        .font(AppFont.body(13, weight: .bold))
                        .tracking(13 * 0.1)
                        .foregroundStyle(Color.bg)
                        .padding(.horizontal, 10)
                        .frame(height: 26)
                        .background(Color.mobility, in: Capsule())
                }
            }
            .padding(.top, 20)

            if let demo {
                ExerciseDemoView(demo: demo)
                    .id(demo.key)
                    .opacity(isRest ? 0.55 : 1)
                    .padding(.top, 14)
            }

            Spacer(minLength: 12)
            Group {
                if step.seconds != nil {
                    TimerRing(model: model, accent: isRest ? .muted : .mobility, size: demo == nil ? 230 : 150)
                } else {
                    Text(RehabFormat.dose(step))
                        .font(AppFont.number(demo == nil ? 120 : 84))
                        .foregroundStyle(Color.ink)
                        .minimumScaleFactor(0.5)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity)
            .id(model.index)
            Spacer(minLength: 12)

            if let cue = step.cue, !cue.isEmpty {
                Text(cue)
                    .font(AppFont.body(16))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let next = model.upNext {
                HStack(spacing: 6) {
                    Text("UP NEXT").font(AppFont.body(11, weight: .semibold)).tracking(11 * 0.14).foregroundStyle(Color.muted)
                    Text(RehabFormat.upNext(next, after: step))
                        .font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                }
                .padding(.top, 14)
            }

            HStack(spacing: 10) {
                Button(action: model.back) {
                    Image(systemName: "backward.end.fill").font(.system(size: 16, weight: .semibold))
                }
                .buttonStyle(OutlineButtonStyle(height: 52))
                .frame(width: 64)
                .disabled(model.index == 0)
                .opacity(model.index == 0 ? 0.4 : 1)
                .accessibilityLabel("Previous step")

                Button(action: model.next) {
                    Label(primaryLabel(step), systemImage: isRest ? "forward.fill" : "checkmark")
                }
                .buttonStyle(VoltButtonStyle())

                if step.seconds != nil {
                    Button(action: model.togglePause) {
                        Image(systemName: model.pausedLeft == nil ? "pause.fill" : "play.fill")
                            .font(.system(size: 16, weight: .semibold))
                    }
                    .buttonStyle(OutlineButtonStyle(height: 52))
                    .frame(width: 64)
                    .accessibilityLabel(model.pausedLeft == nil ? "Pause" : "Resume")
                }
            }
            .padding(.top, 20)
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 16)
    }

    private func primaryLabel(_ step: RehabStep) -> String {
        if step.kind == .rest { return "Skip rest" }
        return model.index + 1 == model.steps.count ? "Finish" : "Done"
    }

    // MARK: Done

    private var done: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 6) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 44))
                            .foregroundStyle(Color.volt)
                        Text("REHAB DONE").font(AppFont.title(44)).foregroundStyle(Color.ink).padding(.top, 6)
                        Text(doneSummary).font(AppFont.body(14)).foregroundStyle(Color.muted)
                        Text(saveLabel).font(AppFont.body(12, weight: .semibold)).foregroundStyle(saveColor).padding(.top, 2)
                    }
                    if let watch = model.session?.watchWorkout {
                        HStack(spacing: 12) {
                            Image(systemName: "applewatch").font(.system(size: 20, weight: .semibold)).foregroundStyle(Color.mobility)
                            Text("Stop and save the \(watch) workout on your Watch.")
                                .font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                        }
                        .card(border: Color.mobility.opacity(0.35))
                    }
                    ForEach(model.issues, id: \.id) { issue in
                        painCard(issue)
                    }
                }
                .padding(16)
            }
            .scrollIndicators(.hidden)
            Button("Close") { dismiss() }
                .buttonStyle(VoltButtonStyle())
                .padding(16)
        }
    }

    private func painCard(_ issue: (id: Int, title: String)) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Kicker("Pain now")
            Text(issue.title).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
            let columns = Array(repeating: GridItem(.flexible(), spacing: 6), count: 6)
            LazyVGrid(columns: columns, spacing: 6) {
                ForEach(0...10, id: \.self) { value in
                    let selected = model.pain[issue.id] == value
                    Button {
                        Task { await model.checkIn(issueId: issue.id, pain: value) }
                    } label: {
                        Text("\(value)")
                            .font(AppFont.number(20))
                            .foregroundStyle(selected ? Color.bg : TodayFormat.painColor(value))
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(selected ? TodayFormat.painColor(value) : Color.inset, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color.cardBorder))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Pain \(value) of 10")
                }
            }
        }
        .card()
    }

    private var doneSummary: String {
        let count = model.session?.exercises.count ?? 0
        let minutes = model.startedAt.map { Int(((model.finishedAt ?? .now).timeIntervalSince($0) / 60).rounded()) } ?? 0
        return "\(count) exercise\(count == 1 ? "" : "s") · \(max(1, minutes)) min · ticked on the routine"
    }

    private var saveLabel: String {
        switch model.saveState {
        case .idle, .saving: "Saving…"
        case .saved: "Saved to today"
        case .queued: "Saved on the phone · syncs when the Mac is back"
        case .failed: "Not saved · the server turned it down"
        }
    }

    private var saveColor: Color {
        switch model.saveState {
        case .saved: .mobility
        case .failed: .danger
        default: .muted
        }
    }

    private func message(_ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Spacer()
            Text(title).font(AppFont.title(36)).foregroundStyle(Color.ink)
            Text(body).font(AppFont.body(15)).foregroundStyle(Color.muted).lineSpacing(3)
            Spacer()
            Button("Close") { dismiss() }.buttonStyle(VoltButtonStyle())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
    }
}

/// Counts down a hold or a rest; ticks for the last three seconds, chimes at zero, then moves on.
private struct TimerRing: View {
    let model: RehabSessionModel
    let accent: Color
    var size: CGFloat = 230

    var body: some View {
        let total = model.current?.seconds ?? 0
        TimelineView(.periodic(from: .now, by: 0.25)) { context in
            let left = secondsLeft(at: context.date)
            ZStack {
                Circle().stroke(Color.track, lineWidth: size > 200 ? 10 : 8)
                Circle()
                    .trim(from: 0, to: total > 0 ? Double(left) / Double(total) : 0)
                    .stroke(accent, style: StrokeStyle(lineWidth: size > 200 ? 10 : 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .animation(.linear(duration: 0.25), value: left)
                VStack(spacing: 2) {
                    Text(StrengthFormat.clock(left))
                        .font(AppFont.number(size * 0.31))
                        .foregroundStyle(Color.ink)
                        .monospacedDigit()
                    if model.pausedLeft != nil {
                        Text("PAUSED").font(AppFont.body(11, weight: .semibold)).tracking(11 * 0.14).foregroundStyle(Color.warning)
                    }
                }
            }
            .frame(width: size, height: size)
            .onChange(of: left) { old, new in
                // Only a live crossing chimes: coming back long after the timer ended stays quiet.
                if new > 0 || old > 0 { RestAlarm.countdown(new) }
                if new == 0 { model.timerEnded(model.index) }
            }
        }
    }

    private func secondsLeft(at date: Date) -> Int {
        if let paused = model.pausedLeft { return paused }
        guard let endsAt = model.endsAt else { return 0 }
        return max(0, Int(endsAt.timeIntervalSince(date).rounded(.up)))
    }
}
