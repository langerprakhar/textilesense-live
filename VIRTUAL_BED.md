# Interactive virtual bed

You drag a pressure mat and a person onto a bed on the laptop, then move and roll the person. A contact model computes the pressure each of the mat's 2,048 sensors would feel. One complete frame per second travels the real pipeline, and your phone shows the result.

```
Person movement → virtual sensor readings → Python validation → CNN inference → Firestore → Expo app on the phone
```

[Console walkthrough video](evidence/interactive/acceptance-console.webm) · [Acceptance results](evidence/interactive/acceptance.json) · [Physical iPhone run](evidence/interactive/physical-phone.json) · [Model behaviour sweep](evidence/interactive/model-behavior.json) · [Phone setup](PHONE.md)

## Run it

Windows, from **PowerShell** or **Command Prompt** in the repository folder. Run setup once:

```powershell
scripts\setup.cmd
```

**Laptop only (offline, local emulators):**

```powershell
scripts\virtual-bed.cmd
```

Open <http://127.0.0.1:8775> (or <http://localhost:8775> if the browser hangs on the numeric address). The terminal prints a temporary viewer password for the browser copy of the phone app at <http://127.0.0.1:8775/monitor>.

**With your phone (hosted Firebase):** set up once using [PHONE.md](PHONE.md), then use two terminals for every demo:

```powershell
scripts\virtual-bed-hosted.cmd
```

```powershell
scripts\phone.cmd
```

If the laptop is on eduroam or another campus network, which block phone-to-laptop traffic, use `scripts\phone.cmd --tunnel`.

## Two data sources, switchable live

| Source | What the CNN receives | Ground truth shown beside the estimate |
|---|---|---|
| **Virtual bed** | New pressure maps generated live from the body model as you move and roll the person. | The posture you selected |
| **Unseen recordings** | Real PhysioNet PmatData frames of persons 11, 12 and 13. These three were held out of both training and validation, so the CNN has never seen them. | The dataset's own label |

Choose **Unseen recordings** on the laptop, or **Play all unseen recordings** on the phone, to start an automatic tour: each of the three people on their back, right side and left side for 8 seconds each, about 72 seconds per loop, repeating. You can also pick a single person and posture. Every frame carries `recording` (for example `S12-2`), `row` and `recorded_label`. The API stores the label but never passes it to the model, and a test sends one grid with two different labels and gets identical scores. In a hosted run, all 32 frames checked in the stored history were byte-for-byte the recorded rows they name, and the CNN matched the label on 32 of 32 ([check](evidence/interactive/tour-identity.json)). Its offline held-out accuracy on these people is 98.9%, so an occasional miss is expected and honest.

## Control it from the phone

The phone's **Stream controls** card has **Play**, **Pause**, **Play all unseen recordings**, and **Choose source** for the virtual bed or one specific recording. A tap writes a small request to `sessions/virtual-bed/controls/{your UID}`. The rules allow only a session viewer, only the fields `action`, `mode`, `subject`, `posture`, `device` and a server-stamped `requested_at`, and only fixed values. The laptop listens, acts, and shows which device asked ("iPhone 17 Pro Max asked to start"). If Play is tapped while the virtual bed is empty, the laptop puts the mat on the bed so readings flow. Dragging and rolling the virtual person stays on the laptop.

## Demonstrate it yourself (about 3 minutes)

| Do this on the laptop | What to point at | What to say |
|---|---|---|
| Drag **Pressure mat** from the toolbox onto the bed. | The dark mat with its 32 × 64 grid. | “This is a virtual version of a 2,048-sensor textile pressure mat.” |
| Click **Start transmitting**. | Frame numbers climbing; the phone shows *No load*. | “Every second, the whole grid goes to Python. An empty mat reads exact zeros, so the model isn't run.” |
| Drag **Person** onto the mat, then click **Centre on mat**. | Heatmap under the body; CNN says *On back*; phone matches. | “The pressure is calculated from how the body rests on an elastic mattress. The CNN sees only these numbers.” |
| Drag the body slowly sideways, then toward the head and foot. | The heatmap follows continuously; grey contact appears beside the mat. | “Grey is real contact that the mat cannot measure. Only the sensing area produces readings.” |
| Click **Right side**, then **Left side**. | The body rolls in place; the knees come forward; the estimate follows. | “Rolling is separate from moving. My setting is stored for comparison, but the model never sees it.” |
| Move the body about 10 cm off centre, or turn it 20°. | The yellow box explains why the estimate may now differ. | “The CNN was trained on centred people. Real recordings shifted the same way fool it too, and I report that rather than hide it.” |
| Click **Get up**. | Zeros return; phone shows *No load*. | “Fresh empty-bed readings keep arriving.” |
| Click **Pause transmission** and wait 4 seconds. | Phone pill turns **Stale**. | “The app never shows an old reading as live.” |
| Click **Start transmitting**. | Phone back to **Live**; sequence continues. | “It recovers on the next frame, with no gap invented.” |
| On the phone, tap **Play all unseen recordings**. | “Real recording: person 12”, the dataset label beside the CNN estimate. | “These are real people the model has never seen, streaming to my phone now. The label comes from the dataset and is only shown for comparison.” |
| Optional: **Diagnostics → Take the link down**, then **Restore the link**. | *Missing sequence numbers* rises by the frames lost. | “Python notices that frames never arrived.” |
| Optional: **Diagnostics → Open it in the Firebase console**. | The same `frame_id` in Firestore. | “Here is the exact document my phone just drew.” |

Keyboard shortcuts for smooth recording: arrow keys move 1 cm (Shift moves 5 cm), `[` and `]` turn 5°, `B`, `L` and `R` roll, `U` gets up, Space starts or pauses.

