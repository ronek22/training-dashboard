import SwiftUI

/// Pure maths for the Day tab (unit-tested).
enum BodyClockMath {
    /// Hours since local midnight of `day`, wrapped into 0..<24 (last evening's bedtime lands at 23:xx).
    static func hour(_ date: Date, day: Date, calendar: Calendar = .current) -> Double {
        let start = calendar.startOfDay(for: day)
        let hours = date.timeIntervalSince(start) / 3600
        return (hours.truncatingRemainder(dividingBy: 24) + 24).truncatingRemainder(dividingBy: 24)
    }

    /// Lights-out time in minutes after midnight: the wake-up minus the night's sleep, minus 15
    /// minutes to fall asleep, rounded down to the quarter. A real debt adds 15–30 minutes.
    static func lightsOut(wakeMinutes: Int, needH: Double, debtH: Double) -> Int {
        let extra = debtH > 3 ? 30 : debtH > 1 ? 15 : 0
        let raw = wakeMinutes - Int((needH * 60).rounded()) - extra - 15
        let wrapped = (raw % 1440 + 1440) % 1440
        return wrapped / 15 * 15
    }

    /// Hours of sleep the target gives before the wake-up.
    static func sleepHours(lightsOut: Int, wakeMinutes: Int) -> Double {
        Double(((wakeMinutes - lightsOut - 15) % 1440 + 1440) % 1440) / 60
    }

    /// "23:45".
    static func clock(minutes: Int) -> String {
        let value = (minutes % 1440 + 1440) % 1440
        return String(format: "%02d:%02d", value / 60, value % 60)
    }
}

/// The day as a 24-hour dial: midnight on top, last night's sleep stages on the ring, steps per hour
/// as bars outside it, the wind-down before lights out dashed, and a hand for now.
struct BodyClockDial<Center: View>: View {
    let now: Date
    let sleep: PhoneBody.Sleep?
    let steps: [LiveDay.Hour]
    let lightsOut: Int
    @ViewBuilder let center: Center

    private let ring: CGFloat = 22

    var body: some View {
        ZStack {
            Canvas { context, size in draw(&context, size) }
            center
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityElement(children: .combine)
    }

    private func draw(_ context: inout GraphicsContext, _ size: CGSize) {
        let c = CGPoint(x: size.width / 2, y: size.height / 2)
        let r = min(size.width, size.height) / 2 - 46
        let nowHour = BodyClockMath.hour(now, day: now)

        context.stroke(arc(c, r, 0, 24), with: .color(.card), lineWidth: ring)
        context.stroke(arc(c, r, 0, nowHour), with: .color(Color(hex: 0x181C25)), lineWidth: ring)

        for hour in 0..<24 {
            let major = hour % 6 == 0
            var tick = Path()
            tick.move(to: point(c, r - ring / 2 - 4, Double(hour)))
            tick.addLine(to: point(c, r - ring / 2 - (major ? 12 : 8), Double(hour)))
            context.stroke(tick, with: .color(major ? .muted : .dim), lineWidth: major ? 1.6 : 1)
            if major {
                let label = context.resolve(Text("\(hour)").font(AppFont.number(13)).foregroundStyle(Color.muted))
                context.draw(label, at: point(c, r - ring / 2 - 24, Double(hour)))
            }
        }

        // Last night's stages on the ring.
        if let sleep {
            for segment in sleep.segments {
                guard let stage = SleepStage(backend: segment.stage),
                      let from = BodyFormat.date(segment.start), let to = BodyFormat.date(segment.end), to > from else { continue }
                let a = BodyClockMath.hour(from, day: now)
                let b = a + to.timeIntervalSince(from) / 3600
                context.stroke(arc(c, r, a, b), with: .color(stage.color), lineWidth: ring)
            }
        }

        // Wind-down: 45 minutes before lights out, dashed just outside the ring, moon at lights out.
        let target = Double(lightsOut) / 60
        context.stroke(arc(c, r + ring / 2 + 5, target - 0.75, target), with: .color(Color.other.opacity(0.8)),
                       style: StrokeStyle(lineWidth: 3, lineCap: .round, dash: [3, 4]))
        let moon = context.resolve(Image(systemName: "moon.fill"))
        context.draw(moon.withForeground(.other), in: CGRect(origin: point(c, r + ring / 2 + 18, target), size: .zero).insetBy(dx: -7, dy: -7))

        // Steps per hour, three bars an hour, outside the ring.
        let peak = max(2600, steps.map(\.value).max() ?? 0)
        for hour in steps where hour.value > 0 {
            let h = BodyClockMath.hour(hour.start, day: now)
            let length = 4 + hour.value / peak * 26
            for offset in [0.2, 0.5, 0.8] {
                var bar = Path()
                bar.move(to: point(c, r + ring / 2 + 4, h + offset))
                bar.addLine(to: point(c, r + ring / 2 + 4 + length, h + offset))
                context.stroke(bar, with: .color(.run), style: StrokeStyle(lineWidth: 3, lineCap: .round))
            }
        }

        // Now.
        var hand = Path()
        hand.move(to: point(c, r - ring / 2 - 2, nowHour))
        hand.addLine(to: point(c, r + ring / 2 + 2, nowHour))
        context.stroke(hand, with: .color(.ink), style: StrokeStyle(lineWidth: 3, lineCap: .round))
        let tip = point(c, r + ring / 2 + 2, nowHour)
        context.fill(Path(ellipseIn: CGRect(x: tip.x - 5, y: tip.y - 5, width: 10, height: 10)), with: .color(.ink))
    }

    private func point(_ c: CGPoint, _ radius: CGFloat, _ hour: Double) -> CGPoint {
        let angle = (hour / 24 * 360 - 90) * .pi / 180
        return CGPoint(x: c.x + radius * cos(angle), y: c.y + radius * sin(angle))
    }

    /// Clockwise from `from` to `to` (hours), sampled so the direction never depends on flipped axes.
    private func arc(_ c: CGPoint, _ radius: CGFloat, _ from: Double, _ to: Double) -> Path {
        var path = Path()
        guard to > from else { return path }
        let steps = max(2, Int((to - from) * 24))
        for index in 0...steps {
            let p = point(c, radius, from + (to - from) * Double(index) / Double(steps))
            index == 0 ? path.move(to: p) : path.addLine(to: p)
        }
        return path
    }
}

private extension GraphicsContext.ResolvedImage {
    func withForeground(_ color: Color) -> Self {
        var copy = self
        copy.shading = .color(color)
        return copy
    }
}
