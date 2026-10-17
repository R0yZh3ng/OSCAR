"use strict";
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = (n) => Math.round(n * 10) / 10;
const pctText = (x) => x == null ? "–" : Math.round(x * 100) + "%";
const ds = (d) => d.toLocaleDateString("sv");
const pd = (s) => new Date(s + "T00:00:00");
const addDays = (s, n) => { const d = pd(s); d.setDate(d.getDate() + n); return ds(d); };

const COLORS = ["#6c8cff","#f43f5e","#f5a524","#34d399","#38bdf8","#a78bfa","#fb923c","#ec4899","#14b8a6","#84cc16"];
const EMOJIS = "💧 🏃 🏋️ 🚴 🧘 📖 📚 ✍️ 📝 💻 🎸 🎨 🧠 🛏️ ⏰ 🥗 🍎 🚭 🧹 🪥 💊 🌱 🐕 📵 ☀️ 🚿 🙏 💰 📞 🎯 🏊 🚶 😴 🍳 ☕ 🧴 📅 🎧 🧩 🌙".split(" ");
const TODS = {morning:["☀️","Morning"], afternoon:["🌤️","Afternoon"], evening:["🌙","Evening"], anytime:["⏳","Anytime"]};
const DAYS = ["M","T","W","T","F","S","S"];
const MOODS = ["😫","😕","😐","🙂","🤩"];
const ACH_ICON = {first_log:"👣", perfect_day:"✨", streak_7:"🔥", streak_30:"⚡", streak_100:"💯",
  total_100:"🎖️", total_500:"🏅", perfect_week:"🌟", level_5:"🥉", level_10:"🥈", level_20:"🥇"};
const TEMPLATES = [
  {icon:"💧", name:"Drink water", type:"count", target:8, unit:" cups", color:"#38bdf8", category:"Health"},
  {icon:"🏋️", name:"Workout", type:"duration", target:30, unit:"m", color:"#f43f5e", category:"Health", difficulty:3, time_of_day:"afternoon"},
  {icon:"📖", name:"Read", type:"duration", target:20, unit:"m", color:"#a78bfa", category:"Mind", time_of_day:"evening", difficulty:2},
  {icon:"🧘", name:"Meditate", type:"duration", target:10, unit:"m", color:"#34d399", category:"Mind", time_of_day:"morning"},
  {icon:"🛏️", name:"Make bed", type:"check", color:"#f5a524", time_of_day:"morning", category:"Home"},
  {icon:"📝", name:"Journal", type:"check", color:"#fb923c", time_of_day:"evening", category:"Mind"},
  {icon:"🪥", name:"Floss", type:"check", color:"#14b8a6", time_of_day:"evening", category:"Health"},
  {icon:"🥗", name:"Eat veggies", type:"count", target:3, unit:" servings", color:"#84cc16", category:"Health"},
  {icon:"📵", name:"No phone in bed", type:"check", color:"#ec4899", time_of_day:"evening", category:"Mind"},
];

let S = null, page = null, navigated = false, viewDate = null, stats = null, sheet = null, touched = null;
let timer = {id: null, running: false, start: 0, base: 0, iv: null};

// ------------------------------------------------------------------ data

async function load() {
  S = await (await fetch("/api/state" + (viewDate ? `?date=${viewDate}` : ""))).json();
  render();
  if (!stats) loadStats();
}
async function loadStats() {
  stats = await (await fetch("/api/stats")).json();
  render();
}
window.refresh = async () => {
  await load();
  if (stats) loadStats();
  if (sheet?.kind === "detail") openDetail(sheet.id, true);
};

// Single mutation path: the same shape voice / RFID / gestures send.
async function act(action, args = {}, ctx = null) {
  const wasDone = ctx ? S.habits.find(h => h.id === ctx.id)?.done : false;
  const wasPerfect = S.today_progress.total > 0 && S.today_progress.done === S.today_progress.total;
  const res = await fetch("/api/actions", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({action, args, source: "ui", view: viewDate})});
  const out = await res.json();
  if (!res.ok) { toast(out.error || "Something went wrong"); return null; }
  S = out.state;
  touched = ctx;
  render();
  if (stats) loadStats();
  const h = ctx && S.habits.find(x => x.id === ctx.id);
  const tileEl = ctx && $(`.tile[data-id="${ctx.id}"]`);
  if (out.xp_delta > 0 && tileEl) floater(tileEl, `+${out.xp_delta} XP`);
  if (h && h.done && !wasDone) burst(tileEl, h.color, 26);
  const perfect = S.today_progress.total > 0 && S.today_progress.done === S.today_progress.total;
  if (perfect && !wasPerfect) { toast("✨ Perfect day!"); burst(null, null, 120); }
  out.unlocked.forEach(a => toast(`🏆 ${a.title}: ${a.description}`));
  if (out.level_up) showLevelUp(out.level_up);
  if (sheet?.kind === "detail") openDetail(sheet.id, true);
  return out;
}

// ------------------------------------------------------------------ svg + chart helpers

function ring(pct, color, size, stroke, inner = "", done = false) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, mid = size / 2;
  return `<span style="position:relative;display:inline-block;width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle cx="${mid}" cy="${mid}" r="${r}" fill="${done ? color : "none"}" fill-opacity=".92"
              stroke="var(--card2)" stroke-width="${stroke}"/>
      <circle class="ring-arc" cx="${mid}" cy="${mid}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}"
              stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - Math.min(Math.max(pct, 0), 1))}"
              transform="rotate(-90 ${mid} ${mid})"/>
    </svg>
    <span style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">${inner}</span>
  </span>`;
}

