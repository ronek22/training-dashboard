import SwiftUI

// Screen chrome shared by the tabs and sheets: the big header, offline and sync notes, the
// grabber for custom sheets. Keep these the only copies so the tabs line up when you switch.

/// Kicker over a 44pt italic title, with optional actions on the right, bottom-aligned. In a
/// List put it in a `plainRow(top: 0)` so it sits at the same height as on ScrollView screens.
struct ScreenHeader<Trailing: View>: View {
    let kicker: String
    let title: String
    @ViewBuilder var trailing: Trailing

    init(kicker: String, title: String, @ViewBuilder trailing: () -> Trailing = { EmptyView() }) {
        self.kicker = kicker
        self.title = title
        self.trailing = trailing()
    }

    var body: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(kicker)
                Text(title.uppercased()).font(AppFont.title(44)).foregroundStyle(Color.ink)
                    .contentTransition(.opacity)
            }
            Spacer()
            trailing
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }
}

/// Shown above the content when the screen is drawing cached data.
struct OfflineNote: View {
    let syncedAt: Date

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "wifi.slash").font(.system(size: 11, weight: .semibold))
            Text("Offline · last synced \(Self.when(syncedAt))")
                .font(AppFont.body(12, weight: .medium))
        }
        .foregroundStyle(Color.muted)
        .padding(.horizontal, 4)
    }

    /// Time only for today, date and time for anything older.
    static func when(_ date: Date) -> String {
        Calendar.current.isDateInToday(date)
            ? date.formatted(date: .omitted, time: .shortened)
            : date.formatted(date: .abbreviated, time: .shortened)
    }
}

/// The card a screen shows when it has nothing to draw: no data yet, or the server is down.
struct SyncStateCard: View {
    let kicker: String
    let message: String
    var hint: String = SyncStateCard.serverHint

    static let serverHint = "Start the backend on the Mac (docker compose up) and pull to refresh."

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(kicker)
            Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Text(hint).font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .card()
    }
}

/// First load with nothing cached: card-shaped placeholders that breathe, in roughly the
/// screen's layout, instead of a spinner on an empty page.
struct LoadingCards: View {
    /// Height of each placeholder card's body block, top to bottom.
    var blocks: [CGFloat] = [120, 80, 160]

    var body: some View {
        VStack(spacing: 12) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, height in
                VStack(alignment: .leading, spacing: 10) {
                    Skeleton(width: 90, height: 10)
                    Skeleton(width: 170, height: 22)
                    Skeleton(height: height, radius: Radius.control)
                }
                .card()
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Loading")
    }
}

/// Drag handle for sheets that draw their own top (the system indicator is hidden there).
struct SheetGrabber: View {
    var body: some View {
        Capsule().fill(Color(hex: 0x3A404C)).frame(width: 36, height: 5)
            .frame(maxWidth: .infinity)
            .padding(.bottom, 12)
    }
}

/// Round outline icon button for screen headers, 36pt visible inside a 44pt target.
struct HeaderIconButton<Icon: View>: View {
    var enabled = true
    let label: String
    let action: () -> Void
    @ViewBuilder var icon: Icon

    var body: some View {
        Button(action: action) {
            icon
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(enabled ? Color.ink : Color.dim)
                .frame(width: 36, height: 36)
                .overlay(Circle().strokeBorder(enabled ? Color.outline : Color.cardBorder))
                .frame(width: 44, height: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
    }
}

extension View {
    /// A List row with no card behind it (headers, chips, notes).
    func plainRow(top: CGFloat = 4) -> some View {
        listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
            .listRowInsets(EdgeInsets(top: top, leading: 0, bottom: 4, trailing: 0))
    }
}
