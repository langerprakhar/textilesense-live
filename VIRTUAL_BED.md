# Phase 2 · Connect a virtual pressure mat to Firestore

[Watch the control panel, live app and Firestore viewer](evidence/virtual_bed/virtual-bed.mp4) · [See a saved document](evidence/virtual_bed/firestore.png)

You control an imaginary person. A Python program calculates how strongly that person would press each spot on a bed. Those numbers actually travel through the API into a database. The pressure itself is simulated in arbitrary counts. The app reads its copy from Firestore. You can see both copies on screen.

## Try it on your laptop

1. Open a terminal **inside the folder containing README.md**. On Windows, install 64-bit Python 3.12 with its `py` launcher, Node.js 24 with npm, and JDK 21. Open a new **Command Prompt** and run:

   ```bat
   scripts\setup.cmd
   scripts\virtual-bed.cmd
   ```

   On macOS or Linux, install Python 3.12, Node 24 with npm, Java 21 and FFmpeg. Run the setup once, then launch the virtual bed.

   ```bash
   bash scripts/setup.sh
   bash scripts/virtual-bed.sh
   ```

2. Wait for the terminal to print **Open http://127.0.0.1:8775**. Open that address on the computer running the script. The controls are on the left and the Expo app is on the right. Sign in on the right with the email and temporary local password printed by the launcher. The emulator lives on your own computer. This path requires no Google account.
3. Click **Start sensor** with the bed empty. The frame number advances about once a second. Click **Inspect one sensor cell** to watch one location. Leave row 15, column 34 selected.
4. Click **Lie on back**. Watch the cell value increase, the heatmap fill in, and the frame number change. Click **Turn left** or **Turn right**. *Scenario* on the left is the command you gave the virtual person. *Result* is what the CNN calculated from the resulting numbers. The two can disagree.
5. Click **Open Firestore database**. A second tab opens Google's local Firebase Emulator Suite UI, directly at the latest document. Find **frame_id**, **scenario**, **prediction**, and **values**. The value at index **994** is row 15, column 34, because each row contains 64 columns. Click **Pause sensor** to make comparing the same frame in both tabs easier.
6. Start again and click **Get up**. The bed unloads gradually and settles to zero, with fresh “Empty bed” frames still arriving. Click **Pause sensor** and wait four seconds. The app keeps the last frame and marks it stale. Click **Start sensor** to resume.

A local run pauses after 120 frames. Press Ctrl+C in the terminal to stop the services. Restarting the launcher starts a fresh, temporary database. If you see an address-in-use error, stop the previous virtual-bed terminal first. The phase-one replay has its own ports and session.

## How I set up Firestore

**Firebase** provides the services. **Authentication** answers “Who is looking?” **Firestore** holds the readings. In Firestore, a *document* is one saved item with named fields. A *collection* groups documents.

| Location | What you can see there |
|---|---|
| devices/virtual-mat-01 | The virtual sensor's identity, dimensions, and units. |
| sessions/virtual-bed | Which device supplies the session and which viewer UIDs may read it. A UID is the viewer's Firebase account identifier. |
| sessions/virtual-bed/state/latest | The most recent grid, sequence number, timestamp, scenario, model version, scores and result together. |
| sessions/virtual-bed/events | The same snapshots in a rotating history of up to 32 items. |

1. **Start Firebase locally.** The launcher asks the Firebase CLI to start Firestore on port 8180, Auth on 9199 and the Firebase inspection UI on 4100. It points Firestore at the project's security rules. The services bind to your own computer. [Firebase configuration](firebase.virtual.json) · [Rules](firestore.rules)
2. **Give a viewer access.** The launcher creates an account in the Auth emulator. It puts that account's UID in the session's readers list and assigns the session to virtual-mat-01. The Expo client signs in with email and password. The rules allow that viewer to read the session state and history. They give the client no write permission. [Setup code](virtual_bed/launch.py)
3. **Take a reading.** Each second the simulator builds a fresh 32 × 64 grid. It applies pressure around the head, shoulders, hips and heels, shifts the distribution for a turn, and gradually loads or unloads the bed. Small variations change successive frames. It sends the grid, its source, device, session, capture time, scenario and sequence to Python over HTTP. The send credential stays on the server. [Pressure calculation](virtual_bed/sensor.py) · [Sender](virtual_bed/controller.py)
4. **Write the result.** The API checks the incoming reading. For a loaded bed it passes just the grid through the saved model. For an all-zero virtual frame it stores “Empty bed” and an empty score list. The API uses the Firebase Admin SDK to commit the result and recent history together. The operator panel independently reads the saved document after the commit. [API](api.py)
5. **Listen on the app.** The Expo app subscribes to state/latest using the Firebase JS SDK's onSnapshot. Firestore delivers a new snapshot to the signed-in app when Python writes a frame. The app colors the cells using that document's grid and displays that same document's result. [App](mobile/App.tsx)