let gid = 0;
function lineChart(layers, {w = 600, h = 140, max = 1} = {}) {
  const id = "g" + gid++;
  const y = (v) => h - 6 - (v / max) * (h - 12);
  const paths = layers.map((l, k) => {
    const n = l.values.length;
    if (n < 2) return "";
    const pts = l.values.map((v, i) => `${(i / (n - 1)) * w},${y(v)}`);
    const line = "M" + pts.join(" L");
    const fill = l.fill ? `<path d="${line} L${w},${h} L0,${h} Z" fill="url(#${id}${k})"/>
      <defs><linearGradient id="${id}${k}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${l.color}" stop-opacity=".35"/><stop offset="1" stop-color="${l.color}" stop-opacity="0"/>
      </linearGradient></defs>` : "";
    return `${fill}<path d="${line}" fill="none" stroke="${l.color}" stroke-width="${l.width || 2.5}"
      stroke-opacity="${l.opacity ?? 1}" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="height:${h}px">
    ${[0, .5, 1].map(g => `<line x1="0" x2="${w}" y1="${y(g * max)}" y2="${y(g * max)}" stroke="var(--line)"
      stroke-dasharray="3 5" vector-effect="non-scaling-stroke"/>`).join("")}${paths}</svg>`;
}

function cols(items, {color = "var(--accent)", pct = true, highlight = true} = {}) {
  const vals = items.map(i => i.v ?? 0), top = Math.max(...vals, pct ? 1 : 1e-9);
  const best = Math.max(...vals);
  return `<div class="cols">${items.map(i => `<div class="c">
    <em>${i.v == null ? "" : (pct ? Math.round(i.v * 100) + "%" : fmt(i.v))}</em>
    <i style="height:${(i.v ?? 0) / top * 100 * .78}%;${i.v == null ? "min-height:0;" : ""}background:${i.color || color};opacity:${highlight && i.v === best && best > 0 ? 1 : .55}"></i>
    <span>${esc(i.label)}</span></div>`).join("")}</div>`;
}

function radar(items, size = 260) {
  const c = size / 2, R = size / 2 - 38, n = items.length;
  const pt = (i, f) => {
    const a = -Math.PI / 2 + (i / n) * 2 * Math.PI;
    return [c + Math.cos(a) * R * f, c + Math.sin(a) * R * f];
  };
  const poly = (f) => items.map((_, i) => pt(i, f).join(",")).join(" ");
  const shape = items.map((it, i) => pt(i, Math.max(it.rate ?? 0, .03)).join(",")).join(" ");
  return `<svg viewBox="0 0 ${size} ${size}" style="width:100%;max-width:300px">
    ${[.25, .5, .75, 1].map(f => `<polygon points="${poly(f)}" fill="none" stroke="var(--line)"/>`).join("")}
    ${items.map((_, i) => `<line x1="${c}" y1="${c}" x2="${pt(i, 1)[0]}" y2="${pt(i, 1)[1]}" stroke="var(--line)"/>`).join("")}
    <polygon points="${shape}" fill="var(--accent)" fill-opacity=".28" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round"/>
    ${items.map((it, i) => { const [x, y] = pt(i, 1.2);
      return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="var(--dim)">${esc(it.name)} ${pctText(it.rate)}</text>`; }).join("")}
  </svg>`;
}

function yearHeat(map, {days = 365, compact = false} = {}) {
  const end = pd(S.today), start = new Date(end); start.setDate(start.getDate() - (days - 1));
  const pad = (start.getDay() + 6) % 7;
  let cells = "<i style='visibility:hidden'></i>".repeat(pad), labels = "", lastMonth = -1;
  const totalCols = Math.ceil((pad + days) / 7);
  for (let i = 0; i < days; i++) {
    const d = new Date(start); d.setDate(d.getDate() + i);
    const key = ds(d), v = map[key];
    const col = Math.floor((pad + i) / 7);
    if (d.getMonth() !== lastMonth && d.getDate() <= 7) {
      labels += `<span style="left:${col / totalCols * 100}%">${d.toLocaleString("en", {month: "short"})}</span>`;
      lastMonth = d.getMonth();
    }
    const bg = v == null ? "" : `background:color-mix(in srgb, var(--ok) ${Math.round(8 + v * 92)}%, var(--card2))`;
    cells += `<i style="${bg}" title="${key}${v == null ? "" : " · " + Math.round(v * 100) + "%"}"></i>`;
  }
  return `<div class="hmwrap ${compact ? "compact" : ""}"><div class="months">${labels}</div><div class="hm" style="grid-template-columns:repeat(${totalCols},1fr)">${cells}</div></div>
    <div class="legend">less ${[.1, .4, .7, 1].map(v => `<i style="background:color-mix(in srgb, var(--ok) ${8 + v * 92}%, var(--card2))"></i>`).join("")} more</div>`;
}

// ------------------------------------------------------------------ dashboard

function render() {
  $("#view").innerHTML = dashboard();
  document.querySelectorAll(".hmwrap").forEach(w => { w.scrollLeft = w.scrollWidth; });  // newest weeks in view
  if (touched) {
    const t = $(`.tile[data-id="${touched.id}"]`);
    if (t) t.classList.add("pop");
    touched = null;
  }
  renderPage();
}

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Burning the midnight oil" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

// A widget is a card; tapping any non-interactive part of it opens its full page.
function widget(key, title, body, cls = "") {
  return `<section class="w ${cls}" data-do="page" data-p="${key}">
    <header><h2>${title}</h2><span class="chev">›</span></header>${body}</section>`;
}
const loading = `<div class="dim small" style="padding:18px 0">Loading…</div>`;
const avg = (a) => a.length ? a.reduce((s, x) => s + x.rate, 0) / a.length : null;

function dashboard() {
  const isToday = S.view === S.today;
  const head = `<header class="top"><div>
      <h1>${isToday ? greeting() : pd(S.view).toLocaleString("en", {weekday: "long", month: "short", day: "numeric"})}</h1>
      <div class="dim small">${isToday ? pd(S.view).toLocaleString("en", {weekday: "long", month: "long", day: "numeric"})
        : `Editing a past day · <a href="#" data-do="day" data-date="${S.today}" style="color:var(--accent)">back to today</a>`}</div></div>
      <button class="btn primary" id="addbtn" data-do="add">+ Habit</button></header>`;
  const ok = stats && stats.totals.habits;
  const st = (fn) => stats ? (ok ? fn() : `<div class="dim small" style="padding:14px 0">Add a habit and log a few days to fill this in.</div>`) : loading;
  return `${head}
    <div class="top-grid"><div>${wHabits()}</div><div class="stack">${wLevel()}${wStreaks()}${wMood()}</div></div>
    <div class="board">
      ${widget("trend", "Completion trend", st(wTrendBody), "s12")}
      ${widget("patterns", "Best days", st(() => cols(weekdayItems(), {})), "s4")}
      ${widget("patterns", "Time of day", st(() => cols(todItems(), {color: "var(--gold)"})), "s4")}
      ${widget("balance", "Life balance", st(() => radarOrBars(190)), "s4")}
      ${widget("year", "Your year", st(() => yearHeat(stats.heatmap, {days: 182, compact: true})), "s12")}
      ${widget("ranking", "Habit strength", st(() => rankRows(stats.ranking.slice(0, 5))), "s6")}
      ${widget("xp", "XP · 2 weeks", st(wXpBody), "s6")}
      ${widget("rewards", "Achievements", wAchBody(), "s12")}
    </div>`;
}

function wHabits() {
  const tp = S.today_progress, weekStart = S.week[0].date, canNext = addDays(weekStart, 7) <= S.today;
  const week = `<div class="week">
    <button class="arrow" data-do="week" data-n="-7" aria-label="Previous week">‹</button>
    ${S.week.map(d => {
      const dt = pd(d.date), fut = d.date > S.today;
      return `<button class="day ${d.date === S.view ? "sel" : ""} ${d.date === S.today ? "today" : ""}" ${fut ? "disabled" : ""}
        data-do="day" data-date="${d.date}"><span>${dt.toLocaleString("en", {weekday: "short"})}</span>
        ${ring(d.ratio ?? 0, d.ratio === 1 ? "var(--ok)" : "var(--accent)", 34, 4,
          `<small style="font-size:11px;font-weight:600">${dt.getDate()}</small>`, d.ratio === 1)}</button>`;
    }).join("")}
    <button class="arrow" data-do="week" data-n="7" ${canNext ? "" : "disabled"} aria-label="Next week">›</button></div>`;

  const todays = S.habits.filter(h => h.scheduled_today);
  const groups = Object.keys(TODS).map(k => [k, todays.filter(h => h.time_of_day === k)]).filter(([, hs]) => hs.length);
  const body = groups.length ? `<div class="groups">${groups.map(([k, hs]) => `<div>
      <h3 class="tod">${TODS[k][0]} ${TODS[k][1]} <span class="grow"></span><span>${hs.filter(h => h.done).length}/${hs.length}</span></h3>
      <div class="habits">${hs.map(tile).join("")}</div></div>`).join("")}</div>`
    : `<div class="empty"><div style="font-size:54px">🌱</div><p><b>Start your first habit</b></p>
        <button class="btn primary" data-do="add">+ Add a habit</button></div>`;
  const done = tp.total && tp.done === tp.total;
  return `<section class="w habits-w" data-do="page" data-p="habits">
    <header><h2>Today · ${tp.done}/${tp.total}${done ? " ✨" : ""}</h2><span class="chev">All habits ›</span></header>
    ${week}${body}</section>`;
}

function tile(h) {
  const pct = h.done ? 1 : Math.min(h.value / h.target, 1);
  const sub = h.skipped_today ? "skipped" : h.type === "check" ? (h.done ? "done ✓" : "") :
    `${fmt(h.value)}/${fmt(h.target)}${esc(h.unit)}`;
  const icon = `<span style="font-size:32px;${h.done ? "filter:drop-shadow(0 1px 2px #0006)" : ""}">${esc(h.icon) || "●"}</span>`;
  return `<div class="tile ${h.skipped_today ? "skipped" : ""}" data-id="${h.id}">
    ${h.streak >= 2 ? `<span class="flame">🔥${h.streak}</span>` : ""}
    <button class="ringbtn" data-do="tap" data-id="${h.id}" aria-label="${esc(h.name)}">
      ${ring(pct, h.color, 84, 7, icon, h.done)}</button>
    <button class="nm" style="background:none;border:0;padding:0" data-do="open" data-id="${h.id}">${esc(h.name)}</button>
    <div class="sub">${sub}</div></div>`;
}

