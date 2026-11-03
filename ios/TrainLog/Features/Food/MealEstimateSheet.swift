import PhotosUI
import SwiftUI

/// Photo (and/or words) → Claude's items → see the breakdown, fix portions → log. Starts
/// estimating straight away when it opens with a photo.
struct MealEstimateSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var model: MealEstimateModel
    @State private var showCamera = false
    @State private var libraryItem: PhotosPickerItem?
    @State private var portion = 1.0
    @State private var fixing = false
    @FocusState private var textFocused: Bool
    let date: String
    let context: MealDayContext
    let onSave: (FoodEntryInput) -> Void

    init(draft: MealDraft, date: String, context: MealDayContext, onSave: @escaping (FoodEntryInput) -> Void) {
        _model = State(initialValue: MealEstimateModel(photo: draft.photo, meal: draft.meal ?? FoodFormat.defaultMeal()))
        self.date = date
        self.context = context
        self.onSave = onSave
    }

    private var estimating: Bool {
        if case .estimating = model.phase { return true }
        return false
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if let photo = model.photo {
                        photoHeader(photo)
                    } else {
                        topBar
                    }
                    content
                        .padding(.horizontal, 16)
                        .padding(.top, model.photo == nil ? 4 : 20)
                        .padding(.bottom, 16)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.bg, in: UnevenRoundedRectangle(topLeadingRadius: 28, topTrailingRadius: 28, style: .continuous))
                        .padding(.top, model.photo == nil ? 0 : -32)
                }
            }
            .scrollIndicators(.hidden)
            .scrollDismissesKeyboard(.interactively)
            footer
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 8)
                .background(Color.bg)
                .overlay(alignment: .top) { Rectangle().fill(Color.cardBorder).frame(height: 1) }
        }
        .background(Color.bg)
        .task {
            if model.photo != nil { await model.estimate() } else { textFocused = true }
        }
        .onChange(of: portion) { old, new in
            model.items = FoodFormat.portioned(model.items, by: new / old)
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraPicker { image in
                showCamera = false
                if let image { replacePhoto(image) }
            }
            .ignoresSafeArea()
        }
        .onChange(of: libraryItem) { _, item in
            guard let item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data) {
                    replacePhoto(image)
                }
                libraryItem = nil
            }
        }
    }

    private func replacePhoto(_ image: UIImage) {
        textFocused = false
        model.photo = image
        reestimate()
    }

    private func reestimate() {
        textFocused = false
        fixing = false
        portion = 1
        Task { await model.estimate() }
    }

    private func photoHeader(_ photo: UIImage) -> some View {
        Color.clear
            .frame(height: 280)
            .overlay { Image(uiImage: photo).resizable().scaledToFill() }
            .clipped()
            .overlay(alignment: .top) {
                HStack {
                    roundButton("xmark", label: "Cancel") { dismiss() }
                    Spacer()
                    roundButton("camera", label: "Retake photo") { showCamera = true }
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
            }
    }

    private func roundButton(_ symbol: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Color.ink)
                .frame(width: 44, height: 44)
                .background(Color.bg.opacity(0.75), in: Circle())
        }
        .accessibilityLabel(label)
    }

    private var topBar: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    private var title: String {
        model.items.isEmpty ? (estimating ? "Estimating" : "Log meal") : FoodFormat.itemNames(model.items, limit: 2)
    }

    @ViewBuilder
    private var content: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 6) {
                    MealChip(meal: $model.meal)
                    if !model.items.isEmpty {
                        Label("Claude estimate", systemImage: "sparkle")
                            .labelStyle(.titleAndIcon)
                            .modifier(ChipStyle(color: .muted))
                    }
                }
                Text(title.uppercased())
                    .font(AppFont.title(34))
                    .foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 4)
                if !model.note.isEmpty, !model.items.isEmpty {
                    Text(model.note)
                        .font(AppFont.body(13).italic())
                        .foregroundStyle(Color.inkSoft)
                        .lineSpacing(3)
                        .padding(.top, 6)
                }
            }
            status
            if model.items.isEmpty {
                if !estimating { describe }
            } else {
                MealSummaryCard(totals: model.totals, target: context.target)
                PortionPicker(factor: $portion, grams: model.items.compactMap(\.grams).reduce(0, +))
                if fixing { fixNote }
                Breakdown(items: $model.items, originals: model.estimated)
                ImpactLine(meal: model.totals.kcal, context: context)
            }
        }
    }

    @ViewBuilder
    private var status: some View {
        switch model.phase {
        case .estimating(let message):
            HStack(spacing: 10) {
                ProgressView().tint(.volt)
                Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            }
            .frame(maxWidth: .infinity, minHeight: 64)
            .card()
        case .failed(let message):
            Text(message)
                .font(AppFont.body(14))
                .foregroundStyle(Color.danger)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .idle, .ready:
            EmptyView()
        }
    }

    /// Words (and optionally a photo) before the first estimate.
    private var describe: some View {
        VStack(alignment: .leading, spacing: 10) {
            textField("What's in it? e.g. big kebab, no sauce")
            if model.photo == nil {
                HStack(spacing: 8) {
                    Button { showCamera = true } label: { Label("Take photo", systemImage: "camera") }
                        .buttonStyle(OutlineButtonStyle(height: 40))
                    PhotosPicker(selection: $libraryItem, matching: .images) {
                        Label("Library", systemImage: "photo.on.rectangle")
                    }
                    .buttonStyle(OutlineButtonStyle(height: 40))
                }
            }
        }
    }

    /// "Sauce was cream-based": re-runs the estimate with these words added.
    private var fixNote: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Fix with a note")
            textField("What did Claude get wrong? e.g. sauce was cream-based")
        }
        .card()
    }

    private func textField(_ prompt: String) -> some View {
        TextField(prompt, text: $model.text, axis: .vertical)
            .font(AppFont.body(15))
            .foregroundStyle(Color.ink)
            .lineLimit(1...4)
            .focused($textFocused)
            .padding(12)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row))
            .overlay(RoundedRectangle(cornerRadius: Radius.row).strokeBorder(Color.cardBorder))
    }

    @ViewBuilder
    private var footer: some View {
        if model.items.isEmpty {
            Button {
                reestimate()
            } label: {
                Label("Estimate", systemImage: "sparkles")
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(!model.canEstimate)
            .opacity(model.canEstimate ? 1 : 0.4)
        } else {
            HStack(spacing: 8) {
                Button {
                    if fixing { reestimate() } else {
                        fixing = true
                        textFocused = true
                    }
                } label: {
                    Label(fixing ? "Re-estimate" : "Fix with note", systemImage: "sparkles")
                        .lineLimit(1)
                }
                .buttonStyle(OutlineButtonStyle(height: 52))
                .frame(width: 150)
                .disabled(estimating || (fixing && !model.canEstimate))
                Button {
                    onSave(model.entry(date: date))
                    dismiss()
                } label: {
                    Text("Log \(FoodFormat.kcal(model.totals.kcal)) kcal")
                }
                .buttonStyle(VoltButtonStyle())
            }
        }
    }
}

/// The system camera; falls back to the photo library where there's no camera (Simulator).
struct CameraPicker: UIViewControllerRepresentable {
    let onFinish: (UIImage?) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = UIImagePickerController.isSourceTypeAvailable(.camera) ? .camera : .photoLibrary
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onFinish: onFinish) }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onFinish: (UIImage?) -> Void

        init(onFinish: @escaping (UIImage?) -> Void) {
            self.onFinish = onFinish
        }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            onFinish(info[.originalImage] as? UIImage)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            onFinish(nil)
        }
    }
}
