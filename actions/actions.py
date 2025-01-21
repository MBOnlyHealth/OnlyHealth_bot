from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fuzzywuzzy import process
import os
import json
import time
from openai import OpenAI
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key and Twilio credentials from environment variables
api_key = os.getenv("OPENAI_API_KEY")
account_sid = os.getenv("TWILIO_ACCOUNT_SID")  # Twilio SID
auth_token = os.getenv("TWILIO_AUTH_TOKEN")    # Twilio Auth Token
from_number = os.getenv("TWILIO_FROM_NUMBER")  # Twilio 'from' number

if not api_key:
    raise ValueError("OpenAI API key not found. Please add OPENAI_API_KEY to your .env file.")
if not all([account_sid, auth_token, from_number]):
    raise ValueError("Twilio credentials are missing. Please check your .env file or Render settings.")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)


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
                            f"{matched_package['description']}\n\n📄 [View PDF Document]({pdf_url})"
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
            dispatcher.utter_message(
                text=f"Error: {str(e)} - There was an issue retrieving package details."
            )
            print(f"Detailed Package Error: {e}")

        return []


class ActionSendCalendlyLink(Action):
    def name(self) -> Text:
        return "action_send_calendly_link"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        time.sleep(15)
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
        time.sleep(15)
        dispatcher.utter_message(
            text=(
                "Our packages are tailored to your needs. For accurate pricing and package details, please visit our booking page: https://calendly.com/onlyhealth-booking. "
                "We provide blood tests at your home in Dubai and include general recommendations with your results, sent directly via WhatsApp."
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
        intent_ranking = tracker.latest_message.get("intent_ranking", [])
        highest_confidence = intent_ranking[0]["confidence"] if intent_ranking else 0

        # Threshold confidence for OpenAI fallback
        OPENAI_FALLBACK_THRESHOLD = 0.4

        print(f"Debug - User Message: {user_message}")
        print(f"Debug - Intent Confidence: {highest_confidence}")

        # Use OpenAI only if Rasa's confidence is below the threshold
        if highest_confidence >= OPENAI_FALLBACK_THRESHOLD:
            dispatcher.utter_message(
                text="Rasa confidently handled this intent, so OpenAI fallback is not used."
            )
            return []

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a warm, charismatic OnlyHealth's AI assistant acting as a receptionist for OnlyHealth, based in Dubai. "
                        "Always assume the user may not understand medical jargon; explain briefly and clearly, like you're teaching a beginner. "
                        "In the context of blood tests, mention that after their results, you will provide general dietary and lifestyle recommendations. "
                        "Never attempt an official diagnosis or therapy, only share general knowledge and encourage healthy habits. "
                        "Use emojis and light humor occasionally 🤭. "
                        "You handle blood tests, ECG, and predefined packages only. "
                        "Mention the Calendly link (https://calendly.com/onlyhealth-booking) ONLY if the user explicitly requests an appointment or booking. Otherwise, just mention calendly but not the link. "
                        "You handle blood tests, ECG, and only the predefined packages: Dad's Health Pit Stop, Make Sure Moms Well!, Performance Boost, Age Strong Check-Up, The Enhanced Athletes Pit Stop, Busy Hustler's Tune-Up, Immune Fit for Students. "
                        "Never list all packages unless asked. Keep replies short (2-3 sentences), direct, and semi-formal with a friendly tone."
                    ),
                },
                {"role": "user", "content": user_message},
            ]

            openai_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=100
            )

            bot_reply = openai_response.choices[0].message.content.strip()

            print(f"Debug - Sending via Twilio: To: {user_phone_number}, Message: {bot_reply}")

            if user_phone_number.startswith("whatsapp:+"):
                if not from_number.startswith("whatsapp:"):
                    from_whatsapp = from_number.lstrip("+")
                    from_whatsapp = f"whatsapp:+{from_whatsapp}"
                else:
                    from_whatsapp = from_number

                twilio_client = Client(account_sid, auth_token)
                twilio_client.messages.create(
                    body=bot_reply,
                    from_=from_whatsapp,
                    to=user_phone_number
                )
            else:
                dispatcher.utter_message(
                    text="You are using a non-WhatsApp platform (likely Rasa shell), so I will not send a Twilio message."
                )

            bot_reply = openai_response.choices[0].message.content.strip()
            dispatcher.utter_message(text=bot_reply)

        except Exception as e:
            dispatcher.utter_message(
                text=f"Error: {str(e)} - OnlyHealth's AI could not process your request."
            )
            print(f"Detailed OpenAI Error: {e}")

        return []