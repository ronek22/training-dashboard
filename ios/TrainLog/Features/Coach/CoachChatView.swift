import SwiftUI

/// A coach chat. Opened as a sheet from an activity, a plan day or a plan week (tied to it), or
/// pushed from the coach list on Today.
struct CoachChatView: View {
    @State private var model: CoachChatModel
    /// Pushed inside the coach list: the leading button goes back instead of closing.
    var pushed = false
    @FocusState private var composing: Bool
    @Environment(\.dismiss) private var dismiss

    init(context: CoachContext? = nil, conversation: CoachConversation? = nil, pushed: Bool = false) {
        _model = State(initialValue: CoachChatModel(context: context, conversation: conversation))
        self.pushed = pushed
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            messages
            composer
        }
        .background(Color.bg)
        .toolbar(.hidden, for: .navigationBar)
        .task { await model.load() }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Button {
                dismiss()
            } label: {
                if pushed {
                    Image(systemName: "chevron.left").font(.system(size: 17, weight: .semibold))
                } else {
                    Text("Done").font(AppFont.body(16, weight: .semibold))
                }
            }
            .foregroundStyle(Color.inkSoft)
            .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            VStack(spacing: 2) {
                Kicker(CoachFormat.kicker(model.context, conversation: model.conversation), color: CoachFormat.color(model.context?.kind ?? model.conversation.flatMap(CoachFormat.kind)))
                Text(model.title)
                    .font(AppFont.body(15, weight: .bold))
                    .foregroundStyle(Color.ink)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            Color.clear.frame(width: 52, height: 44)
        }
        .padding(.horizontal, Space.gutter)
        .padding(.top, 8)
        .padding(.bottom, 6)
        .overlay(alignment: .bottom) { Rectangle().fill(Color.cardBorder).frame(height: 1) }
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if model.messages.isEmpty && model.sent == nil {
                        empty
                    }
                    ForEach(model.messages) { message in
                        bubble(message.content, fromCoach: message.fromCoach).id(message.id)
                    }
                    if let sent = model.sent, model.messages.last?.content != sent {
                        bubble(sent, fromCoach: false)
                    }
                    if let since = model.thinkingSince {
                        ThinkingRow(since: since, status: model.status)
                    }
                    if let error = model.error {
                        StatusLine(tone: .warn, text: error)
                    }
                    Color.clear.frame(height: 1).id("end")
                }
                .padding(Space.gutter)
            }
            .scrollDismissesKeyboard(.interactively)
            .scrollIndicators(.hidden)
            .defaultScrollAnchor(.bottom)
            .onChange(of: model.messages.count) { scrollToEnd(proxy) }
            .onChange(of: model.thinking) { scrollToEnd(proxy) }
            .onChange(of: composing) { if composing { scrollToEnd(proxy) } }
        }
    }

    private func scrollToEnd(_ proxy: ScrollViewProxy) {
        withAnimation(Motion.fade) { proxy.scrollTo("end", anchor: .bottom) }
    }

    @ViewBuilder
    private var empty: some View {
        if !model.loaded {
            ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 200)
        } else {
            VStack(alignment: .leading, spacing: 10) {
                Text(CoachFormat.intro(model.context))
                    .font(AppFont.body(14))
                    .foregroundStyle(Color.muted)
                    .padding(.bottom, 4)
                ForEach(model.suggestions, id: \.self) { suggestion in
                    Button {
                        model.draft = suggestion
                        Task { await model.send() }
                    } label: {
                        HStack {
                            Text(suggestion).font(AppFont.body(14, weight: .medium)).foregroundStyle(Color.ink)
                            Spacer()
                            Image(systemName: "arrow.up.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Color.muted)
                        }
                        .padding(.horizontal, 14)
                        .frame(minHeight: 44)
                        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous).strokeBorder(Color.cardBorder))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.top, 8)
        }
    }

    @ViewBuilder
    private func bubble(_ text: String, fromCoach: Bool) -> some View {
        if fromCoach {
            VStack(alignment: .leading, spacing: 6) {
                Kicker("Coach", color: .volt)
                CoachMarkdown(text: text)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .textSelection(.enabled)
        } else {
            Text(text)
                .font(AppFont.body(15))
                .foregroundStyle(Color.ink)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color.raised, in: RoundedRectangle(cornerRadius: Radius.panel, style: .continuous))
                .frame(maxWidth: 300, alignment: .trailing)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .textSelection(.enabled)
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField("Ask the coach", text: $model.draft, axis: .vertical)
                .font(AppFont.body(15))
                .foregroundStyle(Color.ink)
                .lineLimit(1...5)
                .focused($composing)
                .padding(.horizontal, 14)
                .padding(.vertical, 11)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
            Button {
                Task { await model.send() }
            } label: {
                Image(systemName: "arrow.up")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(model.canSend ? Color.bg : Color.dim)
                    .frame(width: 44, height: 44)
                    .background(model.canSend ? Color.volt : Color.raised, in: Circle())
            }
            .buttonStyle(.plain)
            .disabled(!model.canSend)
            .accessibilityLabel("Send")
        }
        .padding(.horizontal, Space.gutter)
        .padding(.top, 8)
        .padding(.bottom, 8)
        .background(Color.bg)
    }
}

/// "Coach is reading your training" with the seconds it's been at it: replies take a minute or two.
private struct ThinkingRow: View {
    let since: Date
    let status: String?

    var body: some View {
        TimelineView(.periodic(from: since, by: 1)) { context in
            let seconds = max(0, Int(context.date.timeIntervalSince(since)))
            VStack(alignment: .leading, spacing: 6) {
                Kicker("Coach", color: .volt)
                HStack(spacing: 8) {
                    HStack(spacing: 4) {
                        ForEach(0..<3) { dot in
                            Circle().fill(Color.volt)
                                .frame(width: 6, height: 6)
                                .opacity(seconds % 3 == dot ? 1 : 0.3)
                        }
                    }
                    .animation(.easeInOut(duration: 0.3), value: seconds)
                    Text(status ?? "Reading your training…")
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.muted)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    Text(CoachFormat.elapsed(seconds))
                        .font(AppFont.number(14, weight: .semibold))
                        .foregroundStyle(Color.faint)
                        .monospacedDigit()
                }
            }
        }
    }
}

/// Coach replies are Markdown: paragraphs, bullet and numbered lists, headings and inline bold.
struct CoachMarkdown: View {
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(CoachFormat.blocks(text).enumerated()), id: \.offset) { _, block in
                switch block {
                case .heading(let line):
                    Text(CoachFormat.inline(line))
                        .font(AppFont.body(15, weight: .bold))
                        .foregroundStyle(Color.ink)
                        .padding(.top, 4)
                case .bullet(let marker, let line):
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(marker)
                            .font(AppFont.body(15, weight: .semibold))
                            .foregroundStyle(Color.muted)
                            .frame(minWidth: 14, alignment: .leading)
                        Text(CoachFormat.inline(line))
                            .font(AppFont.body(15))
                            .foregroundStyle(Color.ink)
                            .lineSpacing(3)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                case .paragraph(let line):
                    Text(CoachFormat.inline(line))
                        .font(AppFont.body(15))
                        .foregroundStyle(Color.ink)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .tint(.volt)
    }
}
