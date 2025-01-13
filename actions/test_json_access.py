import os
import json

file_path = os.path.join(os.path.dirname(__file__), "package_details.json")

try:
    print(f"Checking file path: {file_path}")
    with open(file_path, "r") as file:
        package_details = json.load(file)
        print("Loaded JSON data:")
        for package in package_details:
            print(f"- {package['name']}: {package['description']}")
except Exception as e:
    print(f"Error accessing JSON file: {e}")
