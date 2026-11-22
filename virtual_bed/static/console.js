"use strict";
// Operator console: drag the mat and the person, watch the live mat, and
// follow each transmitted frame through Python, the CNN, Firestore and phones.

const $ = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";
const MAT_W = 76.8, MAT_L = 185.6; // cm
const BED_W = 152, BED_L = 203;
const NAMES = { Supine: "On back", Right: "Right side", Left: "Left side" };
const POSTURE = { back: "On back", left: "Left side", right: "Right side" };
const MODEL_TO_POSTURE = { Supine: "back", Right: "right", Left: "left" };

let live = null;
let body = null;
let drag = null; // {kind, ...}
let local = { mat: null, person: null, theta: null };
let lastFrameId = null;
let sliderActive = false;
const scratch = document.createElement("canvas");
scratch.width = 32;
scratch.height = 64;
const offCanvas = document.createElement("canvas");

// ---------- requests ----------
async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (e) { /* keep status */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json();
}

// Scene updates: at most one request in flight; repeated moves coalesce.
const queue = [];
let busy = false;
function sceneOp(op) {
  const last = queue[queue.length - 1];
  if (last && last.op === op.op && /move|rotate/.test(op.op)) queue[queue.length - 1] = op;
  else queue.push(op);
  pump();
}
async function pump() {
  if (busy || !queue.length) return;
  busy = true;
  const op = queue.shift();
  try {
    await post("/api/scene", op);
    $("txError").textContent = live && live.link.error ? live.link.error : "";
  } catch (e) {
    $("txError").textContent = e.message;
  } finally {
    busy = false;
    if (queue.length) pump();
    else if (!drag) local = { mat: null, person: null, theta: null };
  }
}

