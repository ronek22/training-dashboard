import SwiftUI

/// Frame 01: what's planned today. One tap starts the session and the HealthKit workout together.
struct StartView: View {
    @Bindable var model: StartModel
    let onStrength: (StrengthSession) -> Void
    let onRehab: (GuidedSession) -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 6) {
                switch model.phase {
                case .loading:
                    ProgressView().tint(.volt).frame(maxWidth: .infinity, minHeight: 120)
                case .failed(let message):
                    unreachable(message)
                case .ready:
                    content
                }
            }
        }
        .navigationTitle {
            Text(dayLabel).foregroundStyle(Color.volt)
        }
        .task { await model.load() }
        // Out of reach at launch: load as soon as the phone turns up.
        .onChange(of: PhoneLink.shared.reachable) { _, reachable in
            if reachable, model.phase != .ready || model.stale { Task { await model.load() } }
        }
        .refreshable { await model.load() }
        .alert("Couldn't start", isPresented: Binding(get: { model.startError != nil }, set: { if !$0 { model.startError = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(model.startError ?? "")
        }
    }

    @ViewBuilder
    private var content: some View {
        if let active = model.active {
            strengthCard(
                kicker: "Running now", title: active.templateName,
                detail: "\(WatchStrength.totals(active).setsDone)/\(WatchStrength.totals(active).setsTotal) sets done",
                action: "Resume"
            )
        } else if let strength = model.strength, !model.strengthDone {
            strengthCard(
                kicker: strength.templateId == nil ? "Bodyweight · today" : "Strength · today",
                title: strength.name ?? "Strength",
                detail: detail(strength),
                action: "Start"
            )
        }
        if let rehab = model.rehab {
            row(title: rehab.title, detail: "\(rehab.exercises.count) ex · \(rehab.durationMin) min", color: .mobility) {
                onRehab(rehab)
            }
        }
        if let strength = model.strength, model.strengthDone, model.active == nil {
            row(title: strength.name ?? "Strength", detail: "Done today", color: .strength) {}
                .disabled(true)
                .opacity(0.5)
        }
        if model.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                WatchTitle("Rest day", size: 22)
                Text("Nothing to lift today. Plan a session on the web.")
                    .font(WatchFont.body(12))
                    .foregroundStyle(Color.muted)
            }
            .padding(.top, 8)
        }
        if model.stale {
            Text("Last synced copy · phone or server out of reach")
                .font(WatchFont.body(10))
                .foregroundStyle(Color.muted)
                .padding(.top, 2)
        }
    }

    private func strengthCard(kicker: String, title: String, detail: String, action: String) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 5) {
                Circle().fill(Color.strength).frame(width: 6, height: 6)
                WatchKicker(kicker, color: .strengthSoft)
            }
            WatchTitle(title, size: 22).padding(.top, 4)
            Text(detail)
                .font(WatchFont.body(11))
                .foregroundStyle(Color.muted)
                .lineLimit(1)
                .padding(.top, 3)
            Button {
                Task {
                    if let session = await model.startStrength() { onStrength(session) }
                }
            } label: {
                if model.starting { ProgressView().tint(.black) } else { Text(action) }
            }
            .buttonStyle(VoltButtonStyle(height: 34))
            .padding(.top, 8)
        }
        .padding(10)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.cardBorder))
    }

    private func row(title: String, detail: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Circle().fill(color).frame(width: 6, height: 6)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title).font(WatchFont.body(13, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                    Text(detail).font(WatchFont.body(10)).foregroundStyle(Color.muted)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold)).foregroundStyle(Color.faint)
            }
            .padding(.horizontal, 10)
            .frame(minHeight: 44)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.cardBorder))
        }
        .buttonStyle(.plain)
    }

    private func unreachable(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: "iphone.slash").font(.system(size: 24)).foregroundStyle(Color.muted)
            Text(message).font(WatchFont.body(12)).foregroundStyle(Color.ink)
            Button("Try again") { Task { await model.load() } }
                .buttonStyle(DarkButtonStyle())
        }
        .padding(.top, 8)
    }

    private func detail(_ strength: WatchToday.Strength) -> String {
        var parts = ["\(strength.exercises.count) ex"]
        if let minutes = model.durationMin { parts.append("~\(minutes) min") }
        return parts.joined(separator: " · ")
    }

    /// "Thu 31" from today's date.
    private var dayLabel: String {
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        let date = model.date.flatMap { parser.date(from: $0) } ?? .now
        return date.formatted(.dateTime.weekday(.abbreviated).day())
    }
}
