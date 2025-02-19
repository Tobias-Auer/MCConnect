import base64
import json

session_cookie = "eyJ1c2VybmFtZSI6InRvYmlhczEyMzRyIn0.Z7YNcA.Sb37ctFbta88HaKS8mvjtJ8Te4w"

def decode_base64_part(data):
    """Decode base64-encoded part of the session cookie."""
    try:
        # Add missing padding if necessary
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(data).decode("utf-8")
    except Exception as e:
        return f"Error decoding base64: {e}"

# Split session into its parts
parts = session_cookie.split(".")
if len(parts) < 2:
    print("Invalid session format!")
else:
    payload_decoded = decode_base64_part(parts[0])
    print("Decoded Payload:", payload_decoded)

    # Attempt to parse JSON
    try:
        print("Parsed JSON:", json.loads(payload_decoded))
    except json.JSONDecodeError:
        print("Payload is not valid JSON!")