// ---------- geometry ----------
const svg = $("bed");
function toBed(evt) {
  const pt = svg.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  return { x: p.x, y: p.y }; // centimetres
}
function overBed(evt) {
  const p = toBed(evt);
  const r = svg.getBoundingClientRect();
  const inside = evt.clientX >= r.left && evt.clientX <= r.right && evt.clientY >= r.top && evt.clientY <= r.bottom;
  return inside && p.x >= -4 && p.x <= BED_W + 4 && p.y >= -4 && p.y <= BED_L + 4;
}
function overTools(evt) {
  const r = $("tools").getBoundingClientRect();
  return evt.clientX >= r.left && evt.clientX <= r.right && evt.clientY >= r.top && evt.clientY <= r.bottom;
}
function el(tag, attrs, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

// ---------- mat layer ----------
let matG = null;
function ensureMat() {
  if (matG) return matG;
  matG = el("g", { class: "draggable", id: "matG" }, $("matLayer"));
  el("rect", { x: -2.2, y: -2.2, width: MAT_W + 4.4, height: MAT_L + 4.4, rx: 2.2, fill: "#252d4c" }, matG);
  el("rect", { x: 0, y: 0, width: MAT_W, height: MAT_L, fill: "#333d61" }, matG);
  el("image", { id: "matHeat", x: 0, y: 0, width: MAT_W, height: MAT_L, preserveAspectRatio: "none", style: "image-rendering:pixelated" }, matG);
  el("rect", { x: 0, y: 0, width: MAT_W, height: MAT_L, fill: "url(#cells)" }, matG);
  el("rect", { x: 0, y: 0, width: MAT_W, height: MAT_L, fill: "url(#major)" }, matG);
  matG.addEventListener("pointerdown", startMatDrag);
  return matG;
}
function removeMat() {
  if (matG) matG.remove();
  matG = null;
}

// ---------- person layer ----------
let personG = null, figBack = null, figSide = null, sideKind = null;
let figureCount = 0;
function figure(parent, segments) {
  // Silhouette = union of capsules. A mask turns it into a crisp outline over a
  // faint fill, so the pressure underneath stays readable.
  const id = "fig" + figureCount++;
  const g = el("g", { class: "fig" }, parent);
  const mask = el("mask", { id, maskUnits: "userSpaceOnUse", x: -120, y: -120, width: 240, height: 240 }, g);
  const caps = (target, color, extra) => {
    for (const s of segments) {
      el("line", {
        x1: s.b0 * 100, y1: s.a0 * 100, x2: s.b1 * 100, y2: s.a1 * 100,
        stroke: color, "stroke-width": s.w * 100 * 2.15 + extra, "stroke-linecap": "round",
      }, target);
    }
  };
  caps(mask, "#fff", 1.3);
  caps(mask, "#000", 0);
  const fill = el("g", { opacity: 0.16 }, g);
  caps(fill, "#ffffff", 0);
  el("rect", { x: -120, y: -120, width: 240, height: 240, fill: "#e9edf8", mask: `url(#${id})` }, g);
  const rim = el("g", { opacity: 0.55 }, g);
  el("rect", { x: -120, y: -120, width: 240, height: 240, fill: "#1b2550", mask: `url(#${id})`, transform: "translate(0.25 0.25)" }, rim);
  return g;
}
function ensurePerson() {
  if (personG || !body) return personG;
  personG = el("g", { id: "personG" }, $("personLayer"));
  const hit = el("g", { class: "draggable" }, personG);
  figBack = figure(hit, body.back);
  figSide = el("g", {}, hit);
  el("circle", { cx: 0, cy: 0, r: 1.6, fill: "none", stroke: "#1b2550", "stroke-width": 0.5 }, hit);
  el("line", { x1: 0, y1: -84, x2: 0, y2: -94, stroke: "#1b2550", "stroke-width": 0.5, "stroke-dasharray": "1 1" }, personG);
  const handle = el("circle", { cx: 0, cy: -97, r: 3.6, fill: "#ffffff", stroke: "#1b2550", "stroke-width": 0.8, class: "draggable" }, personG);
  const t = el("title", {}, handle);
  t.textContent = "Drag to turn the person";
  el("path", { d: "M-1.6 -97.6a1.7 1.7 0 1 1 0.4 1.6", fill: "none", stroke: "#1b2550", "stroke-width": 0.5 }, personG).style.pointerEvents = "none";
  hit.addEventListener("pointerdown", startPersonDrag);
  handle.addEventListener("pointerdown", startRotate);
  return personG;
}
function removePerson() {
  if (personG) personG.remove();
  personG = figBack = figSide = sideKind = null;
}

// ---------- dragging ----------
function capture(evt, state) {
  evt.preventDefault();
  evt.stopPropagation();
  drag = state;
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp, { once: true });
}
function startMatDrag(evt) {
  if (!live || !live.scene.mat) return;
  const p = toBed(evt), m = live.scene.mat;
  matG.classList.add("dragging");
  capture(evt, { kind: "mat", dx: p.x - m.x * 100, dy: p.y - m.y * 100 });
}
function startPersonDrag(evt) {
  if (!live || !live.scene.person) return;
  const p = toBed(evt), s = live.scene.person;
  capture(evt, { kind: "person", dx: p.x - s.x * 100, dy: p.y - s.y * 100 });
}
function startRotate(evt) {
  if (!live || !live.scene.person) return;
  capture(evt, { kind: "rotate" });
}
function onMove(evt) {
  if (!drag) return;
  if (drag.kind === "tool") {
    drag.ghost.style.left = evt.clientX + "px";
    drag.ghost.style.top = evt.clientY + "px";
    return;
  }
  const p = toBed(evt);
  if (drag.kind === "mat") {
    const x = clamp((p.x - drag.dx) / 100, 0, (BED_W - MAT_W) / 100);
    const y = clamp((p.y - drag.dy) / 100, 0, (BED_L - MAT_L) / 100);
    local.mat = { x, y };
    $("tools").classList.toggle("drop-target", overTools(evt));
    sceneOp({ op: "move_mat", x, y });
  } else if (drag.kind === "person") {
    const x = (p.x - drag.dx) / 100, y = (p.y - drag.dy) / 100;
    local.person = { x, y };
    $("tools").classList.toggle("drop-target", overTools(evt));
    sceneOp({ op: "move_person", x, y });
  } else if (drag.kind === "rotate") {
    const s = live.scene.person;
    const theta = (Math.atan2(p.x - s.x * 100, -(p.y - s.y * 100)) * 180) / Math.PI;
    local.theta = Math.round(theta);
    sceneOp({ op: "rotate", theta: local.theta });
  }
  render();
}
function onUp(evt) {
  window.removeEventListener("pointermove", onMove);
  const d = drag;
  drag = null;
  $("tools").classList.remove("drop-target");
  if (matG) matG.classList.remove("dragging");
  if (!d) return;
  if (d.kind === "tool") {
    d.ghost.remove();
    if (overBed(evt)) {
      const p = toBed(evt);
      if (d.tool === "mat") sceneOp({ op: "place_mat", x: (p.x - MAT_W / 2) / 100, y: (p.y - MAT_L / 2) / 100 });
      else sceneOp({ op: "place_person", x: p.x / 100, y: p.y / 100 });
    }
    return;
  }
  if (d.kind === "mat" && overTools(evt)) sceneOp({ op: "remove_mat" });
  if (d.kind === "person" && overTools(evt)) sceneOp({ op: "get_up" });
}
function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

