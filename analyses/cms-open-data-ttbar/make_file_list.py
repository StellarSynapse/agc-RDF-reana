import json

with open("nanoaod_inputs.json") as f:
    data = json.load(f)

with open("file_list.tsv", "w") as out:
    for sample, files in data.items():
        for file in files:
            out.write(f"{sample}\t{file}\n")
