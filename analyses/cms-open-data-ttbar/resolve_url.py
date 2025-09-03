#!/usr/bin/env python3
# scripts/resolve_url.py
import json, sys, hashlib, re, unicodedata, os

def clean_token(x):
    s = str(x)
    s = unicodedata.normalize("NFKC", s).strip()
    s = "_".join(s.split())
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    return "".join(ch for ch in s if ch in allowed) or "unk"

def normalize_url(p):
    p = str(p).strip()
    # normalize scheme://rest  and collapse repeated slashes (after scheme://)
    if "://" in p:
        proto, rest = p.split("://", 1)
        rest = re.sub(r"/+", "/", rest)
        return proto + "://" + rest
    return re.sub(r"/+", "/", p)

USAGE = "Usage: resolve_url.py <sample> <variation> <fid>"

def main():
    if len(sys.argv) != 4:
        print(USAGE, file=sys.stderr)
        sys.exit(2)

    sample_raw, variation_raw, fid = sys.argv[1], sys.argv[2], sys.argv[3]
    sample_c, variation_c = clean_token(sample_raw), clean_token(variation_raw)

    json_path = os.path.join(os.getcwd(), "nanoaod_inputs.json")
    try:
        with open(json_path) as f:
            samples = json.load(f)
    except Exception as e:
        print(f"ERROR: cannot open {json_path}: {e}", file=sys.stderr)
        sys.exit(3)

    # exact-match only: compare normalized url -> fid, but require same sample+variation
    candidates = []
    for sample, variations in samples.items():
        s_c = clean_token(sample)
        for variation, meta in variations.items():
            v_c = clean_token(variation)
            for fmeta in meta.get("files", []):
                raw = fmeta.get("path") or fmeta.get("url") or fmeta.get("file")
                if not raw:
                    continue
                norm = normalize_url(raw)
                if hashlib.md5(norm.encode()).hexdigest()[:8] == fid:
                    candidates.append((sample, variation, raw, norm))

    # Prefer exact sample+variation match
    for s, v, raw, norm in candidates:
        if clean_token(s) == sample_c and clean_token(v) == variation_c:
            print(raw)
            sys.exit(0)

    # If no candidate for that sample+variation -> fail (no silent fallback)
    if candidates:
        # We found same fid but in different sample/variation -> show informative error
        for s, v, raw, norm in candidates:
            print(f"FOUND_OTHER: fid {fid} exists in sample={s} variation={v} -> {raw}", file=sys.stderr)
        print(f"ERROR: fid {fid} found only in other sample/variation, not in requested {sample_raw}/{variation_raw}", file=sys.stderr)
        sys.exit(4)

    # nothing found
    print(f"ERROR: no file with fid={fid} found in nanoaod_inputs.json", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
