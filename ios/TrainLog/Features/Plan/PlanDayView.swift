import SwiftUI

/// Everything needed for the session, nothing to edit: go check, steps, cues, the rehab
/// checklist and the short-on-time fallback. Today's strength day gets the volt Start session.
struct PlanDayView: View {
    let model: PlanModel
    let date: String
    let onMove: (PlanDay) -> Void
    let onStartStrength: (Int?) -> Void
    @State private var starting = false

    var body: some View {
        ScrollView {
            if let day = model.day(date) {
                content(day)
            } else {
                Text("This day isn't in the plan any more.")
                    .font(AppFont.body(14)).foregroundStyle(Color.muted)
                    .frame(maxWidth: .infinity, minHeight: 240)
            }
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .smoothRefreshable {
            await APIClient.current.reconnect()
            await model.load()
        }
    }

    private func content(_ day: PlanDay) -> some View {
        let sport = PlanFormat.sport(day)
        let status = PlanFormat.status(day, today: model.today)
        return VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Kicker(PlanFormat.dayKicker(day), color: sport.color)
                Text(PlanFormat.rowTitle(day.title).uppercased())
                    .font(AppFont.title(32))
                    .foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if let details = day.details, !details.isEmpty {
                    Text(details)
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.muted)
                        .lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if status != .planned && status != .rest {
                    Text(PlanFormat.meta(day, today: model.today))
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(status == .done ? sport.color : Color.warning)
                        .padding(.top, 2)
                }
            }
            .padding(.horizontal, 4)

            tiles(day)

            if let check = day.check, !check.isEmpty {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.circle")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Color.mobility)
                    VStack(alignment: .leading, spacing: 4) {
                        Kicker("Go check", color: .mobility)
                        Text(check).font(AppFont.body(14)).foregroundStyle(Color.ink).lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.mobility.opacity(0.35)))
            }

            if let steps = day.steps, !steps.isEmpty {
                stepsCard(steps, cues: day.cues ?? [], color: sport.color, title: sport == .strength ? "Session" : "Steps")
            }

            ForEach(day.rehab ?? []) { routine in
                NavigationLink {
                    RehabChecklistView(model: model, date: day.date, routineId: routine.routineId)
                } label: {
                    rehabRow(routine)
                }
                .buttonStyle(.plain)
            }

            if let fallback = PlanFormat.fallback(day.fallback) {
                Text("\(Text("Short on time / sore: ").foregroundStyle(Color.ink).bold())\(fallback)")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
            }

            if sport == .strength && day.date == model.today && status == .planned {
                Button {
                    Task {
                        starting = true
                        onStartStrength(await model.templateId(for: day))
                        starting = false
                    }
                } label: {
                    Label("Start session", systemImage: "play.fill")
                }
                .buttonStyle(VoltButtonStyle())
                .disabled(starting)
                .padding(.top, 4)
            }

