import SwiftUI

/// A running strength session: controls ← main → whole workout, like Apple Workout's pages.
struct StrengthScreen: View {
    @Bindable var run: StrengthRun
    let tracker: WorkoutTracker
    /// Opens on the main page; the demo can start on another.
    @State var page = Page.main
    let onEnd: (WorkoutTracker.Summary?, StrengthRun) -> Void

    enum Page: Hashable { case controls, main, list }

    var body: some View {
        TabView(selection: $page) {
            StrengthControls(run: run, tracker: tracker, onEnd: end).tag(Page.controls)
            main.tag(Page.main)
            ExerciseList(run: run) { exercise in
                run.jump(to: exercise)
                withAnimation { page = .main }
            }
            .tag(Page.list)
        }
        .tabViewStyle(.page)
        .navigationBarBackButtonHidden()
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                HeartRateLabel(bpm: tracker.heartRate, trend: run.stage == .rest && tracker.falling ? "↓" : nil)
            }
        }
        .task { await run.loadHistory() }
    }

    @ViewBuilder
    private var main: some View {
        switch run.stage {
        case .set:
            if run.current?.set.isTimed == true { HoldPage(run: run, tracker: tracker) } else { SetPage(run: run, tracker: tracker) }
        case .effort:
            EffortPage(run: run)
        case .rest:
            RestPage(run: run, tracker: tracker)
        case .allDone:
            AllDonePage(run: run) { end(finish: true) }
        }
    }

    private func end(finish: Bool) {
        if finish {
            run.finish()
            Task { onEnd(await tracker.finish(), run) }
        } else {
            run.discard()
            tracker.discard()
            onEnd(nil, run)
        }
    }
}

/// Elapsed workout time, paused time left out.
private struct ElapsedText: View {
    let tracker: WorkoutTracker
    var size: CGFloat = 13
    var color: Color = .ink

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            Text(WatchClock.text(Int(tracker.elapsed(at: context.date))))
                .font(WatchFont.number(size))
                .foregroundStyle(color)
                .monospacedDigit()
        }
    }
}

/// One segment per exercise, filled by sets done.
private struct ProgressSegments: View {
    let session: StrengthSession
    var color: Color = .strength

    var body: some View {
        HStack(spacing: 3) {
            ForEach(session.exercises.sorted { $0.exerciseOrder < $1.exerciseOrder }) { exercise in
                GeometryReader { proxy in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.track)
                        Capsule().fill(color).frame(width: proxy.size.width * StrengthLogic.progress(of: exercise))
                    }
                }
                .frame(height: 3)
            }
        }
    }
}

// MARK: - Set (frame 02)

