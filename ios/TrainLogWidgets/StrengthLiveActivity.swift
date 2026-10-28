import ActivityKit
import SwiftUI
import WidgetKit

/// The rest timer on the Lock Screen and in the Dynamic Island (artboard frame 7). Timers count
/// on their own; when the rest runs out the activity goes stale and flips to "Rest done · go".
struct StrengthLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: StrengthActivityAttributes.self) { context in
            StrengthLockView(context: context)
                .activityBackgroundTint(Color.card.opacity(0.92))
                .activitySystemActionForegroundColor(.volt)
                .widgetURL(URL(string: "trainlog://strength"))
        } dynamicIsland: { context in
            let phase = RestPhase(context)
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Label {
                        Text(context.attributes.workout).lineLimit(1)
                    } icon: {
                        Image(systemName: "dumbbell.fill").foregroundStyle(Color.strength)
                    }
                    .font(AppFont.body(13, weight: .semibold))
                    .foregroundStyle(Color.inkSoft)
                    .padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text("\(context.state.exerciseNumber) of \(context.state.exerciseCount)")
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.muted)
                        .padding(.trailing, 4)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 10) {
                        HStack(alignment: .bottom) {
                            NextUp(state: context.state, phase: phase)
                            Spacer(minLength: 8)
                            BigTimer(state: context.state, phase: phase, size: 44)
                        }
                        ActivityBar(state: context.state, phase: phase)
                    }
                    .padding(.horizontal, 4)
                }
            } compactLeading: {
                HStack(spacing: 5) {
                    Image(systemName: "dumbbell.fill").foregroundStyle(Color.strength)
                    Text(context.state.allSetsDone ? "Done" : context.state.setLabel)
                        .foregroundStyle(Color(hex: 0xFF7AB5))
                }
                .font(AppFont.body(12, weight: .semibold))
                .padding(.leading, 2)
            } compactTrailing: {
                switch phase {
                case .resting(let range):
                    Text(timerInterval: range, countsDown: true)
                        .font(AppFont.number(17))
                        .foregroundStyle(Color.volt)
                        .monospacedDigit()
                        .multilineTextAlignment(.trailing)
                        .frame(width: 42, alignment: .trailing)
                case .restDone:
                    Text("GO").font(AppFont.number(17)).foregroundStyle(Color.volt)
                case .working:
                    Image(systemName: context.state.allSetsDone ? "checkmark" : "play.fill")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(Color.volt)
                }
            } minimal: {
                switch phase {
                case .resting(let range):
                    ProgressView(timerInterval: range, countsDown: true) {
                        EmptyView()
                    } currentValueLabel: {
                        Image(systemName: "dumbbell.fill").font(.system(size: 9)).foregroundStyle(Color.strength)
                    }
                    .progressViewStyle(.circular)
                    .tint(.volt)
                default:
                    Image(systemName: "dumbbell.fill").foregroundStyle(Color.strength)
                }
            }
            .widgetURL(URL(string: "trainlog://strength"))
            .keylineTint(.strength)
        }
    }
}

enum RestPhase {
    case resting(ClosedRange<Date>)
    case restDone
    case working

    init(_ context: ActivityViewContext<StrengthActivityAttributes>) {
        guard let range = context.state.restRange, !context.state.allSetsDone else {
            self = .working
            return
        }
        self = context.isStale || range.upperBound <= .now ? .restDone : .resting(range)
    }
}

private struct StrengthLockView: View {
    let context: ActivityViewContext<StrengthActivityAttributes>

    var body: some View {
        let phase = RestPhase(context)
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Image(systemName: "waveform.path.ecg")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color.bg)
                    .frame(width: 26, height: 26)
                    .background(Color.volt, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                Text("\(context.attributes.workout) · \(context.state.exerciseNumber) of \(context.state.exerciseCount)")
                    .font(AppFont.body(13, weight: .semibold))
                    .foregroundStyle(Color.inkSoft)
                    .lineLimit(1)
                Spacer(minLength: 8)
                Text(timerInterval: context.attributes.startedAt...Date.distantFuture, countsDown: false)
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .monospacedDigit()
                    .multilineTextAlignment(.trailing)
                    .frame(width: 64, alignment: .trailing)
            }
            HStack(alignment: .bottom) {
                NextUp(state: context.state, phase: phase)
                Spacer(minLength: 8)
                BigTimer(state: context.state, phase: phase, size: 52)
            }
            .padding(.top, 12)
            ActivityBar(state: context.state, phase: phase)
                .padding(.top, 12)
        }
        .padding(16)
    }
}

private struct NextUp: View {
    let state: StrengthActivityAttributes.ContentState
    let phase: RestPhase

    private var kicker: String {
        if state.allSetsDone { return "All sets done" }
        switch phase {
        case .resting: return "Rest · next up"
        case .restDone: return "Rest done · go"
        case .working: return "Up next"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker(kicker, color: phase.isRestDone ? .volt : .muted)
            Text(state.allSetsDone ? "Finish the workout" : "\(state.exercise) · \(state.setLabel.lowercased())")
                .font(AppFont.body(19, weight: .bold))
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .padding(.top, 4)
            Text(state.allSetsDone ? "\(state.setsTotal) sets logged" : state.load)
                .font(AppFont.body(13))
                .foregroundStyle(Color.muted)
                .padding(.top, 2)
        }
    }
}

private struct BigTimer: View {
    let state: StrengthActivityAttributes.ContentState
    let phase: RestPhase
    let size: CGFloat

    var body: some View {
        switch phase {
        case .resting(let range):
            Text(timerInterval: range, countsDown: true)
                .font(AppFont.number(size))
                .foregroundStyle(Color.volt)
                .monospacedDigit()
                .multilineTextAlignment(.trailing)
                .frame(width: size * 2, alignment: .trailing)
        case .restDone:
            Text("GO").font(AppFont.title(size * 0.85)).foregroundStyle(Color.volt)
        case .working:
            Image(systemName: state.allSetsDone ? "checkmark.circle.fill" : "figure.strengthtraining.traditional")
                .font(.system(size: size * 0.6, weight: .semibold))
                .foregroundStyle(state.allSetsDone ? Color.volt : Color.strength)
        }
    }
}

/// Rest elapsed while resting, otherwise the workout's sets done.
private struct ActivityBar: View {
    let state: StrengthActivityAttributes.ContentState
    let phase: RestPhase

    var body: some View {
        if case .resting(let range) = phase {
            ProgressView(timerInterval: range, countsDown: false) {
                EmptyView()
            } currentValueLabel: {
                EmptyView()
            }
            .progressViewStyle(.linear)
            .tint(.volt)
        } else {
            LinearBar(
                share: state.setsTotal > 0 ? Double(state.setsDone) / Double(state.setsTotal) : 0,
                fill: .strength, track: .track, height: 4
            )
        }
    }
}

private extension RestPhase {
    var isRestDone: Bool {
        if case .restDone = self { true } else { false }
    }
}

#Preview("Lock screen", as: .content, using: StrengthActivityAttributes(sessionId: 1, workout: "Workout B", startedAt: .now.addingTimeInterval(-1450))) {
    StrengthLiveActivity()
} contentStates: {
    StrengthActivityAttributes.ContentState(
        exercise: "DB Row", setLabel: "Set 3", load: "34 kg × 10", exerciseNumber: 2, exerciseCount: 5,
        setsDone: 5, setsTotal: 15, restStart: .now.addingTimeInterval(-18), restEnd: .now.addingTimeInterval(72), allSetsDone: false
    )
}
