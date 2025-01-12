from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fuzzywuzzy import process
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv  # Import dotenv to load variables from .env

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variable
api_key = os.getenv("OPENAI_API_KEY")

if api_key is None:
    raise ValueError("OpenAI API key not found. Please add OPENAI_API_KEY to your .env file.")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

class ActionSendPackageDetails(Action):
    def name(self) -> Text:
        return "action_send_package_details"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        # Path to the JSON file
        json_file_path = os.path.join(os.path.dirname(__file__), "package_details.json")

        try:
            # Load the JSON data
            with open(json_file_path, "r") as file:
                package_details = json.load(file)

            # Retrieve the package_name slot and user's message text
            package_name = tracker.get_slot("package_name") or ""
            user_message = tracker.latest_message.get("text", "").lower()

            # Debugging raw slot value and user message
            dispatcher.utter_message(text=f"Debug: Raw slot value - {package_name}")
            dispatcher.utter_message(text=f"Debug: User message - {user_message}")

            # Normalize package_name (replace apostrophes, remove "package" suffix, and unnecessary phrases)
            if package_name:
                package_name = package_name.replace("’", "").replace("'", "").strip()
                if package_name.endswith("package"):
                    package_name = package_name[:-7].strip()
                phrases_to_remove = ["tell me about", "what is included in", "show me details of"]
                for phrase in phrases_to_remove:
                    if package_name.lower().startswith(phrase):
                        package_name = package_name[len(phrase):].strip()
                        break

            # Normalize package names from JSON for comparison
            normalized_packages = {
                pkg["name"].replace("’", "").replace("'", "").lower(): pkg for pkg in package_details
            }

            # Debugging normalized package names
            dispatcher.utter_message(text=f"Debug: Normalized package names - {list(normalized_packages.keys())}")

            # Use fuzzy matching to find the best match
            normalized_keys = list(normalized_packages.keys())
            best_match, match_score = process.extractOne(package_name.lower(), normalized_keys)

            # Debugging best match and score
            dispatcher.utter_message(text=f"Debug: Best match - {best_match}, Score - {match_score}")

            # Respond based on the best match if the score is acceptable
            if match_score >= 40:  # Accept matches with a high similarity score
                matched_package = normalized_packages[best_match]

                # Check if PDF URL exists
                pdf_url = matched_package.get("pdf_url")
                if pdf_url:
                    dispatcher.utter_message(
                        text=f"Here is the detailed document for {matched_package['name']}: {matched_package['description']}\n\n📄 [View PDF Document]({pdf_url})"
                    )
                else:
                    # Fallback to sending the description if no PDF exists
                    dispatcher.utter_message(
                        text=f"Here are the details for {matched_package['name']}: {matched_package['description']}"
                    )
            else:
                dispatcher.utter_message(
                    text="Sorry, I couldn't find details for the specified package. Please try rephrasing your query."
                )
        except Exception as e:
            dispatcher.utter_message(
                text=f"Error: {str(e)} - I encountered an issue while retrieving the package details. Please try again later."
            )
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
            text="You can book an appointment here: https://calendly.com/onlyhealth-booking. Our team will visit your home in Dubai to conduct the test."
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
                "We provide blood tests at your home in Dubai and include general recommendations with your results, sent directly via WhatsApp."
            )
        )
        return []


class ActionOpenAIResponse(Action):
    def name(self) -> Text:
        return "action_openai_response"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_message = tracker.latest_message.get("text")

        # Handle predefined responses
        if user_message.lower() in ["hello", "hi", "hey", "how are you?"]:
            dispatcher.utter_message(
                text="👋 Welcome, I'm OnlyHealth's dedicated AI! We specialize in 🩸 blood tests conducted at your home in Dubai. How can we assist you today?"
            )
            return []
        elif user_message.lower() in ["bye", "goodbye", "see you", "thank you"]:
            dispatcher.utter_message(
                text="👋 Thank you for choosing OnlyHealth! Stay healthy and take care. See you soon! 😊"
            )
            return []

        # Handle OpenAI API calls for other queries
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a dedicated OnlyHealth AI, providing blood test services, ECG, and generalized recommendations based on results, in Dubai. "
                        "Recommend packages only when asked based on client needs but only use the predefined packages available (Dad's Health Pit Stop, Make Sure Moms Well!, Performance Boost, Age Strong Check-Up, The Enhanced Athletes Pit Stop, Busy Hustler's Tune-Up, Immune Fit for Students). "
                        "Avoid unnecessary details, don't list all packages unless asked specifically, and focus on providing essential information. "
                        "Guide clients regarding blood tests, available packages, ECG service, and booking procedures. "
                        "Always keep your responses concise and preferable but not limited to 2-3 sentences. "
                        "Include the booking link only when asked: https://calendly.com/onlyhealth-booking for appointments."
                    ),
                },
                {"role": "user", "content": user_message},
            ]

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=100
            )

            bot_reply = response.choices[0].message.content.strip()
            dispatcher.utter_message(text=bot_reply)
        except Exception as e:
            dispatcher.utter_message(
                text=f"Error: {str(e)} - OnlyHealth's AI could not process your request."
            )
            print(f"Detailed OpenAI Error: {e}")
        return []
