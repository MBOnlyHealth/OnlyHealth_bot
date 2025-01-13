from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fuzzywuzzy import process
import os
import json
import time
import openai
from twilio.rest import Client  # Twilio client for messaging
from dotenv import load_dotenv  # To load variables from .env

# Load environment variables (if running locally)
load_dotenv()

# Get OpenAI and Twilio credentials from environment
api_key = os.getenv("OPENAI_API_KEY")
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")

# Check for missing keys so we fail fast
if not api_key:
    raise ValueError("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")
if not all([account_sid, auth_token, from_number]):
    raise ValueError("Twilio credentials are missing. Please check your environment variables.")

# Initialize OpenAI
openai.api_key = api_key

class ActionSendPackageDetails(Action):
    def name(self) -> Text:
        return "action_send_package_details"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        json_file_path = os.path.join(os.path.dirname(__file__), "package_details.json")

        try:
            with open(json_file_path, "r") as file:
                package_details = json.load(file)

            package_name = tracker.get_slot("package_name") or ""
            user_message = tracker.latest_message.get("text", "").lower()

            # Clean up package_name for better matching
            if package_name:
                package_name = package_name.replace("’", "").replace("'", "").strip()
                if package_name.endswith("package"):
                    package_name = package_name[:-7].strip()

                phrases_to_remove = ["tell me about", "what is included in", "show me details of"]
                for phrase in phrases_to_remove:
                    if package_name.lower().startswith(phrase):
                        package_name = package_name[len(phrase):].strip()
                        break

            normalized_packages = {
                pkg["name"].replace("’", "").replace("'", "").lower(): pkg
                for pkg in package_details
            }
            normalized_keys = list(normalized_packages.keys())
            best_match, match_score = process.extractOne(package_name.lower(), normalized_keys)

            if match_score >= 40:
                matched_package = normalized_packages[best_match]
                pdf_url = matched_package.get("pdf_url")
                if pdf_url:
                    dispatcher.utter_message(
                        text=(
                            f"Here is the detailed document for {matched_package['name']}: "
                            f"{matched_package['description']}\n\n"
                            f"📄 [View PDF Document]({pdf_url})"
                        )
                    )
                else:
                    dispatcher.utter_message(
                        text=(
                            f"Here are the details for {matched_package['name']}: "
                            f"{matched_package['description']}"
                        )
                    )
            else:
                dispatcher.utter_message(
                    text="Sorry, I couldn't find details for the specified package. Please try rephrasing your query."
                )

        except Exception as e:
            dispatcher.utter_message(text=f"Error: {str(e)} - There was an issue retrieving package details.")
            print(f"Detailed Package Error: {e}")

        return []


class ActionSendCalendlyLink(Action):
    def name(self) -> Text:
        return "action_send_calendly_link"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        time.sleep(2)
        dispatcher.utter_message(
            text=(
                "You can book an appointment here: https://calendly.com/onlyhealth-booking. "
                "Our team will visit your home in Dubai to conduct the test."
            )
        )
        return []


class ActionSendCalendlyWithGuidance(Action):
    def name(self) -> Text:
        return "action_send_calendly_with_guidance"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        time.sleep(2)
        dispatcher.utter_message(
            text=(
                "Our packages are tailored to your needs. For accurate pricing and package details, "
                "please visit our booking page: https://calendly.com/onlyhealth-booking. "
                "We provide blood tests at your home in Dubai and include general recommendations "
                "with your results, sent directly via WhatsApp."
            )
        )
        return []


class ActionOpenAIResponse(Action):
    def name(self) -> Text:
        return "action_openai_response"

    def run(
        self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text")
        user_phone_number = tracker.sender_id

        # Simple greetings or farewells
        if user_message and user_message.lower() in ["hello", "hi", "hey", "how are you?"]:
            dispatcher.utter_message(
                text="👋 Welcome, I'm OnlyHealth's dedicated AI! We specialize in 🩸 blood tests conducted at your home in Dubai. How can we assist you today?"
            )
            return []
        elif user_message and user_message.lower() in ["bye", "goodbye", "see you", "thank you"]:
            dispatcher.utter_message(
                text="👋 Thank you for choosing OnlyHealth! Stay healthy and take care. See you soon! 😊"
            )
            return []

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a dedicated OnlyHealth AI, providing blood test services, ECG, and generalized "
                        "recommendations based on results, in Dubai. Recommend packages only when asked based "
                        "on client needs but only use the predefined packages (Dad's Health Pit Stop, Make Sure "
                        "Moms Well!, Performance Boost, Age Strong Check-Up, The Enhanced Athletes Pit Stop, "
                        "Busy Hustler's Tune-Up, Immune Fit for Students). Avoid unnecessary details, don't list "
                        "all packages unless asked, and focus on essential info. Provide a booking link only when "
                        "requested: https://calendly.com/onlyhealth-booking."
                    ),
                },
                {"role": "user", "content": user_message},
            ]

            openai_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=100
            )

            bot_reply = openai_response.choices[0].message.content.strip()

            # If this is a WhatsApp user, send via Twilio
            if user_phone_number.startswith("whatsapp:+"):
                twilio_client = Client(account_sid, auth_token)

                # Ensure our 'from_' also has "whatsapp:" if not already
                from_whatsapp = from_number
                if not from_whatsapp.startswith("whatsapp:"):
                    from_whatsapp = from_whatsapp.lstrip("+")
                    from_whatsapp = f"whatsapp:+{from_whatsapp}"

                twilio_client.messages.create(
                    body=bot_reply,
                    from_=from_whatsapp,
                    to=user_phone_number
                )
                dispatcher.utter_message(text="✅ Message sent successfully!")
            else:
                # For non-WhatsApp channels (e.g., Rasa shell), just respond normally
                dispatcher.utter_message(
                    text="(Non-WhatsApp platform) " + bot_reply
                )

        except Exception as e:
            dispatcher.utter_message(
                text=f"Error: {str(e)} - OnlyHealth's AI could not process your request."
            )
            print(f"Detailed OpenAI Error: {e}")

        return []
