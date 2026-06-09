import subprocess
import time
import sys

# Flush output immediately
sys.stdout.reconfigure(line_buffering=True)

print("Starting Registry service on port 10000...")
r1 = subprocess.Popen(["uv", "run", "python", "-m", "registry"])
time.sleep(3)

print("Starting Tax Agent on port 10102...")
r2 = subprocess.Popen(["uv", "run", "python", "-m", "tax_agent"])

print("Starting Compliance Agent on port 10103...")
r3 = subprocess.Popen(["uv", "run", "python", "-m", "compliance_agent"])
time.sleep(3)

print("Starting Law Agent on port 10101...")
r4 = subprocess.Popen(["uv", "run", "python", "-m", "law_agent"])
time.sleep(3)

print("Starting Customer Agent on port 10100...")
r5 = subprocess.Popen(["uv", "run", "python", "-m", "customer_agent"])

print("\nAll services started! Waiting 5 seconds for them to be fully ready...")
time.sleep(5)

print("\n--- RUNNING TEST CLIENT ---")
client_proc = subprocess.run(["uv", "run", "python", "test_client.py"])
print(f"--- TEST CLIENT FINISHED (Code: {client_proc.returncode}) ---\n")

print("Shutting down all services...")
r1.terminate()
r2.terminate()
r3.terminate()
r4.terminate()
r5.terminate()