function wLevel() {
  const L = S.level, tp = S.today_progress;
  return widget("rewards", "Level", `<div class="lvlrow">
    ${ring(L.progress, "var(--gold)", 96, 10, `<span class="dim" style="font-size:10px">LV</span><b style="font-size:30px;line-height:1">${L.level}</b>`)}
    <div class="grow"><div class="lvl">${esc(L.title)}</div>
      <div class="bar"><i style="width:${L.progress * 100}%"></i></div>
      <div class="dim small">${L.level_span - L.into_level} XP to level ${L.level + 1}</div>
      ${S.perfect_run ? `<div class="small" style="margin-top:4px">🔥 ${S.perfect_run}-day perfect run</div>` : ""}</div></div>`);
}

function wStreaks() {
  const hs = S.habits.filter(h => h.streak > 0 || h.best_streak > 0).sort((a, b) => b.streak - a.streak).slice(0, 4);
  return widget("streaks", "Streaks", hs.length ? hs.map(h => {
    const risk = h.scheduled_today && !h.done && !h.skipped_today && h.streak > 0;
    return `<div class="rank"><span class="ic">${esc(h.icon)}</span><span class="nmx">${esc(h.name)}</span>
      <b>${h.streak ? "🔥 " + h.streak : "–"}</b>${risk ? `<span class="risk" title="Do it today to keep the streak">!</span>` : ""}</div>`;
  }).join("") : `<div class="dim small" style="padding:10px 0">Complete a habit to start a streak.</div>`);
}

function wMood() {
  const recent = [];
  for (let i = 6; i >= 0; i--) { const k = addDays(S.today, -i); recent.push([k, stats?.moods?.[k]]); }
  return widget("mood", "Mood", `<div class="moods" role="group" aria-label="Mood for the viewed day">${MOODS.map((m, i) =>
      `<button class="${S.mood === i + 1 ? "on" : ""}" data-do="mood" data-v="${i + 1}" aria-label="Mood ${i + 1}">${m}</button>`).join("")}</div>
    <div class="moodweek">${recent.map(([k, m]) => `<span title="${k}">${m ? MOODS[m - 1] : "·"}</span>`).join("")}</div>`);
}

const weekdayItems = () => ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((l, i) => ({label: l, v: stats.weekday_rate[i]}));
const todItems = () => Object.keys(TODS).filter(k => stats.time_of_day[k] != null)
  .map(k => ({label: TODS[k][0], v: stats.time_of_day[k]}));

function wTrendBody() {
  const D = stats.daily, last7 = D.slice(-7), prev7 = D.slice(-14, -7), T = stats.totals;
  const a = avg(last7), b = avg(prev7), delta = a != null && b != null ? a - b : null;
  return `<div class="kpis">
      <div><b>${pctText(a)}</b><span class="dim small">this week ${delta == null ? "" :
        `<span style="color:${delta >= 0 ? "var(--ok)" : "var(--bad)"}">${delta >= 0 ? "▲" : "▼"}${Math.abs(Math.round(delta * 100))}%</span>`}</span></div>
      <div><b>${T.completions}</b><span class="dim small">completions</span></div>
      <div><b>${T.perfect_days}</b><span class="dim small">perfect days</span></div>
      <div><b>${T.best_streak}🔥</b><span class="dim small">best streak</span></div></div>
    ${lineChart([{values: D.map(x => x.rate), color: "var(--accent)", opacity: .3, width: 1.5},
                 {values: D.map(x => x.avg), color: "var(--accent)", fill: true}], {h: 110})}`;
}

