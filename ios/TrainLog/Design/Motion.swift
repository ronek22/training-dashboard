import SwiftUI

// Shared motion: cards that lift in, numbers that count up, bars that grow. Each runs once,
// the first time its view scrolls into sight, so background refreshes don't replay it and
// cards below the fold wait until you get to them. Use them inside a ScrollView.

/// A number that counts up from zero the first time it appears, then rolls to new values.
struct CountUp: View {
    let value: Double
    var delay: Double = 0
    let format: (Double) -> String
    @State private var shown = 0.0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(value: Double, delay: Double = 0, format: @escaping (Double) -> String) {
        self.value = value
        self.delay = delay
        self.format = format
    }

    var body: some View {
        CountingText(value: shown, format: format)
            .onFirstVisible {
                if reduceMotion { shown = value; return }
                withAnimation(.easeOut(duration: 1.1).delay(delay)) { shown = value }
            }
            .onChange(of: value) { withAnimation(.easeOut(duration: 0.6)) { shown = value } }
            .accessibilityLabel(format(value))
    }
}

private struct CountingText: View, @MainActor Animatable {
    var value: Double
    let format: (Double) -> String

    var animatableData: Double {
        get { value }
        set { value = newValue }
    }

    var body: some View {
        Text(format(value)).monospacedDigit()
    }
}

private struct Reveal: ViewModifier {
    let delay: Double
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown || reduceMotion ? 0 : 18)
            .onFirstVisible(threshold: 0.1) {
                withAnimation(reduceMotion ? .easeOut(duration: 0.2) : .spring(duration: 0.55, bounce: 0.2).delay(delay)) {
                    shown = true
                }
            }
    }
}

/// Starts false and flips to true on appear, inside an animation: drive a bar's width or a
/// ring's trim with it to grow from empty.
private struct Grow<Body: View>: View {
    let delay: Double
    let content: @MainActor (Bool) -> Body
    @State private var grown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        content(grown).onFirstVisible {
            if reduceMotion { grown = true; return }
            withAnimation(.spring(duration: 0.9, bounce: 0.15).delay(delay)) { grown = true }
        }
    }
}

private struct FirstVisible: ViewModifier {
    let threshold: Double
    let action: () -> Void
    @State private var fired = false

    func body(content: Content) -> some View {
        content.onScrollVisibilityChange(threshold: threshold) { visible in
            guard visible, !fired else { return }
            fired = true
            action()
        }
    }
}

/// Whole-card buttons: a slight press-in so the tap feels physical.
struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .opacity(configuration.isPressed ? 0.9 : 1)
            .animation(.snappy(duration: 0.18), value: configuration.isPressed)
    }
}

extension View {
    /// Runs `action` once enough of the view (`threshold`, 0...1) is on screen in its ScrollView.
    func onFirstVisible(threshold: Double = 0.5, _ action: @escaping () -> Void) -> some View {
        modifier(FirstVisible(threshold: threshold, action: action))
    }

    /// Fades and lifts in, `index` steps after the first card.
    func reveal(_ index: Int, base: Double = 0.05) -> some View {
        modifier(Reveal(delay: base + Double(index) * 0.09))
    }
}

/// Grows its content from empty the first time it appears; `grown` is false on the first frame.
@MainActor func growing<Content: View>(delay: Double = 0, @ViewBuilder _ content: @escaping @MainActor (_ grown: Bool) -> Content) -> some View {
    Grow(delay: delay, content: content)
}
