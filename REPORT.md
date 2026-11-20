# Initial prototype report · November 20, 2026

See [the follow-up live tests and recorded demonstration](LIVE_TEST.md) for the latest measurements and current verification status.

**The local vertical slice passes. Hosted Firestore and a physical mobile demonstration remain blocked.** This independent engineering exercise uses public adult pressure-mat recordings. Its outcome is three-way posture classification. There is no clinical validation, pediatric evaluation, hospital data, or laboratory affiliation.

## Acceptance ledger

| Requirement | Result | Observable evidence |
|---|---|---|
| M0 · environment, compatible dependencies, architecture and reproducible setup | PASS | Python 3.12.14, Node 24.22.1, OpenJDK 21.0.13. Firebase CLI 15.37, JS SDK 13.4, Admin 7.8. Expo 58, React Native 0.88.1. Lockfiles, README diagram, exports and integration logs. |
| M1 · Python publish and subscribed JS application | PASS | [Listener proof](evidence/proof.log). A nonce generated after listener setup came back from Python via Firestore. |
| M1 · unauthenticated read, unlisted user read and authorized reader write denied | PASS | The same proof asserted permission-denied in all three cases and observed the authorized read. Mobile code has no ingestion token or admin credentials. |
| M2 · provenance, license, real parsing, recording boundaries, source time and heatmaps | PASS | SHA-256 verified for all 39 files. [Genuine frames](evidence/frames.png), [sample wire event](evidence/example.json). Source provides row order and nominal cadence only. |
| M2/M4 · endpoint replay | PASS | The endpoint test used the saved CNN, so this test ran after training. The browser test streamed all three source recordings. |
| M3 · training, versioned artifact, separation, baseline and held-out metrics | PASS | [CNN and template](evidence/results.json), [forest](evidence/forest.json), [checkpoint digest](evidence/checkpoint.sha256). |
| M4 · validation, binding, ordered state, inference and transaction | PASS | [Pytest](evidence/pytest.log) includes malformed shape/range, token, device mismatch, concurrent duplicate and conflicting content. |
| M5 · live heatmap, scores, timestamps, source, delivery estimate, history, diagnostics | PASS on React Native web | [Live](evidence/live-2.png), [history](evidence/history.png), [diagnostics](evidence/diagnostics.png). The browser test independently constructs the expected SVG paths from each input and checks the rendered paths and frame ID. |
| M5 · iOS JS/assets build | PASS | [Metro iOS export](evidence/ios-bundle.log). |
| M5 · physical iPhone, Expo Go execution or signed installation | BLOCKED | No paired iPhone or authorized signing route. README gives the Expo Go verification path. |
| M6 · stale, resumed, duplicate, gap, delayed, out-of-order, bounded history | PASS | [Browser assertions and counters](evidence/dashboard-latest.log). Replayed at approximately 1 Hz, paused across the 3.5-second threshold, then resumed. A delayed frame and a lower sequence were injected separately. History capped at 32. |
| M6 · Firebase disconnected and recovered | PASS | Chromium networking disabled and re-enabled. The SDK switched to cached state, then re-established its server subscription. Stream staleness is independently derived from capture age. |
| M6 · latency and throughput | PASS locally | [Single-client burst benchmark](evidence/benchmark.json) and browser measurements below. |
| Hosted Firebase Auth, Firestore subscription and production rules | BLOCKED | ADC lookup raised DefaultCredentialsError. No authorized destination project was supplied. Emulator proofs cannot establish hosted IAM behavior. |
| M7 · guide, screenshots, evidence, teaching notes, script and unsent email | PASS | README, DEMO.md, this report and evidence directory. |
| Optional single-channel software transport | PASS locally | [Bench guide and ESP32 sketch](hardware/README.md). Ten clearly labeled generated readings went through a separate API to the Firestore emulator. [Simulation log](evidence/probe-simulation.log). |
| Optional physical mat/ESP32 transmission | BLOCKED | No physical sampling hardware attached. Device firmware, wiring notes and bench plan are included. Board compilation, installation and transmission require separate verification. |
| Public GitHub publication | BLOCKED | At the initial run, no repository destination had been specified. |

## Model comparison

| Model | Correct / 841 | Accuracy | Macro-F1 | Recall supine / right / left |
|---|---:|---:|---:|---|
| CNN | 832 | 98.93% | 0.9891 | 0.993 / 0.988 / 0.987 |
| Nearest mean template | 833 | 99.05% | 0.9905 | 0.989 / 0.980 / 1.000 |
| Spatial-feature random forest | 834 | 99.17% | 0.9914 | 0.996 / 0.988 / 0.990 |

CNN confusion matrix, rows true and columns predicted:

| | Supine | Right | Left |
|---|---:|---:|---:|
| Supine | 281 | 2 | 0 |
| Right | 2 | 244 | 1 |
| Left | 2 | 2 | 307 |

The split contains 2,338 training frames from S1–8, 431 validation frames from S9–10, and 841 test frames from S11–13. The highest validation macro-F1 selected epoch 2 of 15. Test accuracy by person was 98.64%, 99.42% and 98.54%. Adjacent rows are highly correlated. Three held-out adults are too few to establish the ranking on new populations. All models saw the same preprocessing and test split. The forest made two fewer errors than the CNN. Regional pressure magnitude and occupied area can already distinguish these standardized positions. That is a plausible explanation for the strong baselines. This comparison does not identify the cause of the two-frame difference.

One inspectable error is S11, position 1, row 0. The CNN scored right at 39.9%, supine at 35.1% and left at 24.9%. The file label is supine. [Error frame and confusion matrix](evidence/confusion-and-error.png)

## Timing and failure boundaries

In the final 36-frame dashboard run, capture-to-backend processing took 14.5 ms median and 22 ms p95. HTTP submission to the browser test observing the frame ID took 149 ms median and 398 ms p95, including automation polling. The latter is an upper-bound-style observation, not a display-hardware timing measurement. The app's delivery estimate uses the client clock at snapshot callback minus the replay capture timestamp, so cross-device clock skew matters. The interrupted run averaged 0.92 Hz. A separate sequential unpaced 48-frame test achieved 17.77 acknowledged frames/s, with HTTP acknowledgment latency of 49 ms median and 82 ms p95. These are single-computer emulator measurements with no WAN transport.

The first browser run started at zero and finished with one gap, one duplicate and one out-of-order arrival. The second appended to that session and ended with two of each. Reads or retries can cause extra operations. A persistent outage beyond four attempts stops replay visibly. The replay process does not maintain a durable send queue across process death. Reconnect tests exercise the browser subscription; extended backend or emulator outages and multi-device saturation were outside the measured workload. A history item records a stream interruption upon resumption. During an ongoing interruption the live screen shows stale state.

## Deployment limits

The ingestion API is a loopback demonstration with a shared secret and server-side device/session check. A network-exposed fleet deployment would need TLS, per-device credentials, operational monitoring and load tests. Admin SDK writes bypass client rules, so deployed IAM scope matters. Firestore rules protect viewer access by explicit UID. The demo retains 32 event slots per session and one latest document. Session creation is an operator operation. Pressure maps and scores are stored together under one frame ID. Uncertainty is displayed as raw softmax class scores; calibration and out-of-distribution detection have not been evaluated.
