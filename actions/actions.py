from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
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

# Debug environment variables
print(f"Debug - OpenAI Key: {'***' if api_key else 'MISSING'}")
print(f"Debug - Twilio SID: {account_sid if account_sid else 'MISSING'}")
print(f"Debug - Twilio Auth Token: {'***' if auth_token else 'MISSING'}")
print(f"Debug - Twilio From Number: {from_number if from_number else 'MISSING'}")

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

            print(f"Debug - Package Slot: {package_name}")
            print(f"Debug - User Message: {user_message}")

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

            # Additional debug prints
            print(f"Debug - Best Match: {best_match}, Score: {match_score}")  # Fuzzy match result
            print(f"Debug - Package Slot: {package_name}")
            print(f"Debug - User Message: {user_message}")

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
            print(f"Detailed Package Error: {e}")  # Logs detailed error for debugging

            # In case of error, also show the fallback message:
            dispatcher.utter_message(
                text="Sorry, I couldn't find details for the specified package. Please try rephrasing your query."
            )

        return []


class ActionSendCalendlyLink(Action):
    def name(self) -> Text:
        return "action_send_calendly_link"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        # Increased delay from 2s to 15s
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
        # Increased delay from 2s to 15s
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
        user_phone_number = tracker.sender_id

        print(f"Debug - User Phone Number: {user_phone_number}")
        print(f"Debug - User Message: {user_message}")

        last_message = tracker.get_slot("last_client_message")
        print(f"Debug - Last Client Message: {last_message}")

        # Save the last client message into a slot
        events = [SlotSet("last_client_message", user_message)]

        try:
            # Updated system prompt with new style/tone
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a warm, charismatic OnlyHealth's AI assistant acting as a receptionist for OnlyHealth in Dubai. We have blood test packages and ECG. "
                        "Ask the client for relevant information, such as their health goals, concerns, medical history, lifestyle habits, gender. Use this information to recommend the most suitable blood test package and guide them toward their desired outcomes. "
                        "Only provide the number 0553470210 if a user asks to speak to someone or reports a technical issue. Do not share the number proactively or in response to unrelated queries. "
                        "Always assume the user may not understand medical jargon; explain briefly and clearly, like you're teaching a beginner. "
                        "Dont even greet the user, only if they greets you, greet with 👋 Welcome, I'm OnlyHealth's dedicated AI! We specialize in 🩸 blood tests conducted at your home in Dubai. How can we assist you today?, or similar. "
                        "Do not repeatedly say 'see a doctor' unless it’s truly serious or the user specifically asks. "
                        "You can gently mention 'consult a professional' if needed, but mostly focus on easy-to-follow guidance. "
                        "In the context of blood tests, mention that after their results, 3 to 4 days, you will provide general dietary and lifestyle recommendations. "
                        "Never attempt an official diagnosis or therapy, only share general knowledge and encourage healthy habits, making jokes and always promoting OnlyHealth blood tests and ecg. "
                        "You handle blood tests, ECG, and only the predefined packages: Dad's Health Pit Stop, Make Sure Moms Well!, Performance Boost, Age Strong Check-Up, The Enhanced Athletes Pit Stop, Busy Hustler's Tune-Up, Immune Fit for Students.  "
                        "If a user asks for details about a specific package, provide the link to view more details and a very simple short phrase: "
                        "- Make Sure Mom's Well!: https://raw.githubusercontent.com/MBOnlyHealth/Make-Sure-Mom-s-Well-/main/Make%20Sure%20Mom%E2%80%99s%20Well%21.pdf "
                        "- The Enhanced Athlete Check-Up: https://raw.githubusercontent.com/MBOnlyHealth/The-Enhanced-Athletes-Check-Up/main/The%20Enhanced%20Athletes%20Check-Up%20.pdf "
                        "- Dad's Health Pit Stop: https://raw.githubusercontent.com/MBOnlyHealth/Dad-s-Health-Pit-Stop/main/Dad%27s%20Health%20Pit%20Stop.pdf "
                        "- Performance Boost: https://raw.githubusercontent.com/MBOnlyHealth/Performance-Boost/main/Performance%20Boost.pdf "
                        "- Busy Hustler's Tune-Up: https://raw.githubusercontent.com/MBOnlyHealth/Busy-Hustler-s-Tune-Up/main/Busy%20Hustler's%20Tune-Up.pdf "
                        "- Immune Fit for Students: https://raw.githubusercontent.com/MBOnlyHealth/Immune-Fit-for-Students-/main/Immune%20Fit%20for%20Students.pdf "
                        "Never list all packages unless asked, mention always a few. Keep replies short (2-3 sentences), direct, and semi-formal with a friendly tone. "
                        "Use emojis and light humor occasionally 🤭. "
                        "If the user asks for direct meal plans, diet, or lifestyle changes, politely say that OnlyHealth offers general guidance after seeing their blood test results—but avoid detailed or condition-specific advice. "
                        "Mention the Calendly link (https://calendly.com/onlyhealth-booking) ONLY if the user explicitly requests an appointment or booking. Otherwise, do not show it. "
                        "Offer essential details without rambling, and maintain a professional but personable style."
                    ),
                },
                {"role": "user", "content": user_message},
            ]

            openai_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=300
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

        except Exception as e:
            dispatcher.utter_message(
                text=f"Error: {str(e)} - OnlyHealth's AI could not process your request."
            )
            print(f"Detailed OpenAI Error: {e}")

        return events