function rankRows(rows, link = false) {
  return rows.map(r => `<div class="rank" ${link ? `data-do="open" data-id="${r.id}" style="cursor:pointer"` : ""}>
    <span class="ic">${esc(r.icon)}</span><span class="nmx">${esc(r.name)}</span>
    <div class="bar" style="--c:${r.color}"><i style="width:${r.strength * 100}%"></i></div>
    <b style="width:42px;text-align:right">${Math.round(r.strength * 100)}%</b></div>`).join("");
}

function radarOrBars(size) {
  return stats.wheel.length >= 3 ? `<div class="center">${radar(stats.wheel, size)}</div>` :
    stats.wheel.map(w => `<div class="rank"><span class="nmx">${esc(w.name)}</span><div class="bar"><i style="width:${(w.rate || 0) * 100}%"></i></div><b>${pctText(w.rate)}</b></div>`).join("") +
    `<div class="dim small">Use 3+ categories to see your wheel.</div>`;
}

function wXpBody() {
  const x = stats.xp_series.slice(-14);
  return cols(x.map(d => ({label: pd(d.date).getDate(), v: d.xp})), {pct: false, color: "var(--gold)"}) +
    `<div class="dim small" style="margin-top:8px">${stats.xp_series.reduce((s, d) => s + d.xp, 0)} XP in the last 30 days</div>`;
}

function wAchBody() {
  const got = S.achievements.filter(a => a.unlocked_at).length;
  return `<div class="achrow">${S.achievements.map(a =>
    `<span class="${a.unlocked_at ? "on" : "lock"}" title="${esc(a.title)}: ${esc(a.description)}">${ACH_ICON[a.key] || "🏆"}</span>`).join("")}</div>
    <div class="dim small" style="margin-top:6px">${got} of ${S.achievements.length} unlocked</div>`;
}

// ------------------------------------------------------------------ full pages (opened from widgets)

const PAGES = {
  habits: ["All habits", pHabits], trend: ["Completion trend", pTrend], patterns: ["Patterns", pPatterns],
  balance: ["Life balance", pBalance], year: ["Your year", pYear], ranking: ["Habit strength", pRanking],
  xp: ["Experience", pXp], rewards: ["Level & rewards", pRewards], streaks: ["Streaks", pStreaks], mood: ["Mood", pMood],
};

function go(key) { navigated = true; location.hash = "/" + key; }
function syncPage() {
  const m = location.hash.match(/^#\/(\w+)/);
  const key = m && PAGES[m[1]] ? m[1] : null;
  if (key !== page?.key) page = key ? {key, range: 90} : null;
  if (S) renderPage();
}

function renderPage() {
  const el = $("#page");
  if (!page) { el.classList.remove("show"); el.innerHTML = ""; document.body.classList.remove("noscroll"); return; }
  const top = el.scrollTop, [title, fn] = PAGES[page.key];
  const needsStats = page.key !== "habits" && page.key !== "rewards" && page.key !== "streaks";
  el.innerHTML = `<div class="pwrap"><header class="phead"><button class="x" data-do="back" aria-label="Back">‹</button><h1>${title}</h1></header>
    ${needsStats && !stats ? loading : fn()}</div>`;
  el.classList.add("show");
  document.body.classList.add("noscroll");
  el.scrollTop = top;
  el.querySelectorAll(".hmwrap").forEach(w => { w.scrollLeft = w.scrollWidth; });
}

const tiles = (items) => `<div class="tiles">${items.map(([v, l]) => `<div class="card stat"><b>${v}</b><span class="dim small">${l}</span></div>`).join("")}</div>`;
const sub = (t) => `<h2>${t}</h2>`;
const schedText = (wd) => wd.length === 7 ? "Every day" : wd.join() === "0,1,2,3,4" ? "Weekdays" : wd.join() === "5,6" ? "Weekends" :
  wd.map(i => ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i]).join(" ");

function pHabits() {
  const rank = Object.fromEntries((stats?.ranking || []).map(r => [r.id, r.strength]));
  return `<div class="actions"><button class="btn primary" data-do="add">+ New habit</button></div>` +
    (S.habits.length ? S.habits.map(h => `<div class="card hrow" data-do="open" data-id="${h.id}">
      ${ring(rank[h.id] ?? 0, h.color, 56, 6, `<span style="font-size:22px">${esc(h.icon)}</span>`)}
      <div class="grow"><b>${esc(h.name)}</b><div class="dim small">${esc(h.category || "No category")} · ${schedText(h.weekdays)} · ${TODS[h.time_of_day][1]}</div></div>
      <div style="text-align:right"><b>${h.streak ? "🔥 " + h.streak : "–"}</b><div class="dim small">${rank[h.id] != null ? Math.round(rank[h.id] * 100) + "% strength" : ""}</div></div></div>`).join("")
      : `<div class="card empty">No habits yet.</div>`);
}

function pTrend() {
  const D = stats.daily.slice(-page.range), best = [...D].sort((a, b) => b.rate - a.rate)[0];
  const full = D.filter(x => x.rate === 1).length;
  return `<div class="seg" style="max-width:240px;margin-bottom:12px">${[30, 90].map(n =>
      `<button class="${page.range === n ? "on" : ""}" data-do="range" data-n="${n}">${n} days</button>`).join("")}</div>
    <div class="card">${lineChart([{values: D.map(x => x.rate), color: "var(--accent)", opacity: .3, width: 1.5},
        {values: D.map(x => x.avg), color: "var(--accent)", fill: true}], {h: 240})}
      <div class="dim small" style="display:flex;justify-content:space-between"><span>${D[0]?.date ?? ""}</span><span>7-day average over daily completion</span><span>today</span></div></div>
    ${tiles([[pctText(avg(D)), `average over ${D.length} days`], [full, "perfect days"], [best ? pctText(best.rate) : "–", best ? "best day · " + best.date : "best day"],
      [pctText(avg(D.slice(-7))), "last 7 days"]])}
    ${sub("Daily")}<div class="card"><div class="dailygrid">${D.slice().reverse().slice(0, 28).map(x =>
      `<div title="${x.date}: ${x.done}/${x.total}"><i style="--p:${x.rate}"></i><span>${pd(x.date).getDate()}</span></div>`).join("")}</div>
      <div class="dim small" style="margin-top:6px">Last 28 days, newest first. Taller = more habits completed.</div></div>`;
}

