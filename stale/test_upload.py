import requests

with open('.gitignore', 'rb') as f:
    files = {'file': ('test.docx', f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
    try:
        print("Sending request to Hugging Face...")
        r = requests.post("https://syoga8805-antigravity-deploy.hf.space/api/process_stateless", files=files, timeout=60)
        print("Status code:", r.status_code)
        print("Response:", r.text[:500])
    except Exception as e:
        print("Crash:", e)
