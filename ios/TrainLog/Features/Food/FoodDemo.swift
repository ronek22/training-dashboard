import Foundation

extension FoodModel {
    /// The Food tab's model, or with `-foodDemo morning|tapped|evening|protein|ride|refuel` a fixed
    /// day for screenshots that never reaches the server (frames in iOSFoodGap.dc.html).
    static func launch() -> FoodModel {
        #if DEBUG
        if let stage = UserDefaults.standard.string(forKey: "foodDemo") {
            return demo(stage)
        }
        #endif
        return FoodModel()
    }

    #if DEBUG
    static func demo(_ stage: String, now: Date = .now) -> FoodModel {
        let model = FoodModel(today: now)
        let fixture = FoodDemo(stage: stage, now: now)
        model.applyDemo(day: fixture.day, quick: fixture.quick, relogged: fixture.relogged)
        return model
    }
    #endif
}

#if DEBUG
/// Live values from 2–3 Nov and Sunday's sweet spot; today's eaten numbers are made up.
struct FoodDemo {
    let day: FoodDay
    let quick: FoodQuick
    let relogged: FoodModel.Relogged?

    init(stage: String, now: Date) {
        let today = FoodFormat.iso(now)
        let ride = stage == "ride" || stage == "refuel"
        let target = FoodDay.Target(kcal: ride ? 3248 : 2478, dayKind: ride ? "key_ride" : "lift", carbsG: ride ? 480 : 320)

        let kielbasa = Self.entry(1, today, "breakfast", 7, 41, [
            FoodItem(name: "kiełbasa podwawelska", grams: 100, kcal: 280, proteinG: 14, carbsG: 2, fatG: 24),
            FoodItem(name: "chleb żytni", grams: 120, kcal: 295, proteinG: 9.6, carbsG: 54, fatG: 2),
            FoodItem(name: "masło", grams: 15, kcal: 113, proteinG: 0.1, carbsG: 0, fatG: 12.5),
            FoodItem(name: "ketchup", grams: 20, kcal: 22, proteinG: 0.2, carbsG: 5, fatG: 0),
            FoodItem(name: "sałatka jarzynowa tradycyjna", grams: 150, kcal: 215, proteinG: 3.1, carbsG: 9, fatG: 19.5),
        ])
        let pomidorowka = Self.entry(2, today, "lunch", 13, 5, [
            FoodItem(name: "Pomidorówka na domowym rosole", kcal: 708, proteinG: 53, carbsG: 26, fatG: 44),
        ])
        let owsianka = Self.entry(3, today, "breakfast", 7, 30, [
            FoodItem(name: "Owsianka", grams: 300, kcal: 380, proteinG: 13, carbsG: 62, fatG: 9),
            FoodItem(name: "banan", grams: 120, kcal: 107, proteinG: 1.3, carbsG: 27, fatG: 0.4),
            FoodItem(name: "skyr", grams: 150, kcal: 123, proteinG: 15.7, carbsG: 6, fatG: 2.6),
        ])
        let entries: [FoodEntry] = switch stage {
        case "tapped": [kielbasa]
        case "evening": [kielbasa, pomidorowka]
        case "protein": [kielbasa, pomidorowka, Self.entry(4, today, "dinner", 18, 40, [
            FoodItem(name: "Makaron z sosem pomidorowym", grams: 350, kcal: 747, proteinG: 12, carbsG: 120, fatG: 22),
        ])]
        case "refuel": [owsianka, Self.entry(5, today, "lunch", 13, 30, [
            FoodItem(name: "Kanapki z szynką", kcal: 900, proteinG: 40, carbsG: 110, fatG: 34),
        ]), Self.entry(6, today, "snack", 16, 50, [
            FoodItem(name: "Drożdżówka i kakao", kcal: 718, proteinG: 32, carbsG: 95, fatG: 34),
        ])]
        default: []
        }
        day = FoodDay(date: today, entries: entries, totals: entries.map(\.totals).reduce(.zero, Self.sum),
                      target: target, proteinTargetG: 130, week: nil)

        let yesterday: FoodQuick.Again = ride
            ? Self.again("yesterday-3", "yesterday", "breakfast", 1, owsianka.items)
            : Self.again("yesterday-55", "yesterday", "breakfast", 1, kielbasa.items)
        let again = [
            yesterday,
            Self.again("favourite-41", "favourite", "lunch", 4, pomidorowka.items),
            Self.again("favourite-38", "favourite", "dinner", 4, [
                FoodItem(name: "Kurczak w sosie słodko-kwaśnym z ryżem", kcal: 1025, proteinG: 70, carbsG: 158, fatG: 12),
            ]),
        ]
        let daysAgo = { (days: Int) in FoodFormat.iso(now.addingTimeInterval(Double(-days) * 86_400)) }
        let gap: FoodQuick.Gap? = switch stage {
        case "evening": FoodQuick.Gap(focus: "both", meal: "dinner", left: .init(kcal: 845, proteinG: 50), picks: [
            Self.pick("item-171", "Pierś z kurczaka w cieście", lastDate: daysAgo(3), portions: 1,
                      [FoodItem(name: "pierś z kurczaka w cieście smażona", grams: 150, kcal: 460, proteinG: 42, carbsG: 18, fatG: 24)]),
            Self.pick("entry-38", "Kurczak w sosie słodko-kwaśnym z ryżem", lastDate: daysAgo(9), count: 4, portions: 0.5,
                      [FoodItem(name: "Kurczak w sosie słodko-kwaśnym z ryżem", kcal: 513, proteinG: 35, carbsG: 79, fatG: 6, portions: 0.5)]),
        ])
        case "protein": FoodQuick.Gap(focus: "protein", meal: "dinner", left: .init(kcal: 98, proteinG: 38), picks: [
            Self.pick("item-120", "Szynka wieprzowa", lastDate: daysAgo(2), count: 4, portions: 4,
                      [FoodItem(name: "szynka wieprzowa", grams: 160, kcal: 200, proteinG: 32, carbsG: 2, fatG: 8.4)]),
            Self.pick("item-88", "Frankfurterki z jagnięciny (lidl)", lastDate: daysAgo(21), count: 2, portions: 1,
                      [FoodItem(name: "frankfurterki z jagnięciny (lidl)", grams: 100, kcal: 237, proteinG: 21, carbsG: 0.5, fatG: 17)]),
        ])
        case "refuel": FoodQuick.Gap(focus: "refuel", meal: "dinner", left: .init(kcal: 1020, proteinG: 28), picks: [
            Self.pick("entry-38", "Kurczak w sosie słodko-kwaśnym z ryżem", lastDate: daysAgo(9), count: 4, portions: 1,
                      [FoodItem(name: "Kurczak w sosie słodko-kwaśnym z ryżem", kcal: 1025, proteinG: 70, carbsG: 158, fatG: 12)]),
            Self.pick("entry-57", "Ziemniaki gotowane, schab w panierce", lastDate: daysAgo(6), portions: 1,
                      [FoodItem(name: "ziemniaki gotowane", grams: 250, kcal: 193, proteinG: 5, carbsG: 43, fatG: 0.3),
                       FoodItem(name: "schab w panierce z bułki tartej smażony", grams: 150, kcal: 390, proteinG: 30, carbsG: 17, fatG: 21)]),
        ])
        default: nil
        }
        let fuel: FoodQuick.Fuel? = stage == "ride" ? FoodQuick.Fuel(
            title: "Sweet spot 3 × 10 min (knee-gated)", durationMin: 70, totalCarbsG: 70, bottles: 1, carbsGPerH: .init(target: 60),
            blocks: [[12, 22], [27, 37], [42, 52]],
            stops: [.init(min: 15, carbsG: 25), .init(min: 35, carbsG: 25), .init(min: 55, carbsG: 25)]
        ) : nil
        quick = FoodQuick(date: today, slot: FoodFormat.defaultMeal(at: now), again: again, gap: gap, fuel: fuel)
        relogged = stage == "tapped" ? FoodModel.Relogged(key: yesterday.key, meal: "breakfast", kcal: kielbasa.totals.kcal, entryId: 1) : nil
    }

