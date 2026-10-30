import SwiftUI

// "Show more" behind Running form and Splits: the run's dynamics from its HealthFit FIT file.

/// Grabber, centred title over a subtitle, Done on the right.
struct DetailSheetHeader: View {
    let title: String
    let subtitle: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                VStack(spacing: 2) {
                    Text(title).font(AppFont.body(17, weight: .semibold)).foregroundStyle(Color.ink)
                    Text(subtitle).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
                }
                .padding(.horizontal, 72)
                HStack {
                    Spacer()
                    Button("Done") { dismiss() }
                        .font(AppFont.body(16, weight: .semibold))
                        .foregroundStyle(Color(hex: 0x6FAEFF))
                        .frame(minWidth: 44, minHeight: 44)
                }
                .padding(.horizontal, 16)
            }
            .padding(.top, 20)
            .padding(.bottom, 12)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
        }
    }
}

struct RunningFormSheet: View {
    let detail: ActivityDetail
    let fitness: RunningFitness.Form?

    var body: some View {
        let rows = ActivityDetailFormat.formDetails(detail, fitness: fitness)
        let cells = rows.map(\.cell)
        VStack(spacing: 0) {
            DetailSheetHeader(title: "Running form", subtitle: "\(detail.activity.title) · \(ActivityFormat.longDay(detail.activity.date))")
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if let summary = ActivityDetailFormat.formSummary(cells) {
                        StatusLine(tone: summary.tone, text: summary.text, size: 15, color: Color(hex: 0xC9CFDA)).padding(.top, 20)
                    }
                    legend.padding(.top, 16)
                    ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                        FormRow(row: row).padding(.top, index == 0 ? 8 : 0)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 32)
            }
            .scrollIndicators(.hidden)
        }
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.card)
    }

    private var legend: some View {
        HStack(spacing: 16) {
            HStack(spacing: 6) { RoundedRectangle(cornerRadius: 3).fill(Color.mobility.opacity(0.35)).frame(width: 14, height: 6); Text("Good range") }
            HStack(spacing: 6) { RoundedRectangle(cornerRadius: 1).fill(Color.inkSoft).frame(width: 2, height: 12); Text("Your usual") }
            HStack(spacing: 6) { Circle().fill(Color.ink).frame(width: 10, height: 10); Text("This run") }
        }
        .font(AppFont.body(12))
        .foregroundStyle(Color.muted)
    }
}

private struct FormRow: View {
    let row: ActivityDetailFormat.FormDetail

    private var tint: Color {
        row.cell.ranged ? (row.cell.good ? .mobility : ActivityDetailFormat.warn) : .inkSoft
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(row.cell.label).font(AppFont.body(13)).foregroundStyle(Color.muted)
                    MetricValue(parts: [(row.cell.value, row.cell.unit)], size: 30, color: row.cell.metric.color, unitColor: .muted)
                }
                Spacer(minLength: 12)
                VStack(alignment: .trailing, spacing: 4) {
                    Text(row.cell.word).font(AppFont.body(14, weight: .semibold)).foregroundStyle(tint)
                    if let usual = row.cell.usual { Text("usual \(usual) \(row.cell.unit)").font(AppFont.body(12)).foregroundStyle(Color.muted) }
                }
            }
            .padding(.top, 16)
            RangeBar(row: row, tint: row.cell.ranged ? tint : Color.ink).frame(height: 16).padding(.top, 14)
            if let good = row.good {
                HStack {
                    Text(label(row.scale.lowerBound)).frame(maxWidth: .infinity, alignment: .leading)
                    Text("good \(label(good.lowerBound))–\(label(good.upperBound))")
                    Text(label(row.scale.upperBound)).frame(maxWidth: .infinity, alignment: .trailing)
                }
                .font(AppFont.body(10))
                .foregroundStyle(Color.faint)
                .padding(.top, 4)
            }
            if !row.perKm.isEmpty {
                HStack(alignment: .center, spacing: 12) {
                    Spark(values: row.perKm, color: row.cell.metric.color).frame(width: 72, height: 24)
                    if let drift = row.drift { Text(drift).font(AppFont.body(12)).foregroundStyle(Color.inkSoft) }
                }
                .padding(.top, 12)
            }
            if let note = row.note {
                Text(note).font(AppFont.body(13)).foregroundStyle(Color.muted).lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 10)
            }
        }
        .padding(.bottom, 16)
        .accessibilityElement(children: .combine)
    }

    private func label(_ value: Double) -> String {
        row.cell.unit == "m" ? String(format: "%.2f", value) : (value < 20 ? value.formatted(ActivityFormat.upToOneDecimal) : "\(Int(value.rounded()))")
    }
}

