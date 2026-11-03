import SwiftUI

// Today after 20:00 (docs/design/artboards/iOSEveningMode.dc.html): how today went with the day
// strip, the session if it's still open, tonight's lights out and tomorrow.

extension Color {
    /// Time in daylight on the day strip.
    static let sun = Color.warning
    /// Wind-down and sleep, as on Body's day clock.
    static let sleep = Color.other
}

// MARK: - How today went

struct HowTodayWentCard<Footer: View>: View {
    let line: String
    let outside: OutsideDay?
    let sun: (rise: Int, set: Int)?
    let now: Int
    @ViewBuilder let footer: Footer

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker("How today went")
            Text(line)
                .font(AppFont.body(15, weight: .semibold))
                .foregroundStyle(Color.ink)
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 8)
            if let outside {
                HStack(alignment: .firstTextBaseline, spacing: 18) {
                    if let minutes = outside.daylightMinutes {
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Image(systemName: "sun.max.fill").font(.system(size: 13)).foregroundStyle(Color.sun)
                            Text("\(minutes)").font(AppFont.number(30)).foregroundStyle(Color.sun)
                            Text("min outside").font(AppFont.body(12)).foregroundStyle(Color.inkSoft)
                        }
                        .accessibilityElement(children: .combine)
                    }
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(BodyFormat.steps(outside.stepTotal)).font(AppFont.number(30)).foregroundStyle(Color.ink)
                        Text("steps").font(AppFont.body(12)).foregroundStyle(Color.inkSoft)
                    }
                    .accessibilityElement(children: .combine)
                }
                .padding(.top, 12)
                DayStrip(day: outside, sun: outside.daylightMinutes == nil ? nil : sun, now: now)
                    .padding(.top, 10)
            }
            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 14).padding(.bottom, 2)
            footer
        }
        .card()
    }
}

/// 06:00 to midnight on one track: steps per hour in grey, time in daylight in sun yellow over a
/// faint sunrise-to-sunset band, workouts in their sport colour, and the rest of the day dimmed.
struct DayStrip: View {
    let day: OutsideDay
    let sun: (rise: Int, set: Int)?
    let now: Int

    private static let startHour = 6.0
    private static let hours = 18.0
    private let trackHeight: CGFloat = 40

    var body: some View {
        VStack(spacing: 4) {
            Canvas { context, size in draw(&context, size) }
                .frame(height: trackHeight)
            GeometryReader { geometry in
                let x = { (hour: Double) in self.x(hour * 60, width: geometry.size.width) }
                ZStack(alignment: .topLeading) {
                    label("06").position(x: 6, y: 6)
                    label("12").position(x: x(12), y: 6)
                    label("24").position(x: geometry.size.width - 6, y: 6)
                    if let sun {
                        Text("sunset \(EveningFormat.clock(sun.set))")
                            .font(AppFont.body(10)).foregroundStyle(Color.muted)
                            .fixedSize()
                            .offset(x: self.x(Double(sun.set), width: geometry.size.width) + 4)
                    }
                }
            }
            .frame(height: 12)
        }
        .accessibilityElement()
        .accessibilityLabel(accessibilityText)
    }

    private func label(_ text: String) -> some View {
        Text(text).font(AppFont.number(11, weight: .semibold)).foregroundStyle(Color.faint)
    }

    private func x(_ minutes: Double, width: CGFloat) -> CGFloat {
        CGFloat((minutes / 60 - Self.startHour) / Self.hours) * width
    }

