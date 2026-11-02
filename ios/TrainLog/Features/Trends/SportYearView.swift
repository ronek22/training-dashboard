import Charts
import SwiftUI

/// One sport's year, pushed from the Trends year card: months against last year, then month rows.
struct SportYearView: View {
    let row: SportYearRow
    let year: SportYear
    let lastYear: Int
    @State private var selection: String?

    private var color: Color { year.sport.color }
    private var selected: SportYear.Month? {
        selection.flatMap { name in year.months.first { $0.name == name } }
    }
    private var focus: SportYear.Month? { selected ?? year.shown }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Kicker(year.unit == "h" ? "Hours by month" : "Distance by month")
                        Spacer()
                        legend
                    }
                    chart.frame(height: 170)
                    Rectangle().fill(Color.cardBorder).frame(height: 1)
                    footer
                }
                .card()
                monthRows
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .sensoryFeedback(.selection, trigger: selection)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker("\(year.title) · \(String(lastYear + 1))", color: color)
            Text("\(TrendsFormat.total(row.total)) \(year.unit)".uppercased()).font(AppFont.title(44)).foregroundStyle(Color.ink)
            if let comparison = TrendsFormat.comparison(row, year: lastYear) {
                if comparison.pill {
                    Pill(text: comparison.text, color: .mobility).padding(.top, 4)
                } else {
                    Text(comparison.text).font(AppFont.body(13)).foregroundStyle(Color.muted).padding(.top, 4)
                }
            }
        }
        .padding(.horizontal, 4)
    }

    private var hasLastYear: Bool { row.lastYearMonths.contains { $0 > 0 } }

    @ViewBuilder
    private var legend: some View {
        if hasLastYear {
            HStack(spacing: 10) {
                HStack(spacing: 5) { Circle().fill(color).frame(width: 6, height: 6); Text(String(lastYear + 1)) }
                HStack(spacing: 5) {
                    RoundedRectangle(cornerRadius: 2).fill(Color.inkSoft.opacity(0.22)).frame(width: 10, height: 10)
                    Text(String(lastYear))
                }
            }
            .font(AppFont.body(11))
            .foregroundStyle(Color.inkSoft)
        }
    }

    private func lastYearValue(_ index: Int) -> Double {
        row.lastYearMonths.indices.contains(index - 1) ? row.lastYearMonths[index - 1] : 0
    }

    private var chart: some View {
        Chart {
            // Last year as wide faint bars behind, this year narrower on top (ranges, so they don't stack).
            ForEach(Array(TrendsFormat.monthNames.enumerated()), id: \.offset) { offset, name in
                let value = lastYearValue(offset + 1)
                if value > 0 {
                    BarMark(x: .value("Month", name), yStart: .value("Start", 0), yEnd: .value("Last year", value), width: .ratio(0.86))
                        .foregroundStyle(Color.inkSoft.opacity(0.18))
                        .cornerRadius(3)
                }
            }
            ForEach(year.months) { month in
                BarMark(x: .value("Month", month.name), yStart: .value("Start", 0), yEnd: .value("Volume", month.value), width: .ratio(0.56))
                    .foregroundStyle(color.opacity(highlighted(month) ? 1 : 0.55))
                    .cornerRadius(3)
                    .annotation(position: .top, spacing: 3) {
                        if labelled(month), month.value > 0 {
                            Text(year.unit == "h" ? month.value.formatted(ActivityFormat.oneDecimal) : "\(Int(month.value.rounded()))")
                                .font(AppFont.number(11, weight: .semibold))
                                .foregroundStyle(Color.ink)
                        }
                    }
            }
            if let selected {
                RuleMark(x: .value("Month", selected.name))
                    .foregroundStyle(color.opacity(0.5))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 3]))
            }
        }
        .chartXScale(domain: TrendsFormat.monthNames)
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: TrendsFormat.monthNames) { value in
                AxisValueLabel {
                    if let name = value.as(String.self) {
                        let isCurrent = name == year.current?.name
                        let past = year.months.contains { $0.name == name }
                        Text(String(name.prefix(1)))
                            .font(AppFont.body(10, weight: .semibold))
                            .foregroundStyle(isCurrent ? Color.volt : past ? Color.muted : Color.dim)
                    }
                }
            }
        }
        // A tap keeps the month; tap it again to clear.
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle().fill(.clear).contentShape(Rectangle())
                    .onTapGesture { location in
                        let x = location.x - (proxy.plotFrame.map { geometry[$0].origin.x } ?? 0)
                        guard let name: String = proxy.value(atX: x), year.months.contains(where: { $0.name == name }) else { return }
                        selection = selection == name ? nil : name
                    }
            }
        }
    }

    private func highlighted(_ month: SportYear.Month) -> Bool {
        if let selected { return selected.index == month.index }
        return month.index == year.shown?.index || month.index == year.best?.index
    }

    private func labelled(_ month: SportYear.Month) -> Bool {
        [focus?.index, year.best?.index].contains(month.index)
    }

    private var sessionWord: String {
        switch year.sport {
        case .ride: "rides"
        case .run: "runs"
        default: "sessions"
        }
    }

    private var footer: some View {
        HStack(alignment: .top) {
            if let month = focus {
                let detail = year.unit == "km"
                    ? "\(TrendsFormat.monthValue(month.hours, unit: "h")) · \(month.sessions) \(sessionWord)"
                    : "\(month.sessions) \(sessionWord)"
                stat(month.index == year.current?.index ? "\(month.name) so far" : month.name,
                     TrendsFormat.monthValue(month.value, unit: year.unit), detail)
            }
            if let best = year.best {
                stat("Best month", "\(best.name) · \(TrendsFormat.monthValue(best.value, unit: year.unit))", nil)
            }
            if let focus, focus.index > 0 {
                stat("Monthly avg", TrendsFormat.monthValue(focus.cumulative / Double(focus.index), unit: year.unit),
                     "Jan – \(focus.name)")
            }
        }
    }

    private func stat(_ label: String, _ value: String, _ detail: String?) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
            Text(value).font(AppFont.number(20)).foregroundStyle(Color.ink).lineLimit(1).minimumScaleFactor(0.7)
            if let detail {
                Text(detail).font(AppFont.body(11)).foregroundStyle(Color.muted).lineLimit(1).minimumScaleFactor(0.8)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Newest month first, from the one the footer shows back to January.
    private var monthRows: some View {
        let months = year.months.filter { $0.index <= (year.shown?.index ?? 12) }.reversed()
        return VStack(spacing: 0) {
            ForEach(Array(months.enumerated()), id: \.element.id) { offset, month in
                if offset > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                HStack(spacing: 12) {
                    Text(month.name).font(AppFont.body(14, weight: .medium)).foregroundStyle(Color.ink).frame(width: 38, alignment: .leading)
                    if hasLastYear {
                        Text("\(TrendsFormat.monthValue(lastYearValue(month.index), unit: year.unit)) in \(String(lastYear))")
                            .font(AppFont.body(12))
                            .foregroundStyle(Color.muted)
                    } else {
                        Text("\(month.sessions) \(sessionWord)").font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                    Spacer()
                    Text(TrendsFormat.monthValue(month.value, unit: year.unit)).font(AppFont.number(17)).foregroundStyle(Color.ink)
                }
                .frame(minHeight: 44)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
    }
}
