
"""
scale_results.py

Scale histograms inside merged ROOT files so that each process' histograms
have total integral = XSEC_INFO[process] * LUMI (when appropriate).

Usage:
    python3 scale_results.py [--dry-run] [--overwrite] file1.root [file2.root ...]
"""
from __future__ import annotations
import ROOT, re, json, sys, os, argparse
from typing import Optional

# Keep these in sync with analysis.py (or import analysis.XSEC_INFO if available)
XSEC_INFO = {
    "ttbar": 396.87 + 332.97,
    "single_top_s_chan": 2.0268 + 1.2676,
    "single_top_t_chan": (36.993 + 22.175) / 0.252,
    "single_top_tW": 37.936 + 37.906,
    "wjets": 61457 * 0.252,
    "zprimet": 700,
}
LUMI = 3378.0  # /pb

import re

def parse_name(name: str):
    """
    Розбирає назву гістограми на (process, variation).
    Очікується формат типу:
        4j1b_single_top_tW
        4j1b_single_top_tW_pt_scale_up
        4j2b_ttbar
        4j2b_wjets
    Логіка:
        - variation: остання частина (up/down/nominal), або 'nominal', якщо немає
        - process: все, що перед variation
    """
    parts = name.split("_")
    if len(parts) < 2:
        return None, None

    # можливі варіації (systematics)
    known_variations = [
        "up", "down",
        "nominal",
        "scale", "res",
        "btag", "btag_var",
    ]

    # якщо остання частина виглядає як up/down → variation
    if parts[-1] in ["up", "down"]:
        variation = parts[-1]
        process = "_".join(parts[1:-1])  # пропускаємо категорію (наприклад, 4j1b)
    else:
        variation = "nominal"
        process = "_".join(parts[1:])

    return process, variation




def read_agc_metadata(tf: ROOT.TFile) -> Optional[dict]:
    try:
        obj = tf.Get("AGC_metadata")
        if obj and hasattr(obj, "GetString"):
            s = str(obj.GetString())
            try:
                return json.loads(s)
            except Exception:
                return None
    except Exception:
        return None
    return None

def scale_one_file(path: str, overwrite: bool = True, dry_run: bool = False, verbose: bool = False) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if verbose:
        print(f"[scale_results] Opening {path}")

    fin = ROOT.TFile.Open(path, "READ")
    if not fin or fin.IsZombie():
        raise RuntimeError(f"Cannot open input root file {path}")

    metadata = read_agc_metadata(fin)
    if verbose:
        print(f"[scale_results] metadata found: {bool(metadata)}")

    tmp = path + ".tmp"
    fout = ROOT.TFile.Open(tmp, "RECREATE")
    n_scaled = 0
    n_skipped = 0

    for i in range(fin.GetListOfKeys().GetEntries()):
        key = fin.GetListOfKeys().At(i)
        obj = key.ReadObj()

        if obj.InheritsFrom("TH1"):
            hist_name = obj.GetName()
            process, variation = parse_name(hist_name)

            if process is None:
                print(f"[WARN] Cannot parse histogram name: {hist_name}")
                fout.WriteTObject(obj, hist_name)
                n_skipped += 1
                continue

            if process not in XSEC_INFO:
                print(f"[WARN] Unknown process '{process}' in {hist_name}, copying without scale")
                fout.WriteTObject(obj, hist_name)
                n_skipped += 1
                continue

            target = XSEC_INFO[process] * LUMI
            current = obj.Integral()

            meta_factor = None
            try:
                if metadata and "by_process" in metadata:
                    bp = metadata["by_process"]
                    if process in bp and isinstance(bp[process], dict) and bp[process].get("nevents"):
                        nevents_meta = float(bp[process].get("nevents"))
                        if nevents_meta > 0:
                            meta_factor = target / nevents_meta
            except Exception:
                meta_factor = None

            if meta_factor is not None:
                factor = meta_factor
                if verbose:
                    print(f"[scale_results] {hist_name}: using metadata nevents, factor={factor:.6g}")
            else:
                if current <= 0:
                    print(f"[scale_results] WARNING: hist {hist_name} has zero integral -> copying", file=sys.stderr)
                    fout.WriteTObject(obj, hist_name)
                    n_skipped += 1
                    continue
                factor = target / current
                if verbose:
                    rel_diff = abs(current - target) / target if target != 0 else 0
                    if rel_diff < 0.02:
                        print(f"[scale_results] {hist_name}: current ~ target -> skipping scale")
                        fout.WriteTObject(obj, hist_name)
                        n_skipped += 1
                        continue
                    print(f"[scale_results] {hist_name}: using integral ratio, factor={factor:.6g}")

            if dry_run:
                print(f"[scale_results] DRY-RUN {hist_name}: current={current:.6g}, target={target:.6g}, factor={factor:.6g}")
                fout.WriteTObject(obj, hist_name)
            else:
                h_clone = obj.Clone(hist_name)
                h_clone.Scale(factor)
                fout.WriteTObject(h_clone, hist_name)
                n_scaled += 1
                if verbose:
                    print(f"[scale_results] Scaled {hist_name}: current={current:.6g} -> target={target:.6g}, factor={factor:.6g}")

        else:
            fout.WriteTObject(obj, obj.GetName())

    fout.Close()
    fin.Close()

    if dry_run:
        os.remove(tmp)
        print(f"[scale_results] Dry-run done for {path}: scaled {n_scaled}, skipped {n_skipped}")
        return

    if overwrite:
        os.replace(tmp, path)
        print(f"[scale_results] Wrote scaled (overwritten) file: {path} (scaled {n_scaled}, skipped {n_skipped})")
    else:
        newname = path.replace(".root", "_scaled.root")
        os.replace(tmp, newname)
        print(f"[scale_results] Wrote scaled file: {newname} (scaled {n_scaled}, skipped {n_skipped})")

def main(argv=None):
    p = argparse.ArgumentParser(description="Scale merged ROOT histograms to XSEC*LUMI")
    p.add_argument("files", nargs="+", help="merged ROOT files to scale")
    p.add_argument("--dry-run", action="store_true", help="Do not write output, just report")
    p.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Do not overwrite input file; write _scaled.root")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    for f in args.files:
        scale_one_file(f, overwrite=args.overwrite, dry_run=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
    main()