    private func draw(_ context: inout GraphicsContext, _ size: CGSize) {
        let w = size.width, h = size.height
        let track = Path(roundedRect: CGRect(x: 0.5, y: 0.5, width: w - 1, height: h - 1), cornerRadius: 10)
        context.fill(track, with: .color(.inset))
        context.stroke(track, with: .color(.cardBorder), lineWidth: 1)
        context.clip(to: track)
        let calendar = Calendar.current
        func minutes(_ date: Date) -> Double {
            Double(EveningFormat.minutes(date, calendar: calendar)) + Double(calendar.component(.second, from: date)) / 60
        }
        if let sun {
            let rect = CGRect(x: x(Double(sun.rise), width: w), y: 1, width: x(Double(sun.set), width: w) - x(Double(sun.rise), width: w), height: h - 2)
            context.fill(Path(rect), with: .color(.sun.opacity(0.07)))
        }
        let hourWidth = w / Self.hours
        let peak = max(day.steps.map(\.value).max() ?? 1, 1)
        for hour in day.steps {
            let start = minutes(hour.start)
            guard start >= Self.startHour * 60 else { continue }
            let barHeight = max(2, (h - 10) * hour.value / peak)
            let rect = CGRect(x: x(start, width: w) + 2, y: h - 4 - barHeight, width: hourWidth - 4, height: barHeight)
            context.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color(.dim))
        }
        func block(_ start: Date, _ end: Date, _ color: Color, minWidth: CGFloat) {
            let x0 = x(minutes(start), width: w)
            let width = max(minWidth, x(minutes(end), width: w) - x0)
            context.fill(Path(roundedRect: CGRect(x: x0, y: 4, width: width, height: h - 8), cornerRadius: 2), with: .color(color))
        }
        for span in day.daylight { block(span.start, span.end, .sun, minWidth: 2.5) }
        for workout in day.workouts { block(workout.start, workout.end, workout.sport.color, minWidth: 3) }
        let nowX = x(Double(now), width: w)
        context.fill(Path(CGRect(x: nowX, y: 1, width: w - nowX, height: h - 2)), with: .color(.bg.opacity(0.55)))
        context.fill(Path(CGRect(x: nowX - 0.75, y: 0, width: 1.5, height: h)), with: .color(.ink))
    }

    private var accessibilityText: String {
        var parts = ["\(Int(day.stepTotal)) steps"]
        if let minutes = day.daylightMinutes { parts.insert("\(minutes) minutes in daylight", at: 0) }
        if !day.workouts.isEmpty { parts.append("\(day.workouts.count) workout\(day.workouts.count == 1 ? "" : "s")") }
        return parts.joined(separator: ", ")
    }
}

// MARK: - Still on today

struct StillOpenCard: View {
    let session: PhoneToday.Session
    let sport: Sport
    let fits: Bool
    let doneBy: String
    @Binding var showFallback: Bool
    let onStart: () -> Void
    let onMove: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                HStack(spacing: 8) {
                    Circle().fill(sport.color).frame(width: 8, height: 8)
                    Kicker("Still on today", color: sport.color)
                }
                Spacer()
                if let minutes = session.durationMin { Kicker("\(minutes) min") }
            }
            Text((session.title ?? sport.label).uppercased())
                .font(AppFont.title(26)).foregroundStyle(Color.ink)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 10)
            if let note = showFallback ? session.fallback : (fits ? session.purpose : "Wind-down has started. A hard session now pushes lights out back.") {
                Text(note).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 6)
            }
            if fits || onMove == nil {
                Button(action: onStart) {
                    Label(fits ? "Start · done by \(doneBy)" : "Start anyway", systemImage: "play.fill")
                }
                .buttonStyle(VoltButtonStyle())
                .padding(.top, 14)
                HStack(spacing: 8) {
                    if session.fallback != nil {
                        Button {
                            withAnimation(Motion.state) { showFallback.toggle() }
                        } label: {
                            Label(showFallback ? "Full session" : "Short version", systemImage: showFallback ? "arrow.uturn.backward" : "timer")
                        }
                        .buttonStyle(OutlineButtonStyle(height: 44))
                    }
                    if let onMove { moveButton(onMove).buttonStyle(OutlineButtonStyle(height: 44)) }
                }
                .padding(.top, 8)
            } else if let onMove {
                moveButton(onMove).buttonStyle(VoltButtonStyle()).padding(.top, 14)
                Button(action: onStart) { Label("Start anyway", systemImage: "play") }
                    .buttonStyle(OutlineButtonStyle(height: 44))
                    .padding(.top, 8)
            }
        }
        .card(border: sport.color.opacity(0.3))
    }

    private func moveButton(_ action: @escaping () -> Void) -> some View {
        Button(action: action) { Label("Move day", systemImage: "arrow.left.arrow.right") }
    }
}

