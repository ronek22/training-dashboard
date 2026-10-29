import SwiftUI

extension View {
    /// `refreshable` that holds the spinner until the finger lifts. The Mac answers before a long
    /// pull is released, and a refresh that ends mid-drag makes the content snap back on release.
    func smoothRefreshable(action: @escaping @Sendable () async -> Void) -> some View {
        modifier(SmoothRefresh(action: action))
    }
}

private struct SmoothRefresh: ViewModifier {
    let action: @Sendable () async -> Void
    @State private var dragging = false

    func body(content: Content) -> some View {
        content
            .onScrollPhaseChange { _, phase in dragging = phase == .interacting }
            .refreshable {
                // SwiftUI can cancel the refresh task mid-pull (it does on Today), which cut the
                // requests short, flashed the offline note and ended the spinner early. A task of
                // its own isn't cancelled with it, so the reload finishes and the pull eases back.
                await Task { @MainActor in
                    await action()
                    while dragging {
                        try? await Task.sleep(for: .milliseconds(50))
                    }
                }.value
            }
    }
}
