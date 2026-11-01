import SwiftUI

/// The Watch's part in a workout shown on the phone, for a screen's top bar: live heart rate once
/// it's recording, Joining while TrainLog starts on the Watch, Retry when it didn't.
struct WatchChip: View {
    let watch: WatchLive

    var body: some View {
        TimelineView(.periodic(from: .now, by: 5)) { context in
            if let bpm = watch.liveHeartRate(at: context.date) {
                Label("\(Int(bpm.rounded()))", systemImage: "heart.fill")
                    .font(AppFont.number(17))
                    .foregroundStyle(Color(hex: 0xFF5A5F))
                    .accessibilityLabel("Heart rate \(Int(bpm.rounded())) from Apple Watch")
            } else if watch.join == .joining || watch.linked {
                badge("Joining", color: .ride)
                    .accessibilityLabel("Starting on Apple Watch")
            } else if watch.join == .failed {
                Button(action: watch.retry) {
                    badge("Watch · Retry", color: .muted)
                }
                .buttonStyle(.plain)
                .frame(minHeight: 44)
                .accessibilityLabel("Apple Watch didn't start. Retry")
            }
        }
    }

    private func badge(_ text: String, color: Color) -> some View {
        Label(text.uppercased(), systemImage: "applewatch")
            .font(AppFont.body(11, weight: .bold))
            .tracking(1.1)
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .frame(height: 26)
            .background(color.opacity(0.14), in: Capsule())
    }
}

/// Before Start, on the strength brief and the rehab intro: whether the Watch is woken and linked,
/// so Start on either device starts both.
struct WatchReadyRow: View {
    let watch: WatchLive

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            if watch.ready(at: context.date) {
                row("Watch ready", "Start here or on the Watch: both start together.", color: .mobility,
                    heartRate: watch.liveHeartRate(at: context.date))
            } else if watch.join == .joining {
                let waiting = watch.joiningSince.map { context.date.timeIntervalSince($0) } ?? 0
                if waiting < 10 {
                    row("Waking your Watch…", "TrainLog opens on it to record heart rate.", color: .ride)
                } else {
                    row("Still waking…", "Raise your wrist or tap the Watch so it can link up.", color: .ride)
                }
            } else if watch.join == .failed {
                Button(action: watch.retry) {
                    row("Watch didn't answer · Retry", "Start works without it, just no heart rate.", color: .muted)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func row(_ title: String, _ detail: String, color: Color, heartRate: Double? = nil) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "applewatch")
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(color)
                .frame(width: 28)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                Text(detail).font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
            Spacer(minLength: 0)
            if let heartRate {
                Label("\(Int(heartRate.rounded()))", systemImage: "heart.fill")
                    .font(AppFont.number(20))
                    .foregroundStyle(Color(hex: 0xFF5A5F))
                    .accessibilityLabel("Heart rate \(Int(heartRate.rounded())) from Apple Watch")
            }
        }
        .card(border: color.opacity(0.35))
    }
}
