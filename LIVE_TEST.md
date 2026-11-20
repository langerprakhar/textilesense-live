# Live verification · November 20, 2026

[Watch the 90-second take](evidence/live_test/demonstration.mp4) · [Print the narration](Professor-transcript.pdf) · [Read how to reproduce it](README.md).

## System inventory

Real recordings enter replay.py, api.py validates them, and model.py applies trained PyTorch weights from model.pt. The Python Admin SDK commits both the current result and one of 32 rotating history slots. The Expo/Firebase JS client signs in, subscribes to the current document, and converts the 2,048 pressure cells to colored squares. The recording shows the actual app beside an independently read Firestore document. The source is PmatData v1.0.0. All recordings are from adults. The input timestamp comes from the replay clock. The file and source row preserve the original recording reference.

## Acceptance ledger

| Subsystem | Result | Evidence |
|---|---|---|
| Actual recordings and participant identity | PASS | 39 public Experiment I files in data/. Replay verifies hashes for the nine held-out recordings it loads. Positions 1/2/3 are supine/right/left. |
| Python live ingestion and consecutive publication | PASS | [Two-minute run](evidence/live_test/two-minute.json) and [ten-minute run](evidence/live_test/ten-minute.json). Each JSONL row contains the frame ID, source row, timestamps, SHA-256 digest, scores, predicted class, inference and transaction timings, and successful read-back. |
| Real CNN inference | PASS | Two convolution layers execute for each frame using saved preprocessing. [Supine](evidence/live_test/demo-position-1.png), [right](evidence/live_test/demo-position-2.png), [left](evidence/live_test/demo-position-3.png). |
| Held-out evaluation | PASS | Training in a separate temporary directory reproduced every saved model tensor and the entire evaluation JSON, including the template results. [Reproduction](evidence/live_test/model-verification.json) · [Forest comparator](evidence/forest.json) · [Confusion matrix and error](evidence/confusion-and-error.png). |
| Firestore emulator | PASS | Local project demo-textilesense. Each stability frame was acknowledged by the API, compared field-for-field to sessions/{session}/state/latest, and observed by the session change subscription. |
| Cloud Firestore | BLOCKED | No approved hosted project bound to the runtime. Google Application Default Credentials lookup returned DefaultCredentialsError. |
| Authentication and Firestore rules | PASS on emulator | Signed-out and unlisted reads denied. Authorized viewer received the Python update. A viewer write was denied. [Rules proof](evidence/live_test/rules.log). |
| Expo app in cloud computer | PASS on Chromium | [UI proof](evidence/live_test/ui-integrity.log) independently compared every rendered heatmap path and the posture heading with the submitted frame on 36 successive updates. The 90-second video is a separate execution with 60 live UI checks. |
| Physical phone | BLOCKED | iOS bundle exported. No paired device or private test route available in this environment. [iOS build](evidence/live_test/ios-export.log) · [Phone procedure](PHONE.md). |
| Interrupt, go stale, resume | PASS | [Paused screen](evidence/live_test/demo-stale.png) and continuous video. Frame ID remained fixed. A fresh frame cleared stale state. |
| Duplicate, missing, delayed and out-of-order | PASS | [UI test](evidence/live_test/ui-integrity.log) increments cumulative counters by injecting a duplicate, a gap and a late arrival. History stayed within 32 slots. [Validation test](evidence/live_test/validation.log) also exercised concurrent duplicates, conflicting content and invalid pressure values. |
| Malformed map and invalid token | PASS | Bad dimensions, counts, values, capture time and device credentials returned errors. A subsequent valid frame was accepted. |
| Firestore interruption | PASS | An isolated API connected to the real local emulator through a loopback relay. We cut only that connection, observed the old document for six seconds, then restored the relay. The request timed out twice and recovered in 10.83 s from first submission. Three unique frames produced exactly three history documents. [Outage log](evidence/live_test/outages.log). |
| CNN failure | PASS | Injected an exception at the model forward call. The API returned 503, preserved the previous document, and accepted the same input after restoration. [Failure log](evidence/live_test/outages.log). |
| Capture to app measurement | PASS locally | [Timing](evidence/live_test/demo-timing.json). Replay capture and automated confirmation of the frame ID on screen used the same host clock. The latter includes browser assertion and independent read-back time. |
| Physical mat | BLOCKED | No physical mat/controller attached. The optional single-channel ESP32 source and bench plan are separate from the posture pipeline. |

## Performance

| Metric | Two minutes | Ten minutes |
|---|---:|---:|
| Sent | 120.00 | 600.00 |
| Received | 120.00 | 600.00 |
| Published and read back | 120.00 | 600.00 |
| Observed by listener | 120.00 | 600.00 |
| Dropped | 0.00 | 0.00 |
| Rejected | 0.00 | 0.00 |
| Elapsed seconds | 120.00 | 600.00 |
| Frames/s | 1.00 | 1.00 |
| CNN latency, ms (median / p95 / max) | 1.13 / 4.09 / 53.20 | 1.20 / 9.55 / 67.94 |
| Firestore transaction, ms (median / p95 / max) | 28.49 / 131.68 / 210.73 | 28.32 / 138.08 / 444.06 |
| API CPU, percent of one core (median / p95 / max) | 6.00 / 17.70 / 98.00 | 4.25 / 12.60 / 93.80 |
| API resident memory, MiB (median / p95 / max) | 301.29 / 302.10 / 302.38 | 304.19 / 304.84 / 305.92 |

The stability runs used separate sessions. Their first two minutes overlapped; they also shared the host with other tests. CPU and memory refer to the API process, including its concurrent work. Inference includes normalization and score calculation. Transaction time includes Firestore transactional reads, writes, and acknowledgment. Each recorded HTTP request corresponds to one frame. The stability logs and backend access log allow auditing request counts. All accepted payload fields and scores were checked during read-back. The test attests to the mat's 1 Hz workload inside this environment.

The 60-frame recording measured capture to confirmed UI at 195.8 ms median, 343.1 ms p95, and 406.5 ms maximum. Following the intentional pause, the first fresh frame was confirmed in 222.7 ms. These include automation overhead. A 36-frame UI test also exercised cached/disconnected status and reconnection separately from stream staleness. Wide-area and physical-device latencies are unknown.

## Issues encountered and repaired

An existing process occupied the first selected test port. That attempt ended before sampling began; the stability tests used a verified listening port. The video recorder initially lacked its Playwright FFmpeg binary. Installing it enabled a continuous take. A rules proof re-used a session and synchronously rewrote membership inside the listener callback. A cancelled emulator call exposed the problem. The corrected test uses a unique session, sets membership once and writes asynchronously. Its rerun passed. A second execution of the recording launcher produced a separate 90-second video without overwriting the first take.

## Repeat the live tests

Use the README manual setup to start the local emulators, export and serve the web app, set DEMO_PASSWORD and TEXTILE_TOKEN, and start the API. Then run from the active Python environment:

```bash
node proof/listener.mjs
python -m pytest -q test_pipeline.py
python -m proof.stability two-minute
python -m proof.stability ten-minute
python -m proof.outages
python -m proof.dashboard
python -m proof.record_demo --output recordings/manual-take
```

Set TEXTILE_API_PID to the API process ID if you want process resource metrics. TEXTILE_API_URL defaults to http://127.0.0.1:8000. The test API, emulators and web server use loopback. Both stability tests create distinct emulator sessions, use at most 32 history slots each and terminate after the requested observation period.
