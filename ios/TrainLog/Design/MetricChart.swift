import SwiftUI

/// What a metric chart draws, already in the metric's own units.
struct MetricChartModel: Equatable, Sendable {
    struct Point: Equatable, Sendable {
        let x: Double
        let y: Double
    }

    struct Tick: Equatable, Sendable {
        let value: Double
        let label: String
    }

    var key: String
    var title: String
    var color: Color
    var points: [Point]
    /// A grey area behind the line (elevation), heights 0...1.
    var ghost: [Point] = []
    var yDomain: ClosedRange<Double>
    /// Pace: faster (smaller) is up.
    var invert = false
    var yTicks: [Tick] = []
    var xDomain: ClosedRange<Double>
    var xTicks: [Tick] = []
    var average: Double?
    var averageLabel: String?

    /// The sample nearest to `x`.
    func nearest(_ x: Double) -> Point? {
        guard !points.isEmpty else { return nil }
        var low = 0, high = points.count - 1
        while low < high {
            let mid = (low + high) / 2
            if points[mid].x < x { low = mid + 1 } else { high = mid }
        }
        if low > 0, abs(points[low - 1].x - x) < abs(points[low].x - x) { return points[low - 1] }
        return points[low]
    }
}

/// Gridlines with labels, a faint ghost, a 16% fill, a 2 pt line, a dashed average and its pill.
/// With `scrub`, dragging shows a rule and a value pill.
struct MetricChart: View {
    let model: MetricChartModel
    var height: CGFloat = 132
    var scrub: Binding<Double?>?
    var scrubText: ((Double) -> String)?
    /// Off for a chart stacked under another that already shows the pill.
    var showsScrubPill = true

    var body: some View {
        VStack(spacing: 8) {
            Canvas { context, size in draw(&context, size) }
                .frame(height: height)
                .overlay { scrubOverlay }
            xAxis
        }
        .accessibilityElement()
        .accessibilityLabel("\(model.title) chart" + (model.averageLabel.map { ", average \($0)" } ?? ""))
    }

    private func xPos(_ x: Double, _ width: CGFloat) -> CGFloat {
        let span = max(model.xDomain.upperBound - model.xDomain.lowerBound, 0.0001)
        return CGFloat((x - model.xDomain.lowerBound) / span) * width
    }

    private func yPos(_ y: Double, _ height: CGFloat) -> CGFloat {
        let span = max(model.yDomain.upperBound - model.yDomain.lowerBound, 0.0001)
        var fraction = (y - model.yDomain.lowerBound) / span
        if model.invert { fraction = 1 - fraction }
        return height - CGFloat(min(max(fraction, 0), 1)) * height
    }

    private func draw(_ context: inout GraphicsContext, _ size: CGSize) {
        for tick in model.yTicks {
            let y = yPos(tick.value, size.height)
            var line = Path()
            line.move(to: CGPoint(x: 0, y: y))
            line.addLine(to: CGPoint(x: size.width, y: y))
            context.stroke(line, with: .color(Color.track), lineWidth: 1)
            context.draw(Text(tick.label).font(AppFont.body(10)).foregroundStyle(Color.faint), at: CGPoint(x: 0, y: y - 4), anchor: .bottomLeading)
        }
        if model.ghost.count > 1 {
            var ghost = Path()
            ghost.move(to: CGPoint(x: xPos(model.ghost[0].x, size.width), y: size.height))
            for point in model.ghost {
                ghost.addLine(to: CGPoint(x: xPos(point.x, size.width), y: size.height - CGFloat(point.y) * size.height * 0.85))
            }
            ghost.addLine(to: CGPoint(x: xPos(model.ghost[model.ghost.count - 1].x, size.width), y: size.height))
            ghost.closeSubpath()
            context.fill(ghost, with: .color(Color.inkSoft.opacity(0.07)))
        }
        guard model.points.count > 1 else { return }
        var line = Path()
        for (index, point) in model.points.enumerated() {
            let p = CGPoint(x: xPos(point.x, size.width), y: yPos(point.y, size.height))
            if index == 0 { line.move(to: p) } else { line.addLine(to: p) }
        }
        var fill = line
        fill.addLine(to: CGPoint(x: xPos(model.points[model.points.count - 1].x, size.width), y: size.height))
        fill.addLine(to: CGPoint(x: xPos(model.points[0].x, size.width), y: size.height))
        fill.closeSubpath()
        context.fill(fill, with: .color(model.color.opacity(0.16)))
        context.stroke(line, with: .color(model.color), style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))

