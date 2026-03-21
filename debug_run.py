import subprocess
import sys

try:
    with open('full_error.txt', 'w') as f:
        result = subprocess.run([sys.executable, 'main.py'], capture_output=True, text=True, timeout=10)
        f.write("STDOUT:\n")
        f.write(result.stdout)
        f.write("\nSTDERR:\n")
        f.write(result.stderr)
except Exception as e:
    with open('full_error.txt', 'a') as f:
        f.write(f"\nSubprocess Exception: {e}")
