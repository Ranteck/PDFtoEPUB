import os
import sys

print("--- simple_uv_test.py: START ---", flush=True)
print(f"Python version (from simple_uv_test.py): {sys.version}", flush=True)
print(f"CWD (from simple_uv_test.py): {os.getcwd()}", flush=True)
with open('simple_uv_marker.txt', 'w') as f:
    f.write('simple_uv_test.py was run!')
print("--- simple_uv_test.py: END (simple_uv_marker.txt created) ---", flush=True)
