# Demo video script (about 5 minutes)

You record **two tracks at the same time, in one take**, and merge them afterwards:

- **Track L (laptop):** Chrome showing the console (`http://localhost:8775`), and later the Firebase console. Your voice is recorded here.
- **Track P (phone):** the iPhone's own screen recording. No sound needed.

**Sync marker:** the **frame number** (for example `virtual-bed/240`) is visible on both screens. In the editor, line up the two clips at the moment the same frame number appears on both. Do this at Scene 2, then check it again at Scene 7.

## Before you press record

1. Start both terminal windows (`scripts\virtual-bed-hosted.cmd` and `scripts\phone.cmd --tunnel`). Open `http://localhost:8775` in Chrome.
2. In Chrome, open a **second tab** at the Firebase console: `https://console.firebase.google.com/project/textilesense-live/firestore/databases/-default-/data/~2Fsessions~2Fvirtual-bed~2Fstate~2Flatest`
3. On the console, make the bed empty: if the mat or the person is on it, drag them back to the toolbox. Leave transmission paused.
4. iPhone: **Auto-Lock → Never**, Do Not Disturb on, app open on the **Live** tab.
5. Start **Track P**: Control Center → Screen Recording. Start **Track L**: Windows **Win + Alt + R** (Xbox Game Bar records the Chrome window; turn the microphone on in Game Bar → Capture settings), or the Snipping Tool video mode with the microphone on.
6. Wait 3 seconds before speaking, so there is room to trim.

## Scene 1: Introduction (0:00–0:20) · Track L

**Show:** the empty bed console.

> "This is TextileSense Live. On the laptop is a virtual hospital bed with a 2,048-sensor pressure mat. On my phone is the monitoring app. In between, every reading goes through Python validation, a trained CNN, and Firebase Firestore."

## Scene 2: Mat and first readings (0:20–0:40) · L, then P · **SYNC POINT**

**Do:** drag **Pressure mat** onto the bed, then click **Start transmitting**.

> "I place the pressure mat on the bed and start transmitting. One complete frame, all 2,048 values, goes out every second. The mat is empty, so every sensor reads zero. The app says no load, and the model isn't even run, because it only learned occupied beds."

**Phone shows:** Live, "No load", and the frame number climbing. *(Note one frame number for syncing.)*

## Scene 3: Person lies down (0:40–1:05) · L

**Do:** drag **Person** onto the mat, then click **Centre on mat**.

> "Now a person lies down. The pressure isn't a picture; it's calculated from how a 75-kilogram body rests on an elastic mattress, with peaks at the shoulders, sacrum and heels. On the right is the frame that was actually committed to Firestore. The CNN looks only at those numbers and says: on back."

## Scene 4: Moving across the bed (1:05–1:30) · L

**Do:** drag the person slowly sideways, then toward the head and the foot.

> "As I move the person, the measured pattern follows continuously. The grey area is real contact that falls off the mat. The sensor can't feel it, so it never reaches the model."

## Scene 5: Rolling (1:30–1:55) · L with P

**Do:** click **Right side**, wait, then **On back**.

> "Rolling is a separate action from moving. The person turns in place, and the knees come forward. The CNN follows: right side, then back. My setting is stored beside each frame for comparison, but the model never receives it. It only sees pressure."

## Scene 6: What I improved, and what's still not perfect (1:55–2:30) · L

**Do:** with the person on their back, drag them about 15 cm sideways. Then set **Turn** to 20°, and then to 180° (head at the foot of the bed). The estimate stays **On back**.

> "My first model failed exactly here. It had only seen people lying in the middle of the mat. Moved 19 centimetres, it got under half of real frames right, and head-to-foot just 17 percent. So I retrained it on the same real recordings, randomly moved and turned, and never on this simulator. Version 2 stays at about 99 percent on unseen people however they're placed, and you can see it holding here."

**Do:** set **Turn** back to 0°, click **Centre on mat**, then **Left side**.

> "It isn't perfect. Lying on the left side exactly in the centre, my simulated body still reads as back. Move it a few centimetres and it's right. I'd rather show you that than hide it. It's listed in the app with the other limits."

