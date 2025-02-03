import os
from twilio.rest import Client

# Load environment variables
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")  # Your Twilio phone number
to_number = "whatsapp:+971553470210"  # The recipient's number in WhatsApp format

# Debugging: Print Twilio Credentials (Masked for Security)
print(f"Debug - Twilio Account SID: {account_sid if account_sid else 'MISSING'}")
print(f"Debug - Twilio Auth Token: {'***' if auth_token else 'MISSING'}")
print(f"Debug - Twilio From Number: {from_number if from_number else 'MISSING'}")

if not all([account_sid, auth_token, from_number]):
    raise ValueError("Twilio credentials are missing. Check your environment variables.")

# Initialize Twilio client
client = Client(account_sid, auth_token)

# Debugging: Print message details before sending
message_body = "Test message from OnlyHealth Bot!"
print(f"Debug - Preparing to send WhatsApp message:")
print(f"Debug - From: whatsapp:{from_number}")
print(f"Debug - To: {to_number}")
print(f"Debug - Message: {message_body}")

try:
    # Send the WhatsApp message
    message = client.messages.create(
        body=message_body,
        from_=f"whatsapp:{from_number}",  # Prefix with "whatsapp:"
        to=to_number  # Ensure the recipient is also prefixed with "whatsapp:"
    )

    # Debugging: Print Message SID
    print(f"✅ Message Sent Successfully! Message SID: {message.sid}")

except Exception as e:
    # Debugging: Print error message if Twilio API request fails
    print(f"❌ Error Sending Message: {str(e)}")