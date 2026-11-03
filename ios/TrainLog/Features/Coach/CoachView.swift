import SwiftUI

/// The Coach tab: ask about today, start a general chat, or pick up a recent one
/// (the same chats as the web Coach page).
struct CoachView: View {
    @State private var conversations: [CoachConversation] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var route: Route?

    enum Route: Hashable {
        case context(CoachContext)
        case conversation(CoachConversation)
        case new
    }

    private static let path = "/notes/chat/conversations"

    var body: some View {
        NavigationStack {
            List {
                header.plainRow(top: 0)
                Section {
                    startRow(symbol: CoachFormat.symbol(.day), color: CoachFormat.color(.day),
                             title: "Ask about today", detail: "Plan, check-in and recovery") {
                        route = .context(CoachFormat.dayContext(FoodFormat.iso(.now)))
                    }
                    startRow(symbol: "square.and.pencil", color: .inkSoft,
                             title: "New chat", detail: "Anything about your training") {
                        route = .new
                    }
                }
                Section {
                    if conversations.isEmpty {
                        Text(loaded ? (error ?? "No chats yet.") : "Loading…")
                            .font(AppFont.body(13))
                            .foregroundStyle(Color.muted)
                            .listRowBackground(Color.card)
                    }
                    ForEach(conversations.prefix(30)) { conversation in
                        row(conversation)
                    }
                } header: {
                    Kicker("Recent").padding(.leading, -16)
                }
            }
            .listStyle(.insetGrouped)
            .listSectionSpacing(12)
            .scrollContentBackground(.hidden)
            .scrollIndicators(.hidden)
            .contentMargins(.horizontal, 16, for: .scrollContent)
            .contentMargins(.top, 0, for: .scrollContent)
            .background(Color.bg)
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(item: $route) { route in
                switch route {
                case .context(let context): CoachChatView(context: context, pushed: true).hidesTabBar()
                case .conversation(let conversation): CoachChatView(conversation: conversation, pushed: true).hidesTabBar()
                case .new: CoachChatView(pushed: true).hidesTabBar()
                }
            }
            .task(id: route == nil) {
                if route == nil { await load() }
            }
            .refreshable { await load() }
        }
        .tint(.volt)
    }

    private func load() async {
        let api = APIClient.current
        if conversations.isEmpty, let cached = api.cached(Self.path, as: [CoachConversation].self) {
            conversations = cached.value
        }
        do {
            conversations = try await api.get(Self.path, as: [CoachConversation].self).value
            error = nil
        } catch {
            if conversations.isEmpty { self.error = CoachChatModel.message(for: error) }
        }
        loaded = true
    }

    private func delete(_ conversation: CoachConversation) {
        withAnimation { conversations.removeAll { $0.id == conversation.id } }
        Task {
            _ = try? await APIClient.current.send("DELETE", "/notes/chat/conversations/\(conversation.id)")
        }
    }

    private var header: some View {
        ScreenHeader(kicker: "Your coach", title: "Coach")
    }

    private func startRow(symbol: String, color: Color, title: String, detail: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                icon(symbol, color: color)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                    Text(detail).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Color.faint)
            }
            .frame(minHeight: 56)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .listRowBackground(Color.card)
        .listRowSeparatorTint(Color.cardBorder)
    }

    private func row(_ conversation: CoachConversation) -> some View {
        let kind = CoachFormat.kind(conversation)
        let unread = (conversation.unreadCount ?? 0) > 0
        return Button {
            route = .conversation(conversation)
        } label: {
            HStack(spacing: 12) {
                icon(CoachFormat.symbol(kind), color: CoachFormat.color(kind))
                Text(conversation.title)
                    .font(AppFont.body(14, weight: unread ? .bold : .medium))
                    .foregroundStyle(Color.ink)
                    .lineLimit(1)
                Spacer(minLength: 8)
                Text(CoachFormat.updated(conversation.updatedAt))
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                if unread {
                    Circle().fill(Color.volt).frame(width: 8, height: 8).accessibilityLabel("Unread")
                }
            }
            .frame(minHeight: 52)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .listRowBackground(Color.card)
        .listRowSeparatorTint(Color.cardBorder)
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            Button(role: .destructive) {
                delete(conversation)
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
    }

    private func icon(_ symbol: String, color: Color) -> some View {
        Image(systemName: symbol)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(color)
            .frame(width: 32, height: 32)
            .background(color.opacity(0.14), in: Circle())
    }
}

