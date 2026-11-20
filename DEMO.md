# Teaching notes

For the recorded demonstration use the [timed read-aloud transcript](PROFESSOR_TRANSCRIPT.md).

| Milestone | What and why | Mechanism | Command and evidence | Interview wording |
|---|---|---|---|---|
| M0 · system design | Connect Python, ML, cloud storage and a mobile client through independently testable boundaries. | Replay is the sensor clock. The API owns inference and writes. A subscribed viewer receives the latest coherent state. | README diagram and locked dependencies. Running the quick start exercises each boundary. | “I can trace one source row all the way to the pixels and class scores on screen.” |
| M1 · Firebase | Practice authenticated cloud-style publication and subscription. Firebase is the platform. Firestore is its document database. | Auth identifies the viewer. Rules check membership. The Admin SDK writes through a privileged server identity. A listener gets pushed snapshots when data changes. | node proof/listener.mjs observed a Python-generated update and three permission denials. | “I tested both sides of authorization, including an authenticated viewer attempting a write.” |
| M2 · sensor data | Replace invented inputs with measured spatial pressure. Sampling rate describes the original instrument. Throughput describes how quickly a pipeline can accept frames. | Verify file hashes, preserve each person's recording and source row, and issue fresh replay timestamps at 1 Hz. | python dataset.py verified 39 recordings. evidence/frames.png displays real subject S11. | “I replay a real mat recording. I can identify the exact participant, position file and row.” |
| M3 · CNN | Learn spatial patterns from a grid whose neighboring sensors have a physical relationship. | A convolution slides a shared kernel across the mat. Training adjusts its weights to detect useful local patterns. ReLU gates activations. Pooling reduces resolution and sensitivity to small shifts. The final layer combines regional features into class logits. | python train.py selected epoch 2 and scored 832/841 held-out frames. python forest.py produced a second feature-based comparison. | “I trained two convolutional layers and checked them against a template and a random forest on completely unseen people.” |
| M4 · inference | Apply a trained model continuously and preserve frame identity under retries. | Training uses labeled batches to update weights. Serving loads frozen weights once. The transaction publishes the original grid, frame ID, model version and scores together. | python -m pytest -q test_pipeline.py passed, including concurrent submissions with the same sequence. | “If a response is lost and the same reading is retried, the latest prediction stays paired with its original frame.” |
| M5 · mobile | Show how a mobile client reacts to data without polling the API. | A React Native component stores the latest snapshot in state. Updating state rerenders the heatmap and scores. Expo provides native targets and a browser target for automated tests. | python -m proof.dashboard verified all 36 rendered maps. Expo exported the iOS bundle. Browser and device evidence are recorded separately. | “I implemented the Expo client and tested it on the React Native web target. My next deployment check is Expo Go on an iPhone.” |
| M6 · operations | Demonstrate recovery and measure what a viewer experiences. | Timeout measures sensor freshness. Firestore snapshot metadata indicates whether the SDK is serving cached data. Sequence gaps track missed readings. | The dashboard test forced both sensor silence and network loss. python -m proof.benchmark measured 17.77 frames/s locally. | “A connected database can still be showing a stale sensor. I tested those states separately.” |
| M7 · release | Explain how an evaluated model reaches serving and can be rolled back. | Immutable checkpoint, recorded config, input transform and reviewed validation results travel together. | sha256sum -c evidence/checkpoint.sha256 verifies the saved release. See README for promotion and rollback. | “I can identify which weights produced a prediction and restore the previous version if a replacement regresses.” |

A batch is one group of examples used for a gradient update. An epoch covers the complete training split. Cross-entropy penalizes the model for assigning little probability to the true label. Overfitting often shows up as improving training loss alongside deteriorating held-out performance. Participant separation addresses a different danger: nearby frames from one person could make a random frame split look deceptively easy. XGBoost and random forests can work with engineered regional features. The CNN learns its spatial filters during training.

## 90-second demonstration

| Time | Action and narration |
|---|---|
| 0–15 s | Open evidence/frames.png and a source file. “These are public adult pressure-mat recordings. The input comes from the original study. Each row has 2,048 readings.” |
| 15–30 s | Open results.json beside model.py. “I trained on eight people, used two for model selection and held out three. The CNN got 832 frames right. The simpler baselines were competitive.” |
| 30–50 s | Start replay with --pause and open Live. “This sequence is arriving through an authenticated Python endpoint. Firestore publishes its map and CNN scores together. Watch the frame number and pressure distribution.” |
| 50–65 s | Watch the stale indicator and the first resumed frame. “The subscription is connected during this pause. The timer tells me that the last sensor reading is old.” |
| 65–80 s | Open History, select a frame, then Diagnostics. “The history has 32 slots. Diagnostics track rate, gaps and repeated readings. I also tested a browser disconnect and recovery.” |
| 80–90 s | Open the verification ledger. “These results use Firebase emulators and the Expo browser target. I have an exported iOS bundle. Hosted Firebase and an on-device run are the next verification steps.” |

## Draft email · unsent

**Subject — Pressure-mat replay and CNN prototype following our November 20 discussion**

Dear Dr. Park and Professor Jayaraman,

Thank you for describing the engineering work behind your smart-textile research on November 20. My previous experience has focused on historical healthcare data and predictive modeling. Our discussion motivated me to practice three skills you raised: training a CNN on spatial sensor data, transmitting readings continuously, and building a monitoring app that responds to them.

I have since worked through an independent prototype using public adult pressure-mat recordings. It replays individual frames through a Python service, classifies three postures with a PyTorch CNN, and sends each frame and prediction together to an authenticated Firestore listener. On three held-out participants, the CNN classified 832 of 841 frames correctly. A template classifier and a random forest each achieved a slightly higher score.

I have verified the local Firebase emulator pipeline and the Expo dashboard in a browser, including stale readings and reconnection. I would be glad to show you the working replay, the participant split, and a case where the CNN made an error. My next step is to verify the same path on hosted Firebase and a physical phone.

Thank you again for the direction your discussion gave my learning.

Best regards,  
[Your name]

No public artifact URL has been verified. This draft can be sent without links or accompanied by the captured dashboard and evaluation report after review.
