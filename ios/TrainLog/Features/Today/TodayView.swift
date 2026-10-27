import SwiftUI

struct TodayView: View {
    @State private var model = TodayModel()
    @State private var showFallback = false
    var onStartStrength: (Int?) -> Void = { _ in }
    /// Bumped when the strength screen closes, so the banner and plan reload.
    var refresh = 0

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if let workout = model.activeWorkout {
                    ResumeWorkoutCard(workout: workout) { onStartStrength(nil) }
                }
                if let data = model.data {
                    if model.offline, let syncedAt = model.syncedAt {
                        offlineNote(syncedAt)
                    }
                    SessionCard(
                        data: data,
                        showFallback: $showFallback,
                        workoutOpen: model.activeWorkout != nil,
                        onStartStrength: onStartStrength
                    )
                    ReadinessCard(readiness: data.readiness, vitals: data.vitals, checkinDone: data.checkinDone)
                    WeekCard(week: data.week, minutes: data.weekMinutes, today: data.date)
                } else if let error = model.error {
                    errorCard(error)
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .safeAreaInset(edge: .top, spacing: 0) {
            // Keeps scrolled cards from running under the status bar.
            Color.clear.frame(height: 0).background(Color.bg)
        }
        .background(Color.bg)
        .refreshable { await model.load() }
        .task(id: refresh) { await model.load() }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(model.data.map { TodayFormat.dateKicker($0.date) } ?? " ")
                Text("TODAY").font(AppFont.title(44)).foregroundStyle(Color.ink)
            }
            Spacer()
            HStack(spacing: 8) {
                if let streak = model.data?.streakDays, streak > 0 {
                    HStack(spacing: 4) {
                        Image(systemName: "flame.fill").font(.system(size: 12))
                        Text("\(streak)").font(AppFont.body(13, weight: .bold))
                    }
                    .foregroundStyle(Color.volt)
                    .padding(.horizontal, 10)
                    .frame(height: 26)
                    .background(Color.volt.opacity(0.12), in: Capsule())
                    .accessibilityLabel("\(streak) day streak")
                }
                Text("J")
                    .font(AppFont.body(14, weight: .bold))
                    .foregroundStyle(Color.ink)
                    .frame(width: 34, height: 34)
                    .background(Color.raised, in: Circle())
            }
            .padding(.bottom, 4)
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private func offlineNote(_ syncedAt: Date) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "wifi.slash").font(.system(size: 11, weight: .semibold))
            Text("Offline · last synced \(syncedAt.formatted(date: .omitted, time: .shortened))")
                .font(AppFont.body(12, weight: .medium))
        }
        .foregroundStyle(Color.muted)
        .padding(.horizontal, 4)
    }

    private func errorCard(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Not synced yet")
            Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Text("Start the backend on the Mac (docker compose up) and pull to refresh.")
                .font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .card()
    }
}

// MARK: - Session

private struct SessionCard: View {
    let data: PhoneToday
    @Binding var showFallback: Bool
    /// The Resume banner owns the volt action while a workout is open.
    let workoutOpen: Bool
    let onStartStrength: (Int?) -> Void

    var body: some View {
        if let session = data.today, session.sport != .rest {
            planned(session)
        } else {
            restDay
        }
    }

