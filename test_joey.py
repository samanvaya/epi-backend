import urllib.request
import urllib.parse
import json
import time
import os

filepath = "/Users/kumarsamanvaya/Downloads/Joenja_Adapted_QRD_Template.docx"

if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    exit(1)

with open(filepath, "rb") as f:
    file_content = f.read()

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="Joenja_Adapted_QRD_Template.docx"\r\n'
    f"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n".encode("utf-8")
    + file_content +
    f"\r\n--{boundary}--\r\n".encode("utf-8")
)

req = urllib.request.Request(
    "https://syoga8805-antigravity-deploy.hf.space/api/process_stateless",
    data=body,
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Origin": "https://epi-validator.lovable.app"
    },
    method="POST"
)

print("Sending pure backend POST request to measure precise latency and response...")
start = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as response:
        result = response.read().decode("utf-8")
        print(f"SUCCESS! Time: {time.time() - start:.2f}s, Status: {response.status}")
        print("Response Snippet:", result[:200])
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"HTTP ERROR {e.code}! Time: {time.time() - start:.2f}s")
    print("Error Body:", err_body)
except Exception as e:
    print(f"CRASH! Time: {time.time() - start:.2f}s, Error: {e}")
