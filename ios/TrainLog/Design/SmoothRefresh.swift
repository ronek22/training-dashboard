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
                await action()
                while dragging, !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(50))
                }
            }
    }
}