for (const tile of document.querySelectorAll(".tool")) {
  tile.addEventListener("pointerdown", (evt) => {
    if (tile.dataset.placed === "true") return;
    if (tile.dataset.tool === "person" && !(live && live.scene.mat)) {
      $("toolHint").textContent = "Place the mat first. The person lies on the mat.";
    }
    const ghost = tile.querySelector("svg").cloneNode(true);
    ghost.classList.add("ghost");
    const scale = svg.getScreenCTM().a; // px per cm
    if (tile.dataset.tool === "mat") {
      ghost.style.width = MAT_W * scale + "px";
      ghost.style.height = MAT_L * scale + "px";
    } else {
      ghost.style.width = 62 * scale + "px";
      ghost.style.height = 175 * scale + "px";
    }
    ghost.style.left = evt.clientX + "px";
    ghost.style.top = evt.clientY + "px";
    document.body.appendChild(ghost);
    capture(evt, { kind: "tool", tool: tile.dataset.tool, ghost });
  });
  tile.addEventListener("keydown", (evt) => {
    if (evt.key !== "Enter" && evt.key !== " ") return;
    evt.preventDefault();
    if (tile.dataset.placed === "true") return;
    if (tile.dataset.tool === "mat") sceneOp({ op: "place_mat", x: (BED_W - MAT_W) / 200, y: (BED_L - MAT_L) / 200 });
    else if (live && live.scene.mat) sceneOp({ op: "place_person", x: live.scene.mat.x + MAT_W / 200, y: live.scene.mat.y + 0.89 });
    else sceneOp({ op: "place_person", x: 0.76, y: 0.98 });
  });
}

// ---------- controls ----------
for (const b of document.querySelectorAll("#posture button")) {
  b.addEventListener("click", () => sceneOp({ op: "posture", posture: b.dataset.posture }));
}
function setSource(body) {
  post("/api/source", body).catch((e) => { $("txError").textContent = e.message; });
}
for (const b of document.querySelectorAll("#sourceMode button")) {
  b.addEventListener("click", () => setSource({ mode: b.dataset.mode }));
}
for (const b of document.querySelectorAll("#subject button")) {
  b.addEventListener("click", () => setSource({ mode: "recordings", subject: Number(b.dataset.subject) }));
}
for (const b of document.querySelectorAll("#recPosture button")) {
  b.addEventListener("click", () => setSource({ mode: "recordings", posture: b.dataset.rec }));
}
const recording = () => live && live.source && live.source.mode === "recordings";
$("tourBtn").addEventListener("click", () => setSource({ mode: "recordings" }));