// MARK: - Tonight

struct TonightEveningCard: View {
    let now: Int
    let lightsOut: Int
    let wakeMinutes: Int
    let reason: String?
    /// A still-open session drawn as a ghost block from now.
    let ghostMinutes: Int?
    let food: EveningFormat.Food?
    let onWake: () -> Void
    let onFood: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Tonight")
                Spacer()
                Button(action: onWake) {
                    HStack(spacing: 4) {
                        Text("wake \(EveningFormat.clock(wakeMinutes))")
                        Image(systemName: "pencil").font(.system(size: 10, weight: .semibold))
                    }
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
                    .frame(minHeight: 32)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Wake time \(EveningFormat.clock(wakeMinutes)), edit")
            }
            .frame(height: 16)
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(EveningFormat.clock(lightsOut)).font(AppFont.number(46)).foregroundStyle(Color.ink)
                HStack(spacing: 4) {
                    Image(systemName: "moon.fill").font(.system(size: 11))
                    Text("lights out")
                }
                .font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.sleep)
                .fixedSize()
            }
            .padding(.top, 8)
            if let reason {
                Text(reason).font(AppFont.body(13)).foregroundStyle(Color.inkSoft).padding(.top, 4)
            }
            TonightRunway(now: now, lightsOut: lightsOut, wakeMinutes: wakeMinutes, ghostMinutes: ghostMinutes)
                .padding(.top, 14)
            if let food {
                Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 14)
                Button(action: onFood) {
                    HStack(spacing: 10) {
                        Image(systemName: "fork.knife").font(.system(size: 14)).foregroundStyle(Color.inkSoft)
                        foodText(food).lineLimit(1)
                        Spacer(minLength: 4)
                        Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Color.faint)
                    }
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .card()
    }

    private func foodText(_ food: EveningFormat.Food) -> Text {
        switch food {
        case .left(let kcal, let protein):
            let rest = [kcal > 0 ? "\(BodyFormat.steps(Double(kcal))) kcal" : nil, protein > 0 ? "\(protein) g protein" : nil]
                .compactMap { $0 }.joined(separator: " · ")
            return Text("Food left").font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                + Text(" · " + rest).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
        case .done(let eaten, let target):
            return Text("Food’s in").font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                + Text(" · \(BodyFormat.steps(Double(eaten))) of \(BodyFormat.steps(Double(target))) kcal").font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
        }
    }
}

/// Now to lights out, then the night as a bar running off the edge: free time, the dashed
/// wind-down, sleep to the wake-up. An open session is a ghost block from now.
struct TonightRunway: View {
    let now: Int
    let lightsOut: Int
    let wakeMinutes: Int
    let ghostMinutes: Int?

    private var sleepText: String {
        let hours = BodyClockMath.sleepHours(lightsOut: lightsOut, wakeMinutes: wakeMinutes)
        return "sleep \(BodyFormat.duration(hours)) → \(EveningFormat.clock(wakeMinutes))"
    }

