import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { randomUUID } from "node:crypto";
import { initializeApp } from "firebase/app";
import { getAuth, connectAuthEmulator, signInAnonymously } from "firebase/auth";
import {
  getFirestore,
  connectFirestoreEmulator,
  getDocFromServer,
  doc,
  onSnapshot,
  setDoc,
} from "firebase/firestore";
const app = initializeApp({ apiKey: "demo", projectId: "demo-textilesense" });
const auth = getAuth(app);
connectAuthEmulator(auth, "http://127.0.0.1:9099");
const db = getFirestore(app);
connectFirestoreEmulator(db, "127.0.0.1", 8080);
const sid = "listener-" + randomUUID();
const ref = doc(db, "sessions/"+sid+"/state/proof");
const denied = (e) => e.code === "permission-denied";
await assert.rejects(getDocFromServer(ref), denied);
const { user } = await signInAnonymously(auth);
await assert.rejects(getDocFromServer(ref), denied);
const write = (...args) =>
  promisify(execFile)(".venv/bin/python", ["-m", "proof.write", sid, user.uid, ...args]);
await write();
await assert.rejects(setDoc(ref, { sample: 0 }), denied);
const sample = Date.now();
await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(Error("Listener timed out")), 15000);
  let sent = false;
  const stop = onSnapshot(
    ref,
    (s) => {
      if (s.data()?.sample === sample) {
        clearTimeout(timer);
        stop();
        resolve();
      } else if (!sent) {
        sent = true;
        write(String(sample)).catch(reject);
      }
    },
    reject,
  );
});
console.log(
  "PASS anonymous and unlisted reads denied, listed write denied, authorized listener observed Python sample",
  sample,
);
process.exit(0);
