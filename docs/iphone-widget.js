// TrainLog Today: a Scriptable Home Screen widget (large; medium and small also work).
// Reads trainlog-today.json, which the backend writes to an iCloud Drive folder.
// Setup: docs/iphone.md → "Home Screen widget".
// Widget parameter (optional): the phone app URL, e.g. http://192.168.1.42:3080. Opened on tap,
// and on home Wi-Fi the widget reads /api/widget/today from it before falling back to iCloud.

const BOOKMARK = "TrainLog";
const FILE_NAME = "trainlog-today.json";
const STALE_HOURS = 3;

const C = {
  bg: Color.dynamic(new Color("#f6f7f9"), new Color("#1f2226")),
  card: Color.dynamic(new Color("#ffffff"), new Color("#2a2e33")),
  text: Color.dynamic(new Color("#16181b"), new Color("#eef0f2")),
  muted: Color.dynamic(new Color("#6b7280"), new Color("#9aa1ab")),
  faint: Color.dynamic(new Color("#d7dbe0"), new Color("#41464d")),
  accent: Color.dynamic(new Color("#2f6fde"), new Color("#6a9cf0")),
  green: Color.dynamic(new Color("#1f9d55"), new Color("#3ccf7a")),
  amber: Color.dynamic(new Color("#c27c0e"), new Color("#f0b23f")),
  red: Color.dynamic(new Color("#d0393e"), new Color("#f2676b")),
};
const LEVEL_COLORS = { green: C.green, amber: C.amber, red: C.red, unknown: C.muted };
const SPORT_SYMBOLS = {
  strength: "dumbbell.fill",
  weighttraining: "dumbbell.fill",
  ride: "bicycle",
  virtualride: "bicycle",
  run: "figure.run",
  walk: "figure.walk",
  hike: "figure.hiking",
  recovery: "figure.walk",
  rest: "bed.double.fill",
  mobility: "figure.flexibility",
};

function parseBrief(raw) {
  if (!raw) return null;
  try {
    const brief = JSON.parse(raw);
    return brief?.date && brief?.readiness ? brief : null;
  } catch {
    return null;
  }
}

// Live API first (home Wi-Fi), so the widget is fresh without waiting on iCloud.
async function fromApi(appUrl) {
  if (!appUrl) return null;
  try {
    const request = new Request(`${appUrl.replace(/\/+$/, "")}/api/widget/today`);
    request.timeoutInterval = 4;
    return parseBrief(await request.loadString());
  } catch {
    return null;
  }
}

// The backend replaces the file every 15 min; mid-sync the read can come back empty.
async function fromICloud() {
  const fm = FileManager.iCloud();
  if (!fm.bookmarkExists(BOOKMARK)) return null;
  const path = fm.joinPath(fm.bookmarkedPath(BOOKMARK), FILE_NAME);
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      if (fm.fileExists(path)) {
        await fm.downloadFileFromiCloud(path);
        const brief = parseBrief(fm.readString(path));
        if (brief) return brief;
      }
    } catch {}
  }
  return null;
}

function cachePath() {
  const fm = FileManager.local();
  return fm.joinPath(fm.cacheDirectory(), "trainlog-today-last.json");
}

async function loadBrief(appUrl) {
  const fm = FileManager.local();
  const fresh = (await fromApi(appUrl)) || (await fromICloud());
  if (fresh) {
    fm.writeString(cachePath(), JSON.stringify(fresh));
    return fresh;
  }
  // Last good copy; the footer turns amber once it is older than STALE_HOURS.
  const cached = fm.fileExists(cachePath()) ? parseBrief(fm.readString(cachePath())) : null;
  if (cached) return cached;
  if (!FileManager.iCloud().bookmarkExists(BOOKMARK)) {
    throw new Error(`Add a File Bookmark named "${BOOKMARK}" in Scriptable settings.`);
  }
  throw new Error(`${FILE_NAME} has not synced yet. Open Files → iCloud Drive → TrainLog once, then refresh.`);
}

function text(stack, value, size, color = C.text, weight = "regular", lines = 1) {
  const item = stack.addText(String(value ?? ""));
  item.font = weight === "bold" ? Font.boldSystemFont(size) : weight === "semibold" ? Font.semiboldSystemFont(size) : Font.systemFont(size);
  item.textColor = color;
  item.lineLimit = lines;
  item.minimumScaleFactor = 0.8;
  return item;
}

function symbol(stack, name, size, color) {
  const sf = SFSymbol.named(name) || SFSymbol.named("figure.mixed.cardio");
  sf.applyFont(Font.semiboldSystemFont(size));
  const image = stack.addImage(sf.image);
  image.imageSize = new Size(size + 4, size + 4);
  image.tintColor = color;
  return image;
}