            if PlanFormat.canMove(day, today: model.today) {
                Button {
                    onMove(day)
                } label: {
                    Label("Move to another day", systemImage: "arrow.left.arrow.right")
                }
                .buttonStyle(OutlineButtonStyle(height: 44))
                .font(AppFont.body(14, weight: .semibold))
            }
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 24)
    }

    private func tiles(_ day: PlanDay) -> some View {
        var items: [(label: String, value: String, unit: String?)] = []
        if let minutes = day.targetDurationMin { items.append(("Time", "\(minutes)", "min")) }
        if let km = day.targetDistanceKm, km > 0 { items.append(("Distance", TodayFormat.number(km), "km")) }
        if let workout = day.cyclingWorkoutName { items.append(("Workout", workout, nil)) }
        let rehabCount = (day.rehab ?? []).reduce(0) { $0 + $1.exercises.count }
        if rehabCount > 0 { items.append(("Rehab", "\(rehabCount)", "ex")) }
        return HStack(spacing: 8) {
            ForEach(items.prefix(3), id: \.label) { item in
                VStack(alignment: .leading, spacing: 6) {
                    Text(item.label.uppercased())
                        .font(AppFont.body(9, weight: .semibold))
                        .tracking(9 * 0.14)
                        .foregroundStyle(Color.muted)
                    if let unit = item.unit {
                        Text("\(Text(item.value).font(AppFont.number(24)).foregroundStyle(Color.ink))\(Text(" \(unit)").font(AppFont.body(12)).foregroundStyle(Color.muted))")
                            .lineLimit(1)
                    } else {
                        Text(item.value).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                            .lineLimit(2).minimumScaleFactor(0.8)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
            }
        }
        // Text and number tiles grow to the tallest one.
        .fixedSize(horizontal: false, vertical: true)
    }

    private func stepsCard(_ steps: [String], cues: [String], color: Color, title: String) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker(title)
            VStack(alignment: .leading, spacing: 10) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text(String(format: "%02d", index + 1))
                            .font(AppFont.number(16))
                            .foregroundStyle(color)
                            .frame(width: 22, alignment: .leading)
                        Text(step)
                            .font(AppFont.body(14))
                            .foregroundStyle(Color.ink)
                            .lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(.top, 10)
            if !cues.isEmpty {
                FlowLayout(spacing: 6) {
                    ForEach(cues, id: \.self) { cue in
                        Text(cue)
                            .font(AppFont.body(12, weight: .semibold))
                            .foregroundStyle(Color.inkSoft)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color(hex: 0x1A1E27), in: Capsule())
                    }
                }
                .padding(.top, 12)
            }
        }
        .card()
    }

    private func rehabRow(_ routine: RehabRoutine) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 2).fill(Color.mobility).frame(width: 4, height: 34)
            VStack(alignment: .leading, spacing: 3) {
                Text("Rehab · \(routine.exercises.count) exercises")
                    .font(AppFont.body(15, weight: .semibold))
                    .foregroundStyle(Color.ink)
                Text(rehabSubtitle(routine))
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .lineLimit(1)
            }
            Spacer(minLength: 8)
            Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(Color.dim)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
        .contentShape(Rectangle())
    }

    private func rehabSubtitle(_ routine: RehabRoutine) -> String {
        if !routine.ticked.isEmpty {
            return "\(routine.ticked.count) of \(routine.exercises.count) done · \(routine.title)"
        }
        return routine.title
    }
}

/// The day's rehab routine as a checklist. Ticks work on the day (or after), not ahead of it.
struct RehabChecklistView: View {
    let model: PlanModel
    let date: String
    let routineId: Int
    @State private var guided = false

    private var routine: RehabRoutine? {
        model.day(date)?.rehab?.first { $0.routineId == routineId }
    }

    var body: some View {
        ScrollView {
            if let routine {
                VStack(alignment: .leading, spacing: 12) {
                    VStack(alignment: .leading, spacing: 6) {
                        Kicker("Rehab · \(ActivityFormat.longDay(date))", color: .mobility)
                        Text(routine.title.uppercased())
                            .font(AppFont.title(30))
                            .foregroundStyle(Color.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        if date > model.today {
                            Text("Tick these off on the day.").font(AppFont.body(13)).foregroundStyle(Color.muted)
                        }
                    }
                    .padding(.horizontal, 4)
                    VStack(spacing: 0) {
                        ForEach(Array(routine.exercises.enumerated()), id: \.offset) { index, exercise in
                            if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                            exerciseRow(routine, index: index, exercise: exercise)
                        }
                    }
                    .padding(.horizontal, 16)
                    .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
                    if date == model.today, routine.ticked.count < routine.exercises.count {
                        Button {
                            guided = true
                        } label: {
                            Label("Start guided", systemImage: "play.fill")
                        }
                        .buttonStyle(VoltButtonStyle())
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .fullScreenCover(isPresented: $guided, onDismiss: { Task { await model.load() } }) {
            RehabSessionView()
        }
    }

    private func exerciseRow(_ routine: RehabRoutine, index: Int, exercise: RehabRoutine.Exercise) -> some View {
        let done = routine.ticked.contains(index)
        let canTick = date <= model.today
        return Button {
            Task { await model.tick(routine, index: index, done: !done, on: date) }
        } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: done ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 22))
                    .foregroundStyle(done ? Color.mobility : Color.outline)
                VStack(alignment: .leading, spacing: 3) {
                    Text(exercise.name ?? "Exercise")
                        .font(AppFont.body(15, weight: .semibold))
                        .foregroundStyle(Color.ink)
                    if let dose = exercise.dose {
                        Text(dose).font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.mobility)
                    }
                    if let how = exercise.how {
                        Text(how).font(AppFont.body(13)).foregroundStyle(Color.muted).lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(.vertical, 12)
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!canTick)
    }
}
