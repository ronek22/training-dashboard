import SwiftUI

/// Pushed from the avatar on Today: server address, Apple Health and reminders.
struct SettingsView: View {
    @State private var model = SettingsModel()
    @State private var sheet: AddressSheet?
    @State private var notificationsDenied = false

    @AppStorage(Reminders.morningEnabledKey) private var morningOn = false
    @AppStorage(Reminders.morningMinutesKey) private var morningMinutes = Reminders.defaultMorningMinutes
    @AppStorage(Reminders.dinnerEnabledKey) private var dinnerOn = false

    enum AddressSheet: String, Identifiable {
        case find, manual
        var id: String { rawValue }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("SETTINGS")
                    .font(AppFont.title(40))
                    .foregroundStyle(Color.ink)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 6)
                server
                health
                reminders
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.bg, for: .navigationBar)
        .refreshable { await model.check() }
        .task { await model.check() }
        .sheet(item: $sheet) { kind in
            Group {
                switch kind {
                case .find: FindServerSheet(current: model.baseURL) { url in await model.use(url) }
                case .manual: ManualAddressSheet(current: model.baseURL) { url in await model.use(url) }
                }
            }
            .presentationDetents([.medium, .large])
            .presentationBackground(Color(hex: 0x161A22))
        }
        .onChange(of: morningOn) { reschedule(turnedOn: morningOn) { morningOn = false } }
        .onChange(of: dinnerOn) { reschedule(turnedOn: dinnerOn) { dinnerOn = false } }
        .onChange(of: morningMinutes) { Task { await Reminders.apply() } }
    }

    // MARK: Server

    private var server: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker("Server").padding(.horizontal, 4)
            SettingsCard {
                Button {
                    Task { await model.check() }
                } label: {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(ServerAddress.displayName(model.baseURL))
                                .font(AppFont.body(15, weight: .semibold))
                                .foregroundStyle(Color.ink)
                            Text(model.baseURL)
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(Color.muted)
                                .lineLimit(1)
                                .truncationMode(.middle)
                        }
                        Spacer(minLength: 0)
                        StatusPill(status: model.status)
                    }
                    .settingsRow()
                }
                .buttonStyle(.plain)
                .accessibilityHint("Checks the connection again")
                Divider().overlay(Color.cardBorder)
                navRow("Find on this Wi-Fi", detail: "Bonjour") { sheet = .find }
                Divider().overlay(Color.cardBorder)
                navRow("Enter address manually") { sheet = .manual }
            }
            footnote("Works on home Wi-Fi only for now. Away from home the app shows the last synced data read-only and queues new logs until it's back.")
        }
    }

    // MARK: Apple Health

    private var health: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker("Apple Health").padding(.horizontal, 4).padding(.top, 6)
            SettingsCard {
                comingSoonRow("Read sleep, resting HR, HRV")
                Divider().overlay(Color.cardBorder)
                comingSoonRow("Save strength sessions as workouts")
                Divider().overlay(Color.cardBorder)
                comingSoonRow("Read body weight")
            }
            footnote("Coming with the HealthKit build. Until then sleep and HRV reach TrainLog through the Mac's Health import.")
        }
    }

    private func comingSoonRow(_ title: String) -> some View {
        Toggle(isOn: .constant(false)) {
            Text(title).font(AppFont.body(15)).foregroundStyle(Color.faint)
        }
        .tint(Color.mobility)
        .disabled(true)
        .settingsRow()
    }

    // MARK: Reminders

    private var reminders: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker("Reminders").padding(.horizontal, 4).padding(.top, 6)
            SettingsCard {
                Toggle(isOn: $morningOn) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Morning check-in").font(AppFont.body(15)).foregroundStyle(Color.ink)
                        if morningOn {
                            DatePicker("Time", selection: morningTime, displayedComponents: .hourAndMinute)
                                .labelsHidden()
                                .datePickerStyle(.compact)
                                .scaleEffect(0.9, anchor: .leading)
                                .padding(.top, 2)
                        } else {
                            Text(Reminders.timeLabel(morningMinutes)).font(AppFont.body(12)).foregroundStyle(Color.muted)
                        }
                    }
                }
                .tint(Color.mobility)
                .settingsRow()
                Divider().overlay(Color.cardBorder)
                Toggle(isOn: $dinnerOn) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Log dinner nudge").font(AppFont.body(15)).foregroundStyle(Color.ink)
                        Text("\(Reminders.timeLabel(Reminders.dinnerMinutes)) if under target")
                            .font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                }
                .tint(Color.mobility)
                .settingsRow()
            }
            if notificationsDenied {
                footnote("Notifications are off for TrainLog. Turn them on in the iPhone's Settings → Notifications → TrainLog.")
                    .foregroundStyle(Color.warning)
            }
        }
    }

    private var morningTime: Binding<Date> {
        Binding {
            Calendar.current.date(bySettingHour: morningMinutes / 60, minute: morningMinutes % 60, second: 0, of: .now) ?? .now
        } set: { date in
            let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
            morningMinutes = (parts.hour ?? 7) * 60 + (parts.minute ?? 30)
        }
    }

    private func reschedule(turnedOn: Bool, revert: @escaping () -> Void) {
        Task {
            if turnedOn {
                let allowed = await Reminders.requestPermission()
                notificationsDenied = !allowed
                if !allowed {
                    revert()
                    return
                }
            }
            await Reminders.apply()
        }
    }

    // MARK: Pieces

    private func navRow(_ title: String, detail: String? = nil, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Text(title).font(AppFont.body(15)).foregroundStyle(Color.ink)
                Spacer(minLength: 0)
                if let detail {
                    Text(detail).font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color(hex: 0x4A5263))
            }
            .settingsRow()
        }
        .buttonStyle(.plain)
    }

    private func footnote(_ text: String) -> some View {
        Text(text)
            .font(AppFont.body(12))
            .foregroundStyle(Color.muted)
            .lineSpacing(2)
            .padding(.horizontal, 4)
    }
}

