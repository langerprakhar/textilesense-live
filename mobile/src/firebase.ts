// Firebase is set up once, here, so a hot reload of App.tsx never re-runs it.
import { Platform } from "react-native";
import { getApp, getApps, initializeApp } from "firebase/app";
import { Auth, connectAuthEmulator, getAuth, initializeAuth } from "firebase/auth";
import { connectFirestoreEmulator, getFirestore } from "firebase/firestore";
import AsyncStorage from "@react-native-async-storage/async-storage";

export const projectId = process.env.EXPO_PUBLIC_PROJECT_ID || "demo-textilesense";
export const SESSION = process.env.EXPO_PUBLIC_SESSION || "demo";
export const EMULATED = projectId.startsWith("demo-");

const fresh = getApps().length === 0;
const app = fresh
  ? initializeApp({
      projectId,
      apiKey: process.env.EXPO_PUBLIC_API_KEY || "demo",
      authDomain: projectId + ".firebaseapp.com",
    })
  : getApp();

function makeAuth(): Auth {
  if (!fresh || Platform.OS === "web") return getAuth(app);
  // The React Native build of firebase/auth exports this; the web typings don't.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { getReactNativePersistence } = require("firebase/auth") as {
    getReactNativePersistence: (storage: unknown) => any;
  };
  // Keeps the viewer signed in across app reloads and restarts.
  return initializeAuth(app, { persistence: getReactNativePersistence(AsyncStorage) });
}

export const auth = makeAuth();
export const db = getFirestore(app);

if (EMULATED && fresh) {
  const host = process.env.EXPO_PUBLIC_EMULATOR_HOST || "127.0.0.1";
  connectAuthEmulator(auth, `http://${host}:${process.env.EXPO_PUBLIC_AUTH_PORT || "9099"}`, {
    disableWarnings: true,
  });
  connectFirestoreEmulator(db, host, Number(process.env.EXPO_PUBLIC_FIRESTORE_PORT || 8080));
}