**Do:** drag the person about 8 cm toward the **left of the screen** (or press ← eight times). It now reads **Left side**. Moving right instead does not fix it. Then click **Get up**.

> "When the person gets up, fresh empty-bed readings keep arriving."

## Scene 7: Inside Firestore (2:30–3:05) · L, then P · **SECOND SYNC POINT**

**Do:** drag the person back on and click **Centre on mat**. Click **Pause transmission**. Switch to the **Firebase console tab** and press F5.

> "I'll pause so the numbers hold still. This is Google's Firebase console, the real database. Here is the latest document. Its frame ID matches the one on my phone. Here is the CNN's prediction, the scores, my posture setting stored separately, and the 2,048 values themselves."

**Do:** click **viewers**, then the document inside it.

> "And this is my iPhone reporting which frame it drew, with physical device true, stamped by the server's clock."

**Phone shows:** the same frame number, now marked **Stale**.

> "Because nothing new has arrived, the phone marks the reading as stale instead of showing an old value as if it were current."

## Scene 8: Real people the model has never seen (3:05–3:50) · Track P full screen

**Do:** switch Chrome back to the console tab. On the phone, tap **Play all unseen recordings**.

> "Now real data. These are pressure-mat recordings of three people who were held out of training completely, so the CNN has never seen them. I'm starting the stream from my phone. For each frame you see the dataset's own label next to the model's estimate. On these unseen people, version 2's tested accuracy is about 99 percent."

**Let it run** through two or three postures and read one aloud: "Person 12, right side, the model says right side."

## Scene 8b: A tour of the phone app (3:50–4:35) · Track P full screen

Keep the recordings playing. On the phone, scroll down the **Live** tab a little, then tap each tab in turn. Spend about 10 seconds on each.

**Live** (scroll down to the tiles):

> "Under the map are the measurements Python calculates for every frame: peak pressure, average contact pressure, how much load is on the mat, and how much of the mat is in contact. If a frame looks unusual, for example pressure right at the mat's edge, a yellow warning appears here."

**Trends:**

> "Trends shows the last 32 frames. This colour strip is the CNN's estimate over time. Blue is back, green is right side, amber is left side. You can see it change as the recordings switch posture. Below are peak pressure and load over time, and I can tap any recent frame to see its map alongside its own estimate."

**Delivery:**

> "Delivery follows this exact frame through the system: captured on the laptop, validated by Python, scored by the CNN in a couple of milliseconds, committed to Firestore, and drawn on this phone. Underneath are the reliability counters: frames received, any missing sequence numbers, duplicates, and the rate, about one frame per second."

**Model:**

> "And Model explains what the CNN is and isn't: trained on eight real people, moved and turned during training, about 99 percent accurate on three it had never seen however they lie. It also lists its limits: simulated pressure, a few placements it still misreads, and no clinical claims."

Tap back to **Live**.

## Scene 9: Pause and close (4:35–5:00) · P, then L

**Do:** on the phone, tap **Pause**.

> "I can stop and resume the whole stream from the phone too. To sum up: readings travel from the mat through Python validation, a trained CNN, and Firestore, to a real phone, live, with every frame traceable from end to end. The pressure on the bed is simulated, and this is a monitoring prototype, not a clinical tool. The next step is a physical textile mat."

Stop **Track P** (red pill → Stop), then stop **Track L** (Win + Alt + R).

## Putting the two clips together

1. Put **Track L** on the main video track. Its audio is your narration.
2. Put **Track P** above it. Slide it until the **frame number from Scene 2** appears at the same instant on both. Check that Scene 7 still lines up.
3. Layout:
   - **Scenes 1–7:** laptop full screen, phone as a small picture-in-picture in the bottom-right corner (about 30% height).
   - **Scenes 8 and 8b:** swap, with the phone large or side-by-side, since the action happens on the phone.
   - **Scene 9:** back to the laptop, phone in the corner.
4. Mute Track P's audio. Trim the first 3 seconds of both clips.

Free editors that do this: **Clipchamp** (built into Windows 11) or **CapCut**. In Clipchamp, drag the phone clip onto the timeline above the laptop clip, then use **Picture in picture**.
