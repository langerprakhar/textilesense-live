# Optional single-channel bench extension

The software simulation exercises a second FastAPI route and writes only the most recently received ADC sample to devices/probe-sim/state/latest. The ESP32 sketch targets devices/probe-fsr/state/latest through that same bridge. The classifier expects 2,048 spatial readings. A single force-sensitive resistor supplies one uncalibrated ADC count and has no posture output. The bridge uses a probe-specific shared token and is intended for one device. Its latest document follows arrival order. The main mat API provides the stronger sequence and deduplication guarantees.

With the local emulators running, activate the Python environment and run:

```bash
export TEXTILE_PROBE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m uvicorn hardware.bridge:app --host 127.0.0.1 --port 8010 &
python -m hardware.simulate
```

For future bench testing use a classic ESP32 development board with GPIO34 (ADC1). With power removed, connect 3.3 V to one FSR lead, the other lead to GPIO34, and a 10 kΩ resistor from GPIO34 to ground. Verify the divider with a meter before connecting the ADC. Use the board's USB power and common ground. Check the exact board pinout and sensor datasheet. Keep the input within the board's ADC voltage rating. Apply light pressure by hand on a tabletop. Raw counts depend on contact area and mechanical mounting.

Install the Espressif Arduino core for the board. Create an ignored esp32/settings.h defining WIFI_SSID, WIFI_PASSWORD, PROBE_URL, PROBE_TOKEN and ROOT_CA as string constants. Use an operator-controlled HTTPS endpoint that forwards only /probe to the local backend. Provide its issuing CA and ensure the board can obtain network time. Keep Firestore emulator ports private. Check serial status codes, boot ID, rising sequence and changing counts. Disconnect Wi-Fi and reconnect to test recovery. An operator would need to supply the board, network and endpoint before this step.

The archive includes the device source and simulated transport evidence. Compilation, power, wiring, sensor response, TLS handshake on the board and physical transmission remain unverified.
