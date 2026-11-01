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
        if watch.linked {
            row("Watch ready", "Start here or on the Watch: both start together.", color: .mobility)
        } else if watch.join == .joining {
            row("Waking your Watch…", "TrainLog opens on it to record heart rate.", color: .ride)
        } else if watch.join == .failed {
            Button(action: watch.retry) {
                row("Watch didn't answer · Retry", "Start works without it, just no heart rate.", color: .muted)
            }
            .buttonStyle(.plain)
        }
    }

    private func row(_ title: String, _ detail: String, color: Color) -> some View {
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
        }
        .card(border: color.opacity(0.35))
    }
}