function pPatterns() {
  const wk = weekdayItems(), FULL = ["Mondays","Tuesdays","Wednesdays","Thursdays","Fridays","Saturdays","Sundays"];
  const known = wk.map((x, i) => ({...x, full: FULL[i]})).filter(x => x.v != null).sort((a, b) => b.v - a.v);
  return `${sub("By day of the week · 90 days")}<div class="card">${cols(wk)}
      ${known.length > 1 ? `<p class="small">You're strongest on <b>${known[0].full}</b> (${pctText(known[0].v)}) and weakest on <b>${known.at(-1).full}</b> (${pctText(known.at(-1).v)}).</p>` : ""}</div>
    ${sub("By time of day · 30 days")}<div class="card">${cols(Object.keys(TODS).filter(k => stats.time_of_day[k] != null)
      .map(k => ({label: TODS[k][0] + " " + TODS[k][1], v: stats.time_of_day[k]})), {color: "var(--gold)"})}</div>`;
}

function pBalance() {
  return `<div class="card">${radarOrBars(300)}</div>${sub("Skills")}
    <div class="grid2">${S.categories.map(c => `<div class="card"><div class="lvlrow">${ring(c.progress, c.color, 64, 7, `<b>${c.level}</b>`)}
      <div class="grow"><b>${esc(c.name)}</b><div class="dim small">${esc(c.title)} · ${c.xp} XP</div>
      <div class="dim small">${pctText(stats.wheel.find(w => w.name === c.name)?.rate)} completion, 30 days</div></div></div></div>`).join("") ||
      '<div class="dim">Give habits a category to grow skill levels.</div>'}</div>`;
}

function pYear() {
  const months = {};
  for (const [k, v] of Object.entries(stats.heatmap)) (months[k.slice(0, 7)] ??= []).push(v);
  const items = Object.entries(months).slice(-12).map(([m, vs]) => ({label: new Date(m + "-02").toLocaleString("en", {month: "short"}),
    v: vs.reduce((a, b) => a + b, 0) / vs.length}));
  return `<div class="card">${yearHeat(stats.heatmap)}</div>${sub("Month by month")}<div class="card">${cols(items, {color: "var(--ok)"})}</div>`;
}

function pRanking() {
  const r = stats.ranking, weak = r.slice(-3).reverse();
  return `<div class="card">${rankRows(r, true)}<div class="dim small" style="margin-top:8px">Strength rewards consistency: one miss only dents it a little. Tap a habit for its full history.</div></div>
    ${r.length > 3 ? `${sub("Needs attention")}<div class="card">${rankRows(weak, true)}</div>` : ""}`;
}

function pXp() {
  const x = stats.xp_series, total = x.reduce((s, d) => s + d.xp, 0), best = [...x].sort((a, b) => b.xp - a.xp)[0], L = S.level;
  return `<div class="card">${cols(x.map(d => ({label: pd(d.date).getDate(), v: d.xp})), {pct: false, color: "var(--gold)"})}</div>
    ${tiles([[total, "XP in 30 days"], [Math.round(total / 30), "XP per day"], [best.xp, "best day · " + best.date.slice(5)], [`Lv ${L.level}`, `${L.level_span - L.into_level} XP to go`]])}
    ${sub("How XP works")}<div class="card small">
      <p>Easy habits are worth 10 XP, medium 20 and hard 35. Streaks add up to +50% at 30 days, count and minute habits give partial credit, and finishing every habit in a day pays a 25% bonus. Undoing a habit takes its XP back.</p></div>`;
}

function pMood() {
  const days = [];
  for (let i = 41; i >= 0; i--) { const k = addDays(S.today, -i); days.push([k, stats.moods[k]]); }
  const keys = Object.keys(stats.mood_rate);
  return `${sub("Last 6 weeks")}<div class="card"><div class="moodgrid">${days.map(([k, m]) =>
      `<span title="${k}">${m ? MOODS[m - 1] : "·"}</span>`).join("")}</div></div>
    ${sub("Mood vs. follow-through")}<div class="card">${keys.length >= 2 ? cols(MOODS.map((m, i) => ({label: m, v: stats.mood_rate[i + 1] ?? null})), {highlight: false, color: "var(--ok)"}) +
      `<div class="dim small" style="margin-top:8px">Average habit completion on days you logged each mood.</div>` :
      `<div class="dim">Log your mood for a few days to see how it connects to your habits.</div>`}</div>`;
}

function pStreaks() {
  const hs = [...S.habits].sort((a, b) => b.streak - a.streak || b.best_streak - a.best_streak);
  return hs.map(h => {
    const risk = h.scheduled_today && !h.done && !h.skipped_today && h.streak > 0;
    return `<div class="card hrow" data-do="open" data-id="${h.id}"><span style="font-size:28px">${esc(h.icon)}</span>
      <div class="grow"><b>${esc(h.name)}</b><div class="dim small">best ${h.best_streak} days${risk ? " · <span style='color:var(--bad)'>do it today to keep it</span>" : ""}</div></div>
      <b style="font-size:22px">${h.streak ? "🔥 " + h.streak : "–"}</b></div>`;
  }).join("") || `<div class="card empty">No habits yet.</div>`;
}

function pRewards() {
  const L = S.level, got = S.achievements.filter(a => a.unlocked_at).length;
  return `<section class="card center">
    ${ring(L.progress, "var(--gold)", 168, 14, `<span class="dim small">LEVEL</span><b style="font-size:54px;line-height:1">${L.level}</b>`)}
    <div class="lvl" style="margin-top:10px;font-size:22px">${esc(L.title)}</div>
    <div class="dim">${L.xp} XP total · ${L.level_span - L.into_level} to level ${L.level + 1}</div>
    <div class="ladder" style="width:100%">${S.titles.map(([lv, t]) => `<div class="${L.level >= lv ? "on" : ""}"><i></i>${esc(t)}<span>Lv ${lv}</span></div>`).join("")}</div>
  </section>
  ${sub("Skills")}
  <div class="grid2">${S.categories.map(c => `<div class="card"><div class="lvlrow">
      ${ring(c.progress, c.color, 56, 6, `<b>${c.level}</b>`)}
      <div class="grow"><b>${esc(c.name)}</b><div class="dim small">${esc(c.title)} · ${c.xp} XP</div></div></div></div>`).join("") ||
      '<div class="dim">Give habits a category to grow skill levels.</div>'}</div>
  <h2>Achievements <span class="grow"></span><span>${got}/${S.achievements.length}</span></h2>
  <div class="ach">${S.achievements.map(a => `<div class="card a ${a.unlocked_at ? "on" : "lock"}">
    <span class="ic">${ACH_ICON[a.key] || "🏆"}</span><b>${esc(a.title)}</b><div class="dim small">${esc(a.description)}</div></div>`).join("")}</div>`;
}

// ------------------------------------------------------------------ Sheets

function openSheet(html) {
  $("#scrim").innerHTML = `<div class="sheet" role="dialog" aria-modal="true">${html}</div>`;
  $("#scrim").classList.add("show");
}
function closeSheet() {
  $("#scrim").classList.remove("show");
  $("#scrim").innerHTML = "";
  sheet = null;
  clearInterval(timer.iv); timer = {id: null, running: false, start: 0, base: 0, iv: null};
}

async function openDetail(id, keep = false) {
  const h = S.habits.find(x => x.id === id);
  if (!h) return closeSheet();
  const d = await (await fetch(`/api/habits/${id}`)).json();
  const month = keep && sheet?.id === id ? sheet.month : S.view.slice(0, 7);
  const scroll = $(".sheet")?.scrollTop || 0;
  sheet = {kind: "detail", id, d, month};
  renderDetail(h, d, month);
  if (keep) $(".sheet").scrollTop = scroll;
}

function renderDetail(h, d, month) {
  const sc = Object.values(d.strength_series), now = d.strength, ago = sc[Math.max(0, sc.length - 31)] ?? 0;
  const diff = Math.round((now - ago) * 100);
  const wk = DAYS.map((l, i) => ({label: l, v: d.weekday_rate[i], color: h.color}));
  const weeks = d.weeks.map(w => ({label: pd(w.start).getDate(), v: w.count, color: h.color}));
  const my = month.split("-").map(Number), first = new Date(my[0], my[1] - 1, 1);
  const dim = new Date(my[0], my[1], 0).getDate(), lead = (first.getDay() + 6) % 7;
  const canNext = month < S.today.slice(0, 7);
  let cal = DAYS.map(x => `<div class="h">${x}</div>`).join("") + "<span></span>".repeat(lead);
  for (let i = 1; i <= dim; i++) {
    const key = `${month}-${String(i).padStart(2, "0")}`, st = d.calendar[key];
    const style = st === "done" ? `background:${h.color}` : st === "partial" ? `color:${h.color}` : "";
    cal += `<button class="${st || ""} ${key === S.today ? "today" : ""}" style="${style}" ${key > S.today ? "disabled" : ""}
      data-do="caltoggle" data-date="${key}" title="${key}${st ? " · " + st : ""}">${i}</button>`;
  }
  const isCount = h.type === "count", isDur = h.type === "duration";
  const quick = isDur ? [5, 10, 30].map(n => `<button class="btn" data-do="logadd" data-v="${n}">+${n}m</button>`).join("") : "";
  const mainBtn = h.done ? `<button class="btn" data-do="undo">Undo</button>` :
    isCount ? `<button class="btn hue" style="background:${h.color}" data-do="logadd" data-v="1">+1</button>
      <button class="btn" data-do="complete">Mark done</button>` :
    `<button class="btn hue" style="background:${h.color}" data-do="complete">Mark done</button>`;
  openSheet(`
    <div class="head"><span style="font-size:30px">${esc(h.icon)}</span><h3>${esc(h.name)}</h3>
      <button class="btn" data-do="edit" data-id="${h.id}">Edit</button><button class="x" data-do="close" aria-label="Close">✕</button></div>
    <div class="center">
      ${ring(now, h.color, 150, 13, `<b style="font-size:38px;line-height:1">${Math.round(now * 100)}%</b><span class="dim small">strength</span>`)}
      <div class="small" style="margin-top:8px;color:${diff >= 0 ? "var(--ok)" : "var(--bad)"}">${diff >= 0 ? "▲" : "▼"} ${Math.abs(diff)}% vs. 30 days ago</div>
    </div>
    <div class="chips">
      <div class="chip"><b>🔥 ${d.streak}</b><span class="dim small">streak</span></div>
      <div class="chip"><b>${d.best_streak}</b><span class="dim small">best</span></div>
      <div class="chip"><b>${d.completions}</b><span class="dim small">done</span></div>
      <div class="chip"><b>${pctText(d.rate_30d)}</b><span class="dim small">30 days</span></div>
      <div class="chip"><b>${d.xp}</b><span class="dim small">XP</span></div>
    </div>
    <div class="actions">${mainBtn}${quick}
      <button class="btn" data-do="${h.skipped_today ? "unskip" : "skip"}">${h.skipped_today ? "Unskip" : "Skip day"}</button></div>
    ${isDur ? `<div class="card center" style="padding:12px"><div class="timer" id="timer">${fmtTimer(timerMs(h.id))}</div>
      <div class="actions" style="margin:6px 0 0"><button class="btn primary" data-do="timer">${timer.running && timer.id === h.id ? "Pause" : "Start timer"}</button>
      <button class="btn" data-do="timerlog">Log time</button><button class="btn" data-do="timerreset">Reset</button></div></div>` : ""}
    ${h.value ? `<label class="f">Note for ${S.view === S.today ? "today" : S.view}</label>
      <textarea rows="2" id="note" placeholder="How did it go?">${esc(h.note)}</textarea>` : ""}
    <h2>Strength · 90 days</h2><div class="card">${lineChart([{values: sc, color: h.color, fill: true}], {h: 110})}</div>
    <h2>${first.toLocaleString("en", {month: "long", year: "numeric"})} <span class="grow"></span>
      <button class="x" data-do="month" data-n="-1" aria-label="Previous month">‹</button>
      <button class="x" data-do="month" data-n="1" ${canNext ? "" : "disabled"} aria-label="Next month">›</button></h2>
    <div class="card"><div class="cal">${cal}</div>
      <div class="dim small" style="margin-top:8px">Tap any day to mark it done or undo it.</div></div>
    <div class="grid2"><div><h2>By weekday</h2><div class="card">${cols(wk, {highlight: true})}</div></div>
      <div><h2>Per week</h2><div class="card">${cols(weeks, {pct: false})}</div></div></div>
    ${d.notes.length ? `<h2>Recent notes</h2>${d.notes.map(n => `<div class="card small" style="margin-bottom:8px"><span class="dim">${n.date}</span> · ${esc(n.note)}</div>`).join("")}` : ""}
    <div class="actions" style="margin-top:20px"><button class="btn danger" data-do="archive">Archive habit</button></div>`);
}

const timerMs = (id) => timer.id === id ? timer.base + (timer.running ? Date.now() - timer.start : 0) : 0;
const fmtTimer = (ms) => { const s = Math.floor(ms / 1000); return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; };

// ---- add / edit form

let form = null;
function openForm(h) {
  form = h ? {id: h.id, name: h.name, icon: h.icon, color: h.color, type: h.type, target: h.target, unit: h.unit,
      time_of_day: h.time_of_day, weekdays: [...h.weekdays], difficulty: h.difficulty, category: h.category || ""}
    : {name: "", icon: "💧", color: COLORS[S.habits.length % COLORS.length], type: "check", target: 1, unit: "",
      time_of_day: "anytime", weekdays: [0,1,2,3,4,5,6], difficulty: 1, category: ""};
  sheet = {kind: "form"};
  renderForm();
}

function seg(field, opts) {
  return `<div class="seg">${opts.map(([v, l]) => `<button class="${form[field] === v ? "on" : ""}" data-do="set" data-f="${field}" data-v="${v}">${l}</button>`).join("")}</div>`;
}

function renderForm() {
  const f = form, adding = !f.id;
  openSheet(`
    <div class="head"><h3>${adding ? "New habit" : "Edit habit"}</h3><button class="x" data-do="close" aria-label="Close">✕</button></div>
    ${adding ? `<label class="f" style="margin-top:0">Quick start</label><div class="tpl">${TEMPLATES.map((t, i) =>
      `<button data-do="tpl" data-i="${i}">${t.icon} ${esc(t.name)}</button>`).join("")}</div>` : ""}
    <label class="f">Name</label><input type="text" data-f="name" value="${esc(f.name)}" placeholder="e.g. Morning run" maxlength="40" autofocus>
    <label class="f">Icon</label><div class="emojis">${EMOJIS.map(e => `<button class="${f.icon === e ? "on" : ""}" data-do="set" data-f="icon" data-v="${e}">${e}</button>`).join("")}</div>
    <label class="f">Color</label><div class="swatches">${COLORS.map(c => `<button class="${f.color === c ? "on" : ""}" style="background:${c}" data-do="set" data-f="color" data-v="${c}" aria-label="${c}"></button>`).join("")}</div>
    <label class="f">How do you track it?</label>${seg("type", [["check", "Yes / no"], ["count", "Count"], ["duration", "Minutes"]])}
    ${f.type !== "check" ? `<div class="row2" style="margin-top:10px"><div><label class="f" style="margin-top:0">Daily goal</label>
        <input type="number" min="1" step="any" data-f="target" value="${f.target}"></div>
      ${f.type === "count" ? `<div><label class="f" style="margin-top:0">Unit</label><input type="text" data-f="unit" value="${esc(f.unit)}" placeholder="cups, pages…"></div>` : ""}</div>` : ""}
    <label class="f">When</label>${seg("time_of_day", Object.entries(TODS).map(([k, v]) => [k, `${v[0]} ${v[1]}`]))}
    <label class="f">Repeat on</label>
    <div class="days">${DAYS.map((d, i) => `<button class="${f.weekdays.includes(i) ? "on" : ""}" data-do="day-toggle" data-i="${i}">${d}</button>`).join("")}</div>
    <div class="actions" style="margin:8px 0 0"><button class="btn" data-do="days" data-v="all">Every day</button>
      <button class="btn" data-do="days" data-v="week">Weekdays</button><button class="btn" data-do="days" data-v="end">Weekends</button></div>
    <label class="f">Difficulty (more XP for harder habits)</label>${seg("difficulty", [[1, "Easy · 10"], [2, "Medium · 20"], [3, "Hard · 35"]])}
    <label class="f">Category (grows a skill level)</label><input type="text" data-f="category" value="${esc(f.category)}" placeholder="Health, Mind, Work…" list="cats" maxlength="24">
    <datalist id="cats">${S.categories.map(c => `<option value="${esc(c.name)}">`).join("")}</datalist>
    <div class="actions" style="margin-top:22px"><button class="btn primary grow" data-do="save">${adding ? "Add habit" : "Save changes"}</button></div>`);
}

// ------------------------------------------------------------------ effects

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), 2800);
}
function floater(el, text) {
  const f = document.createElement("span");
  f.className = "floater"; f.textContent = text;
  el.append(f);
  setTimeout(() => f.remove(), 1000);
}
function showLevelUp(l) {
  $("#lvnum").textContent = l.to;
  $("#lvtitle").textContent = `You're now a ${l.title}`;
  $("#levelup").classList.add("show");
  burst(null, null, 200);
}
$("#levelup").onclick = () => $("#levelup").classList.remove("show");

