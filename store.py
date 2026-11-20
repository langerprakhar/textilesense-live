import os

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials


class EmulatorCredential(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


def database():
    project = os.environ.get("TEXTILE_PROJECT", "demo-textilesense")
    if project in {"demo-textilesense", "demo-textilesense-bed"}:
        os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:" + str(
            int(os.getenv("TEXTILE_EMULATOR_PORT", "8080"))
        )
        credential = EmulatorCredential()
    else:
        credential = credentials.ApplicationDefault()
    app = firebase_admin.initialize_app(credential, {"projectId": project})
    return firestore.client(app)
