"""Sample request code."""

import requests as rq
from pathlib import Path
import io
import zipfile
import requests
import json

url = "http://localhost:8000/decode_float/6903014"
file_dir = r"mockfiles_6903014"


files = [str(file) for file in Path(file_dir).glob("*.txt")]
files = [("files", (str(Path(file_path).name), open(file_path, "rb"), "text/plain")) for file_path in files]
##################


with open(r"mockfiles_6903014\info_json.json") as file:
   float_info = json.loads(file.read())

with open(r"mockfiles_6903014\meta_info.json") as file:
   meta_info = json.loads(file.read())

float_metadata = {"float_info": float_info,
                  "float_meta_info": meta_info}

print(float_metadata)
data = {"float_metadata": json.dumps(float_metadata)}
response = requests.post(url, files=files, data=data)

print(response.status_code)
print(response)

# Close all opened files
for _, (name, file_obj, _) in files:
    file_obj.close()

# Save the response content as a ZIP file
if response.status_code == 200:
    with open("output.zip", "wb") as f:
        f.write(response.content)
    print("ZIP file saved as 'output.zip'")
else:
    print("Request failed with status:", response.status_code)
    print(response.text)