    private func planned(_ session: PhoneToday.Session) -> some View {
        let sport = session.sport ?? .other
        return VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                Pill(text: sport.label, color: sport.color == .strength ? Color(hex: 0xFF7AB5) : sport.color)
                Text(subtitle(session)).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            Text((session.title ?? "Session").uppercased())
                .font(AppFont.title(30))
                .foregroundStyle(Color.ink)
                .padding(.top, 12)
            if let meta = meta(session) {
                Text(meta).font(AppFont.body(13)).foregroundStyle(Color.muted).padding(.top, 4)
            }

            if let exercises = session.strength?.exercises, !exercises.isEmpty {
                exerciseList(exercises, color: sport.color).padding(.top, 14)
            } else if let details = session.details {
                Text(details)
                    .font(AppFont.body(14))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(3)
                    .padding(.top, 12)
            }

            if showFallback, let fallback = session.fallback {
                Text(fallback)
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
                    .padding(.top, 12)
            }

            if session.isDone {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                    Text("Done today").font(AppFont.body(15, weight: .bold))
                }
                .foregroundStyle(Color.volt)
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(Color.volt.opacity(0.12), in: Capsule())
                .padding(.top, 16)
            } else if !workoutOpen {
                Button {
                    onStartStrength(session.strength?.templateId)
                } label: {
                    Label("Start session", systemImage: "play.fill")
                }
                .buttonStyle(VoltButtonStyle())
                .disabled(session.strength == nil)
                .padding(.top, 16)

                HStack(spacing: 8) {
                    Button(showFallback ? "Full session" : "Short on time") {
                        withAnimation(.snappy) { showFallback.toggle() }
                    }
                    .buttonStyle(OutlineButtonStyle(height: 44))
                    .disabled(session.fallback == nil)
                    Button("Swap day") {}
                        .buttonStyle(OutlineButtonStyle(height: 44))
                }
                .padding(.top, 10)
            }
        }
        .card(border: sport.color.opacity(0.35))
    }

    private var restDay: some View {
        VStack(alignment: .leading, spacing: 0) {
            Pill(text: "Rest day", color: .muted)
            Text("RECOVER").font(AppFont.title(30)).foregroundStyle(Color.ink).padding(.top, 12)
            if let tomorrow = data.tomorrow, let title = tomorrow.title {
                Text("Tomorrow: \(title)").font(AppFont.body(13)).foregroundStyle(Color.muted).padding(.top, 4)
            }
        }
        .card()
    }

    private func exerciseList(_ exercises: [PhoneToday.Exercise], color: Color) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(Array(exercises.prefix(3).enumerated()), id: \.offset) { index, exercise in
                HStack(spacing: 12) {
                    Text(String(format: "%02d", index + 1))
                        .font(AppFont.number(16))
                        .foregroundStyle(color)
                        .frame(width: 22, alignment: .leading)
                    Text(exercise.name).font(AppFont.body(14)).foregroundStyle(Color.ink).lineLimit(1)
                    Spacer(minLength: 8)
                    Text(TodayFormat.exerciseTarget(exercise)).font(AppFont.body(14)).foregroundStyle(Color.muted)
                }
            }
            if exercises.count > 3 {
                Text("+ \(exercises.count - 3) more")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.muted)
                    .padding(.leading, 34)
            }
        }
    }

    private func subtitle(_ session: PhoneToday.Session) -> String {
        var parts = [session.isDone ? "Done" : "Planned"]
        if let minutes = session.durationMin { parts.append("~\(minutes) min") }
        if let km = session.distanceKm { parts.append("\(TodayFormat.number(km)) km") }
        return parts.joined(separator: " · ")
    }

    private func meta(_ session: PhoneToday.Session) -> String? {
        if let strength = session.strength {
            var parts = ["\(strength.exercises.count) exercises"]
            if let last = strength.lastDone { parts.append("last done \(TodayFormat.shortDay(last, relativeTo: data.date))") }
            return parts.joined(separator: " · ")
        }
        return session.intentLabel
    }
}

// MARK: - Resume

private struct ResumeWorkoutCard: View {
    let workout: StrengthSession
    let onResume: () -> Void

    var body: some View {
        let working = workout.exercises.flatMap(\.workingSets)
        let done = working.filter(\.isCompleted).count
        let index = workout.exercises.firstIndex { $0.exerciseOrder == workout.currentExerciseOrder }
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Kicker("Workout in progress", color: Color(hex: 0xFF7AB5))
                Spacer()
                if let startedAt = StrengthFormat.parseMoment(workout.startedAt) {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        Text(StrengthFormat.clock(Int(context.date.timeIntervalSince(startedAt))))
                            .font(AppFont.number(20))
                            .foregroundStyle(Color.ink)
                            .monospacedDigit()
                    }
                }
            }
            Text(workout.templateName.uppercased())
                .font(AppFont.title(26))
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .padding(.top, 8)
            Text(meta(done: done, total: working.count, index: index))
                .font(AppFont.body(13))
                .foregroundStyle(Color.muted)
                .padding(.top, 4)
            GeometryReader { proxy in
                Capsule().fill(Color.track).overlay(alignment: .leading) {
                    Capsule().fill(Color.strength)
                        .frame(width: proxy.size.width * (working.isEmpty ? 0 : Double(done) / Double(working.count)))
                }
            }
            .frame(height: 4)
            .padding(.top, 12)
            Button(action: onResume) {
                Label("Resume workout", systemImage: "play.fill")
            }
            .buttonStyle(VoltButtonStyle())
            .padding(.top, 16)
        }
        .card(border: Color.strength.opacity(0.35))
    }

    private func meta(done: Int, total: Int, index: Int?) -> String {
        var parts = ["\(done) of \(total) sets"]
        if let index { parts.insert("Exercise \(index + 1) of \(workout.exercises.count)", at: 0) }
        return parts.joined(separator: " · ")
    }
}

// MARK: - Readiness

private struct ReadinessCard: View {
    let readiness: PhoneToday.Readiness
    let vitals: PhoneToday.Vitals
    let checkinDone: Bool

