import os
import base64
from email import message_from_bytes

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

CREDENTIALS_PATH = os.path.join(
    PROJECT_ROOT,
    "credentials.json"
)

TOKEN_PATH = os.path.join(
    PROJECT_ROOT,
    "token.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(
            TOKEN_PATH,
            SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH,
                SCOPES
            )

            creds = flow.run_local_server(
                port=0,
                open_browser=False
            )

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build(
        "gmail",
        "v1",
        credentials=creds
    )


def decode_body(payload):
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:

            mime_type = part.get("mimeType", "")

            if mime_type == "text/plain":
                data = part.get("body", {}).get("data")

                if data:
                    body += base64.urlsafe_b64decode(
                        data
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )

            elif "parts" in part:
                body += decode_body(part)

    else:
        data = payload.get("body", {}).get("data")

        if data:
            body = base64.urlsafe_b64decode(
                data
            ).decode(
                "utf-8",
                errors="ignore"
            )

    return body


def get_header(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")

    return ""


def main():

    print("Connecting to Gmail...")

    service = get_gmail_service()

    print("Connected.")

    result = service.users().messages().list(
        userId="me",
        q="label:news",
        maxResults=5
    ).execute()

    messages = result.get("messages", [])

    if not messages:
        print("No messages found with label:news")
        return

    print(
        f"\nFound {len(messages)} messages.\n"
    )

    for item in messages:

        message = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="full"
        ).execute()

        payload = message.get("payload", {})
        headers = payload.get("headers", [])

        subject = get_header(headers, "Subject")
        sender = get_header(headers, "From")
        date = get_header(headers, "Date")

        body = decode_body(payload)

        body_preview = (
            body.replace("\n", " ")
            .replace("\r", " ")
            .strip()
        )

        body_preview = body_preview[:500]

        print("=" * 70)
        print(f"Message ID: {message['id']}")
        print(f"Subject: {subject}")
        print(f"From: {sender}")
        print(f"Date: {date}")
        print()
        print("Body preview:")
        print(body_preview)
        print()


if __name__ == "__main__":
    main()
