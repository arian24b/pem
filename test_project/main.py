import requests
import sys

def main():
    print("Hello from test_project!")
    try:
        response = requests.get("https://www.google.com", timeout=5)
        print(f"Google responded with status: {response.status_code}")
        print("Test project finished successfully.")
    except requests.RequestException as e:
        print(f"Failed to connect to Google: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