    var body: some View {
        let status = TodayFormat.readiness(readiness.level)
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Readiness")
                Spacer()
                HStack(spacing: 6) {
                    Circle().fill(status.color).frame(width: 8, height: 8)
                    Text(status.label).font(AppFont.body(13, weight: .semibold))
                }
                .foregroundStyle(status.color)
            }
            HStack(alignment: .top, spacing: 14) {
                stat(vitals.restingHr.map { String(Int($0.rounded())) }, unit: "bpm", label: "Resting HR")
                divider
                stat(vitals.sleepH.map { String(format: "%.1f", $0) }, unit: "h", label: "Sleep")
                divider
                stat(vitals.pain.map(String.init), unit: "/10", label: "Pain", color: vitals.pain.map(TodayFormat.painColor) ?? .ink)
            }
            .padding(.top, 14)
            if let advice = readiness.advice {
                Text(advice)
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(.top, 12)
            }
            if !checkinDone {
                Text("No check-in yet today. Tap + to log one.")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .padding(.top, 6)
            }
        }
        .card()
    }

    private var divider: some View {
        Rectangle().fill(Color.cardBorder).frame(width: 1, height: 52)
    }

    private func stat(_ value: String?, unit: String, label: String, color: Color = .ink) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(value ?? "–").font(AppFont.number(30)).foregroundStyle(value == nil ? Color.muted : color)
                if value != nil {
                    Text(unit).font(AppFont.body(13, weight: .medium)).foregroundStyle(Color.muted)
                }
            }
            Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Week

private struct WeekCard: View {
    let week: [PhoneToday.WeekDay]
    let minutes: PhoneToday.WeekMinutes
    let today: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Kicker("This week")
                Spacer()
                Text(TodayFormat.duration(minutes.done)).font(AppFont.number(22)).foregroundStyle(Color.ink)
                    + Text(minutes.planned > 0 ? " of \(TodayFormat.duration(minutes.planned))" : "")
                    .font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
            progressBar.padding(.top, 10)
            HStack(spacing: 0) {
                ForEach(week) { day in
                    DayRing(day: day, isToday: day.date == today).frame(maxWidth: .infinity)
                }
            }
            .padding(.top, 14)
        }
        .card()
    }

    private var progressBar: some View {
        GeometryReader { proxy in
            let total = Double(max(minutes.planned, minutes.done, 1))
            HStack(spacing: 2) {
                ForEach(Array(minutes.bySport.enumerated()), id: \.offset) { _, part in
                    Rectangle()
                        .fill(part.sport.color)
                        .frame(width: max(2, proxy.size.width * Double(part.minutes) / total))
                }
                Spacer(minLength: 0)
            }
        }
        .frame(height: 6)
        .background(Color.track)
        .clipShape(Capsule())
    }
}

private struct DayRing: View {
    let day: PhoneToday.WeekDay
    let isToday: Bool

    private var isDone: Bool { !day.doneSports.isEmpty }

    var body: some View {
        VStack(spacing: 7) {
            Text(String(day.label.prefix(1)))
                .font(AppFont.body(11, weight: isToday ? .bold : .semibold))
                .foregroundStyle(isToday ? Color.volt : Color.muted)
            ring.frame(width: 32, height: 32)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(day.label): \(day.title ?? "Rest"), \(isDone ? "done" : day.status)")
    }

    @ViewBuilder
    private var ring: some View {
        if isDone {
            ZStack {
                Circle().fill(fill)
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.bg)
            }
            .overlay { if isToday { Circle().strokeBorder(Color.volt, lineWidth: 2).padding(-4) } }
        } else if isToday {
            ZStack {
                Circle().strokeBorder(Color.volt, lineWidth: 2)
                if day.sport != .rest { Circle().fill(day.sport.color).frame(width: 10, height: 10) }
            }
        } else if day.sport == .rest {
            Circle().fill(Color.dim).frame(width: 5, height: 5)
        } else {
            Circle()
                .strokeBorder(
                    day.sport.color.opacity(0.45),
                    style: StrokeStyle(lineWidth: 2, dash: day.status == "missed" || day.status == "skipped" ? [3, 3] : [])
                )
        }
    }

    /// One sport fills the ring; two or more split it like the artboard's Tuesday.
    private var fill: AnyShapeStyle {
        let colors = day.doneSports.map(\.color)
        guard colors.count > 1 else { return AnyShapeStyle(colors.first ?? .muted) }
        let step = 1.0 / Double(colors.count)
        let stops = colors.enumerated().flatMap { index, color in
            [Gradient.Stop(color: color, location: Double(index) * step), .init(color: color, location: Double(index + 1) * step)]
        }
        return AnyShapeStyle(AngularGradient(stops: stops, center: .center, startAngle: .degrees(-90), endAngle: .degrees(270)))
    }
}

#Preview {
    TodayView().preferredColorScheme(.dark)
}