const cv = $("#confetti"), cx = cv.getContext("2d");
let bits = [], raf = 0;
function burst(el, color, n) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  cv.width = innerWidth; cv.height = innerHeight;
  const r = el?.getBoundingClientRect();
  const x0 = r ? r.left + r.width / 2 : innerWidth / 2, y0 = r ? r.top + 40 : innerHeight / 3;
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2, v = (r ? 3 : 6) + Math.random() * (r ? 4 : 9);
    bits.push({x: x0, y: y0, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 3, life: 70 + Math.random() * 40, rot: Math.random() * 6,
      c: color || COLORS[Math.floor(Math.random() * COLORS.length)]});
  }
  if (!raf) raf = requestAnimationFrame(tickConfetti);
  navigator.vibrate?.(15);
}
function tickConfetti() {
  cx.clearRect(0, 0, cv.width, cv.height);
  bits = bits.filter(b => b.life > 0);
  for (const b of bits) {
    b.x += b.vx; b.y += b.vy; b.vy += .22; b.vx *= .985; b.life--; b.rot += .2;
    cx.save(); cx.translate(b.x, b.y); cx.rotate(b.rot); cx.globalAlpha = Math.min(1, b.life / 30);
    cx.fillStyle = b.c; cx.fillRect(-4, -2, 8, 4); cx.restore();
  }
  raf = bits.length ? requestAnimationFrame(tickConfetti) : 0;
  if (!raf) cx.clearRect(0, 0, cv.width, cv.height);
}