/// Card with the artboard's tighter list padding (4 top/bottom, 16 sides).
private struct SettingsCard<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        VStack(spacing: 0) { content }
            .padding(.horizontal, 16)
            .padding(.vertical, 4)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
    }
}

private extension View {
    func settingsRow() -> some View {
        padding(.vertical, 12)
            .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
    }
}

struct StatusPill: View {
    let status: SettingsModel.Status

    var body: some View {
        HStack(spacing: 6) {
            switch status {
            case .checking:
                ProgressView().controlSize(.mini).tint(.muted)
                Text("Checking")
            case .online(let ms):
                Circle().fill(color).frame(width: 7, height: 7)
                Text("\(ms) ms")
            case .offline:
                Circle().fill(color).frame(width: 7, height: 7)
                Text("Offline")
            }
        }
        .font(AppFont.body(12, weight: .bold))
        .foregroundStyle(color)
        .padding(.horizontal, 10)
        .frame(height: 24)
        .background(color.opacity(0.12), in: Capsule())
    }

    private var color: Color {
        switch status {
        case .checking: .muted
        case .online: .mobility
        case .offline: .danger
        }
    }
}

// MARK: - Address sheets

/// Lists TrainLog servers that answered on this Wi-Fi; tap one to use it.
struct FindServerSheet: View {
    let current: String
    let onPick: (String) async -> Void
    @State private var finder = ServerFinder()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SheetHeader(kicker: "Bonjour", title: "Find on this Wi-Fi")
            VStack(spacing: 0) {
                ForEach(finder.found) { server in
                    Button {
                        Task {
                            await onPick(server.url)
                            dismiss()
                        }
                    } label: {
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(ServerAddress.displayName(server.url))
                                    .font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                                Text(server.url)
                                    .font(.system(size: 12, design: .monospaced)).foregroundStyle(Color.muted)
                                    .lineLimit(1)
                                    .truncationMode(.middle)
                            }
                            Spacer(minLength: 0)
                            if server.url == current {
                                Image(systemName: "checkmark").font(.system(size: 14, weight: .bold)).foregroundStyle(Color.volt)
                            } else {
                                StatusPill(status: .online(ms: server.ms))
                            }
                        }
                        .settingsRow()
                    }
                    .buttonStyle(.plain)
                    if server != finder.found.last || finder.searching { Divider().overlay(Color.cardBorder) }
                }
                if finder.searching {
                    HStack(spacing: 10) {
                        ProgressView().tint(.muted)
                        Text("Looking for TrainLog on port \(String(ServerAddress.defaultPort))…")
                            .font(AppFont.body(14)).foregroundStyle(Color.muted)
                    }
                    .settingsRow()
                } else if finder.found.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("No TrainLog server found").font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                        Text("Check the Mac is on this Wi-Fi and the backend is running (docker compose up), or enter its address manually.")
                            .font(AppFont.body(13)).foregroundStyle(Color.muted)
                    }
                    .settingsRow()
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 4)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
            if !finder.searching {
                Button("Search again") { finder.start() }
                    .buttonStyle(OutlineButtonStyle(height: 44))
            }
            Spacer(minLength: 0)
        }
        .padding(20)
        .onAppear { finder.start() }
        .onDisappear { finder.stop() }
    }
}

