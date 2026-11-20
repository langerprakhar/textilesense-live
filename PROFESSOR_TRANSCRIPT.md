# TextileSense Live · 90-second narration

Play [the continuous recording](evidence/live_test/demonstration.mp4) from the beginning. The left panel shows the actual source row, Python results and a Firestore read-back. The right panel is the running Expo app. The recording has no audio. Read only the quoted text.

**0:00–0:15 · Source**

“Professor Jayaraman and Dr. Park, our November 20 conversation motivated me to build this demo. These numbers come from a public study of adults lying on a pressure mat. Each moment contains 2,048 measurements showing where the body pressed against the bed.”

**0:15–0:30 · Start the replay**

“The replay has just started. Once a second, Python sends one recorded pressure map. The receiving service checks its size and values. Each map has a source row and a frame number, so I can trace it back to the recording.”

**0:30–0:45 · Read the prediction**

“The model learned from examples labeled back, right side, or left side. It looks at which nearby sensors carry weight. I tested it on three people held out from training. It classified 832 of 841 frames correctly. Two simpler models scored slightly higher.”

**0:45–1:05 · Follow one frame from left to right**

“Look at the frame number on the left, then find the same number on the right. Python saved the pressure map and its prediction together. The app listens to Firestore and draws that frame automatically. This run uses the local Firebase emulator and the browser version of the mobile app.”

**1:05–1:20 · Pause**

“I’ve paused the readings. The frame number stays still, the age goes up, and the app marks the picture stale. That tells the viewer exactly where the last known position came from and that it may be out of date.”

**1:20–1:30 · Resume**

“Now the readings are back. A new frame arrives and the app returns to live. The next steps are connecting a physical mat and verifying the same flow on a phone.”

## Recording it yourself

Run the two commands in the [quick start](README.md). Each rehearsal creates a new MP4 in recordings/. For a narrated copy, play the MP4 at normal speed and record your screen with your microphone enabled, or import the MP4 into a video editor and record a voiceover against this timeline. The automated pause and restart align with the narration. You can also use the manual replay procedure in the README to demonstrate it in person.
