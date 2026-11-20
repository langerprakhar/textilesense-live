# Physical iPhone check

**Status: BLOCKED.** This execution host has no attached USB device interface, paired iPhone, or configured private network route to the user's phone. The iOS bundle exported successfully. A public Metro URL by itself would leave the phone unable to reach the protected local Auth and Firestore emulators.

## On your laptop and iPhone

Use a laptop and phone signed into your own private Tailscale network. Restrict that network's access policy to your devices. Sign in through the Tailscale apps. Keep Firebase bound to 127.0.0.1 as configured in firebase.json. First start the local Firestore/Auth emulators, run provision.py, and start the Python API as described in the README. Run these on the laptop:

```bash
tailscale serve --bg --tcp=9099 tcp://127.0.0.1:9099
tailscale serve --bg --tcp=8080 tcp://127.0.0.1:8080
cd mobile
export EXPO_PUBLIC_EMULATOR_HOST="$(tailscale ip -4)"
export REACT_NATIVE_PACKAGER_HOSTNAME="$EXPO_PUBLIC_EMULATOR_HOST"
npx expo start --lan --port 8081
```

Allow Metro port 8081 from your phone on the private network. Open Expo Go supporting SDK 58 on the iPhone. Open the QR code, or enter exp:// followed by the laptop's Tailscale IP and :8081. Sign in as viewer@example.test with the demo password you set in provision.py. In the backend terminal run `python replay.py --pause` on a fresh session. Watch the frame ID on the iPhone match the Python output, capture the pause, and verify the next frame clears “Stale.” Save the phone recording and device/Expo versions before marking PASS. After the run use `tailscale serve --tcp=9099 off` and `tailscale serve --tcp=8080 off` on the laptop. These instructions are a private-network handoff; this route has not been device-tested here.

An alternative is an approved hosted Spark project, using the account setup in README.md and its EXPO_PUBLIC_PROJECT_ID and EXPO_PUBLIC_API_KEY. A project owner must provision a viewer, deploy the access rules, and grant the backend a scoped identity. Keep private keys and backend tokens out of Expo configuration.
