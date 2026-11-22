# Demo: start, reset, record, stop

Follow this from top to bottom. Text in a grey box is a command to paste. Text after **Say:** is what you read aloud. The whole video is about 5 minutes.

---

## Part A · Start everything (5 minutes, before recording)

**A1.** Open **PowerShell** (Start menu, type *PowerShell*, press Enter). Paste this line and press Enter. It stops anything left over from earlier, so you begin clean:

```powershell
Get-NetTCPConnection -LocalPort 8775,18735,8081 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
```

Nothing is printed. That's normal.

**A2.** In the same window, paste these two lines one at a time:

```powershell
cd C:\Textilesense-live\textilesense-live
```

```powershell
scripts\virtual-bed-hosted.cmd
```

Wait until you see **`Virtual bed console: http://127.0.0.1:8775`**. **Leave this window open.** This is window 1, the bed.

**A3.** Open a **second** PowerShell window. Paste these two lines one at a time:

```powershell
cd C:\Textilesense-live\textilesense-live
```

```powershell
scripts\phone.cmd --tunnel
```

Wait about one minute for a large **QR code**. **Leave this window open.** This is window 2, the phone app.

**A4.** In Chrome, open **http://localhost:8775** (use *localhost*, not 127.0.0.1). Open a second Chrome tab with the Firebase database:

`https://console.firebase.google.com/project/textilesense-live/firestore/databases/-default-/data/~2Fsessions~2Fvirtual-bed~2Fstate~2Flatest`

Click back to the first tab (the bed).

**A5.** On the iPhone:
1. **Settings → Display & Brightness → Auto-Lock → Never**, and turn on **Do Not Disturb**.
2. Close Expo Go completely: swipe up from the bottom and swipe the Expo Go card away.
3. Open the **Camera**, point it at the QR code in window 2, and tap **Open in Expo Go**. Wait for it to load.
4. If asked, sign in with **prakhar.langer@gmail.com** and your viewer password.

## Part B · Reset to empty (30 seconds)

**B1.** On the laptop console, in the left column under **Transmission**, click **Reset everything**, then **OK**.

**B2.** Check that everything is empty:
- **Laptop:** the bed is empty, the toolbox shows the mat and the person, and the top says **Paused**.
- **iPhone:** the Live tab says **"Waiting for the first frame"**, and Trends says **"No history yet"**.

If the phone still shows an old map, shake the phone, tap **Reload**, and check again.

**B3.** On the iPhone, open the **Live** tab and scroll to the top.

## Part C · Record

**C1.** Start the **phone** recording: swipe down Control Center, then tap **Screen Recording**.

**C2.** Start the **laptop** recording: click on Chrome, then press **Win + Alt + R** (Xbox Game Bar; make sure its microphone is on).

**C3.** Wait 3 seconds, then begin.

### Scene 1: Introduction (0:00–0:20)

**Show:** the empty bed console.

**Say:** "This is TextileSense Live. On the laptop is a virtual hospital bed with a 2,048-sensor pressure mat. On my phone is the monitoring app. In between, every reading goes through Python validation, a trained CNN, and Firebase Firestore. Right now everything is empty: no data has been sent yet."

### Scene 2: Mat and first readings (0:20–0:40) · sync point

**Do:** drag **Pressure mat** from the toolbox onto the bed. Click **Start transmitting**.

**Say:** "I place the pressure mat on the bed and start transmitting. One complete frame, all 2,048 values, goes out every second. The mat is empty, so every sensor reads zero. The phone says no load, and the model isn't even run, because it only learned occupied beds. The frame numbers start from zero."

