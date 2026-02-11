import os
import subprocess
import sys
import time
import socket
import webbrowser

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_port_owner(port):
    """Try to kill the process listening on the given port (Windows only for now)."""
    if os.name != 'nt': return
    try:
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
        for line in output.strip().split('\n'):
            if 'LISTENING' in line:
                pid = line.strip().split()[-1]
                print(f"Killing process {pid} on port {port}...")
                os.system(f"taskkill /F /PID {pid}")
    except Exception:
        pass

def run():
    print("=== Pathseeker Diagnostic & Startup ===")
    
    # 1. Check requirements
    print("Checking dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies checked/installed.")
    except Exception as e:
        print(f"Error installing dependencies: {e}")
    
    # 2. Cleanup port 5050
    port = 5050
    print(f"Cleaning up port {port}...")
    kill_port_owner(port)
    time.sleep(1)
    
    # 3. Start the server
    print("Starting Flask server...")
    if os.name == 'nt': # Windows
        # Use 'start' to run in a NEW window so user can see logs
        cmd = f'start "Pathseeker Server" {sys.executable} app.py'
        os.system(cmd)
    else: # Unix/Mac
        subprocess.Popen([sys.executable, "app.py"])
    
    # 4. Wait for server to be ready
    print("Waiting for server to start...")
    max_retries = 10
    ready = False
    for i in range(max_retries):
        time.sleep(2)
        if check_port(port):
            ready = True
            break
        print(f"Retrying connection ({i+1}/{max_retries})...")
    
    if ready:
        url = f"http://127.0.0.1:{port}/login"
        print(f"\nSUCCESS: Server is running at {url}")
        print("Opening browser...")
        webbrowser.open(url)
    else:
        print("\nERROR: Server did not seem to start in time.")
        print("Please check the 'Pathseeker Server' window that just opened for error messages.")
    
    print("\nYou can keep this window open for status or close it.")
    input("Press Enter to finish...")

if __name__ == "__main__":
    run()
