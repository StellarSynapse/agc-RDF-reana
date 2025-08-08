import json
from pathlib import Path

with open("nanoaod_inputs.json") as f:
    input_data = json.load(f)

input_files = []
seen = set()

for sample, variations in input_data.items():
    for variation, data in variations.items():
        for file in data["files"]:
            path = file["path"].replace('//', '/')  # приберемо подвійні /
            # Але залишимо протокол (https://)
            if path.startswith('https:/') and not path.startswith('https://'):
                path = path.replace('https:/', 'https://')
            file_id = Path(path).name.replace(".root", "")
            key = (sample, variation, file_id)
            if key in seen:
                raise ValueError(f"Duplicate file: {key}")
            seen.add(key)
            input_files.append({
                "sample": sample,
                "variation": variation,
                "file_id": file_id,
                "file_path": path
            })

with open("input_files.json", "w") as f:
    json.dump(input_files, f, indent=2)
