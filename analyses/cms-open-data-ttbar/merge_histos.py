import sys
import glob
from utils import load_histos_from_file, save_histos

def merge(files, output):
    all_results = []
    for f in files:
        print(f"Merging {f} ...")
        all_results.extend(load_histos_from_file(f))
    save_histos([r.histo for r in all_results], output_fname=output)
    print(f"Saved merged histograms in {output}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python merge.py <pattern> <output>")
        sys.exit(1)

    pattern, output = sys.argv[1], sys.argv[2]
    partials = glob.glob(pattern)
    merge(partials, output)

