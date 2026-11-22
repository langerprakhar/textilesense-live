// Pressure heatmap shared by every screen. Same colour scale as the laptop
// console: position = sqrt(mmHg / 100); 100 mmHg and above share the top colour.
import React, { useMemo } from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Path, Rect, Defs, LinearGradient, Stop } from "react-native-svg";
import { C } from "./theme";

const STOPS: [number, number[]][] = [
  [0.0, [77, 38, 110]],
  [0.25, [155, 37, 87]],
  [0.5, [210, 83, 58]],
  [0.75, [240, 163, 58]],
  [1.0, [251, 239, 196]],
];
export const pos = (mmhg: number) => Math.min(1, Math.sqrt(Math.max(0, mmhg) / 100));
export function rgb(mmhg: number) {
  const t = pos(mmhg);
  for (let i = 1; i < STOPS.length; i++) {
    if (t <= STOPS[i][0]) {
      const [t0, a] = STOPS[i - 1];
      const [t1, b] = STOPS[i];
      const f = (t - t0) / (t1 - t0);
      const c = a.map((v, k) => Math.round(v + (b[k] - v) * f));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return "rgb(251,239,196)";
}

const LEVELS = 40;
const LEVEL_COLOR = Array.from({ length: LEVELS }, (_, i) => rgb(Math.pow((i + 0.5) / LEVELS, 2) * 100));

// Seen from above: head at the top, sensor row 0 along the right-hand edge.
export function Heatmap({ values, width }: { values: number[]; width: number }) {
  const paths = useMemo(() => {
    const out = Array(LEVELS).fill("");
    values.forEach((v, i) => {
      if (v <= 0) return;
      const level = Math.min(LEVELS - 1, Math.floor(pos(v / 10) * LEVELS));
      const row = Math.floor(i / 64), col = i % 64;
      out[level] += `M${31 - row} ${col}h1v1h-1z`;
    });
    return out;
  }, [values]);
  return (
    <Svg width={width} height={width * 2} viewBox="0 0 32 64">
      <Rect x={0} y={0} width={32} height={64} fill={C.mat} />
      {paths.map((d, i) => (d ? <Path key={i} d={d} fill={LEVEL_COLOR[i]} /> : null))}
      {Array.from({ length: 3 }, (_, k) => (
        <Path key={"v" + k} d={`M${(k + 1) * 8} 0V64`} stroke="#8d9bc8" strokeOpacity={0.3} strokeWidth={0.08} />
      ))}
      {Array.from({ length: 7 }, (_, k) => (
        <Path key={"h" + k} d={`M0 ${(k + 1) * 8}H32`} stroke="#8d9bc8" strokeOpacity={0.3} strokeWidth={0.08} />
      ))}
    </Svg>
  );
}

export function Legend({ caption = "Simulated pressure, mmHg" }: { caption?: string }) {
  const ticks = [1, 10, 25, 50, 100];
  return (
    <View>
      <Text style={s.cap}>{caption}</Text>
      <Svg height={10} width="100%">
        <Defs>
          <LinearGradient id="g" x1="0" y1="0" x2="1" y2="0">
            {Array.from({ length: 11 }, (_, i) => (
              <Stop key={i} offset={i / 10} stopColor={rgb(Math.max(0.01, Math.pow(i / 10, 2) * 100))} />
            ))}
          </LinearGradient>
        </Defs>
        <Rect x={0} y={0} width="100%" height={10} rx={3} fill="url(#g)" />
      </Svg>
      <View style={s.ticks}>
        {ticks.map((t) => (
          <Text key={t} style={[s.tick, { left: `${pos(t) * 100}%` }, t === 100 && { transform: [{ translateX: -30 }] }]}>
            {t === 100 ? "100+" : t}
          </Text>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  cap: { color: C.ink2, fontSize: 12, marginBottom: 4 },
  ticks: { height: 16, position: "relative", marginTop: 2 },
  tick: { position: "absolute", fontSize: 11, color: C.ink3, transform: [{ translateX: -4 }] },
});
