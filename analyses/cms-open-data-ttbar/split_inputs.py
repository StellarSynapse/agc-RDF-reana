import json
import os

with open("nanoaod_inputs.json") as f:
    data = json.load(f)

os.makedirs("inputs", exist_ok=True)

for sample, files in data.items():
    sample_data = {sample: files}
    with open(f"inputs/{sample}.json", "w") as out:
        json.dump(sample_data, out, indent=2)

print(f"✅ Created {len(data)} sample files in 'inputs/' directory.")