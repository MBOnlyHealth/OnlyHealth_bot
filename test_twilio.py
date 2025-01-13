from twilio.rest import Client
import os

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")

print(f"Account SID: {account_sid}")
print(f"Auth Token: {'***' if auth_token else 'MISSING'}")
print(f"From Number: {from_number}")

twilio_client = Client(account_sid, auth_token)
twilio_client.messages.create(
    body="Test Message",
    from_=from_number,
    to="whatsapp:+971553470210"
)