    private static func sum(_ a: Macros, _ b: Macros) -> Macros {
        Macros(kcal: a.kcal + b.kcal, proteinG: a.proteinG + b.proteinG, carbsG: a.carbsG + b.carbsG, fatG: a.fatG + b.fatG)
    }

    private static func entry(_ id: Int, _ date: String, _ meal: String, _ hour: Int, _ minute: Int, _ items: [FoodItem]) -> FoodEntry {
        // Stored like SQLite's CURRENT_TIMESTAMP: UTC.
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = .current
        let local = FoodFormat.parse(date).flatMap { calendar.date(bySettingHour: hour, minute: minute, second: 0, of: $0) } ?? .now
        let utc = DateFormatter()
        utc.locale = Locale(identifier: "en_US_POSIX")
        utc.timeZone = TimeZone(identifier: "UTC")
        utc.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return FoodEntry(id: id, date: date, meal: meal, source: "text", rawText: nil, createdAt: utc.string(from: local),
                         items: items, totals: items.reduce(.zero, FoodFormat.add))
    }

    private static func again(_ key: String, _ kind: String, _ meal: String, _ count: Int, _ items: [FoodItem]) -> FoodQuick.Again {
        let title = items.count == 1 ? items[0].name : FoodFormat.itemNames(items).replacingOccurrences(of: " +2", with: "…")
        return FoodQuick.Again(key: key, kind: kind, meal: meal, date: nil, count: count, title: title, items: items,
                               totals: items.reduce(.zero, FoodFormat.add))
    }

    private static func pick(_ key: String, _ title: String, lastDate: String?, count: Int = 1, portions: Double,
                             _ items: [FoodItem]) -> FoodQuick.Pick {
        FoodQuick.Pick(key: key, title: title, source: "log", lastDate: lastDate, count: count, portions: portions,
                       items: items, totals: items.reduce(.zero, FoodFormat.add))
    }
}

#endif