/// Track, good range in translucent teal, a tick at your usual, a dot for this run.
private struct RangeBar: View {
    let row: ActivityDetailFormat.FormDetail
    let tint: Color

    var body: some View {
        GeometryReader { proxy in
            let width = proxy.size.width
            let span = max(row.scale.upperBound - row.scale.lowerBound, 0.0001)
            let x = { (v: Double) in CGFloat((v - row.scale.lowerBound) / span) * width }
            ZStack(alignment: .leading) {
                Capsule().fill(Color(hex: 0x1A1F29)).frame(height: 8)
                if let good = row.good {
                    Capsule().fill(Color.mobility.opacity(0.35)).frame(width: max(x(good.upperBound) - x(good.lowerBound), 4), height: 8)
                        .offset(x: x(good.lowerBound))
                }
                if let usual = row.usual {
                    RoundedRectangle(cornerRadius: 1).fill(Color.inkSoft).frame(width: 2, height: 16).offset(x: x(usual) - 1)
                }
                Circle().fill(tint).frame(width: 16, height: 16).overlay(Circle().stroke(Color.card, lineWidth: 3))
                    .offset(x: min(max(x(row.value) - 8, 0), width - 16))
            }
            .frame(height: 16)
        }
    }
}

struct SplitsSheet: View {
    let detail: ActivityDetail

    var body: some View {
        let columns = ActivityDetailFormat.splitColumns(detail)
        let rows = ActivityDetailFormat.splits(detail)
        VStack(spacing: 0) {
            DetailSheetHeader(title: "Splits", subtitle: "\(detail.activity.title) · \(ActivityFormat.longDay(detail.activity.date))")
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    table(columns, rows: rows).padding(.top, 16)
                    let lines = ActivityDetailFormat.splitLines(rows)
                    if !lines.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(Array(lines.enumerated()), id: \.offset) { _, line in StatusLine(tone: line.tone, text: line.text) }
                        }
                        .padding(.top, 16)
                    }
                    Text("GCT ground contact (ms) · VO vertical oscillation (cm) · Step step length (m). Only completed kilometres.")
                        .font(AppFont.body(12)).foregroundStyle(Color.faint).lineSpacing(2)
                        .padding(.top, 16)
                    if let model = ActivityDetailFormat.chartModel(detail, key: "pace") {
                        Text("Pace").font(AppFont.number(22)).foregroundStyle(Color.ink).padding(.top, 32)
                        MetricChart(model: model, height: 140).padding(.top, 16)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 32)
            }
            .scrollIndicators(.hidden)
        }
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.card)
    }

    private func table(_ columns: [ActivityDetailFormat.SplitColumn], rows: [ActivityDetailFormat.SplitRow]) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 6) {
                Text("Km").frame(width: 22, alignment: .leading)
                ForEach(columns, id: \.title) { column in
                    Text(column.title).frame(maxWidth: .infinity, alignment: column.title == "Pace" ? .leading : .trailing)
                }
            }
            .font(AppFont.body(12))
            .foregroundStyle(Color.muted)
            .padding(.bottom, 8)
            ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                Rectangle().fill(Color.cardBorder).frame(height: 1)
                HStack(spacing: 6) {
                    Text("\(row.km)").foregroundStyle(Color.muted).frame(width: 22, alignment: .leading)
                    ForEach(columns, id: \.title) { column in
                        let pace = column.title == "Pace"
                        Text(column.values[safe: index] ?? "–")
                            .foregroundStyle(pace && row.fastest ? Color.bg : column.metric.color)
                            .padding(.horizontal, pace ? 6 : 0)
                            .background(pace && row.fastest ? Metric.pace.color : .clear, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
                            .frame(maxWidth: .infinity, alignment: pace ? .leading : .trailing)
                    }
                }
                .font(AppFont.number(17))
                .frame(height: 40)
            }
        }
    }
}