private struct SetPage: View {
    @Bindable var run: StrengthRun
    let tracker: WorkoutTracker
    @State private var crown = 0.0
    @State private var applied = 0
    @Environment(\.isLuminanceReduced) private var dimmed

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ProgressSegments(session: run.session)
            HStack {
                WatchKicker(run.kicker, color: .strengthSoft)
                Spacer(minLength: 4)
                ElapsedText(tracker: tracker, size: 13, color: .muted)
            }
            .padding(.top, 6)
            WatchTitle(run.current?.exercise.exerciseName ?? "", size: 24).padding(.top, 1)
            HStack(spacing: 6) {
                tile(.weight, label: "kg", value: StrengthFormat.weight(run.draftWeight),
                     sub: WatchStrength.versusLast(run.draftWeight, last: run.last?.weightKg) ?? "target")
                tile(.reps, label: "reps", value: "\(run.draftReps)",
                     sub: WatchStrength.versusLast(Double(run.draftReps), last: run.last.map { Double($0.reps) }) ?? "target")
            }
            .padding(.vertical, 6)
            if !dimmed {
                Button("Set done") { run.logSet() }
                    .buttonStyle(VoltButtonStyle())
            }
        }
        .focusable()
        .digitalCrownRotation($crown, from: -10_000, through: 10_000, by: 1, sensitivity: .medium,
                              isContinuous: true, isHapticFeedbackEnabled: true)
        .onChange(of: crown) { _, value in
            let detent = Int(value.rounded())
            run.turn(detent - applied)
            applied = detent
        }
        .padding(.horizontal, 2)
    }

    private func tile(_ field: StrengthRun.Field, label: String, value: String, sub: String) -> some View {
        let focused = run.focus == field && !dimmed
        return Button {
            run.focus = field
        } label: {
            VStack(spacing: 2) {
                WatchKicker(label, color: focused ? .strengthSoft : .muted)
                Text(value)
                    .font(WatchFont.number(value.count > 3 ? 36 : 44))
                    .foregroundStyle(dimmed ? Color.muted : .ink)
                    .contentTransition(.numericText())
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                Text(sub)
                    .font(WatchFont.body(9))
                    .foregroundStyle(Color.muted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(focused ? Color.strengthTint : Color.card, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(focused ? Color.strength : Color.cardBorder, lineWidth: focused ? 2 : 1))
            .overlay(alignment: .topTrailing) {
                if focused {
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(Color.strength)
                        .padding(7)
                }
            }
        }
        .buttonStyle(.plain)
        .animation(.snappy(duration: 0.15), value: value)
    }
}

// MARK: - Hold (timed sets: planks, wall sits)

private struct HoldPage: View {
    @Bindable var run: StrengthRun
    let tracker: WorkoutTracker
    @State private var crown = 0.0
    @State private var applied = 0
    @Environment(\.isLuminanceReduced) private var dimmed

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ProgressSegments(session: run.session)
            HStack {
                WatchKicker(run.kicker, color: .strengthSoft)
                Spacer(minLength: 4)
                ElapsedText(tracker: tracker, size: 13, color: .muted)
            }
            .padding(.top, 6)
            WatchTitle(run.current?.exercise.exerciseName ?? "", size: 24).fixedSize(horizontal: false, vertical: true).padding(.top, 1)
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let total = max(1, run.draftSeconds)
                let left = run.holdStartedAt.map { max(0, total - Int(context.date.timeIntervalSince($0))) } ?? total
                HStack(spacing: 10) {
                    ZStack {
                        CountdownRing(progress: Double(left) / Double(total), color: .strength, track: .strengthTint, lineWidth: dimmed ? 5 : 8)
                        Text(WatchClock.text(left)).font(WatchFont.number(24)).foregroundStyle(dimmed ? Color.muted : .ink)
                    }
                    .frame(width: 72, height: 72)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Hold").font(WatchFont.body(11)).foregroundStyle(Color.muted)
                        Text(StrengthFormat.hold(run.draftSeconds)).font(WatchFont.number(20)).foregroundStyle(Color.ink)
                        if run.holdStartedAt == nil {
                            Text("Crown sets time").font(WatchFont.body(9)).foregroundStyle(Color.muted)
                        }
                    }
                }
                .padding(.vertical, 4)
            }
            Spacer(minLength: 0)
            if !dimmed {
                if run.holdStartedAt == nil {
                    Button("Start hold") { run.startHold() }.buttonStyle(VoltButtonStyle())
                } else {
                    Button("Stop · log time") { run.stopHold() }.buttonStyle(DarkButtonStyle(height: 36))
                }
            }
        }
        .focusable()
        .digitalCrownRotation($crown, from: -10_000, through: 10_000, by: 1, sensitivity: .low,
                              isContinuous: true, isHapticFeedbackEnabled: true)
        .onChange(of: crown) { _, value in
            let detent = Int(value.rounded())
            run.turn(detent - applied)
            applied = detent
        }
        .padding(.horizontal, 2)
    }
}

// MARK: - Effort (frame 04)

private struct EffortPage: View {
    @Bindable var run: StrengthRun

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("✓ " + (run.lastLogged ?? "Set done"))
                    .font(WatchFont.body(12, weight: .semibold))
                    .foregroundStyle(Color.mobility)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Spacer(minLength: 4)
                if let ends = run.restEndsAt {
                    Text(timerInterval: Date.now...max(ends, .now), countsDown: true)
                        .font(WatchFont.number(15))
                        .foregroundStyle(Color.mobility)
                        .frame(maxWidth: 40, alignment: .trailing)
                }
            }
            WatchTitle("How did it feel?", size: 21)
            ForEach(SetEffort.allCases, id: \.self) { effort in
                Button(effort.label) { run.rate(effort) }
                    .buttonStyle(EffortButtonStyle(highlighted: effort == .solid))
            }
        }
        .padding(.horizontal, 2)
    }
}

private struct EffortButtonStyle: ButtonStyle {
    let highlighted: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(WatchFont.body(16, weight: .semibold))
            .foregroundStyle(configuration.isPressed ? Color.strengthSoft : .ink)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .frame(minHeight: 40)
            .background(configuration.isPressed ? Color.strength.opacity(0.22) : Color.raised, in: RoundedRectangle(cornerRadius: 20))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(configuration.isPressed ? Color.strength : .clear, lineWidth: 1.5))
    }
}

// MARK: - Rest (frames 05 and 06)

private struct RestPage: View {
    @Bindable var run: StrengthRun
    let tracker: WorkoutTracker
    @Environment(\.isLuminanceReduced) private var dimmed