function sportSymbol(session) {
  return SPORT_SYMBOLS[String(session?.session_type || "").toLowerCase()] || "figure.mixed.cardio";
}

function sessionMeta(session) {
  const parts = [session.intent_label];
  if (session.duration_min) parts.push(`${Math.round(session.duration_min)} min`);
  if (session.distance_km) parts.push(`${session.distance_km} km`);
  if (session.rpe) parts.push(`RPE ${session.rpe}`);
  return parts.filter(Boolean).join(" · ");
}

function pill(stack, readiness) {
  const color = LEVEL_COLORS[readiness.level] || C.muted;
  const box = stack.addStack();
  box.layoutHorizontally();
  box.centerAlignContent();
  box.setPadding(3, 8, 3, 8);
  box.cornerRadius = 9;
  box.backgroundColor = C.card;
  box.borderColor = color;
  box.borderWidth = 1;
  symbol(box, "circle.fill", 7, color);
  box.addSpacer(4);
  text(box, readiness.label, 12, color, "semibold");
}

function card(parent) {
  const box = parent.addStack();
  box.layoutVertically();
  box.setPadding(8, 10, 8, 10);
  box.cornerRadius = 10;
  box.backgroundColor = C.card;
  return box;
}

function fullWidth(stack) {
  const row = stack.addStack();
  row.layoutHorizontally();
  return row;
}

function header(widget, brief) {
  const row = widget.addStack();
  row.layoutHorizontally();
  row.centerAlignContent();
  const day = new Date(`${brief.date}T12:00:00`);
  const df = new DateFormatter();
  df.dateFormat = "EEE d MMM";
  text(row, df.string(day).toUpperCase(), 12, C.muted, "semibold");
  row.addSpacer();
  pill(row, brief.readiness);
}

function todayBlock(parent, brief, { purposeLines }) {
  if (brief.sick) {
    const row = parent.addStack();
    row.centerAlignContent();
    symbol(row, "cross.case.fill", 15, C.red);
    row.addSpacer(6);
    text(row, `Sick mode · day ${brief.sick.day}`, 17, C.text, "bold");
    parent.addSpacer(2);
    text(parent, `${brief.sick.label}. Follow the guided home sessions.`, 12, C.muted, "regular", 2);
    return;
  }
  const session = brief.today;
  if (!session) {
    text(parent, "No session planned", 17, C.text, "bold");
    text(parent, "No plan for this week yet.", 12, C.muted);
    return;
  }
  const done = ["matched", "linked"].includes(session.status);
  const row = parent.addStack();
  row.centerAlignContent();
  symbol(row, done ? "checkmark.circle.fill" : sportSymbol(session), 15, done ? C.green : C.accent);
  row.addSpacer(6);
  text(row, session.title, 17, C.text, "bold");
  const meta = sessionMeta(session);
  if (meta) {
    parent.addSpacer(2);
    text(parent, done ? `Done · ${meta}` : meta, 12, done ? C.green : C.muted, "semibold");
  }
  const purpose = session.purpose || session.details;
  if (purpose && purposeLines) {
    parent.addSpacer(3);
    text(parent, purpose, 12, C.muted, "regular", purposeLines);
  }
}

function readinessBlock(parent, brief, { driverCount }) {
  const box = card(parent);
  const r = brief.readiness;
  text(box, r.advice || "No readiness read yet.", 12, C.text, "semibold", 2);
  for (const driver of (r.drivers || []).slice(0, driverCount)) {
    box.addSpacer(3);
    const row = box.addStack();
    row.centerAlignContent();
    symbol(row, "circle.fill", 4, LEVEL_COLORS[r.level] || C.muted);
    row.addSpacer(5);
    text(row, driver, 11, C.muted);
    row.addSpacer();
  }
  if (!brief.checkin_done) {
    box.addSpacer(4);
    const row = box.addStack();
    row.centerAlignContent();
    symbol(row, "sun.max.fill", 10, C.amber);
    row.addSpacer(4);
    text(row, "No morning check-in yet", 11, C.amber, "semibold");
  }
  fullWidth(box).addSpacer();
}