$("turn").addEventListener("input", (e) => {
  sliderActive = true;
  local.theta = Number(e.target.value);
  sceneOp({ op: "rotate", theta: local.theta });
  render();
});
$("turn").addEventListener("change", () => { sliderActive = false; });
$("centre").addEventListener("click", () => sceneOp({ op: "centre" }));
$("getUp").addEventListener("click", () => sceneOp({ op: "get_up" }));
$("transmit").addEventListener("click", toggleTransmit);
function toggleTransmit() {
  if (!live) return;
  post("/api/transmit", { action: live.link.streaming ? "pause" : "start" })
    .catch((e) => { $("txError").textContent = e.message; });
}
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey) return;
  const s = live && live.scene.person;
  const step = e.shiftKey ? 0.05 : 0.01;
  const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
  if (moves[e.key] && s) {
    e.preventDefault();
    const base = local.person || s;
    local.person = { x: base.x + moves[e.key][0], y: base.y + moves[e.key][1] };
    sceneOp({ op: "move_person", ...local.person });
  } else if ((e.key === "[" || e.key === "]") && s) {
    const base = local.theta ?? s.theta;
    local.theta = Math.round(base + (e.key === "]" ? 5 : -5));
    sceneOp({ op: "rotate", theta: local.theta });
  } else if ("blr".includes(e.key.toLowerCase()) && e.key.length === 1 && recording()) {
    setSource({ mode: "recordings", posture: { b: "back", l: "left", r: "right" }[e.key.toLowerCase()] });
  } else if ("blr".includes(e.key.toLowerCase()) && e.key.length === 1) {
    sceneOp({ op: "posture", posture: { b: "back", l: "left", r: "right" }[e.key.toLowerCase()] });
  } else if (e.key.toLowerCase() === "u") {
    sceneOp({ op: "get_up" });
  } else if (e.key === " " && !e.target.closest("button, [role=button]")) {
    e.preventDefault();
    toggleTransmit();
  } else return;
  render();
});

