import os
from twilio.rest import Client

# Load environment variables
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")  # Your Twilio phone number
to_number = "whatsapp:+971553470210"  # The recipient's number in WhatsApp format

if not all([account_sid, auth_token, from_number]):
    raise ValueError("Twilio credentials are missing. Check your environment variables.")

client = Client(account_sid, auth_token)

# Ensure the "From" number is formatted as a WhatsApp channel
message = client.messages.create(
    body="Test message from OnlyHealth Bot!",
    from_=f"whatsapp:{from_number}",  # Prefix with "whatsapp:"
    to=to_number  # Ensure the recipient is also prefixed with "whatsapp:"
)

print(f"Message SID: {message.sid}")
