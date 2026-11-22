import React, { useEffect, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  Platform,
  useWindowDimensions,
  KeyboardAvoidingView,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as Device from "expo-device";
import Svg, { Polyline, Rect } from "react-native-svg";
import { signInWithEmailAndPassword, signOut, onAuthStateChanged, User } from "firebase/auth";
import {
  doc,
  onSnapshot,
  collection,
  query,
  orderBy,
  limit,
  setDoc,
  serverTimestamp,
} from "firebase/firestore";
import { C, NAMES, POSTURE, MODEL_TO_POSTURE, POSTURE_COLOR } from "./src/theme";
import { Heatmap, Legend } from "./src/heat";
import { auth, db, projectId, SESSION, EMULATED } from "./src/firebase";

const STALE_MS = 3500;

type Measurement = {
  peak_mmhg: number;
  contact_cells: number;
  contact_area_m2: number;
  mean_contact_mmhg: number;
  load_n: number;
  load_kg: number;
  edge_load_fraction: number;
};
type Frame = {
  seq: number;
  frame_id: string;
  digest?: string;
  values: number[];
  captured_ms: number;
  received_ms: number;
  processed_ms: number;
  first_ms: number;
  count: number;
  missing: number;
  duplicates: number;
  out_of_order: number;
  gap_frames?: number;
  latency_ms: number;
  inference_ms: number;
  api_ms?: number;
  prediction: string | null;
  labels: string[];
  scores: number[];
  source: string;
  model: string;
  model_status?: string;
  unit?: string;
  measurement?: Measurement;
  input_flags?: string[];
  validation?: { sequence: string; cells: number; clock_skew_ms: number };
  simulator?: {
    person_on_bed: boolean;
    posture_selected: string | null;
    roll: number;
    coverage: number | null;
  };
  scenario?: string;
  recording?: string;
  row?: number;
  recorded_label?: "Supine" | "Right" | "Left" | null;
  playlist?: "tour" | "single";
  resumed: boolean;
};

const FLAG_TEXT: Record<string, string> = {
  load_at_mat_edge: "Pressure reaches the edge of the mat, so part of the body may be off the sensing area.",
  small_contact_area: "Very little of the mat is loaded.",
  above_model_cap: "Some sensors exceed 100 mmHg, the CNN's input ceiling.",
};

function clock(ms: number) {
  const d = new Date(ms);
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}
const pct = (v: number | null | undefined, digits = 0) =>
  v == null ? "–" : (v * 100).toFixed(digits) + "%";

// ---------- App ----------
export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [frame, setFrame] = useState<Frame>();
  const [history, setHistory] = useState<Frame[]>([]);
  const [online, setOnline] = useState(false);
  const [arrival, setArrival] = useState(0);
  const [lag, setLag] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [tab, setTab] = useState("Live");
  const [error, setError] = useState("");

  // Restore a saved sign-in so a reload or restart goes straight to the monitor.
  useEffect(() => onAuthStateChanged(auth, (u) => setUser(u)), []);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!user) return;
    let lastId = "";
    const fail = (e: Error) => {
      setOnline(false);
      setError(
        e.message.includes("permission")
          ? "This account cannot read the session. Add its UID to the session's readers."
          : e.message,
      );
    };
    const a = onSnapshot(
      doc(db, "sessions", SESSION, "state", "latest"),
      { includeMetadataChanges: true },
      (snap) => {
        setOnline(!snap.metadata.fromCache);
        const next = snap.data() as Frame | undefined;
        if (next && next.frame_id !== lastId) {
          lastId = next.frame_id;
          const t = Date.now();
          setArrival(t);
          setLag(t - next.processed_ms);
          setFrame(next);
        }
      },
      fail,
    );
    const b = onSnapshot(
      query(collection(db, "sessions", SESSION, "events"), orderBy("seq", "desc"), limit(32)),
      (snap) => setHistory(snap.docs.map((d) => d.data() as Frame)),
      fail,
    );
    return () => {
      a();
      b();
    };
  }, [user]);

  // Tell the console which frame this screen is now showing.
  useEffect(() => {
    if (!user || !frame) return;
    setDoc(doc(db, "sessions", SESSION, "viewers", user.uid), {
      frame_id: frame.frame_id,
      seq: frame.seq,
      digest: frame.digest || "",
      prediction: frame.prediction ?? null,
      rendered_at: serverTimestamp(),
      platform: Platform.OS,
      os_version: String(Platform.Version ?? ""),
      device: Device.modelName || (Platform.OS === "web" ? "Web browser" : Platform.OS),
      physical_device: Platform.OS !== "web" && Device.isDevice,
      app: "TextileSense Live (Expo)",
    }).catch(() => undefined); // receipts are best-effort diagnostics
  }, [user, frame?.frame_id]);

  const status = !online
    ? { label: "Disconnected", tone: "error" }
    : !frame
      ? { label: "Waiting", tone: "" }
      : now - arrival > STALE_MS
        ? { label: "Stale", tone: "stale" }
        : { label: "Live", tone: "live" };

  if (!user) return <SignIn onSignedIn={setUser} />;

  return (
    <View style={s.page}>
      <StatusBar style="dark" />
      <View style={s.header}>
        <View>
          <Text style={s.brand}>TextileSense Live</Text>
          <Text style={s.sub}>{EMULATED ? "Local emulator" : projectId} · {SESSION}</Text>
        </View>
        <Pill tone={status.tone}>{status.label}</Pill>
      </View>
      <ScrollView contentContainerStyle={s.body}>
        {!!error && <Text style={s.errorBox}>{error}</Text>}
        {tab === "Live" && (
          <>
            <Controls frame={frame} live={status.tone === "live"} send={(req) => sendControl(user, req)} />
            <Live frame={frame} now={now} arrival={arrival} stale={status.tone !== "live"} />
          </>
        )}
        {tab === "Trends" && <Trends history={history} />}
        {tab === "Delivery" && <Delivery frame={frame} lag={lag} online={online} now={now} arrival={arrival} />}
        {tab === "Model" && (
          <ModelCard
            onSignOut={async () => {
              await signOut(auth);
              setUser(null);
              setFrame(undefined);
            }}
            email={user.email || ""}
          />
        )}
      </ScrollView>
      <View style={s.tabbar}>
        {["Live", "Trends", "Delivery", "Model"].map((t) => (
          <Pressable
            key={t}
            accessibilityRole="tab"
            accessibilityState={{ selected: t === tab }}
            onPress={() => setTab(t)}
            style={[s.tab, t === tab && s.tabOn]}
          >
            <Text style={[s.tabText, t === tab && s.tabTextOn]}>{t}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

// ---------- Stream controls ----------
type ControlRequest = {
  action: "start" | "pause" | "source";
  mode?: "bed" | "recordings";
  subject?: 11 | 12 | 13;
  posture?: "back" | "left" | "right";
};
async function sendControl(user: User, req: ControlRequest) {
  // Rules require every field, so unused ones are sent as null.
  await setDoc(doc(db, "sessions", SESSION, "controls", user.uid), {
    action: req.action,
    mode: req.mode ?? null,
    subject: req.subject ?? null,
    posture: req.posture ?? null,
    requested_at: serverTimestamp(),
    device: (Device.modelName || Platform.OS).slice(0, 60),
  });
}

const POSITION_TO_POSTURE: Record<string, "back" | "right" | "left"> = { "1": "back", "2": "right", "3": "left" };

function Controls({ frame, live, send }: { frame?: Frame; live: boolean; send: (r: ControlRequest) => Promise<void> }) {
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(false);
  const rec = frame?.recording ? frame.recording.replace("S", "").split("-") : null;
  const curPerson = rec ? Number(rec[0]) : 12;
  const curPosture = rec ? POSITION_TO_POSTURE[rec[1]] : "back";
  const run = async (label: string, req: ControlRequest) => {
    setBusy(label);
    setNote("");
    try {
      console.log("Sending control request", JSON.stringify(req));
      await send(req);
      console.log("Control request stored", req.action);
      setNote("Sent to the laptop. The next frame arrives within about a second.");
    } catch (e: any) {
      console.warn("Control request failed", e?.code, e?.message);
      setNote(`The laptop did not receive it (${e?.code || e?.message || "unknown error"}).`);
    } finally {
      setBusy("");
    }
  };
  const Btn = ({ label, req, on, wide }: { label: string; req: ControlRequest; on?: boolean; wide?: boolean }) => (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!on }}
      disabled={!!busy}
      onPress={() => run(label, req)}
      style={[s.ctl, on && s.ctlOn, wide && { flexBasis: "100%" }, busy === label && { opacity: 0.6 }]}
    >
      <Text style={[s.ctlText, on && s.ctlTextOn]}>{label}</Text>
    </Pressable>
  );
  return (
    <View style={s.card}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text style={[s.h2, { marginBottom: 0 }]}>Stream controls</Text>
        <Pressable accessibilityRole="button" onPress={() => setOpen(!open)}>
          <Text style={[s.small, s.strong]}>{open ? "Hide sources" : "Choose source"}</Text>
        </Pressable>
      </View>
      <View style={s.ctlRow}>
        <Btn label={live ? "Streaming" : "Play"} req={{ action: "start" }} on={live} />
        <Btn label="Pause" req={{ action: "pause" }} />
      </View>
      <View style={s.ctlRow}>
        <Btn
          label={frame?.playlist === "tour" ? "Touring unseen recordings" : "Play all unseen recordings"}
          req={{ action: "source", mode: "recordings" }}
          on={frame?.playlist === "tour"}
          wide
        />
      </View>
      <Text style={[s.small, { marginTop: 6 }]}>
        Three real people the CNN never trained on, each on their back, right side and left side, 8 seconds each.
      </Text>
      {open && (
        <>
          <Text style={[s.small, { marginTop: 10 }]}>Virtual bed: the laptop moves a simulated person.</Text>
          <View style={s.ctlRow}>
            <Btn label="Virtual bed" req={{ action: "source", mode: "bed" }} on={!rec && !!frame} wide />
          </View>
          <Text style={[s.small, { marginTop: 10 }]}>
            Or play one recording on its own, from the start.
          </Text>
          {([11, 12, 13] as const).map((p) => (
            <View key={p} style={s.ctlRow}>
              <Text style={[s.small, s.strong, { width: 70, alignSelf: "center" }]}>Person {p}</Text>
              {(["back", "left", "right"] as const).map((pos) => (
                <Btn
                  key={pos}
                  label={POSTURE[pos]}
                  req={{ action: "source", mode: "recordings", subject: p, posture: pos }}
                  on={!!rec && frame?.playlist !== "tour" && curPerson === p && curPosture === pos}
                />
              ))}
            </View>
          ))}
        </>
      )}
      {!!note && <Text style={[s.small, { marginTop: 8 }]}>{note}</Text>}
    </View>
  );
}

// ---------- Sign in ----------
function SignIn({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const [email, setEmail] = useState(process.env.EXPO_PUBLIC_VIEWER_EMAIL || "viewer@example.test");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.page}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={[s.body, { paddingTop: 90 }]} keyboardShouldPersistTaps="handled">
        <Text style={s.brand}>TextileSense Live</Text>
        <Text style={s.h1}>Pressure-mat monitor</Text>
        <Text style={s.p}>
          Shows the newest frame from the {SESSION} session: the pressure map, the CNN’s posture estimate, and how the reading
          travelled from the mat to this phone.
        </Text>
        <View style={s.card}>
          <Text style={s.label}>Email</Text>
          <TextInput
            accessibilityLabel="Email"
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            style={s.input}
            value={email}
            onChangeText={setEmail}
          />
          <Text style={s.label}>Password</Text>
          <TextInput
            accessibilityLabel="Password"
            secureTextEntry
            autoComplete="password"
            style={s.input}
            value={password}
            onChangeText={setPassword}
          />
          <Pressable
            accessibilityRole="button"
            disabled={busy}
            style={[s.button, busy && { opacity: 0.6 }]}
            onPress={async () => {
              setBusy(true);
              try {
                const cred = await signInWithEmailAndPassword(auth, email.trim(), password);
                setPassword("");
                onSignedIn(cred.user);
              } catch (e: any) {
                setError(
                  e?.code === "auth/network-request-failed"
                    ? "Cannot reach Firebase. Check the phone's internet connection."
                    : "Sign-in failed. Check the email and password.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <Text style={s.buttonText}>{busy ? "Signing in" : "Sign in"}</Text>
          </Pressable>
          {!!error && <Text style={[s.errorBox, { marginTop: 12 }]}>{error}</Text>}
        </View>
        <Text style={s.fine}>
          {EMULATED ? "Connected to a local Firebase emulator." : `Firebase project ${projectId}.`} Viewer accounts can read the
          session but cannot change readings.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ---------- Live ----------
function Live({ frame, now, arrival, stale }: { frame?: Frame; now: number; arrival: number; stale: boolean }) {
  const { width } = useWindowDimensions();
  if (!frame) return <Empty text="Waiting for the first frame. Start transmitting on the laptop console." />;
  const m = frame.measurement;
  const sim = frame.simulator;
  const top = frame.scores?.length ? Math.max(...frame.scores) : 0;
  const mapWidth = Math.min(170, (Math.min(width, 640) - 40) * 0.42);
  const agree =
    frame.prediction && sim?.person_on_bed ? MODEL_TO_POSTURE[frame.prediction] === sim.posture_selected : null;
  const flags = (frame.input_flags || []).filter((f) => FLAG_TEXT[f]);
  const person = frame.recording ? frame.recording.replace("S", "").split("-")[0] : null;
  const labelAgree = frame.prediction && frame.recorded_label ? frame.prediction === frame.recorded_label : null;
  return (
    <>
      <View style={[s.sourceBox, person ? s.sourceReal : s.sourceSim]}>
        <Text style={s.sourceTitle}>
          {person ? `Real recording: person ${person}${frame.playlist === "tour" ? " (automatic tour)" : ""}` : "Virtual bed"}
        </Text>
        <Text style={s.sourceText}>
          {person
            ? "Recorded on a real pressure mat. This person was held out of training, so the CNN has never seen them."
            : "Pressure generated live from a body model as the laptop moves the person."}
        </Text>
      </View>
      <View style={[s.card, stale && { opacity: 0.75 }]}>
        <View style={{ flexDirection: "row", gap: 16 }}>
          <View style={s.mapBox}>
            <Heatmap values={frame.values} width={mapWidth} />
            <Text style={s.mapCap}>Head</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.label}>CNN estimate</Text>
            <Text style={[s.estimate, !frame.prediction && { color: C.ink3, fontSize: 24 }]}>
              {frame.prediction ? NAMES[frame.prediction] || frame.prediction : "No load"}
            </Text>
            {frame.prediction ? (
              <View style={{ gap: 9, marginTop: 10 }}>
                {frame.labels.map((l, i) => (
                  <ScoreBar key={l} label={NAMES[l] || l} value={frame.scores[i]} lead={frame.scores[i] === top} />
                ))}
              </View>
            ) : (
              <Text style={s.small}>Every sensor reads zero, so the model was not run.</Text>
            )}
            {frame.recorded_label && (
              <View style={s.compare}>
                <Text style={s.small}>Label in the dataset</Text>
                <Text style={s.compareVal}>{NAMES[frame.recorded_label]}</Text>
                {labelAgree != null && (
                  <Text style={[s.chip, labelAgree ? s.chipOk : s.chipWarn]}>
                    {labelAgree ? "Model matches" : "Model differs"}
                  </Text>
                )}
              </View>
            )}
            {sim && (
              <View style={s.compare}>
                <Text style={s.small}>Set on the laptop</Text>
                <Text style={s.compareVal}>
                  {sim.person_on_bed ? POSTURE[sim.posture_selected || "back"] : "Nobody on the bed"}
                </Text>
                {agree != null && (
                  <Text style={[s.chip, agree ? s.chipOk : s.chipWarn]}>{agree ? "Model matches" : "Model differs"}</Text>
                )}
              </View>
            )}
          </View>
        </View>
        <View style={s.frameLine}>
          <Text style={s.small}>
            Frame <Text style={s.strong}>{frame.frame_id}</Text>
          </Text>
          <Text style={[s.small, stale && { color: C.stale, fontWeight: "700" }]}>
            {stale ? "Stale, " : "Updated "}
            {((now - arrival) / 1000).toFixed(1)} s ago
          </Text>
        </View>
        <Legend caption={person ? "Recorded pressure, mmHg (1 count read as 0.1 mmHg)" : "Simulated pressure, mmHg"} />
      </View>

      {m && (
        <View style={s.grid}>
          <Metric label="Peak pressure" value={`${m.peak_mmhg.toFixed(1)}`} unit="mmHg" />
          <Metric label="Mean contact pressure" value={`${m.mean_contact_mmhg.toFixed(1)}`} unit="mmHg" />
          <Metric label="Load on mat" value={`${m.load_kg.toFixed(1)}`} unit="kg" />
          <Metric label="Contact area" value={`${Math.round(m.contact_area_m2 * 10000)}`} unit="cm²" />
          <Metric label="Loaded sensors" value={`${m.contact_cells}`} unit="of 2,048" />
          {person ? (
            <Metric label="Recorded frame" value={String(frame.row ?? "–")} unit={`of person ${person}`} />
          ) : (
            <Metric
              label="Body load on mat"
              value={sim?.person_on_bed ? pct(sim.coverage) : "–"}
              unit="simulator truth"
            />
          )}
        </View>
      )}
      {flags.length > 0 && (
        <View style={s.warnBox}>
          <Text style={s.warnTitle}>Outside the CNN’s training conditions</Text>
          {flags.map((f) => (
            <Text key={f} style={s.warnText}>
              {FLAG_TEXT[f]}
            </Text>
          ))}
        </View>
      )}
      <Text style={s.fine}>
        {person
          ? "PhysioNet PmatData Experiment I. The CNN sees only the grid; the dataset label is shown for comparison."
          : "Pressures are simulated by a contact model of a 75 kg person on a virtual 32 × 64 mat. The CNN sees only the grid; the laptop setting is shown for comparison."}
      </Text>
    </>
  );
}

function ScoreBar({ label, value, lead }: { label: string; value: number; lead: boolean }) {
  return (
    <View>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={[s.small, lead && s.strong]}>{label}</Text>
        <Text style={[s.small, s.strong]}>{(value * 100).toFixed(1)}%</Text>
      </View>
      <View style={s.track}>
        <View style={[s.fill, { width: `${value * 100}%`, backgroundColor: lead ? C.ink : C.ink3 }]} />
      </View>
    </View>
  );
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <View style={s.metric}>
      <Text style={s.small}>{label}</Text>
      <Text style={s.metricVal}>{value}</Text>
      <Text style={s.unit}>{unit}</Text>
    </View>
  );
}

// ---------- Trends ----------
function Trends({ history }: { history: Frame[] }) {
  const { width } = useWindowDimensions();
  const [picked, setPicked] = useState<Frame>();
  if (!history.length) return <Empty text="No history yet." />;
  const chron = [...history].reverse();
  const w = Math.min(width, 640) - 72;
  return (
    <>
      <View style={s.card}>
        <Text style={s.h2}>CNN estimate, last {chron.length} frames</Text>
        <Svg width={w} height={28}>
          {chron.map((f, i) => (
            <Rect
              key={f.frame_id}
              x={(i * w) / chron.length}
              y={0}
              width={w / chron.length - 1.5}
              height={28}
              rx={2}
              fill={POSTURE_COLOR[f.prediction || "none"]}
            />
          ))}
        </Svg>
        <View style={s.keyRow}>
          {(["Supine", "Left", "Right", "none"] as const).map((k) => (
            <View key={k} style={s.keyItem}>
              <View style={[s.swatch, { backgroundColor: POSTURE_COLOR[k] }]} />
              <Text style={s.small}>{k === "none" ? "No load" : NAMES[k]}</Text>
            </View>
          ))}
        </View>
        <Text style={[s.small, { marginTop: 6 }]}>
          Frames {chron[0].seq} to {chron[chron.length - 1].seq}. Oldest on the left.
        </Text>
      </View>
      <Spark title="Peak pressure" unit="mmHg" width={w} values={chron.map((f) => f.measurement?.peak_mmhg ?? 0)} />
      <Spark title="Load on mat" unit="kg" width={w} values={chron.map((f) => f.measurement?.load_kg ?? 0)} />
      <View style={s.card}>
        <Text style={s.h2}>Recent frames</Text>
        <Text style={s.small}>Tap one to see its map. Each map belongs to the estimate on the same line.</Text>
        {picked && (
          <View style={{ alignItems: "center", marginVertical: 10 }}>
            <View style={s.mapBox}>
              <Heatmap values={picked.values} width={130} />
            </View>
            <Text style={[s.small, { marginTop: 6 }]}>
              {picked.frame_id}: {picked.prediction ? NAMES[picked.prediction] : "No load"}
            </Text>
          </View>
        )}
        {history.slice(0, 12).map((f) => (
          <Pressable key={f.frame_id} onPress={() => setPicked(f)} style={s.listRow}>
            <Text style={s.small}>
              #{f.seq} {clock(f.captured_ms)}
            </Text>
            <Text style={[s.small, s.strong]}>
              {f.gap_frames ? `after gap of ${f.gap_frames}, ` : f.resumed ? "resumed, " : ""}
              {f.prediction ? NAMES[f.prediction] : "No load"}
            </Text>
          </Pressable>
        ))}
      </View>
    </>
  );
}

function Spark({ title, unit, width, values }: { title: string; unit: string; width: number; values: number[] }) {
  const max = Math.max(1, ...values);
  const min = Math.min(...values);
  const lo = Math.max(0, min - (max - min) * 0.25 - 1);
  const h = 56;
  const pts = values
    .map((v, i) => `${(i / Math.max(1, values.length - 1)) * width},${h - 4 - ((v - lo) / (max - lo)) * (h - 8)}`)
    .join(" ");
  return (
    <View style={s.card}>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={s.h2}>{title}</Text>
        <Text style={s.small}>
          now {values[values.length - 1].toFixed(1)} {unit}, max {max.toFixed(1)}
        </Text>
      </View>
      <Svg width={width} height={h}>
        <Polyline points={pts} fill="none" stroke={C.ink} strokeWidth={2} />
      </Svg>
    </View>
  );
}

// ---------- Delivery ----------
function Delivery({ frame, lag, online, now, arrival }: { frame?: Frame; lag: number | null; online: boolean; now: number; arrival: number }) {
  if (!frame) return <Empty text="Waiting for the first frame." />;
  const rate = ((frame.count - 1) * 1000) / Math.max(1, frame.received_ms - frame.first_ms);
  const steps: [string, string][] = [
    ["Virtual sensor", `Captured frame ${frame.seq} at ${clock(frame.captured_ms)}`],
    [
      "Python validation",
      `Received after ${frame.received_ms - frame.captured_ms} ms. ${frame.validation ? `${frame.validation.cells} values checked, sequence ${frame.validation.sequence}.` : "Checked."}`,
    ],
    [
      "CNN inference",
      frame.model_status === "not_run_no_load"
        ? "Not run: no load on the mat."
        : `${frame.inference_ms.toFixed(1)} ms with model ${frame.model}.`,
    ],
    ["Firestore commit", `${frame.latency_ms} ms after capture, at ${clock(frame.processed_ms)}.`],
    [
      "This phone",
      lag == null ? "Waiting" : `About ${Math.max(0, lag)} ms after the commit (laptop and phone clocks).`,
    ],
  ];
  return (
    <>
      <View style={s.card}>
        <Text style={s.h2}>How frame {frame.seq} reached this phone</Text>
        {steps.map(([name, what], i) => (
          <View key={name} style={s.step}>
            <View style={s.stepDot}>
              <Text style={s.stepNum}>{i + 1}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.strong}>{name}</Text>
              <Text style={s.small}>{what}</Text>
            </View>
          </View>
        ))}
      </View>
      <View style={s.grid}>
        <Metric label="Frames committed" value={String(frame.count)} unit="this session" />
        <Metric label="Missing" value={String(frame.missing)} unit="sequence numbers" />
        <Metric label="Duplicates" value={String(frame.duplicates)} unit="absorbed" />
        <Metric label="Out of order" value={String(frame.out_of_order)} unit="rejected" />
        <Metric label="Average rate" value={rate.toFixed(2)} unit="frames per s" />
        <Metric label="Since last frame" value={((now - arrival) / 1000).toFixed(1)} unit="s, stale after 3.5" />
      </View>
      <View style={s.card}>
        <Text style={s.h2}>Connection</Text>
        <Text style={s.small}>
          Firestore listener: <Text style={s.strong}>{online ? "connected" : "offline, showing cached data"}</Text>
        </Text>
        <Text style={s.small}>
          The app subscribes to sessions/{SESSION}/state/latest with onSnapshot. Firestore pushes each new frame; the app does
          not poll. If nothing arrives for 3.5 seconds the reading is marked stale instead of being shown as current.
        </Text>
      </View>
    </>
  );
}

// ---------- Model ----------
function ModelCard({ onSignOut, email }: { onSignOut: () => void; email: string }) {
  const rows: [string, string][] = [
    ["Model", "pmat-flat-v2, a small convolutional network (PostureCNN)"],
    ["Learned from", "Real pressure-mat recordings of 8 adults, each randomly moved, turned or reversed head-to-foot while training"],
    ["Held-out test", "99.2% accuracy on 3 unseen adults, and 98.8–99.3% when those recordings are moved or turned"],
    ["Input", "The complete 32 × 64 grid only. Values clipped at 100 mmHg and log-scaled."],
    ["Output", "Scores for back, right side and left side. Not calibrated probabilities."],
  ];
  return (
    <>
      <View style={s.card}>
        <Text style={s.h2}>About the estimate</Text>
        {rows.map(([k, v]) => (
          <View key={k} style={s.kv}>
            <Text style={[s.small, { width: 100 }]}>{k}</Text>
            <Text style={[s.small, s.strong, { flex: 1 }]}>{v}</Text>
          </View>
        ))}
      </View>
      <View style={s.card}>
        <Text style={s.h2}>Limits</Text>
        {[
          "The pressures here are simulated, in mmHg, from a body contact model. Treating the training data's raw counts as 0.1 mmHg is an assumption.",
          "Version 1 failed when a body was moved about 10 cm or turned. Version 2 was retrained with moved and turned examples and holds up to 24 cm and 25°, and head-to-foot.",
          "It still struggles with a body mostly off the mat, turns near 90°, and, in the simulator, a left-side body lying exactly in the centre.",
          "Mid-roll frames and empty beds are outside what it learned. An all-zero frame is reported as no load without running the model.",
          "This is a monitoring prototype. It does not diagnose anything or predict pressure injuries.",
        ].map((t) => (
          <Text key={t} style={[s.small, { marginBottom: 8 }]}>
            {t}
          </Text>
        ))}
      </View>
      <View style={s.card}>
        <Text style={s.small}>Signed in as {email}</Text>
        <Pressable accessibilityRole="button" style={[s.button, s.buttonGhost]} onPress={onSignOut}>
          <Text style={[s.buttonText, { color: C.ink }]}>Sign out</Text>
        </Pressable>
      </View>
    </>
  );
}

// ---------- bits ----------
function Pill({ tone, children }: { tone: string; children: string }) {
  const bg = tone === "live" ? C.liveBg : tone === "stale" ? C.staleBg : tone === "error" ? C.errorBg : C.rule2;
  const fg = tone === "live" ? C.live : tone === "stale" ? C.stale : tone === "error" ? C.error : C.ink2;
  return (
    <View style={[s.pill, { backgroundColor: bg }]} accessibilityLabel={`Status ${children}`}>
      <View style={[s.dot, { backgroundColor: fg }]} />
      <Text style={[s.pillText, { color: fg }]}>{children}</Text>
    </View>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <View style={[s.card, { alignItems: "center", paddingVertical: 40 }]}>
      <Text style={[s.small, { textAlign: "center" }]}>{text}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: C.paper },
  header: {
    paddingTop: Platform.OS === "web" ? 18 : 56,
    paddingHorizontal: 20,
    paddingBottom: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: C.panel,
    borderBottomWidth: 1,
    borderColor: C.rule,
  },
  body: { width: "100%", maxWidth: 640, alignSelf: "center", padding: 16, paddingBottom: 40, gap: 12 },
  brand: { color: C.ink, fontWeight: "800", fontSize: 17 },
  sub: { color: C.ink2, fontSize: 12, marginTop: 1 },
  h1: { color: C.ink, fontSize: 32, fontWeight: "800", letterSpacing: -0.6, marginTop: 6 },
  h2: { color: C.ink, fontSize: 15, fontWeight: "800", marginBottom: 8 },
  p: { color: C.ink2, fontSize: 15, lineHeight: 22, marginVertical: 12 },
  fine: { color: C.ink3, fontSize: 12, lineHeight: 17, marginTop: 4 },
  card: { backgroundColor: C.panel, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: C.rule },
  label: { color: C.ink2, fontSize: 13, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: C.rule,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
    color: C.ink,
    backgroundColor: C.paper,
  },
  button: { backgroundColor: C.ink, borderRadius: 8, paddingVertical: 13, alignItems: "center", marginTop: 4 },
  buttonGhost: { backgroundColor: C.panel, borderWidth: 2, borderColor: C.ink, marginTop: 10 },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  ctlRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  ctl: {
    flexGrow: 1,
    flexBasis: 0,
    borderWidth: 1.5,
    borderColor: C.ink,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 6,
    alignItems: "center",
  },
  ctlOn: { backgroundColor: C.ink },
  ctlText: { color: C.ink, fontWeight: "700", fontSize: 14 },
  ctlTextOn: { color: "#fff" },
  sourceBox: { borderRadius: 12, padding: 12, borderWidth: 1 },
  sourceReal: { backgroundColor: "#e8ecfb", borderColor: "#c3cdf3" },
  sourceSim: { backgroundColor: C.panel, borderColor: C.rule },
  sourceTitle: { color: C.ink, fontWeight: "800", fontSize: 15 },
  sourceText: { color: C.ink2, fontSize: 13, lineHeight: 18, marginTop: 2 },
  errorBox: { backgroundColor: C.errorBg, color: C.error, padding: 10, borderRadius: 8, fontSize: 13 },
  pill: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 5, paddingHorizontal: 11, borderRadius: 999 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  pillText: { fontWeight: "700", fontSize: 13 },
  mapBox: { backgroundColor: C.mat, borderRadius: 8, padding: 5, alignItems: "center" },
  mapCap: { position: "absolute", top: 6, left: 8, color: "#c4cbe2", fontSize: 10 },
  estimate: { color: C.ink, fontSize: 30, fontWeight: "800", letterSpacing: -0.6 },
  small: { color: C.ink2, fontSize: 13, lineHeight: 18 },
  strong: { color: C.ink, fontWeight: "700" },
  track: { height: 7, backgroundColor: C.rule2, borderRadius: 4, marginTop: 3, overflow: "hidden" },
  fill: { height: 7, borderRadius: 4 },
  compare: { marginTop: 14, paddingTop: 10, borderTopWidth: 1, borderColor: C.rule2, gap: 2, alignItems: "flex-start" },
  compareVal: { color: C.ink, fontWeight: "700", fontSize: 15 },
  chip: { fontSize: 12, fontWeight: "700", paddingHorizontal: 7, paddingVertical: 2, borderRadius: 4, overflow: "hidden", marginTop: 4 },
  chipOk: { backgroundColor: C.liveBg, color: C.live },
  chipWarn: { backgroundColor: C.staleBg, color: C.stale },
  frameLine: {
    flexDirection: "row",
    justifyContent: "space-between",
    flexWrap: "wrap",
    marginTop: 12,
    marginBottom: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderColor: C.rule2,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  metric: {
    flexBasis: "47%",
    flexGrow: 1,
    backgroundColor: C.panel,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: C.rule,
  },
  metricVal: { color: C.ink, fontSize: 24, fontWeight: "800", marginTop: 2 },
  unit: { color: C.ink3, fontSize: 12 },
  warnBox: { backgroundColor: C.staleBg, borderRadius: 12, padding: 14, gap: 4 },
  warnTitle: { color: C.stale, fontWeight: "800" },
  warnText: { color: C.stale, fontSize: 13 },
  keyRow: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 8 },
  keyItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  swatch: { width: 10, height: 10, borderRadius: 2 },
  listRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 8, borderBottomWidth: 1, borderColor: C.rule2 },
  step: { flexDirection: "row", gap: 12, marginBottom: 12 },
  stepDot: { width: 24, height: 24, borderRadius: 12, backgroundColor: C.ink, alignItems: "center", justifyContent: "center" },
  stepNum: { color: "#fff", fontWeight: "800", fontSize: 12 },
  kv: { flexDirection: "row", gap: 10, paddingVertical: 6, borderBottomWidth: 1, borderColor: C.rule2 },
  tabbar: {
    flexDirection: "row",
    backgroundColor: C.panel,
    borderTopWidth: 1,
    borderColor: C.rule,
    paddingBottom: Platform.OS === "ios" ? 26 : 8,
    paddingTop: 8,
    paddingHorizontal: 8,
    gap: 6,
  },
  tab: { flex: 1, alignItems: "center", paddingVertical: 9, borderRadius: 8 },
  tabOn: { backgroundColor: C.ink },
  tabText: { color: C.ink2, fontWeight: "700", fontSize: 14 },
  tabTextOn: { color: "#fff" },
});