    var body: some View {
        VStack(spacing: 6) {
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let left = run.restEndsAt.map { max(0, Int($0.timeIntervalSince(context.date).rounded(.up))) } ?? 0
                ZStack {
                    CountdownRing(
                        progress: Double(left) / Double(max(1, run.restTotal)),
                        color: dimmed ? Color.mobility.opacity(0.55) : .mobility,
                        track: dimmed ? Color.mobilityTrack.opacity(0.5) : .mobilityTrack,
                        lineWidth: dimmed ? 5 : 9
                    )
                    VStack(spacing: 0) {
                        WatchKicker("Rest", color: dimmed ? Color.mobility.opacity(0.6) : .mobility)
                        Text(WatchClock.text(left))
                            .font(WatchFont.number(44))
                            .foregroundStyle(dimmed ? Color.muted : .ink)
                            .contentTransition(.numericText(countsDown: true))
                    }
                }
                .frame(width: 124, height: 124)
            }
            if let next = run.upNext {
                (Text("Next · ").foregroundStyle(Color.muted) + Text(next).foregroundStyle(dimmed ? Color.muted : .ink).bold())
                    .font(WatchFont.body(11))
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            if !dimmed {
                HStack(spacing: 6) {
                    Button("+30 s") { run.addRest(30) }.buttonStyle(DarkButtonStyle(height: 30))
                    Button("Skip") { run.skipRest() }.buttonStyle(DarkButtonStyle(height: 30))
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - All sets done

private struct AllDonePage: View {
    @Bindable var run: StrengthRun
    let onFinish: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            WatchKicker("All sets done", color: .volt)
            WatchTitle(run.session.templateName, size: 24)
            Text("\(run.totals.setsDone)/\(run.totals.setsTotal) sets · " + volume(run.totals.volumeKg))
                .font(WatchFont.body(12))
                .foregroundStyle(Color.muted)
            Spacer(minLength: 0)
            Button("Finish workout", action: onFinish).buttonStyle(VoltButtonStyle())
        }
        .padding(.horizontal, 2)
    }
}

func volume(_ kg: Double) -> String {
    kg >= 1000 ? String(format: "%.1f t", kg / 1000) : "\(Int(kg.rounded())) kg"
}

// MARK: - Whole workout (frame 03)

private struct ExerciseList: View {
    @Bindable var run: StrengthRun
    let onPick: (StrengthSession.Exercise) -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    WatchKicker("\(run.totals.setsDone) / \(run.totals.setsTotal) sets")
                    Spacer()
                    WatchKicker("~\(WatchStrength.minutesLeft(run.session)) min left")
                }
                .padding(.horizontal, 2)
                .padding(.bottom, 4)
                ForEach(run.session.exercises.sorted { $0.exerciseOrder < $1.exerciseOrder }) { exercise in
                    row(exercise)
                }
            }
        }
        .navigationTitle(run.session.templateName)
    }

    private func row(_ exercise: StrengthSession.Exercise) -> some View {
        let isCurrent = exercise.exerciseOrder == run.session.currentExerciseOrder && !exercise.isDone
        return Button { onPick(exercise) } label: {
            HStack(spacing: 8) {
                status(exercise, isCurrent: isCurrent)
                VStack(alignment: .leading, spacing: 1) {
                    Text(exercise.exerciseName)
                        .font(WatchFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.ink)
                        .lineLimit(1)
                    Text(detail(exercise, isCurrent: isCurrent))
                        .font(WatchFont.body(10))
                        .foregroundStyle(Color.muted)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                HStack(spacing: 3) {
                    ForEach(exercise.workingSets) { set in
                        Circle()
                            .fill(set.isCompleted ? Color.mobility : (isCurrent && set.setOrder == run.session.currentSetOrder ? .strength : .track))
                            .frame(width: 5, height: 5)
                    }
                }
            }
            .padding(.horizontal, 8)
            .frame(minHeight: 44)
            .background(isCurrent ? Color.strengthTint : .clear, in: RoundedRectangle(cornerRadius: 13))
            .overlay(RoundedRectangle(cornerRadius: 13).stroke(isCurrent ? Color.strength : .clear, lineWidth: 1.5))
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func status(_ exercise: StrengthSession.Exercise, isCurrent: Bool) -> some View {
        if exercise.isDone {
            Image(systemName: "checkmark")
                .font(.system(size: 8, weight: .heavy))
                .foregroundStyle(Color.mobility)
                .frame(width: 16, height: 16)
                .background(Color.mobility.opacity(0.2), in: Circle())
        } else if isCurrent {
            Circle().stroke(Color.strength, lineWidth: 2).frame(width: 16, height: 16)
        } else {
            Circle().stroke(Color.faint, style: StrokeStyle(lineWidth: 1.5, dash: [2, 2])).frame(width: 16, height: 16)
        }
    }

    private func detail(_ exercise: StrengthSession.Exercise, isCurrent: Bool) -> String {
        let working = exercise.workingSets
        guard let first = working.first else { return "" }
        if isCurrent, let set = exercise.sets.first(where: { $0.setOrder == run.session.currentSetOrder }) {
            return StrengthLogic.label(for: set, in: exercise) + " of \(working.count) · " +
                StrengthFormat.load(weight: set.targetWeightKg, reps: set.targetReps, seconds: set.targetSeconds)
        }
        let dose = first.targetSeconds.map { StrengthFormat.hold($0) } ?? "\(first.targetReps)"
        let load = first.targetWeightKg.map { " · \(StrengthFormat.number($0)) kg" } ?? " · bodyweight"
        return "\(working.count) × \(dose)" + load
    }
}

// MARK: - Controls (frame 08)

private struct StrengthControls: View {
    @Bindable var run: StrengthRun
    let tracker: WorkoutTracker
    let onEnd: (Bool) -> Void
    @State private var confirmEnd = false
    @State private var error: String?

    var body: some View {
        Grid(horizontalSpacing: 8, verticalSpacing: 8) {
            GridRow {
                control("End", symbol: "xmark", tint: .heart) { confirmEnd = true }
                control(tracker.paused ? "Resume" : "Pause", symbol: tracker.paused ? "play.fill" : "pause.fill") {
                    tracker.togglePause()
                }
            }
            GridRow {
                control("Skip exercise", symbol: "forward.end.fill") { run.skipExercise() }
                    .disabled(run.current.flatMap { WatchStrength.nextExercise(after: $0.exercise, in: run.session) } == nil)
                control(run.addingSet ? "Adding…" : "Add set", symbol: "plus") {
                    Task { error = await run.addSet() }
                }
            }
        }
        .confirmationDialog("End workout?", isPresented: $confirmEnd) {
            Button("Finish & save") { onEnd(true) }
            Button("Discard", role: .destructive) { onEnd(false) }
            Button("Keep going", role: .cancel) {}
        }
        .alert("Couldn't add a set", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(error ?? "")
        }
    }

    private func control(_ title: String, symbol: String, tint: Color? = nil, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: symbol).font(.system(size: 20, weight: .semibold))
                Text(title).font(WatchFont.body(12, weight: .semibold)).lineLimit(1).minimumScaleFactor(0.8)
            }
            .foregroundStyle(tint ?? .ink)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background((tint?.opacity(0.18) ?? Color.raised), in: RoundedRectangle(cornerRadius: 18))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Summary (frame 09)

struct StrengthSummaryView: View {
    let title: String
    let totals: WatchStrength.Totals
    let summary: WorkoutTracker.Summary?
    let pendingWrites: Int
    let onDone: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                WatchKicker(title, color: .strengthSoft)
                Text(WatchClock.text(Int(summary?.duration ?? 0)))
                    .font(WatchFont.number(42))
                    .foregroundStyle(Color.ink)
                    .padding(.top, 3)
                Grid(alignment: .leading, horizontalSpacing: 4, verticalSpacing: 6) {
                    GridRow {
                        stat("\(totals.setsDone)/\(totals.setsTotal)", "sets")
                        stat(volume(totals.volumeKg), "volume")
                        stat(summary?.activeKcal.map { String(Int($0.rounded())) } ?? "--", "kcal")
                    }
                    GridRow {
                        stat(summary?.averageHeartRate.map { String(Int($0.rounded())) } ?? "--", "avg hr", color: .heart)
                        stat(summary?.maxHeartRate.map { String(Int($0.rounded())) } ?? "--", "max hr")
                        Color.clear.frame(height: 1)
                    }
                }
                .padding(.top, 8)
                Group {
                    if summary?.saved == true {
                        Text("✓ Saved to Apple Health").foregroundStyle(Color.mobility)
                    } else {
                        Text("Not saved to Apple Health").foregroundStyle(Color.muted)
                    }
                    if pendingWrites > 0 {
                        Text("\(pendingWrites) changes wait for your iPhone").foregroundStyle(Color.muted)
                    }
                }
                .font(WatchFont.body(10))
                .padding(.top, 8)
                Button("Done", action: onDone)
                    .buttonStyle(VoltButtonStyle(height: 34))
                    .padding(.top, 8)
            }
        }
        .navigationBarBackButtonHidden()
    }

    private func stat(_ value: String, _ label: String, color: Color = .ink) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value).font(WatchFont.number(20)).foregroundStyle(color)
            WatchKicker(label).font(.system(size: 8))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