        if let average = model.average {
            let y = yPos(average, size.height)
            var rule = Path()
            rule.move(to: CGPoint(x: 0, y: y))
            rule.addLine(to: CGPoint(x: size.width, y: y))
            context.stroke(rule, with: .color(Color.inkSoft.opacity(0.55)), style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
            if let label = model.averageLabel {
                let text = context.resolve(Text(label).font(AppFont.number(11)).foregroundStyle(Color.ink))
                let width = text.measure(in: size).width + 16
                let pill = CGRect(x: size.width - width, y: y - 9, width: width, height: 18)
                context.fill(Path(roundedRect: pill, cornerRadius: 9), with: .color(Color.raised))
                context.draw(text, at: CGPoint(x: pill.midX, y: pill.midY))
            }
        }
    }

    @ViewBuilder
    private var scrubOverlay: some View {
        if let scrub {
            GeometryReader { proxy in
                ZStack(alignment: .topLeading) {
                    Color.clear.contentShape(Rectangle())
                    if let x = scrub.wrappedValue, let point = model.nearest(x) {
                        let px = xPos(point.x, proxy.size.width)
                        let py = yPos(point.y, proxy.size.height)
                        Rectangle().fill(Color.ink.opacity(0.7)).frame(width: 1, height: proxy.size.height).offset(x: px)
                        Circle().fill(model.color).frame(width: 8, height: 8).overlay(Circle().stroke(Color.bg, lineWidth: 2))
                            .offset(x: px - 4, y: py - 4)
                        if showsScrubPill {
                        Text(scrubText?(point.x) ?? "")
                            .font(AppFont.body(12, weight: .semibold))
                            .foregroundStyle(Color.bg)
                            .padding(.horizontal, 10)
                            .frame(height: 24)
                            .background(Color.ink, in: Capsule())
                            .fixedSize()
                            .alignmentGuide(.leading) { dimension in
                                -min(max(px - dimension.width / 2, 0), proxy.size.width - dimension.width)
                            }
                            .offset(y: -34)
                        }
                    }
                }
                .gesture(DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        let fraction = min(max(value.location.x / max(proxy.size.width, 1), 0), 1)
                        let x = model.xDomain.lowerBound + Double(fraction) * (model.xDomain.upperBound - model.xDomain.lowerBound)
                        scrub.wrappedValue = model.nearest(x)?.x
                    })
            }
            .sensoryFeedback(.selection, trigger: scrub.wrappedValue.map { Int($0 * 4) })
        }
    }

    private var xAxis: some View {
        GeometryReader { proxy in
            ZStack(alignment: .topLeading) {
                ForEach(Array(model.xTicks.enumerated()), id: \.offset) { index, tick in
                    let anchor: UnitPoint = index == 0 ? .leading : (index == model.xTicks.count - 1 ? .trailing : .center)
                    Text(tick.label)
                        .font(AppFont.body(10))
                        .foregroundStyle(Color.faint)
                        .fixedSize()
                        .frame(width: 80, alignment: Alignment(horizontal: anchor == .leading ? .leading : (anchor == .trailing ? .trailing : .center), vertical: .center))
                        .offset(x: xPos(tick.value, proxy.size.width) - (anchor == .leading ? 0 : (anchor == .trailing ? 80 : 40)))
                }
            }
        }
        .frame(height: 12)
    }
}
