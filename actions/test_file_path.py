import os

# Print the current directory
print("Current script directory:", os.path.dirname(__file__))

# Construct the file path
file_path = os.path.join(os.path.dirname(__file__), "package_details.json")
print("Constructed file path:", file_path)

# Check if the file exists
print("File exists:", os.path.isfile(file_path))
