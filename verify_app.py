import http.client
import sys

def check_app():
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 5000)
        conn.request("GET", "/")
        response = conn.getresponse()
        print(f"Status: {response.status}")
        print(f"Reason: {response.reason}")
        if response.status == 200 or response.status == 302:
            print("Application is responsive!")
            sys.exit(0)
        else:
            print(f"Application returned unexpected status: {response.status}")
            sys.exit(1)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_app()
