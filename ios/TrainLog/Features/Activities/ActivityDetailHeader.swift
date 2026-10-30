import MapKit
import SwiftUI

// The visual that leads the page (map, trace or muscle map), fading into the background with the
// title and one big number on it. Animations play once on open and are static under Reduce Motion.

struct DetailHeaderView: View {
    let header: ActivityDetailFormat.Header
    let visual: ActivityDetailFormat.Visual?
    /// Shown under the date: offline, last synced.
    var offlineLine: String?
    /// Loading: a flat block where the visual will be.
    var placeholderHeight: CGFloat?

    static func height(_ visual: ActivityDetailFormat.Visual?) -> CGFloat? {
        switch visual {
        case .route: 560
        case .trace: 470
        case .muscles: 420
        default: nil
        }
    }

    var body: some View {
        if let height = Self.height(visual) ?? placeholderHeight {
            ZStack(alignment: .bottomLeading) {
                visualView.frame(height: height).clipped()
                BackgroundFade().frame(height: height * (isRoute ? 0.62 : 0.46))
                text.padding(.horizontal, 16).padding(.bottom, isRoute ? 20 : 16)
            }
            .frame(height: height, alignment: .bottom)
            .frame(maxWidth: .infinity)
        } else {
            text.padding(.horizontal, 16).padding(.top, 150)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var isRoute: Bool {
        if case .route = visual { return true }
        return false
    }

    @ViewBuilder
    private var visualView: some View {
        switch visual {
        case let .route(coordinates, fractions, legend):
            GlowRouteMap(coordinates: coordinates, fractions: fractions)
                .overlay(alignment: .topLeading) { RouteLegend(low: legend.low, high: legend.high).padding(.leading, 16).padding(.top, 116) }
        case .trace(let trace):
            TraceView(trace: trace)
        case .muscles(let summary):
            ZStack {
                Color.bg
                MusclePair(summary: summary, background: .bg)
                    .padding(.horizontal, 36)
                    .padding(.top, 72)
                    .padding(.bottom, 96)
            }
        default:
            Color(hex: 0x0C0F15)
        }
    }

    private var text: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                if header.isPlace { Image(systemName: "location.circle").font(.system(size: 14, weight: .semibold)) }
                Text(header.kicker).lineLimit(1)
            }
            .font(AppFont.body(15, weight: .semibold))
            .foregroundStyle(header.kickerColor)
            Text(header.title.uppercased())
                .font(AppFont.title(40))
                .foregroundStyle(Color.ink)
                .lineSpacing(-6)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 6)
            if let big = header.big {
                Text("\(Text(big.value).font(AppFont.number(44)))\(Text(" ").font(AppFont.number(12)))\(Text(big.unit.uppercased()).font(AppFont.number(24)))")
                    .foregroundStyle(big.metric.color)
                    .padding(.top, 2)
            }
            Text(header.dateLine)
                .font(AppFont.body(14))
                .foregroundStyle(Color.inkSoft)
                .padding(.top, 8)
            if let offlineLine {
                HStack(spacing: 6) {
                    Circle().fill(Color(hex: 0xFFC83A)).frame(width: 6, height: 6)
                    Text(offlineLine).font(AppFont.body(13)).foregroundStyle(Color(hex: 0xFFC83A))
                }
                .padding(.top, 8)
            }
            if !header.facts.isEmpty {
                HStack(spacing: 24) {
                    ForEach(header.facts, id: \.label) { fact in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(fact.value).font(AppFont.number(20)).foregroundStyle(fact.color)
                            Text(fact.label).font(AppFont.body(12)).foregroundStyle(Color.muted)
                        }
                    }
                }
                .padding(.top, 16)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

private struct RouteLegend: View {
    let low: String
    let high: String

    var body: some View {
        HStack(spacing: 6) {
            Text(low)
            Capsule()
                .fill(LinearGradient(colors: ColorScale.route.stops.map { Color(hex: $0.hex) }, startPoint: .leading, endPoint: .trailing))
                .frame(width: 56, height: 4)
            Text(high)
        }
        .font(AppFont.body(11))
        .foregroundStyle(Color.inkSoft)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.bg.opacity(0.7), in: Capsule())
        .accessibilityHidden(true)
    }
}

// MARK: Glowing route