// ---------- rendering ----------
function fmtTime(ms) {
  const d = new Date(ms);
  return d.toLocaleTimeString([], { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}
function pct(v) { return v == null ? "–" : (v * 100).toFixed(v > 0.995 && v < 1 ? 1 : 0) + "%"; }

function renderBed() {
  const sc = live.scene;
  const mat = sc.mat && (local.mat || sc.mat);
  if (mat) {
    ensureMat();
    matG.setAttribute("transform", `translate(${mat.x * 100} ${mat.y * 100})`);
    Heat.draw(scratch, live.counts);
    $("matHeat").setAttribute("href", scratch.toDataURL());
  } else removeMat();

  // True contact outside the sensing area, drawn in grey ink: real, unmeasured.
  const [h, w] = live.field_shape || [68, 51];
  offCanvas.width = w;
  offCanvas.height = h;
  const ctx = offCanvas.getContext("2d");
  const img = ctx.createImageData(w, h);
  let any = false;
  for (let i = 0; i < live.field.length; i++) {
    const v = live.field[i] / 10;
    if (v < 1) continue;
    const x = (i % w) * 3 + 1.5, y = Math.floor(i / w) * 3 + 1.5;
    if (mat && x > mat.x * 100 && x < mat.x * 100 + MAT_W && y > mat.y * 100 && y < mat.y * 100 + MAT_L) continue;
    any = true;
    img.data[i * 4] = 27; img.data[i * 4 + 1] = 37; img.data[i * 4 + 2] = 80;
    img.data[i * 4 + 3] = Math.round(60 + 150 * Heat.pos(v));
  }
  ctx.putImageData(img, 0, 0);
  $("offmat").setAttribute("href", any ? offCanvas.toDataURL() : "");

  const p = recording() ? null : sc.person;
  if (p) {
    ensurePerson();
    if (!personG) return;
    const pos = local.person || p;
    const theta = local.theta ?? p.theta;
    personG.setAttribute("transform", `translate(${pos.x * 100} ${pos.y * 100}) rotate(${theta})`);
    const kind = p.roll < 0 ? "left" : "right";
    if (kind !== sideKind) {
      figSide.replaceChildren();
      figure(figSide, body[kind]);
      sideKind = kind;
    }
    const t = smooth(Math.abs(p.roll));
    figBack.setAttribute("opacity", (1 - t).toFixed(3));
    figSide.setAttribute("opacity", t.toFixed(3));
  } else removePerson();

  const src = live.source || {};
  const banner = $("recBanner");
  banner.hidden = !recording();
  if (recording()) {
    banner.innerHTML = "";
    const b = document.createElement("b");
    b.textContent = `Person ${src.subject}, ${POSTURE[src.posture].toLowerCase()}`;
    banner.append(b, src.auto
      ? ` (automatic tour, recording ${src.tour_step} of ${src.tour_len}, next in ${src.clip_left} s)`
      : ` (real recording, frame ${src.row} of ${src.rows})`);
  }
  $("stageTitle").textContent = recording() ? "Real mat recording, seen from above" : "Bed, seen from above";
  $("stageSub").textContent = recording()
    ? "PhysioNet PmatData, a person the CNN never saw. Head at the top."
    : "Head of the bed at the top. Queen mattress 152 × 203 cm.";
  $("emptyHint").textContent = recording() ? "" : !sc.mat
    ? "Drag the pressure mat from the toolbox onto the bed."
    : !sc.person ? "Drag the person onto the mat. With nobody on it, every sensor reads zero." : "";
}
function smooth(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }

function renderReadout() {
  const m = live.measure, t = live.truth || {};
  const on = !!live.scene.mat;
  $("rPeak").textContent = on ? m.peak_mmhg.toFixed(1) + " mmHg" : "No mat";
  $("rLoad").textContent = on ? m.load_kg.toFixed(1) + " kg" : "–";
  $("rArea").textContent = on ? (m.contact_area_m2 * 10000).toFixed(0) + " cm²" : "–";
  $("rCov").textContent = recording() ? "Real recording" : !live.scene.person ? "Nobody on bed" : !on ? "0%" : pct(t.coverage);
}

function renderControls() {
  const sc = live.scene;
  const src = live.source || { mode: "bed" };
  for (const b of document.querySelectorAll("#sourceMode button")) b.setAttribute("aria-pressed", String(b.dataset.mode === src.mode));
  for (const b of document.querySelectorAll("#subject button")) b.setAttribute("aria-pressed", String(!src.auto && Number(b.dataset.subject) === src.subject));
  for (const b of document.querySelectorAll("#recPosture button")) b.setAttribute("aria-pressed", String(!src.auto && b.dataset.rec === src.posture));
  $("tourBtn").classList.toggle("primary", !!src.auto);
  $("tourBtn").textContent = src.auto ? "Touring all recordings" : "Tour all automatically";
  document.querySelector(".rec-only").hidden = !recording();
  document.querySelector(".bed-only").hidden = recording();
  $("sourceHint").textContent = recording()
    ? "Stream real pressure maps of people the model was never trained on."
    : "Generate new pressure maps by moving a virtual person.";
  $("toolMat").dataset.placed = String(!!sc.mat);
  $("toolPerson").dataset.placed = String(!!sc.person);
  $("toolHint").textContent = !sc.mat
    ? "Drag the mat onto the bed first, then the person."
    : !sc.person ? "Now drag the person onto the mat." : "Drag a tool back here to take it off the bed.";
  for (const b of document.querySelectorAll("#posture button")) {
    b.setAttribute("aria-pressed", String(b.dataset.posture === sc.posture));
    b.disabled = !sc.person;
  }
  $("turn").disabled = $("getUp").disabled = !sc.person;
  $("centre").disabled = !(sc.person && sc.mat);
  if (sc.person && !sliderActive && drag?.kind !== "rotate") {
    const th = local.theta ?? sc.person.theta;
    $("turn").value = th;
  }
  $("turnOut").textContent = sc.person ? Math.round(local.theta ?? sc.person.theta) + "°" : "–";

  const L = live.link;
  const btn = $("transmit");
  btn.textContent = L.streaming ? "Pause transmission" : "Start transmitting";
  btn.classList.toggle("pause", L.streaming);
  $("txState").textContent = L.streaming
    ? `Sending frame ${L.pending ?? L.next_seq} next. ${L.sent} of ${L.cap} sent in this run.`
    : `Paused. The next frame will be number ${L.pending ?? L.next_seq}.`;
  const r = live.remote;
  const fromPhone = r && live.server_ms - r.at_ms < 8000
    ? `${r.device} asked to ${r.action === "source"
      ? (r.mode === "recordings" ? `play person ${r.subject}, ${POSTURE[r.posture].toLowerCase()}` : "use the virtual bed")
      : r.action}.`
    : "";
  $("txNote").textContent = L.drop ? "Link loss is switched on in Diagnostics. Frames are numbered but never arrive." : fromPhone || L.note;
  if (L.error || !busy) $("txError").textContent = L.error;

  const pill = $("streamPill");
  const state = L.error ? ["error", "Retrying"] : L.drop && L.streaming ? ["stale", "Link down"]
    : L.streaming && sc.mat ? ["live", "Transmitting"] : L.streaming ? ["stale", "Waiting for mat"] : ["", "Paused"];
  pill.className = "pill " + state[0];
  pill.textContent = state[1];
  $("where").textContent = live.hosted
    ? `Firebase project ${live.project}, session ${live.session}`
    : `Local Firebase emulator, session ${live.session}`;
}

function setStage(name, cls, text) {
  const li = document.querySelector(`#chain li[data-stage="${name}"]`);
  li.className = cls;
  li.querySelector(".what").textContent = text;
}

function renderMonitor() {
  const f = live.frame;
  const L = live.link;
  if (!f) return;
  const isNew = f.frame_id !== lastFrameId;
  lastFrameId = f.frame_id;
  Heat.draw($("frameMap"), f.values);
  $("frameId").textContent = f.frame_id;
  $("frameTime").textContent = `Captured ${fmtTime(f.captured_ms)}`;
  const est = $("estimate");
  if (f.prediction) {
    est.textContent = NAMES[f.prediction] || f.prediction;
    est.classList.remove("none");
  } else {
    est.textContent = f.source === "interactive_virtual_mat" ? "No load on the mat" : "No prediction";
    est.classList.add("none");
  }
  const bars = $("bars");
  bars.replaceChildren();
  if (f.scores && f.scores.length) {
    const top = f.scores.indexOf(Math.max(...f.scores));
    f.labels.forEach((label, i) => {
      const row = document.createElement("div");
      row.className = "bar-row" + (i === top ? " lead" : "");
      row.innerHTML = `<span></span><div class="track"><div class="fill"></div></div><span></span>`;
      row.children[0].textContent = NAMES[label] || label;
      row.querySelector(".fill").style.transform = `scaleX(${f.scores[i].toFixed(4)})`;
      row.children[2].textContent = (f.scores[i] * 100).toFixed(1) + "%";
      bars.appendChild(row);
    });
  } else {
    const p = document.createElement("p");
    p.className = "small";
    p.textContent = "Every sensor read zero, so the CNN was not run. It only learned occupied-bed postures.";
    bars.appendChild(p);
  }
  const sim = f.simulator || {};
  if (f.recording) {
    const [subj] = f.recording.replace("S", "").split("-");
    $("selectedLabel").textContent = "Label in the dataset";
    $("agreementLabel").textContent = "Model compared with the label";
    $("coverageLabel").textContent = "Recording";
    $("selected").textContent = NAMES[f.recorded_label] || "–";
    const ag = $("agreement");
    if (f.prediction && f.recorded_label) {
      const same = f.prediction === f.recorded_label;
      ag.innerHTML = `<span class="agree ${same ? "yes" : "no"}">${same ? "Matches" : "Differs"}</span>`;
    } else ag.textContent = "–";
    $("coverage").textContent = `Person ${subj} (unseen), frame ${f.row}`;
  } else {
  $("selectedLabel").textContent = "Posture you selected";
  $("agreementLabel").textContent = "Model compared with your setting";
  $("coverageLabel").textContent = "Body load on the sensing area";
  $("selected").textContent = sim.person_on_bed ? POSTURE[sim.posture_selected] + (Math.abs(sim.roll) % 1 > 0.01 ? " (rolling)" : "") : "Nobody on the bed";
  const ag = $("agreement");
  if (f.prediction && sim.person_on_bed) {
    const same = MODEL_TO_POSTURE[f.prediction] === sim.posture_selected;
    ag.innerHTML = `<span class="agree ${same ? "yes" : "no"}">${same ? "Matches" : "Differs"}</span>`;
  } else ag.textContent = "–";
  $("coverage").textContent = sim.person_on_bed ? pct(sim.coverage) : "–";
  }

  const env = live.envelope || { ok: true, reasons: [] };
  const box = $("envelope");
  box.classList.toggle("out", !env.ok);
  if (recording() || !live.scene.mat || !live.scene.person) {
    box.textContent = env.reasons[0] || "";
  } else if (env.ok) {
    box.textContent = "Current placement is inside the conditions the CNN was trained on.";
  } else {
    box.innerHTML = "Current placement is outside the CNN’s training conditions, so treat its estimate with caution:<ul></ul>";
    for (const r of env.reasons) {
      const li = document.createElement("li");
      li.textContent = r;
      box.querySelector("ul").appendChild(li);
    }
  }

  // Signal chain
  const m = f.measurement || {};
  setStage("sensor", "ok", `Frame ${f.seq} captured ${fmtTime(f.captured_ms)}. Peak ${m.peak_mmhg ?? "–"} mmHg, ${m.contact_cells ?? 0} loaded sensors.`);
  const v = f.validation;
  const lost = L.stages.python && L.stages.python.status === "lost";
  if (L.error) setStage("python", "bad", L.error);
  else if (lost) setStage("python", "warn", `Frame ${L.stages.sensor?.seq} was lost on the link. Python will report the gap when frames return.`);
  else if (v) {
    const flags = (f.input_flags || []).length ? ` Flags: ${f.input_flags.join(", ").replaceAll("_", " ")}.` : "";
    setStage("python", v.sequence.startsWith("gap") ? "warn" : "ok",
      `${v.cells.toLocaleString()} values in range, sequence ${v.sequence}, ${f.api_ms} ms.${flags}`);
  }
  if (f.model_status === "ran") {
    const top = Math.max(...f.scores);
    setStage("cnn", "ok", `${NAMES[f.prediction]} at ${(top * 100).toFixed(1)}% in ${f.inference_ms.toFixed(1)} ms. Model ${f.model}.`);
  } else setStage("cnn", "ok", "Not run: the mat reads zero everywhere.");
  setStage("firestore", "ok", `Committed to state/latest and history ${f.latency_ms} ms after capture.`);

  const phone = (live.phones || [])[0];
  if (!phone) setStage("phone", "", "No phone has reported yet. Sign in on the phone app.");
  else {
    const behind = f.seq - phone.seq;
    const age = (live.server_ms - phone.rendered_ms) / 1000;
    const who = `${phone.device || phone.platform}${phone.physical_device ? " (physical phone)" : " (not a physical phone)"}`;
    if (behind <= 1 && age < 4) {
      const lag = phone.seq === f.seq ? `, ${Math.max(0, phone.rendered_ms - f.processed_ms)} ms after commit` : "";
      setStage("phone", "ok", `${who} is showing frame ${phone.seq}${lag}.`);
    } else setStage("phone", "warn", `${who} last showed frame ${phone.seq}, ${age.toFixed(0)} s ago.`);
  }
  if (isNew) {
    for (const li of document.querySelectorAll("#chain li")) {
      li.classList.remove("flash");
      void li.offsetWidth;
      li.classList.add("flash");
    }
  }
}

function render() {
  if (!live) return;
  renderBed();
  renderReadout();
  renderControls();
  renderMonitor();
}

async function poll() {
  try {
    const r = await fetch("/api/live", { cache: "no-store" });
    if (!r.ok) throw new Error("Console service returned " + r.status);
    live = await r.json();
    render();
  } catch (e) {
    $("streamPill").className = "pill error";
    $("streamPill").textContent = "Console offline";
    $("txError").textContent = "The console service is not responding. Check the terminal running the launcher.";
  }
  setTimeout(poll, 70);
}

function legend() {
  $("legendBar").style.background = Heat.gradientCss();
  const ticks = document.querySelector(".legend .ticks");
  ticks.replaceChildren();
  for (const t of Heat.TICKS) {
    const s = document.createElement("span");
    s.textContent = t === 100 ? "100+" : String(t);
    s.style.left = Heat.pos(t) * 100 + "%";
    ticks.appendChild(s);
  }
}

legend();
fetch("/api/body").then((r) => r.json()).then((b) => { body = b; render(); });
poll();