function weekStrip(parent, brief) {
  if (!brief.week?.length) return;
  const row = parent.addStack();
  row.layoutHorizontally();
  for (const [index, day] of brief.week.entries()) {
    if (index) row.addSpacer();
    const col = row.addStack();
    col.layoutVertically();
    col.centerAlignContent();
    const isToday = day.status === "today";
    const label = col.addStack();
    label.size = new Size(28, 0);
    label.addSpacer();
    text(label, day.label?.[0] ?? "", 10, isToday ? C.accent : C.muted, isToday ? "bold" : "semibold");
    label.addSpacer();
    col.addSpacer(3);
    const dotRow = col.addStack();
    dotRow.size = new Size(28, 14);
    dotRow.centerAlignContent();
    dotRow.addSpacer();
    const dot = dotRow.addStack();
    const restLike = ["rest", "recovery"].includes(String(day.session_type).toLowerCase());
    if (day.status === "done") {
      dot.size = new Size(12, 12);
      dot.cornerRadius = 6;
      dot.backgroundColor = C.green;
    } else if (isToday) {
      dot.size = new Size(12, 12);
      dot.cornerRadius = 6;
      dot.borderColor = C.accent;
      dot.borderWidth = 2.5;
    } else if (day.status === "missed" || day.status === "skipped") {
      dot.size = new Size(12, 12);
      dot.cornerRadius = 6;
      dot.borderColor = C.red;
      dot.borderWidth = 1.5;
    } else if (restLike || day.status === "rest") {
      dot.size = new Size(10, 3);
      dot.cornerRadius = 1.5;
      dot.backgroundColor = C.faint;
    } else {
      dot.size = new Size(12, 12);
      dot.cornerRadius = 6;
      dot.backgroundColor = C.faint;
    }
    dotRow.addSpacer();
  }
}

function tomorrowLine(parent, brief) {
  const session = brief.tomorrow;
  if (!session) return;
  const row = parent.addStack();
  row.centerAlignContent();
  text(row, "TOMORROW", 10, C.muted, "semibold");
  row.addSpacer(6);
  symbol(row, sportSymbol(session), 10, C.muted);
  row.addSpacer(4);
  const minutes = session.duration_min ? ` · ${Math.round(session.duration_min)} min` : "";
  text(row, `${session.title}${minutes}`, 12, C.text);
  row.addSpacer();
}

function footer(widget, brief) {
  const generated = new Date(brief.generated_at);
  const ageHours = (Date.now() - generated.getTime()) / 3_600_000;
  const row = widget.addStack();
  row.addSpacer();
  const tf = new DateFormatter();
  tf.dateFormat = "HH:mm";
  if (ageHours >= STALE_HOURS) {
    const rel = new RelativeDateTimeFormatter();
    text(row, `Updated ${rel.string(generated, new Date())} · Mac offline?`, 10, C.amber, "semibold");
  } else {
    text(row, `Updated ${tf.string(generated)}`, 10, C.muted);
  }
}

function buildLarge(widget, brief) {
  header(widget, brief);
  widget.addSpacer(10);
  todayBlock(widget, brief, { purposeLines: 2 });
  widget.addSpacer(10);
  readinessBlock(widget, brief, { driverCount: 3 });
  widget.addSpacer();
  weekStrip(widget, brief);
  widget.addSpacer(10);
  tomorrowLine(widget, brief);
  widget.addSpacer(6);
  footer(widget, brief);
}

function buildMedium(widget, brief) {
  header(widget, brief);
  widget.addSpacer(6);
  todayBlock(widget, brief, { purposeLines: 0 });
  widget.addSpacer();
  text(widget, brief.readiness.advice || "", 11, C.muted, "regular", 2);
  widget.addSpacer(6);
  weekStrip(widget, brief);
}

function buildSmall(widget, brief) {
  pill(widget, brief.readiness);
  widget.addSpacer();
  const session = brief.today;
  if (session) {
    symbol(widget, sportSymbol(session), 16, C.accent);
    widget.addSpacer(4);
    text(widget, session.title, 15, C.text, "bold", 3);
    if (session.duration_min) text(widget, `${Math.round(session.duration_min)} min`, 12, C.muted, "semibold");
  } else {
    text(widget, brief.sick ? "Sick mode" : "No session", 15, C.text, "bold", 2);
  }
}

function buildError(widget, message) {
  symbol(widget, "exclamationmark.triangle.fill", 16, C.amber);
  widget.addSpacer(6);
  text(widget, "TrainLog widget", 14, C.text, "bold");
  widget.addSpacer(4);
  text(widget, message, 12, C.muted, "regular", 4);
}

async function main() {
  const family = config.widgetFamily || "large";
  const widget = new ListWidget();
  widget.backgroundColor = C.bg;
  widget.setPadding(14, 16, 12, 16);
  widget.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
  const appUrl = (args.widgetParameter || "").trim();
  if (appUrl) widget.url = appUrl;

  try {
    const brief = await loadBrief(appUrl);
    if (family === "small") buildSmall(widget, brief);
    else if (family === "medium") buildMedium(widget, brief);
    else buildLarge(widget, brief);
  } catch (error) {
    buildError(widget, error.message);
  }

  if (config.runsInWidget) Script.setWidget(widget);
  else await widget.presentLarge();
  Script.complete();
}

await main();
