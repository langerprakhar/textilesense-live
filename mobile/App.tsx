import React, { useEffect, useMemo, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
} from "react-native";
import Svg, { Path } from "react-native-svg";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  connectAuthEmulator,
  signInWithEmailAndPassword,
} from "firebase/auth";
import {
  getFirestore,
  connectFirestoreEmulator,
  doc,
  onSnapshot,
  collection,
  query,
  orderBy,
  limit,
} from "firebase/firestore";

const projectId = process.env.EXPO_PUBLIC_PROJECT_ID || "demo-textilesense";
const app = initializeApp({
  projectId,
  apiKey: process.env.EXPO_PUBLIC_API_KEY || "demo",
  authDomain: projectId + ".firebaseapp.com",
});
const auth = getAuth(app),
  db = getFirestore(app);
if (["demo-textilesense", "demo-textilesense-bed"].includes(projectId)) {
  const host = process.env.EXPO_PUBLIC_EMULATOR_HOST || "127.0.0.1";
  connectAuthEmulator(auth, "http://" + host + ":" + (process.env.EXPO_PUBLIC_AUTH_PORT || "9099"), {
    disableWarnings: true,
  });
  connectFirestoreEmulator(db, host, Number(process.env.EXPO_PUBLIC_FIRESTORE_PORT || 8080));
}
type Frame = {
  seq: number;
  frame_id: string;
  values: number[];
  captured_ms: number;
  processed_ms: number;
  first_ms: number;
  received_ms: number;
  count: number;
  missing: number;
  duplicates: number;
  out_of_order: number;
  latency_ms: number;
  prediction: string;
  labels: string[];
  scores: number[];
  source: string;
  model: string;
  scenario?: string;
  recording?: string;
  row?: number;
  resumed: boolean;
};
const colors = [
  "#142a3a",
  "#17435a",
  "#17647a",
  "#168d95",
  "#40b6ac",
  "#96d59c",
  "#eed97d",
  "#ffac62",
  "#fa7556",
];
function Heatmap({ frame }: { frame: Frame }) {
  const paths = useMemo(() => {
    const paths = colors.map(() => "");
    frame.values.forEach((v, i) => {
      const level = Math.min(
        8,
        Math.floor((Math.log1p(v) / Math.log(501)) * 9),
      );
      paths[level] += "M" + Math.floor(i / 64) + " " + (i % 64) + "h1v1h-1z";
    });
    return paths;
  }, [frame.values]);
  return (
    <Svg height={292} width={146} viewBox="0 0 32 64">
      {paths.map((d, i) => d && <Path key={i} d={d} fill={colors[i]} />)}
    </Svg>
  );
}
const tabs = ["Live", "History", "Diagnostics"];
export default function App() {
  const [email, E] = useState("viewer@example.test"),
    [password, P] = useState(""),
    [signed, S] = useState(false),
    [error, X] = useState("");
  const [delivery, D] = useState(0),
    [selected, Select] = useState<Frame>();
  const [f, F] = useState<Frame>(),
    [hist, H] = useState<Frame[]>([]),
    [tab, T] = useState("Live"),
    [online, O] = useState(false),
    [now, N] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => N(Date.now()), 300);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!signed) return;
    const fail = (e: Error) => {
      O(false);
      X(e.message);
    };
    const sid = process.env.EXPO_PUBLIC_SESSION || "demo";
    let lastId = "";
    const a = onSnapshot(
      doc(db, "sessions", sid, "state", "latest"),
      { includeMetadataChanges: true },
      (s) => {
        O(!s.metadata.fromCache);
        const next = s.data() as Frame | undefined;
        if (next && next.frame_id !== lastId) {
          lastId = next.frame_id;
          D(Date.now() - next.captured_ms);
        }
        F(next);
      },
      fail,
    );
    const b = onSnapshot(
      query(
        collection(db, "sessions", sid, "events"),
        orderBy("seq", "desc"),
        limit(32),
      ),
      (s) => H(s.docs.map((x) => x.data() as Frame)),
      fail,
    );
    return () => {
      a();
      b();
    };
  }, [signed]);
  const status = !online
    ? "Disconnected"
    : !f
      ? "Waiting"
      : now - f.captured_ms > 3500
        ? "Stale"
        : "Live";
  const line = (k: string, v: string | number) => (
    <View key={k} style={s.row}>
      <Text style={s.muted}>{k}</Text>
      <Text style={s.val}>{v}</Text>
    </View>
  );
  return (
    <ScrollView
      style={s.page}
      contentContainerStyle={s.body}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={s.brand}>TextileSense Live</Text>
      <Text style={s.title}>
        {!signed
          ? "Monitor sign-in"
          : tab === "Live"
            ? "Live monitoring"
            : tab === "History"
              ? "Session history"
              : "System diagnostics"}
      </Text>
      {!signed ? (
        <View style={s.card}>
          <Text style={s.val}>Authorized session viewer</Text>
          <TextInput
            accessibilityLabel="Email"
            autoCapitalize="none"
            style={s.input}
            value={email}
            onChangeText={E}
          />
          <TextInput
            accessibilityLabel="Password"
            placeholder="Password"
            secureTextEntry
            style={s.input}
            value={password}
            onChangeText={P}
          />
          <Pressable
            style={s.button}
            onPress={async () => {
              try {
                await signInWithEmailAndPassword(auth, email, password);
                P("");
                S(true);
                X("");
              } catch {
                X("Sign-in failed. Check your credentials and connection.");
              }
            }}
          >
            <Text style={s.val}>Sign in</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <View style={s.tabs}>
            {tabs.map((t) => (
              <Pressable
                key={t}
                onPress={() => T(t)}
                style={[s.tab, t === tab && s.active]}
              >
                <Text style={s.val}>{t}</Text>
              </Pressable>
            ))}
          </View>
          <Text style={s.status}>
            {status} · {f?.source === "virtual_pressure_mat" ? "Virtual pressure mat" : f?.source === "recorded_replay" ? "Recorded pressure mat" : f?.source || "Waiting for a frame"}
          </Text>
          {f && tab === "Live" && (
            <View style={s.card}>
              <Text style={s.muted}>ESTIMATED POSTURE</Text>
              <Text style={s.title}>{f.prediction}</Text>
              <View style={s.map}>
                <Heatmap frame={f} />
              </View>
              {line("Sensor grid", "32 × 64")}
              {line("Frame", f.frame_id)}
              {line("Frame age", (Math.max(0, now - f.captured_ms) / 1000).toFixed(1) + " s")}
              {line(
                "Captured",
                new Date(f.captured_ms).toISOString().slice(11, 23) + " UTC",
              )}
              {line("Delivery estimate", delivery + " ms")}
              {f.labels.map((l, i) =>
                line(l, (f.scores[i] * 100).toFixed(1) + "%"),
              )}
            </View>
          )}
          {tab === "History" && (
            <View style={s.card}>
              {selected && (
                <>
                  <Text style={s.val}>
                    {selected.frame_id} · {selected.prediction}
                  </Text>
                  <Heatmap frame={selected} />
                </>
              )}
              {hist.map((h) => (
                <Pressable key={h.frame_id} onPress={() => Select(h)}>
                  {line(
                    "#" + h.seq + " · " + (h.scenario ? "Virtual · " + h.scenario : h.recording + " / " + h.row),
                    (h.resumed ? "Resumed · " : "") + h.prediction,
                  )}
                </Pressable>
              ))}
            </View>
          )}
          {f && tab === "Diagnostics" && (
            <View style={s.card}>
              {line(
                "Firebase subscription",
                online ? "Connected" : "Disconnected",
              )}
              {line("Received frames", f.count)}
              {line("Last sequence", f.seq)}
              {line("Missing", f.missing)}
              {line("Duplicates", f.duplicates)}
              {line("Out of order", f.out_of_order)}
              {line(
                "Average rate",
                (
                  ((f.count - 1) * 1000) /
                  Math.max(1, f.received_ms - f.first_ms)
                ).toFixed(2) + " Hz",
              )}
              {line("Ingestion latency", f.latency_ms + " ms")}
              {line("Model", f.model)}
            </View>
          )}
        </>
      )}
      {!!error && <Text style={s.status}>{error}</Text>}
    </ScrollView>
  );
}
const s = StyleSheet.create({
  page: { backgroundColor: "#0b1925" },
  body: {
    width: "100%",
    maxWidth: 640,
    alignSelf: "center",
    paddingHorizontal: 20,
    paddingTop: 52,
    paddingBottom: 36,
    gap: 12,
  },
  brand: {
    color: "#77d3c5",
    fontWeight: "700",
    letterSpacing: 1.1,
    fontSize: 16,
  },
  title: { color: "#f1f6f5", fontSize: 31, fontWeight: "700" },
  card: { backgroundColor: "#142939", borderRadius: 18, padding: 18, gap: 8 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderColor: "#294050",
    paddingVertical: 5,
  },
  val: { fontWeight: "600", color: "#f0f6f7" },
  muted: { color: "#afc4ce" },
  map: {
    alignItems: "center",
    backgroundColor: "#102231",
    borderRadius: 10,
    padding: 8,
  },
  tabs: { flexDirection: "row", gap: 4 },
  tab: { paddingVertical: 9, paddingHorizontal: 14, borderRadius: 20 },
  active: { backgroundColor: "#25616a" },
  status: { color: "#e8c58c", fontSize: 14 },
  button: {
    backgroundColor: "#286473",
    alignItems: "center",
    padding: 12,
    borderRadius: 8,
  },
  input: { padding: 10, backgroundColor: "#fff", borderRadius: 6 },
});
