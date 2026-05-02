import subprocess
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

result = subprocess.run(
    [sys.executable, "-m", "pytest", "autorepair/tests/repair/test_executor_mock.py", "-x", "--tb=short", "-q"],
    capture_output=True,
    text=True,
    timeout=120,
    cwd=script_dir
)

output_path = os.path.join(script_dir, 'test_output.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(result.stdout)
    f.write(result.stderr)

print(f"Written to {output_path}")
print(f"Exit code: {result.returncode}")
print(f"Output length: {len(result.stdout) + len(result.stderr)}")