*(The phone shows Live and frame numbers counting up from 0. You'll use this moment to line up the two videos.)*

### Scene 3: Person lies down (0:40–1:05)

**Do:** drag **Person** onto the mat. Click **Centre on mat**.

**Say:** "Now a person lies down. The pressure isn't a picture; it's calculated from how a 75-kilogram body rests on an elastic mattress, with peaks at the shoulders, sacrum and heels. On the right is the frame actually committed to Firestore. The CNN looks only at those numbers and says: on back."

### Scene 4: Moving across the bed (1:05–1:30)

**Do:** drag the person slowly toward the left of the bed, then toward the head and the foot. Click **Centre on mat** when done.

**Say:** "As I move the person, the measured pattern follows continuously. The grey area is real contact that falls off the mat. The sensor can't feel it, so it never reaches the model."

### Scene 5: Rolling (1:30–1:55)

**Do:** click **Right side**. Wait 3 seconds. Click **On back**.

**Say:** "Rolling is a separate action from moving. The person turns in place, and the knees come forward. The CNN follows: right side, then back. My setting is stored beside each frame for comparison, but the model never receives it. It only sees pressure."

### Scene 6: What I improved, and what's still not perfect (1:55–2:30)

**Do:** with the person on their back, drag them about 15 cm sideways. Then drag the **Turn** slider to **20°**, then to **180°** (head at the foot of the bed). It keeps saying **On back**.

**Say:** "My first model failed exactly here. It had only seen people lying in the middle of the mat. Moved 19 centimetres, it got under half of real frames right, and head-to-foot just 17 percent. So I retrained it on the same real recordings, randomly moved and turned, and never on this simulator. Version 2 stays at about 99 percent on unseen people however they're placed, and you can see it holding here."

**Do:** drag the **Turn** slider back to **0°**. Click **Centre on mat**. Click **Left side**. It says **On back**.

**Say:** "It isn't perfect. Lying on the left side exactly in the centre, my simulated body still reads as back. Move it a few centimetres and it's right. I'd rather show you that than hide it."

**Do:** click on the bed picture once, then press the **←** key **eight times**. It now says **Left side**. Click **Get up**.

**Say:** "When the person gets up, fresh empty-bed readings keep arriving."

### Scene 7: Inside Firestore (2:30–3:05) · second sync point

**Do:** drag **Person** back onto the mat. Click **Centre on mat**. Wait 3 seconds. Click **Pause transmission**. Switch to the **Firebase tab** and press **F5**.

**Say:** "I'll pause so the numbers hold still. This is Google's Firebase console, the real database. Here is the latest document. Its frame ID matches the one on my phone. Here is the CNN's prediction, the scores, my posture setting stored separately, and the 2,048 values themselves."

**Do:** in the left column of the Firebase page, click **viewers**, then the document inside it.

**Say:** "And this is my iPhone reporting which frame it drew, with physical device true, stamped by the server's clock."

**Say:** "Because nothing new has arrived, the phone marks the reading as stale instead of showing an old value as if it were current."

### Scene 8: Real people the model has never seen (3:05–3:50) · phone

**Do:** switch Chrome back to the bed tab. On the phone, in **Stream controls**, tap **Play all unseen recordings**.

**Say:** "Now real data. These are pressure-mat recordings of three people who were held out of training completely, so the CNN has never seen them. I'm starting the stream from my phone. For each frame you see the dataset's own label next to the model's estimate. On these unseen people, version 2's tested accuracy is about 99 percent."

**Do:** let it run for about 20 seconds. Read one aloud.

**Say (example):** "Person 11, right side, and the model says right side."

### Scene 9: A tour of the phone app (3:50–4:35) · phone

**Do:** keep it playing. On the **Live** tab, scroll down a little to the measurement tiles.

**Say:** "Under the map are the measurements Python calculates for every frame: peak pressure, average contact pressure, how much load is on the mat, and how much of the mat is in contact."

**Do:** tap **Trends**.

**Say:** "Trends shows the last 32 frames. This colour strip is the CNN's estimate over time, and you can see it change as the recordings switch posture. Below are peak pressure and load over time."

**Do:** tap **Delivery**.

**Say:** "Delivery follows this exact frame through the system: captured on the laptop, validated by Python, scored by the CNN in a couple of milliseconds, committed to Firestore, and drawn on this phone. Underneath are the reliability counters: missing frames, duplicates, and the rate, about one per second."

**Do:** tap **Model**.

**Say:** "And Model explains what the CNN is and isn't: trained on eight real people, moved and turned during training, about 99 percent accurate on three it had never seen. It also lists its limits: simulated pressure, a few placements it still misreads, and no clinical claims."

**Do:** tap **Live**.

### Scene 10: Close (4:35–5:00)

**Do:** on the phone, tap **Pause**.

**Say:** "I can stop and resume the whole stream from the phone too. To sum up: readings travel from the mat through Python validation, a trained CNN, and Firestore, to a real phone, live, with every frame traceable from end to end. The pressure on the bed is simulated, and this is a monitoring prototype, not a clinical tool. The next step is a physical textile mat."

**C4.** Stop the **phone** recording (tap the red pill at the top, then **Stop**). Stop the **laptop** recording (**Win + Alt + R**).

## Part D · If you want another take

On the laptop, click **Reset everything** and then **OK**, and start again at **Part C**. Everything returns to empty and the frame numbers restart at 0.

## Part E · Finish

In window 1 and in window 2, press **Ctrl+C**, then close both windows. The videos are in **Photos** on the iPhone and in **Videos → Captures** on the laptop.

## Part F · Merging the two videos (Clipchamp, built into Windows)

1. Open **Clipchamp**, then **Create a new video**. Import both videos.
2. Drag the **laptop** video onto the timeline. Its sound is your voice.
3. Drag the **phone** video onto the track **above** it.
4. Line them up: in Scene 2, find the moment frame **virtual-bed/1** appears in both videos, and slide the phone clip until they match. Check that the frame number in Scene 7 matches too.
5. Click the phone clip, then **Picture in picture**, and place it in the bottom-right corner for Scenes 1–7 and 10. For Scenes 8 and 9, make the phone clip large.
6. Mute the phone clip. Trim the first 3 seconds from both. **Export** at 1080p.

## If something goes wrong

| What you see | What to do |
|---|---|
| Phone says *Waiting* after you press Start transmitting | Check that the mat is on the bed. |
| Phone shows a red error screen | In window 2 press Ctrl+C, run `scripts\phone.cmd --tunnel` again, close Expo Go fully, and scan the new QR code. |
| Phone stops updating | It locked. Unlock it and check that Auto-Lock is set to Never. |
| Chrome keeps loading | Use **http://localhost:8775**, not 127.0.0.1. |
| Reset everything shows an error | Window 1 is running old code. Press Ctrl+C there and run `scripts\virtual-bed-hosted.cmd` again. |