/// A muted dark map with the route drawn over it in pace/speed/elevation colours, glowing.
struct GlowRouteMap: View {
    let coordinates: [CLLocationCoordinate2D]
    let fractions: [Double]
    @State private var points: [CGPoint] = []
    @State private var progress = 0.0
    @State private var dotScale = 0.0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GeometryReader { geometry in
            MapReader { proxy in
                Map(initialPosition: .rect(Self.frame(coordinates, in: geometry.size)), interactionModes: []) {}
                    .mapStyle(.standard(elevation: .flat, emphasis: .muted, pointsOfInterest: .excludingAll, showsTraffic: false))
                    .environment(\.colorScheme, .dark)
                    .allowsHitTesting(false)
                    .onMapCameraChange(frequency: .onEnd) { project(proxy) }
                    .task {
                        try? await Task.sleep(for: .milliseconds(350))
                        if points.isEmpty { project(proxy) }
                    }
            }
            .overlay(Color.bg.opacity(0.66))
            .overlay {
                RouteGlow(points: points, colors: fractions.map(ColorScale.route.color), progress: progress)
            }
            .overlay {
                if let end = points.last {
                    ZStack {
                        Circle().fill(Color.ink.opacity(0.25)).frame(width: 18, height: 18)
                        Circle().fill(Color.ink).frame(width: 9, height: 9).overlay(Circle().stroke(Color.bg, lineWidth: 2))
                    }
                    .scaleEffect(dotScale)
                    .position(end)
                }
            }
        }
        .accessibilityLabel("Route map")
    }

    private func project(_ proxy: MapProxy) {
        let projected = coordinates.compactMap { proxy.convert($0, to: .local) }
        guard projected.count == coordinates.count, projected != points else { return }
        let first = points.isEmpty
        points = projected
        guard first else { return }
        if reduceMotion {
            progress = 1
            dotScale = 1
            return
        }
        withAnimation(.timingCurve(0.45, 0.05, 0.35, 1, duration: 2.4)) { progress = 1 } completion: {
            withAnimation(.easeOut(duration: 0.15)) { dotScale = 1.3 } completion: {
                withAnimation(.easeInOut(duration: 0.2)) { dotScale = 1 }
            }
        }
    }

    /// A map rect that puts the route in the top part of the header, above the title block.
    static func frame(_ coordinates: [CLLocationCoordinate2D], in size: CGSize) -> MKMapRect {
        let points = coordinates.map(MKMapPoint.init)
        let minX = points.map(\.x).min() ?? 0, maxX = points.map(\.x).max() ?? 0
        let minY = points.map(\.y).min() ?? 0, maxY = points.map(\.y).max() ?? 0
        let box = CGRect(x: 64, y: 118, width: max(size.width - 128, 1), height: max(size.height * 0.29, 1))
        let scale = max((maxX - minX) / box.width, (maxY - minY) / box.height, 2)
        let originX = (minX + maxX) / 2 - Double(box.midX) * scale
        let originY = (minY + maxY) / 2 - Double(box.midY) * scale
        return MKMapRect(x: originX, y: originY, width: Double(size.width) * scale, height: Double(size.height) * scale)
    }
}

/// The route as coloured segments: a 9 pt blurred copy for the glow, a 3.5 pt line on top,
/// drawn up to `progress`.
private struct RouteGlow: View, @MainActor Animatable {
    let points: [CGPoint]
    let colors: [Color]
    var progress: Double

    var animatableData: Double {
        get { progress }
        set { progress = newValue }
    }

    var body: some View {
        Canvas { context, _ in
            guard points.count > 1 else { return }
            let reach = progress * Double(points.count - 1)
            // A soft halo from two wide, faint strokes (no blur), then the crisp line.
            draw(&context, reach: reach, width: 10, opacity: 0.07)
            draw(&context, reach: reach, width: 6.5, opacity: 0.16)
            draw(&context, reach: reach, width: 3.5, opacity: 1)
        }
        .allowsHitTesting(false)
    }

    /// Consecutive points of the same colour become one path, so strokes stay clean at the joins.
    private func draw(_ context: inout GraphicsContext, reach: Double, width: CGFloat, opacity: Double) {
        let full = min(Int(reach), points.count - 1)
        var path = Path()
        var current: Color?
        func flush() {
            if let current, !path.isEmpty {
                context.stroke(path, with: .color(current.opacity(opacity)), style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round))
            }
        }
        for index in 0..<full {
            let color = colors[safe: index] ?? .ink
            if color != current {
                flush()
                current = color
                path = Path()
                path.move(to: points[index])
            }
            path.addLine(to: points[index + 1])
        }
        let rest = reach - Double(full)
        if full < points.count - 1, rest > 0 {
            let a = points[full], b = points[full + 1]
            if current == nil { path.move(to: a); current = colors[safe: full] ?? .ink }
            path.addLine(to: CGPoint(x: a.x + (b.x - a.x) * rest, y: a.y + (b.y - a.y) * rest))
        }
        flush()
    }
}