## What is being measured

**Units.** Every value is simulated interface pressure in **mmHg**, sent as integer counts of 0.1 mmHg (`unit: "mmHg"`, `value_scale: 0.1`). 1 mmHg = 133.3 Pa. Readings below a 1 mmHg dead band are 0. The sensor saturates at 409.5 mmHg.

**Body.** A 75 kg, 1.75 m adult made of capsule-shaped segments carrying standard segment-mass shares. Each segment sinks into a Winkler (elastic) mattress until the mattress pushes back with exactly its weight. Bony areas (sacrum, shoulder blades, heels, hip, shoulder, knee, ankle) are stiffer segments, so they show peaks. In the side postures the hips and knees flex, so the knees rest in front of the trunk. A roll blends the two postures' load paths, which keeps total load equal to body weight throughout. Breathing moves about 1.5% of chest load. Sensor effects are a 3% fixed gain spread, 1.5% frame-to-frame noise, and 1 cell of cover-layer spreading. [body.py](virtual_bed/body.py) · [sensor.py](virtual_bed/sensor.py)

**Mat geometry.** 32 rows across the bed and 64 columns along it. Sensels are 2.4 cm × 2.9 cm, giving a sensing area of 76.8 × 185.6 cm on a 152 × 203 cm queen mattress. Column 0 is at the head. Seen from above, **row 0 runs along the mat's right edge**. That orientation is taken from the training recordings: in PmatData side-lying frames, the flexed knees sit at higher row numbers for “Right” and lower ones for “Left”. The original simulator had this mirrored, which is why its “Turn left” came back as “Right”.

**Coverage.** Only load reaching the sensing area is measured. A body partly off the mat produces a truncated pressure map, and the uncovered part is drawn in grey on the laptop as “real but unmeasured”. *Body load on mat* is simulator ground truth: the share of the person's weight on the sensing area. It is displayed and stored, never sent to the model.

## How placement and coverage affect the CNN input

- The CNN always receives the **complete 32 × 64 mat grid exactly as stored**. It is not cropped, re-centred or padded, and the mat's position on the bed is not an input. Moving the mat changes only which part of the body it sees.
- Values are clipped at 1,000 counts (100 mmHg), then log-scaled with `log(1+v)/log(1001)`. The training data were raw 0–1,000 counts. **Treating one count as 0.1 mmHg is a stated assumption, not a calibration.** Summed over the mat it implies median loads of 58–75 kg for the recorded adults, which is plausible, but it is not proven.
- An all-zero frame is stored with `prediction: null` and `model_status: "not_run_no_load"`.
- The API never reads `simulator.posture_selected`. A test sends identical grids labelled “right” and “left” and gets bit-identical scores.
- Python attaches data-only warnings: `load_at_mat_edge` (more than 2% of load in the outermost ring), `small_contact_area` and `above_model_cap`.

**Unsupported or outside the model's training:** a mat turned on the bed (not offered), a body turned more than about 5°, shifted more than about 6 cm sideways, or partly off the mat, mid-roll frames, empty beds, sitting, other body sizes, and anything clinical. The console's yellow box lists which of these applies to the current placement.

## Results, reported separately

**Simulator correctness: 19/19 unit checks and 11/11 live checks.** Body weight is conserved on the mat (75 kg ± 3%), during a roll and at any turn. A 1 cm move changes the frame smoothly, and a 10 cm move shifts the centroid by 10 cm in rows or columns. Off-mat load gives zeros. Partial coverage shrinks steadily as the body slides off, and measured load matches true load on the mat within the dead-band loss. Left and right postures are mirror images. Empty readings are exact zeros. [test_simulator.py](test_simulator.py)

**Model behaviour: 9/9 recorded live, with known limits.** Centred and aligned, the saved CNN labels all three simulated postures correctly: on back 88–89%, left side 98–99%, right side 99%. It was trained without shift or rotation augmentation. Moving the body about 10 cm sideways, turning it 10–20°, or pushing it partly off the mat can change its answer. Shifting real held-out recordings by 8 rows (19 cm) causes the same failures, so this is a property of the model, not of the simulator. Its 98.9% held-out accuracy applies to recorded frames, not to simulated ones. [Sweep](evidence/interactive/model-behavior.json)

**Transport: 6/6 local checks, 5/5 API checks, and verified on a physical iPhone.** Pause stops frames, and the app marks the last one stale. Resume continues the sequence and flags the first frame as resumed. A link outage is counted exactly as missing frames. Every stored score recomputes from its stored grid. On 21 November 2026, an iPhone 17 Pro Max (iOS 26.6.2, Expo Go) on hosted Firebase reported drawing frames `virtual-bed/27` to `68`. It was at most one frame behind, its CNN result changed in step with each action, it showed Stale when paused, and it recovered. [test_interactive.py](test_interactive.py) · [iPhone run](evidence/interactive/physical-phone.json)

## Where things live in Firestore

| Path | Contents |
|---|---|
| `devices/virtual-mat-01` | Mat identity, units, dimensions and pitch |
| `sessions/virtual-bed` | `device` and `readers`, the viewer UIDs allowed to read |
| `sessions/virtual-bed/state/latest` | The newest frame: grid, `frame_id`, digest, timestamps, `validation`, `measurement`, `model_input`, `input_flags`, CNN `prediction`/`scores`, `simulator` truth, counters |
| `sessions/virtual-bed/events/0…31` | The same snapshots as a rotating history of 32 |
| `sessions/virtual-bed/viewers/{uid}` | Each phone's receipt: which frame it drew, device, `physical_device`, server time |

The heatmap and the prediction on every screen come from the same document, so a map can never be paired with another frame's result.
