import os
import sys

from store import database

if os.getenv("TEXTILE_PROJECT", "demo-textilesense") != "demo-textilesense":
    raise RuntimeError("This test writes only to the local demo emulator")

db = database()
session = db.collection("sessions").document(sys.argv[1])
if len(sys.argv) == 3:
    session.set({"readers": [sys.argv[2]], "device": "mat01"})
else:
    session.collection("state").document("proof").set(
        {"source": "synthetic-proof", "sample": int(sys.argv[3])}
    )