## Use your own hosted Firebase project

This is an optional route for running the same virtual mat through Google's hosted service. The verified demonstration above uses the local emulator. Hosted verification requires access to your project. Use a **dedicated Spark project** and keep billing disabled.

1. In the [Firebase console](https://console.firebase.google.com/), create or select the dedicated project. Under **Build → Firestore Database**, create the **(default)** database in Standard edition with production rules and select your location. Under **Authentication → Sign-in method**, enable Email/Password. Under **Users**, add a demo viewer, set a password, and copy its UID.
2. Under **Project settings → General → Your apps**, register a Web app. Expo uses Firebase's JavaScript SDK. Copy **projectId** and **apiKey** from its web configuration. The API key identifies the client project. The rules control database access.
3. Open **Firestore Database → Rules**, replace the starter rules in this dedicated project with the contents of **firestore.rules** from this folder, and click **Publish**. Then open **Data** and create these two documents. Use the exact IDs, field names and types below. Firestore creates their collections as you add the documents.

   | Collection | Document ID | Fields to enter |
   |---|---|---|
   | devices | virtual-mat-01 | source (string) = virtual_pressure_mat, rows (number) = 32, cols (number) = 64, units (string) = simulated counts |
   | sessions | virtual-bed | device (string) = virtual-mat-01, readers (array) = one string containing the viewer UID |

   Python creates **state/latest** on the first accepted reading. Leave that document for the service to create.
4. Give the backend identity permission to read and write Firestore data in this demo project, for example the **Cloud Datastore User** project role. On a trusted laptop, install the Google Cloud CLI and run `gcloud auth application-default login` as that identity. This creates local credentials for Python. Keep them outside the repository. The app viewer signs in separately through Firebase Auth.
5. Stop the local virtual-bed launcher. In the project directory run the following using the web configuration from step 2.

   ```bash
   export TEXTILE_PROJECT='your-project-id'
   export EXPO_PUBLIC_API_KEY='your-web-api-key'
   bash scripts/virtual-bed.sh --hosted
   ```

6. Open the terminal's address, enter the hosted viewer's email and password in the app, and click **Start sensor**, then **Lie on back**. In the actual Firebase console, open **Firestore → Data → sessions → virtual-bed → state → latest**. Confirm the same frame ID, source and result that the app shows. Pause to compare a single cell. The hosted launcher caps each start at 30 frames. Each accepted frame writes two documents and incurs reads for the transaction, verification and listeners.

If Python reports missing credentials, revisit step 4. A viewer “permission denied” points to the rules or the UID in the readers array. A 403 from ingestion can indicate a mismatched device in the session. [Official Firestore quick start](https://firebase.google.com/docs/firestore/quickstart) · [Emulator guide](https://firebase.google.com/docs/emulator-suite/connect_firestore) · [Firestore listeners](https://firebase.google.com/docs/firestore/query-data/listen)

## What the live test verified

The automated browser test operated every control, checked one saved frame for each scenario against the Expo screen, reran the CNN independently on the saved grids, and opened the final frame in the official Firestore viewer. It also paused and resumed the stream. A separate rules check received 403 for a signed-out read, 200 for the authorized viewer read and 403 for a viewer write. These tests used the emulator and the browser build of Expo. The saved CNN was trained on recorded adult pressure maps. Its dataset accuracy does not establish accuracy on simulated bodies or other mats. [Frame evidence](evidence/virtual_bed/observed.json) · [Access checks](evidence/virtual_bed/rules.json)

**What to say during the demonstration**

“In the first phase I replayed recorded measurements. Here I control a virtual person and generate new measurements every second. Watch this one spot on the bed as I lie down. Python receives the whole grid and the trained model estimates the posture. Now I can open Firestore and show you exactly the frame my app received. Getting up produces a fresh empty reading. Pausing the sensor makes the last reading go stale. This run uses simulated pressure and a local Firebase emulator.”