    var body: some View {
        GeometryReader { geometry in
            let w = geometry.size.width
            let span = Double(lightsOut + 100 - now)
            let x = { (m: Int) in CGFloat(Double(m - now) / span) * w }
            let windDown = EveningFormat.windDown(lightsOut: lightsOut)
            let wdStart = max(windDown, now)
            ZStack(alignment: .topLeading) {
                if windDown > now {
                    Capsule().fill(Color.track).frame(width: x(windDown), height: 8).offset(y: 10)
                }
                Capsule()
                    .strokeBorder(Color.sleep, style: StrokeStyle(lineWidth: 1, dash: [3, 2.5]))
                    .frame(width: max(0, x(lightsOut) - x(wdStart) - 2), height: 7)
                    .offset(x: x(wdStart) + 1, y: 10.5)
                Capsule().fill(Color.sleep.opacity(0.9))
                    .frame(width: w - x(lightsOut), height: 20)
                    .overlay(alignment: .leading) {
                        Text(sleepText).font(AppFont.number(13)).foregroundStyle(Color.bg).lineLimit(1).padding(.leading, 10)
                    }
                    .offset(x: x(lightsOut), y: 4)
                if let ghostMinutes {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.strength.opacity(0.22))
                        .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(Color.strength, style: StrokeStyle(lineWidth: 1, dash: [3, 2])))
                        .frame(width: CGFloat(Double(ghostMinutes) / span) * w, height: 16)
                        .offset(y: 6)
                }
                Circle().fill(Color.ink).frame(width: 8, height: 8).offset(x: -2, y: 10)
                Group {
                    if let ghostMinutes {
                        Text("now → done \(EveningFormat.clock(now + ghostMinutes))").foregroundStyle(Color.strength)
                    } else if windDown <= now {
                        Text("now · winding down, \(lightsOut - now) min to lights out").foregroundStyle(Color.sleep)
                    } else {
                        Text("now").foregroundStyle(Color.inkSoft)
                    }
                }
                .font(AppFont.number(12, weight: .semibold))
                .fixedSize()
                .offset(y: 28)
                if windDown > now, x(windDown) > 70 {
                    Text("wind down \(EveningFormat.clock(windDown))")
                        .font(AppFont.number(12, weight: .semibold)).foregroundStyle(Color.sleep)
                        .fixedSize()
                        .offset(x: x(windDown) + 2, y: 28)
                }
            }
        }
        .frame(height: 44)
        .accessibilityElement()
        .accessibilityLabel("Wind down at \(EveningFormat.clock(EveningFormat.windDown(lightsOut: lightsOut))), \(sleepText)")
    }
}

// MARK: - Tomorrow

extension Sport {
    /// The plan's session type in the backend's `sport_of` terms.
    init(sessionType: String?) {
        let key = (sessionType ?? "").replacingOccurrences(of: " ", with: "").lowercased()
        switch key {
        case _ where key.contains("ride"): self = .ride
        case _ where key.contains("run"): self = .run
        case "strength", "weighttraining", "crossfit", "workout": self = .strength
        case "yoga", "pilates", "mobility", "recovery", "rehab", "stretching": self = .mobility
        case "walk": self = .walk
        case "hike": self = .hike
        case "rest": self = .rest
        default: self = .other
        }
    }
}

struct TomorrowCard: View {
    let session: PhoneToday.Session?
    let weekday: String
    let onOpen: () -> Void

    var body: some View {
        // The server sends tomorrow without a sport colour; its session type says the same.
        let sport = session.map { $0.sport ?? Sport(sessionType: $0.sessionType) }
        let rest = sport == .rest
        let color = session == nil ? Color.muted : rest ? Color.mobility : sport?.color ?? .muted
        Button(action: onOpen) {
            HStack(spacing: 12) {
                RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                    .fill(color.opacity(0.13))
                    .frame(width: 40, height: 40)
                    .overlay(Image(systemName: (sport ?? .rest).symbol).font(.system(size: 17, weight: .semibold)).foregroundStyle(color))
                    .frame(maxHeight: .infinity, alignment: .top)
                VStack(alignment: .leading, spacing: 5) {
                    Kicker("Tomorrow · \(weekday)", color: color)
                    Text(title.uppercased()).font(AppFont.title(24)).foregroundStyle(Color.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    if let meta {
                        Text(meta).font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineLimit(2)
                    }
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Color.faint)
            }
            .card()
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var title: String {
        guard let session else { return "Nothing planned" }
        return session.sport == .rest ? "Rest day" : session.title ?? "Session"
    }

    private var meta: String? {
        guard let session else { return "Plan the week on the web; Today stays quiet." }
        if session.sport == .rest { return "Recover; nothing to set up." }
        let first = session.details.flatMap { $0.split(separator: ".").first.map(String.init) }
        return [session.durationMin.map { "\($0) min" }, first].compactMap { $0 }.joined(separator: " · ")
    }
}
