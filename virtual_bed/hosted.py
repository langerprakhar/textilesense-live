"""Prepare and check a hosted Firebase project for the phone demonstration.

    python -m virtual_bed.hosted check
    python -m virtual_bed.hosted setup --email viewer@yourdomain

Reads TEXTILE_PROJECT and EXPO_PUBLIC_API_KEY (scripts\\hosted-*.cmd load them
from hosted.env). The Python service authenticates with Google Application
Default Credentials: either `gcloud auth application-default login` as a
project owner, or GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account
key kept outside the repository. Nothing secret is written into the app.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

SESSION = "virtual-bed"
DEVICE = "virtual-mat-01"
ROOT = Path(__file__).resolve().parent.parent


def need(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Set {name} in hosted.env first (see PHONE.md).")
    return value


def credentials():
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    except DefaultCredentialsError:
        sys.exit(
            "No Google credentials for Python. Run:\n"
            "  gcloud auth application-default login\n"
            "  gcloud auth application-default set-quota-project YOUR_PROJECT_ID"
        )
    return creds


def deploy_rules(project, creds):
    from google.auth.transport.requests import AuthorizedSession

    http = AuthorizedSession(creds)
    base = f"https://firebaserules.googleapis.com/v1/projects/{project}"
    source = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    made = http.post(
        base + "/rulesets",
        json={"source": {"files": [{"name": "firestore.rules", "content": source}]}},
    )
    if not made.ok:
        return f"could not upload rules ({made.status_code}): {made.text[:200]}"
    ruleset = made.json()["name"]
    release = f"projects/{project}/releases/cloud.firestore"
    r = http.patch(f"{base}/releases/cloud.firestore", json={"release": {"name": release, "rulesetName": ruleset}})
    if r.status_code == 404:
        r = http.post(f"{base}/releases", json={"name": release, "rulesetName": ruleset})
    return "deployed" if r.ok else f"could not release rules ({r.status_code}): {r.text[:200]}"


def check():
    project = need("TEXTILE_PROJECT")
    if project.startswith("demo-"):
        sys.exit("TEXTILE_PROJECT must be your real Firebase project ID, not a demo- ID.")
    need("EXPO_PUBLIC_API_KEY")
    creds = credentials()
    from store import database

    db = database()
    ok = True
    try:
        session = db.document(f"sessions/{SESSION}").get(timeout=10).to_dict()
    except Exception as exc:  # report every failure plainly
        sys.exit(f"Firestore is not reachable for {project}: {exc}\nCreate the Firestore database (PHONE.md step 3).")
    print(f"Firestore reachable in {project}.")
    if not session or session.get("device") != DEVICE or not session.get("readers"):
        print(f"sessions/{SESSION} is not provisioned yet. Run scripts\\hosted-setup.cmd.")
        ok = False
    else:
        print(f"sessions/{SESSION} has {len(session['readers'])} viewer(s).")
    env = ROOT / "mobile" / ".env.local"
    if env.exists() and project in env.read_text():
        print("mobile/.env.local points the app at this project.")
    else:
        print("mobile/.env.local is missing or points elsewhere. Run scripts\\hosted-setup.cmd.")
        ok = False
    del creds
    return ok


def setup(email):
    project = need("TEXTILE_PROJECT")
    api_key = need("EXPO_PUBLIC_API_KEY")
    if project.startswith("demo-"):
        sys.exit("TEXTILE_PROJECT must be your real Firebase project ID.")
    creds = credentials()
    from firebase_admin import auth

    from store import database
    from virtual_bed.launch import DEVICE_DOC

    db = database()  # initialises the Admin SDK for this project
    print("Security rules:", deploy_rules(project, creds))
    try:
        user = auth.get_user_by_email(email)
        print(f"Viewer {email} already exists. Keeping its password.")
    except auth.UserNotFoundError:
        password = getpass.getpass(f"Choose a password for {email} (8+ characters, hidden): ")
        if len(password) < 8:
            sys.exit("Use at least 8 characters.")
        user = auth.create_user(email=email, password=password, email_verified=False)
        print(f"Created viewer {email}.")
    except Exception as exc:
        sys.exit(
            f"Could not reach Firebase Authentication: {exc}\n"
            "Enable Authentication > Sign-in method > Email/Password in the console (PHONE.md step 4)."
        )
    db.document(f"devices/{DEVICE}").set(DEVICE_DOC)
    ref = db.document(f"sessions/{SESSION}")
    current = ref.get().to_dict() or {}
    readers = sorted(set(current.get("readers", [])) | {user.uid})
    ref.set({"device": DEVICE, "readers": readers}, merge=True)
    print(f"sessions/{SESSION}: device {DEVICE}, {len(readers)} viewer(s).")
    env = ROOT / "mobile" / ".env.local"
    env.write_text(
        "# Written by virtual_bed.hosted. Public client configuration only.\n"
        f"EXPO_PUBLIC_PROJECT_ID={project}\n"
        f"EXPO_PUBLIC_API_KEY={api_key}\n"
        f"EXPO_PUBLIC_SESSION={SESSION}\n"
        f"EXPO_PUBLIC_VIEWER_EMAIL={email}\n",
        encoding="utf-8",
    )
    print(f"Wrote {env.relative_to(ROOT)}. Next: scripts\\virtual-bed-hosted.cmd, then scripts\\phone.cmd.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    s = sub.add_parser("setup")
    s.add_argument("--email", required=True, help="viewer account the phone signs in with")
    args = parser.parse_args()
    if args.command == "check":
        sys.exit(0 if check() else 1)
    setup(args.email)


if __name__ == "__main__":
    main()