/// Full-screen, interactive version from the map button.
struct RouteMapScreen: View {
    let coordinates: [CLLocationCoordinate2D]
    let fractions: [Double]
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Map(initialPosition: .rect(Self.fit(coordinates))) {
            ForEach(Array(stride(from: 0, to: coordinates.count - 1, by: 2)), id: \.self) { index in
                MapPolyline(coordinates: Array(coordinates[index...min(index + 2, coordinates.count - 1)]))
                    .stroke(ColorScale.route.color(fractions[safe: index] ?? 0.5), style: StrokeStyle(lineWidth: 4.5, lineCap: .round, lineJoin: .round))
            }
        }
        .mapStyle(.standard(elevation: .flat, emphasis: .muted, pointsOfInterest: .excludingAll))
        .environment(\.colorScheme, .dark)
        .ignoresSafeArea()
        .overlay(alignment: .topTrailing) {
            GlassCircleButton(symbol: "xmark", label: "Close map") { dismiss() }
                .padding(.trailing, 16)
                .padding(.top, 8)
        }
    }

    private static func fit(_ coordinates: [CLLocationCoordinate2D]) -> MKMapRect {
        let rect = coordinates.map(MKMapPoint.init).reduce(MKMapRect.null) { $0.union(MKMapRect(origin: $1, size: MKMapSize(width: 0, height: 0))) }
        let pad = max(rect.width, rect.height) * 0.2 + 200
        return rect.insetBy(dx: -pad, dy: -pad)
    }
}

// MARK: Trace

/// The power (or heart-rate) trace in zone colours: grid, faint HR line, glow, fading fill, Zone 2
/// guide and avg pill. Draws left to right in 1.6 s; the rest fades in after.
struct TraceView: View {
    let trace: ActivityDetailFormat.Trace
    @State private var progress = 0.0
    @State private var late = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GeometryReader { geometry in
            let plot = CGRect(x: 0, y: 100, width: geometry.size.width, height: 146)
            ZStack(alignment: .topLeading) {
                Color(hex: 0x0C0F15)
                Canvas { context, size in grid(&context, size) }
                if let guide = trace.guide {
                    let y = plot.maxY - guide.y * plot.height
                    Path { $0.move(to: CGPoint(x: 0, y: y)); $0.addLine(to: CGPoint(x: plot.width, y: y)) }
                        .stroke(ZonePalette.color(1).opacity(0.45), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
                        .opacity(late ? 1 : 0)
                    Text(guide.label).font(AppFont.body(11, weight: .semibold)).foregroundStyle(ZonePalette.color(1).opacity(0.8))
                        .frame(width: plot.width - 16, alignment: .trailing)
                        .offset(y: y - 20)
                        .opacity(late ? 1 : 0)
                }
                TraceLines(trace: trace, plot: plot, progress: progress, fill: late ? 1 : 0)
                if let average = trace.average {
                    let y = plot.maxY - average.y * plot.height
                    Group {
                        Path { $0.move(to: CGPoint(x: 0, y: y)); $0.addLine(to: CGPoint(x: plot.width, y: y)) }
                            .stroke(Color.ink.opacity(0.28), style: StrokeStyle(lineWidth: 1, dash: [2, 4]))
                        Text(average.label)
                            .font(AppFont.number(11))
                            .foregroundStyle(Color.ink)
                            .padding(.horizontal, 12)
                            .frame(height: 20)
                            .background(Color(hex: 0x12151C).opacity(0.9), in: Capsule())
                            .overlay(Capsule().strokeBorder(Color.outline))
                            .offset(x: 16, y: y - 10)
                    }
                    .opacity(late ? 1 : 0)
                }
            }
        }
        .onAppear {
            if reduceMotion {
                progress = 1
                late = true
                return
            }
            withAnimation(.timingCurve(0.22, 0.8, 0.3, 1, duration: 1.6)) { progress = 1 }
            withAnimation(.easeOut(duration: 0.5).delay(0.5)) { late = true }
        }
        .accessibilityLabel("Trace of the session")
    }

