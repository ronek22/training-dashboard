import PhotosUI
import SwiftUI

/// Photo (and/or words) → Claude's items → correct them → log. Starts estimating straight away
/// when it opens with a photo.
struct MealEstimateSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var model: MealEstimateModel
    @State private var showCamera = false
    @State private var libraryItem: PhotosPickerItem?
    @FocusState private var textFocused: Bool
    let date: String
    let onSave: (FoodEntryInput) -> Void

    init(draft: MealDraft, date: String, onSave: @escaping (FoodEntryInput) -> Void) {
        _model = State(initialValue: MealEstimateModel(photo: draft.photo))
        self.date = date
        self.onSave = onSave
    }

    var body: some View {
        VStack(spacing: 0) {
            topBar
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    photoRow
                    TextField("What's in it? e.g. big kebab, no sauce", text: $model.text, axis: .vertical)
                        .font(AppFont.body(15))
                        .foregroundStyle(Color.ink)
                        .lineLimit(1...4)
                        .focused($textFocused)
                        .padding(12)
                        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
                        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
                    mealPicker
                    result
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
            }
            .scrollDismissesKeyboard(.interactively)
            action
                .padding(.horizontal, 16)
                .padding(.bottom, 8)
        }
        .padding(.top, 8)
        .task {
            if model.photo != nil { await model.estimate() } else { textFocused = true }
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
        model.items = []
        Task { await model.estimate() }
    }

    private var topBar: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            Spacer()
            Text("Log meal").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
            Spacer()
            Color.clear.frame(width: 52, height: 44)
        }
        .padding(.horizontal, 16)
    }

    private var photoRow: some View {
        HStack(spacing: 12) {
            if let photo = model.photo {
                Image(uiImage: photo)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 88, height: 88)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(alignment: .topTrailing) {
                        Button {
                            model.photo = nil
                        } label: {
                            Image(systemName: "xmark")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundStyle(Color.ink)
                                .frame(width: 24, height: 24)
                                .background(Color.bg.opacity(0.75), in: Circle())
                        }
                        .frame(width: 44, height: 44, alignment: .topTrailing)
                        .padding(4)
                        .accessibilityLabel("Remove photo")
                    }
            }
            VStack(spacing: 8) {
                Button {
                    showCamera = true
                } label: {
                    Label(model.photo == nil ? "Take photo" : "Retake", systemImage: "camera")
                }
                .buttonStyle(OutlineButtonStyle(height: 40))
                PhotosPicker(selection: $libraryItem, matching: .images) {
                    Label("Library", systemImage: "photo.on.rectangle")
                }
                .buttonStyle(OutlineButtonStyle(height: 40))
            }
        }
    }

    private var mealPicker: some View {
        HStack(spacing: 4) {
            ForEach(FoodFormat.meals, id: \.value) { meal in
                let selected = model.meal == meal.value
                Button {
                    model.meal = meal.value
                } label: {
                    Text(meal.label)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(selected ? Color.ink : Color.muted)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(selected ? Color.raised : .clear, in: RoundedRectangle(cornerRadius: 10))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(4)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
    }

    @ViewBuilder
    private var result: some View {
        switch model.phase {
        case .estimating(let message):
            HStack(spacing: 10) {
                ProgressView().tint(.volt)
                Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            }
            .frame(maxWidth: .infinity, minHeight: 64)
        case .failed(let message):
            Text(message)
                .font(AppFont.body(14))
                .foregroundStyle(Color.danger)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .idle, .ready:
            EmptyView()
        }
        if !model.items.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Kicker("Claude's estimate")
                    Spacer()
                    Text("\(FoodFormat.kcal(model.totals.kcal)) kcal · \(Int(model.totals.proteinG.rounded())) g P")
                        .font(AppFont.body(12, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                }
                .padding(.bottom, 4)
                ForEach($model.items) { $item in
                    Rectangle().fill(Color.cardBorder).frame(height: 1)
                    ItemEditor(item: $item) { model.items.removeAll { $0.id == item.id } }
                }
                if !model.note.isEmpty {
                    Text(model.note).font(AppFont.body(12)).foregroundStyle(Color.muted).padding(.top, 10)
                }
            }
            .card()
        }
    }

    @ViewBuilder
    private var action: some View {
        if model.items.isEmpty {
            Button {
                textFocused = false
                Task { await model.estimate() }
            } label: {
                Label("Estimate", systemImage: "sparkles")
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(!model.canEstimate)
            .opacity(model.canEstimate ? 1 : 0.4)
        } else {
            HStack(spacing: 8) {
                Button("Re-estimate") {
                    textFocused = false
                    Task { await model.estimate() }
                }
                .buttonStyle(OutlineButtonStyle(height: 52))
                .frame(width: 128)
                .disabled(!model.canEstimate)
                Button {
                    onSave(model.entry(date: date))
                    dismiss()
                } label: {
                    Label("Log \(FoodFormat.kcal(model.totals.kcal)) kcal", systemImage: "checkmark")
                }
                .buttonStyle(VoltButtonStyle())
            }
        }
    }
}

/// One estimated item: name, then grams / kcal / protein to correct.
private struct ItemEditor: View {
    @Binding var item: FoodItem
    let onRemove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                TextField("Food", text: $item.name)
                    .font(AppFont.body(14, weight: .semibold))
                    .foregroundStyle(Color.ink)
                if item.confidence == "low" {
                    Text("guess").font(AppFont.body(10, weight: .bold)).foregroundStyle(Color.warning)
                }
                Button(action: onRemove) {
                    Image(systemName: "minus.circle").font(.system(size: 17)).foregroundStyle(Color.faint)
                        .frame(width: 44, height: 32, alignment: .trailing)
                }
                .accessibilityLabel("Remove \(item.name)")
            }
            HStack(spacing: 8) {
                if item.portions == nil {
                    field("g", value: gramsBinding)
                } else {
                    field("portion", value: Binding(get: { item.portions ?? 1 }, set: { item.portions = $0 }))
                }
                field("kcal", value: $item.kcal)
                field("g P", value: $item.proteinG)
            }
        }
        .padding(.vertical, 10)
    }

    /// Changing grams rescales kcal and macros, so correcting the portion keeps them consistent.
    private var gramsBinding: Binding<Double> {
        Binding(
            get: { item.grams ?? 0 },
            set: { item = FoodFormat.rescale(item, grams: $0) }
        )
    }

    private func field(_ unit: String, value: Binding<Double>) -> some View {
        HStack(spacing: 4) {
            TextField("0", value: value, format: .number.precision(.fractionLength(0...1)))
                .keyboardType(.decimalPad)
                .font(AppFont.number(18, weight: .semibold))
                .foregroundStyle(Color.ink)
                .multilineTextAlignment(.trailing)
            Text(unit).font(AppFont.body(11)).foregroundStyle(Color.muted)
        }
        .padding(.horizontal, 10)
        .frame(maxWidth: .infinity, minHeight: 40)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.cardBorder))
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