// ------------------------------------------------------------------ events

const detailArgs = () => ({habit: sheet.id, ...(viewDate ? {date: viewDate} : {})});
const ctxOf = () => ({id: sheet.id});

const handlers = {
  page: (el) => go(el.dataset.p),
  back: () => { if (navigated) history.back(); else location.hash = ""; },
  range: (el) => { page.range = +el.dataset.n; renderPage(); },
  day: (el, e) => { e.preventDefault(); const d = el.dataset.date; viewDate = d === S.today ? null : d; load(); },
  week: (el) => {
    const t = addDays(S.view, +el.dataset.n);
    viewDate = t >= S.today ? null : t; load();
  },
  mood: (el) => act("mood.set", {mood: +el.dataset.v, ...(viewDate ? {date: viewDate} : {})}),
  tap: (el) => {
    if (holdFired) { holdFired = false; return; }
    const id = +el.dataset.id, h = S.habits.find(x => x.id === id), a = viewDate ? {date: viewDate} : {};
    if (h.skipped_today) return act("habit.unskip", {habit: id, ...a}, {id});
    if (h.type === "duration") return openDetail(id);
    if (h.done) return act("habit.undo", {habit: id, ...a}, {id});
    if (h.type === "count") return act("habit.log", {habit: id, value: 1, ...a}, {id});
    act("habit.complete", {habit: id, ...a}, {id});
  },
  open: (el) => openDetail(+el.dataset.id),
  close: closeSheet,
  add: () => openForm(null),
  edit: (el) => openForm(S.habits.find(h => h.id === +el.dataset.id)),
  complete: () => act("habit.complete", detailArgs(), ctxOf()),
  undo: () => act("habit.undo", detailArgs(), ctxOf()),
  logadd: (el) => act("habit.log", {...detailArgs(), value: +el.dataset.v}, ctxOf()),
  skip: () => act("habit.skip", detailArgs(), ctxOf()),
  unskip: () => act("habit.unskip", detailArgs(), ctxOf()),
  archive: async () => { if (confirm("Archive this habit? Your history is kept.")) { await act("habit.archive", {habit: sheet.id}); closeSheet(); } },
  caltoggle: (el) => {
    const h = S.habits.find(x => x.id === sheet.id), st = sheet.d.calendar[el.dataset.date];
    act(st === "done" ? "habit.undo" : "habit.complete", {habit: h.id, date: el.dataset.date}, ctxOf());
  },
  month: (el) => {
    const [y, m] = sheet.month.split("-").map(Number), n = +el.dataset.n, d = new Date(y, m - 1 + n, 1);
    sheet.month = ds(d).slice(0, 7); renderDetail(S.habits.find(x => x.id === sheet.id), sheet.d, sheet.month);
  },
  timer: () => {
    const id = sheet.id;
    if (timer.id !== id) timer = {id, running: false, start: 0, base: 0, iv: null};
    if (timer.running) { timer.base += Date.now() - timer.start; timer.running = false; clearInterval(timer.iv); }
    else {
      timer.start = Date.now(); timer.running = true;
      timer.iv = setInterval(() => { const t = $("#timer"); if (t) t.textContent = fmtTimer(timerMs(id)); }, 500);
    }
    renderDetail(S.habits.find(x => x.id === id), sheet.d, sheet.month);
  },
  timerlog: async () => {
    const mins = Math.round(timerMs(sheet.id) / 60000);
    if (mins < 1) return toast("Run the timer for at least a minute first");
    clearInterval(timer.iv); timer = {id: null, running: false, start: 0, base: 0, iv: null};
    await act("habit.log", {...detailArgs(), value: mins}, ctxOf());
  },
  timerreset: () => { clearInterval(timer.iv); timer = {id: null, running: false, start: 0, base: 0, iv: null}; renderDetail(S.habits.find(x => x.id === sheet.id), sheet.d, sheet.month); },
  set: (el) => { const v = el.dataset.v; form[el.dataset.f] = ["difficulty"].includes(el.dataset.f) ? +v : v;
    if (el.dataset.f === "type") { form.unit = v === "duration" ? "m" : ""; form.target = v === "check" ? 1 : v === "duration" ? 20 : 8; }
    renderForm(); },
  tpl: (el) => { Object.assign(form, {type: "check", target: 1, unit: "", time_of_day: "anytime", difficulty: 1, category: ""}, TEMPLATES[+el.dataset.i]); renderForm(); },
  "day-toggle": (el) => { const i = +el.dataset.i, w = form.weekdays; form.weekdays = w.includes(i) ? w.filter(x => x !== i) : [...w, i].sort(); renderForm(); },
  days: (el) => { form.weekdays = {all: [0,1,2,3,4,5,6], week: [0,1,2,3,4], end: [5,6]}[el.dataset.v]; renderForm(); },
  save: async () => {
    if (!form.name.trim()) return toast("Give your habit a name");
    if (!form.weekdays.length) return toast("Pick at least one day");
    const args = {name: form.name.trim(), icon: form.icon, color: form.color, type: form.type, target: +form.target || 1,
      unit: form.unit, time_of_day: form.time_of_day, weekdays: form.weekdays, difficulty: form.difficulty, category: form.category.trim()};
    const out = form.id ? await act("habit.update", {habit: form.id, ...args}) : await act("habit.create", args);
    if (out) { closeSheet(); toast(form.id ? "Saved" : "Habit added 🎉"); }
  },
};