    private func grid(_ context: inout GraphicsContext, _ size: CGSize) {
        for index in 0..<5 {
            let y = 100 + CGFloat(index) * 36.5
            context.stroke(Path { $0.move(to: CGPoint(x: 0, y: y)); $0.addLine(to: CGPoint(x: size.width, y: y)) }, with: .color(Color(hex: 0x151A23)), lineWidth: 1)
        }
        for index in 1..<6 {
            let x = size.width * CGFloat(index) / 6
            context.stroke(Path { $0.move(to: CGPoint(x: x, y: 80)); $0.addLine(to: CGPoint(x: x, y: 266)) }, with: .color(Color(hex: 0x12161E)), lineWidth: 1)
        }
    }
}

private struct TraceLines: View, @MainActor Animatable {
    let trace: ActivityDetailFormat.Trace
    let plot: CGRect
    var progress: Double
    var fill: Double

    var animatableData: AnimatablePair<Double, Double> {
        get { AnimatablePair(progress, fill) }
        set { progress = newValue.first; fill = newValue.second }
    }

    var body: some View {
        Canvas { context, size in
            let points = trace.points.map { CGPoint(x: plot.minX + $0.x * plot.width, y: plot.maxY - $0.y * plot.height) }
            guard points.count > 1 else { return }
            let reach = progress * Double(points.count - 1)
            let visible = Int(reach) + 1

            if trace.heartRate.count > 1 {
                let hr = trace.heartRate.map { CGPoint(x: plot.minX + $0.x * plot.width, y: plot.maxY - $0.y * plot.height) }
                var path = Path()
                path.addLines(Array(hr.prefix(Int(progress * Double(hr.count - 1)) + 1)))
                context.stroke(path, with: .color(Metric.heartRate.color.opacity(0.5)), lineWidth: 1.5)
                if progress >= 1, let last = hr.last {
                    context.draw(Text("Heart rate").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Metric.heartRate.color.opacity(0.85)),
                                 at: CGPoint(x: size.width - 16, y: max(last.y - 8, 130)), anchor: .bottomTrailing)
                }
            }
            // Fill: zone colours at 32%, fading downwards.
            if fill > 0 {
                context.drawLayer { layer in
                    layer.opacity = fill
                    for index in 0..<(points.count - 1) {
                        var quad = Path()
                        quad.move(to: CGPoint(x: points[index].x, y: plot.maxY + 20))
                        quad.addLine(to: points[index])
                        quad.addLine(to: points[index + 1])
                        quad.addLine(to: CGPoint(x: points[index + 1].x, y: plot.maxY + 20))
                        quad.closeSubpath()
                        layer.fill(quad, with: .color(ZonePalette.color(trace.points[index].zone).opacity(0.32)))
                    }
                    layer.blendMode = .destinationIn
                    layer.fill(Path(CGRect(x: 0, y: 0, width: size.width, height: size.height)),
                               with: .linearGradient(Gradient(colors: [.white, .white.opacity(0)]), startPoint: CGPoint(x: 0, y: plot.minY), endPoint: CGPoint(x: 0, y: plot.maxY + 20)))
                }
            }
            context.drawLayer { glow in
                glow.addFilter(.blur(radius: 6))
                glow.opacity = 0.55
                strokeSegments(&glow, points, upTo: reach, width: 6)
            }
            strokeSegments(&context, points, upTo: reach, width: 2.5)
            if progress >= 1, let end = points.last {
                let color = ZonePalette.color(trace.points.last?.zone ?? 0)
                context.fill(Path(ellipseIn: CGRect(x: end.x - 9, y: end.y - 9, width: 18, height: 18)), with: .color(color.opacity(0.25)))
                context.fill(Path(ellipseIn: CGRect(x: end.x - 4, y: end.y - 4, width: 8, height: 8)), with: .color(color))
            }
            _ = visible
        }
        .allowsHitTesting(false)
    }

    /// Runs of the same zone become one stroked path each, cut at `reach`.
    private func strokeSegments(_ context: inout GraphicsContext, _ points: [CGPoint], upTo reach: Double, width: CGFloat) {
        let last = min(Int(reach), points.count - 2)
        guard last >= 0 else { return }
        var start = 0
        while start <= last {
            let zone = trace.points[start].zone
            var end = start
            while end < last, trace.points[end + 1].zone == zone { end += 1 }
            var path = Path()
            path.move(to: points[start])
            for index in start...end {
                var next = points[index + 1]
                if index == Int(reach), reach < Double(points.count - 1) {
                    let t = reach - Double(index)
                    next = CGPoint(x: points[index].x + (next.x - points[index].x) * t, y: points[index].y + (next.y - points[index].y) * t)
                }
                path.addLine(to: next)
            }
            context.stroke(path, with: .color(ZonePalette.color(zone)), style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round))
            start = end + 1
        }
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
