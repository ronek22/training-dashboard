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
