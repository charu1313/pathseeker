import google.generativeai as genai
import os

def test_api():
    key_file = "api_key.txt"
    if not os.path.exists(key_file):
        print("api_key.txt not found")
        return
        
    with open(key_file, "r") as f:
        api_key = f.read().strip()
        
    if "PASTE_YOUR" in api_key:
        print("API key is still the placeholder.")
        return
        
    print(f"Testing with key: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        genai.configure(api_key=api_key)
        # Try a different model if flash isn't found
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Say 'Hello Pathseeker'")
        print("Response:", response.text)
        print("SUCCESS: API is working!")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    test_api()