/// Typed address: a bare host gets http:// and :8000. Tested before it's saved.
struct ManualAddressSheet: View {
    let current: String
    let onSave: (String) async -> Void
    @State private var text = ""
    @State private var testing = false
    @State private var error: String?
    @FocusState private var focused: Bool
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SheetHeader(kicker: "Server", title: "Enter address")
            TextField("192.168.1.24 or mac.local", text: $text)
                .font(.system(size: 16, design: .monospaced))
                .foregroundStyle(Color.ink)
                .keyboardType(.URL)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .focused($focused)
                .onSubmit { Task { await save() } }
                .padding(.horizontal, 14)
                .frame(height: 50)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
            Group {
                if let error {
                    Text(error).foregroundStyle(Color.danger)
                } else if let url = ServerAddress.normalize(text), url != text {
                    Text("Will use \(url)").foregroundStyle(Color.muted)
                } else {
                    Text("Port \(String(ServerAddress.defaultPort)) and http:// are added when left out.").foregroundStyle(Color.muted)
                }
            }
            .font(AppFont.body(12))
            .padding(.horizontal, 4)
            Button {
                Task { await save() }
            } label: {
                HStack(spacing: 8) {
                    if testing { ProgressView().tint(Color.bg) }
                    Text(testing ? "Checking…" : error == nil ? "Save" : "Save anyway")
                }
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(testing || ServerAddress.normalize(text) == nil)
            .opacity(ServerAddress.normalize(text) == nil ? 0.5 : 1)
            if current != APIClient.defaultBaseURL {
                Button("Reset to \(APIClient.defaultBaseURL)") {
                    Task {
                        await onSave(APIClient.defaultBaseURL)
                        dismiss()
                    }
                }
                .buttonStyle(OutlineButtonStyle(height: 44))
            }
            Spacer(minLength: 0)
        }
        .padding(20)
        .onAppear {
            text = current
            focused = true
        }
        .onChange(of: text) { error = nil }
    }

    /// Checks the address first so a typo can't quietly cut the app off; a second tap saves it
    /// anyway (a Tailscale address set up while away from home).
    private func save() async {
        guard let url = ServerAddress.normalize(text) else { return }
        if error != nil {
            await onSave(url)
            dismiss()
            return
        }
        testing = true
        let ms = await ServerAddress.ping(url)
        testing = false
        guard ms != nil else {
            error = "No TrainLog server answered at \(url)."
            return
        }
        await onSave(url)
        dismiss()
    }
}

private struct SheetHeader: View {
    let kicker: String
    let title: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker(kicker)
            Text(title.uppercased()).font(AppFont.title(30)).foregroundStyle(Color.ink)
        }
        .padding(.top, 8)
    }
}
