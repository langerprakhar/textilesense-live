export const C = {
  ink: "#1b2550",
  ink2: "#4f5a78",
  ink3: "#626b84",
  paper: "#eef1f4",
  panel: "#ffffff",
  rule: "#d6dbe4",
  rule2: "#e7eaf0",
  mat: "#333d61",
  live: "#1f7a55",
  liveBg: "#e3f3eb",
  stale: "#a2620c",
  staleBg: "#fbf0dc",
  error: "#b42318",
  errorBg: "#fde9e7",
};

export const NAMES: Record<string, string> = {
  Supine: "On back",
  Right: "Right side",
  Left: "Left side",
};
export const POSTURE: Record<string, string> = {
  back: "On back",
  left: "Left side",
  right: "Right side",
};
export const MODEL_TO_POSTURE: Record<string, string> = {
  Supine: "back",
  Right: "right",
  Left: "left",
};
// Colours for the posture timeline (categorical, distinct from the heat ramp).
export const POSTURE_COLOR: Record<string, string> = {
  Supine: "#3e63dd",
  Right: "#1f7a55",
  Left: "#a2620c",
  none: "#c4cad6",
};
