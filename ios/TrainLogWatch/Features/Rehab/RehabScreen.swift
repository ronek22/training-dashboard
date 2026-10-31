import SwiftUI

/// Frame 07: rehab and bodyweight holds that count themselves; rep drills get a Done button.
struct RehabScreen: View {
    @Bindable var run: RehabRun
    let tracker: WorkoutTracker
    let onEnd: (WorkoutTracker.Summary?) -> Void

    @State private var page = 1
    @State private var confirmEnd = false
    @Environment(\.isLuminanceReduced) private var dimmed

    var body: some View {
        TabView(selection: $page) {
            controls.tag(0)
            main.tag(1)
        }
        .tabViewStyle(.page)
        .navigationBarBackButtonHidden()
        .toolbar {
            ToolbarItem(placement: .topBarLeading) { HeartRateLabel(bpm: tracker.heartRate, dimmed: dimmed) }
        }
        .onAppear { run.start() }
        .onChange(of: run.finished) { _, finished in
            if finished { Task { onEnd(await tracker.finish()) } }
        }
    }

    @ViewBuilder
    private var main: some View {
        if let step = run.current {
            VStack(alignment: .leading, spacing: 0) {
                GeometryReader { proxy in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.track)
                        Capsule().fill(Color.mobility).frame(width: proxy.size.width * run.progress)
                    }
                }
                .frame(height: 3)
                WatchKicker(kicker(step), color: .mobility).padding(.top, 6)
                WatchTitle(step.side.map { "\(step.name) · \($0.prefix(1))" } ?? step.name, size: 24)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 1)
                if step.seconds != nil {
                    timed(step)
                } else {
                    reps(step)
                }
            }
            .padding(.horizontal, 2)
        }
    }

    private func timed(_ step: RehabStep) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let total = max(1, step.seconds ?? 1)
                let left = run.pausedLeft ?? run.endsAt.map { max(0, Int($0.timeIntervalSince(context.date).rounded(.up))) } ?? total
                HStack(spacing: 10) {
                    ZStack {
                        CountdownRing(progress: Double(left) / Double(total), lineWidth: dimmed ? 5 : 8)
                        Text(WatchClock.text(left)).font(WatchFont.number(24)).foregroundStyle(dimmed ? Color.muted : .ink)
                    }
                    .frame(width: 72, height: 72)
                    cue(step)
                }
                .padding(.top, 4)
            }
            Spacer(minLength: 0)
            if !dimmed {
                HStack(spacing: 6) {
                    Button(run.pausedLeft == nil ? "Pause" : "Resume") { run.togglePause() }
                        .buttonStyle(DarkButtonStyle(height: 34))
                    Button("Skip") { run.next() }
                        .buttonStyle(DarkButtonStyle(height: 34))
                }
            }
        }
    }

    private func reps(_ step: RehabStep) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(RehabFormat.dose(step)).font(WatchFont.number(46)).foregroundStyle(dimmed ? Color.muted : .ink)
                cue(step)
            }
            .padding(.top, 4)
            Spacer(minLength: 0)
            if !dimmed {
                Button("Done") { run.next() }.buttonStyle(VoltButtonStyle())
            }
        }
    }

    private func cue(_ step: RehabStep) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            if step.kind == .rest, let next = run.upNext {
                Text("Next").font(WatchFont.body(10)).foregroundStyle(Color.muted)
                Text(next).font(WatchFont.body(11, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(3)
            } else {
                if let cue = step.cue {
                    Text(cue).font(WatchFont.body(10)).foregroundStyle(Color.muted).lineLimit(4)
                }
            }
        }
    }

    private func kicker(_ step: RehabStep) -> String {
        step.kind == .rest ? "Rest" : "\(run.session.title) · \(step.position)/\(step.count)" + (step.sets > 1 ? " · Set \(step.set)/\(step.sets)" : "")
    }

    private var controls: some View {
        VStack(spacing: 8) {
            HStack(spacing: 8) {
                tile("End", symbol: "xmark", tint: .heart) { confirmEnd = true }
                tile("Back", symbol: "backward.end.fill") { run.back(); page = 1 }
            }
            HStack(spacing: 8) {
                tile("Skip", symbol: "forward.end.fill") { run.next(); page = 1 }
                tile(tracker.paused ? "Resume" : "Pause", symbol: tracker.paused ? "play.fill" : "pause.fill") { tracker.togglePause() }
            }
        }
        .confirmationDialog("End rehab?", isPresented: $confirmEnd) {
            Button("Finish & save") { run.finish() }
            Button("Discard", role: .destructive) {
                run.discard()
                tracker.discard()
                onEnd(nil)
            }
            Button("Keep going", role: .cancel) {}
        }
    }

    private func tile(_ title: String, symbol: String, tint: Color? = nil, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: symbol).font(.system(size: 20, weight: .semibold))
                Text(title).font(WatchFont.body(12, weight: .semibold))
            }
            .foregroundStyle(tint ?? .ink)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(tint?.opacity(0.18) ?? Color.raised, in: RoundedRectangle(cornerRadius: 18))
        }
        .buttonStyle(.plain)
    }
}

struct RehabSummaryView: View {
    let title: String
    let steps: Int
    let summary: WorkoutTracker.Summary?
    let onDone: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 6) {
                WatchKicker(title, color: .mobility)
                Text(WatchClock.text(Int(summary?.duration ?? 0))).font(WatchFont.number(42)).foregroundStyle(Color.ink)
                HStack(spacing: 14) {
                    stat("\(steps)", "steps")
                    stat(summary?.averageHeartRate.map { String(Int($0.rounded())) } ?? "--", "avg hr", color: .heart)
                    stat(summary?.activeKcal.map { String(Int($0.rounded())) } ?? "--", "kcal")
                }
                Text(summary?.saved == true ? "✓ Saved to Apple Health · checklist ticked" : "Checklist ticked")
                    .font(WatchFont.body(10))
                    .foregroundStyle(Color.mobility)
                Button("Done", action: onDone).buttonStyle(VoltButtonStyle(height: 34)).padding(.top, 4)
            }
        }
        .navigationBarBackButtonHidden()
    }

    private func stat(_ value: String, _ label: String, color: Color = .ink) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value).font(WatchFont.number(20)).foregroundStyle(color)
            WatchKicker(label)
        }
    }
}