let holdFired = false, holdTimer = 0;
document.addEventListener("pointerdown", (e) => {
  const b = e.target.closest('.ringbtn[data-do="tap"]');
  if (!b) return;
  holdFired = false;
  holdTimer = setTimeout(() => { holdFired = true; navigator.vibrate?.(20); openDetail(+b.dataset.id); }, 480);
});
["pointerup", "pointerleave", "pointercancel", "scroll"].forEach(t => document.addEventListener(t, () => clearTimeout(holdTimer), true));

document.addEventListener("click", (e) => {
  if (e.target === $("#scrim")) return closeSheet();
  const el = e.target.closest("[data-do]");
  if (el && handlers[el.dataset.do]) handlers[el.dataset.do](el, e);
});
document.addEventListener("input", (e) => {
  const f = e.target.dataset?.f;
  if (f && form) form[f] = e.target.type === "number" ? e.target.value : e.target.value;
});
document.addEventListener("focusout", (e) => {
  if (e.target.id === "note" && sheet?.kind === "detail") {
    act("habit.note", {...detailArgs(), note: e.target.value});
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (sheet) closeSheet();
  else if (page) handlers.back();
  $("#levelup").classList.remove("show");
});
addEventListener("hashchange", syncPage);
oncontextmenu = (e) => { if (e.target.closest(".ringbtn")) e.preventDefault(); };

if (location.search.includes("wall=1")) document.body.classList.add("wall");
// deep links: #/trend (any widget page), #habit=3, #new
const hash = location.hash.slice(1);
syncPage();
load().then(() => {
  if (hash.startsWith("habit=")) openDetail(+hash.slice(6));
  if (hash === "new") openForm(null);
});
setInterval(() => { if (!sheet && S && S.today !== ds(new Date(Date.now() - 4 * 3600e3))) window.refresh(); }, 60000);
