import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, List
from urllib.request import urlretrieve
import logging

import ROOT
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)

@dataclass
class AGCInput:
    paths: list[str]
    process: str
    variation: str
    nevents: int

@dataclass
class AGCResult:
    histo: Union[
        ROOT.TH1D,
        ROOT.RDF.RResultPtr[ROOT.TH1D],
        ROOT.RDF.Experimental.RResultMap[ROOT.TH1D],
    ]
    region: str
    process: str
    variation: str
    nominal_histo: ROOT.RDF.RResultPtr[ROOT.TH1D]
    should_vary: bool = False

def _tqdm_urlretrieve_hook(t: tqdm):
    last_b = [0]
    def update_to(b=1, bsize=1, tsize=None):
        if tsize not in (None, -1):
            t.total = tsize
        displayed = t.update((b - last_b[0]) * bsize)
        last_b[0] = b
        return displayed
    return update_to

def _cache_files(file_paths: list, cache_dir: str, remote_prefix: str):
    for url in file_paths:
        out_path = Path(cache_dir) / url.removeprefix(remote_prefix).lstrip("/")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not out_path.exists():
            with tqdm(
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
                desc=out_path.name,
            ) as t:
                urlretrieve(
                    url,
                    out_path.absolute(),
                    reporthook=_tqdm_urlretrieve_hook(t),
                )

def retrieve_inputs(
    max_files_per_sample: Optional[int] = None,
    remote_data_prefix: Optional[str] = None,
    data_cache: Optional[str] = None,
    sample: Optional[str] = None,
    file_name: Optional[str] = None,
    input_json: Path = Path("nanoaod_inputs.json"),
) -> List[AGCInput]:
    if file_name is not None and sample is None:
        raise ValueError("Must specify 'sample' when 'file_name' is provided")

    if not input_json.exists():
        raise FileNotFoundError(f"Input JSON file {input_json} not found")

    with open(input_json) as f:
        input_spec = json.load(f)

    input_files: List[AGCInput] = []

    for process, process_spec in input_spec.items():
        if process == "data":
            continue

        if sample is not None and process != sample:
            continue

        for variation, sample_info in process_spec.items():
            sample_info = sample_info["files"]

            if file_name is not None:
                matched = [f for f in sample_info if f["path"] == file_name or f["path"].endswith(file_name)]
                if not matched:
                    logging.warning(f"No file matching '{file_name}' found in sample '{process}' variation '{variation}'")
                    continue
                sample_info = matched
                logging.info(f"Selected file '{file_name}' from sample '{process}' variation '{variation}'")

            if max_files_per_sample is not None:
                sample_info = sample_info[:max_files_per_sample]

            file_paths = [f["path"] for f in sample_info]
            prefix = "https://xrootd-local.unl.edu:1094//store/user/AGC"

            if remote_data_prefix is not None:
                assert all(f.startswith(prefix) for f in file_paths), f"Paths do not start with expected prefix {prefix}"
                file_paths = [f.replace(prefix, remote_data_prefix) for f in file_paths]

            if data_cache is not None:
                assert all(f.startswith(prefix) for f in file_paths), f"Paths do not start with expected prefix {prefix}"
                _cache_files(file_paths, data_cache, prefix)
                old_prefix, prefix = prefix, str(Path(data_cache).absolute())
                file_paths = [f.replace(old_prefix, prefix) for f in file_paths]

            nevents = sum(f["nevts"] for f in sample_info)
            input_files.append(
                AGCInput(file_paths, process, variation, nevents)
            )

    if not input_files and (sample or file_name):
        raise ValueError(f"No files matched sample='{sample}' and file_name='{file_name}'")

    return input_files


def postprocess_results(results: list[AGCResult]):
    """Extract TH1D objects from list of RDF's ResultPtrs and RResultMaps.
    The function also gives appropriate names to each varied histogram.
    """

    # Substitute RResultPtrs and RResultMaps of histograms to actual histograms
    new_results = []
    for res in results:
        if hasattr(res.histo, "GetValue"):  # RResultPtr or distrdf equivalent
            # just extract the histogram from the RResultPtr
            h = res.histo.GetValue()
            new_results.append(
                AGCResult(
                    h,
                    res.region,
                    res.process,
                    res.variation,
                    res.nominal_histo,
                )
            )
        else:
            resmap = res.histo
            assert hasattr(
                resmap, "GetKeys"
            )  # RResultMap or distrdf equivalent
            # extract each histogram in the map
            for variation in resmap.GetKeys():
                h = resmap[variation]
                # strip the varied variable name: it's always 'weights'
                variation_name = str(variation).split(":")[-1]
                new_name = h.GetName().replace("nominal", variation_name)
                h.SetName(new_name)
                new_results.append(
                    AGCResult(
                        h,
                        res.region,
                        res.process,
                        variation_name,
                        res.nominal_histo,
                    )
                )

    return new_results


def simplify_histo_name(name) -> str:
    """Simplify histogram name by removing the process and nominal variation."""
    if "_nominal" in name:
        name = name.replace("_nominal", "")
    if "_Jet" in name:
        name = name.split("_Jet")[0]
    if "_Weights" in name:
        name = name.split("_Weights")[0]
    return name


def save_histos(results: list[ROOT.TH1D], output_fname: str, metadata: dict | None = None):
    """
    Save histograms to a ROOT file and attach AGC_metadata (JSON) describing:
      - histogram names
      - integrals per histogram
      - provided per-process metadata (if any)
      - global LUMI
    metadata: optional dict, e.g. { "ttbar": {"variation":"nominal","nevents":12345,"xsec":729.8}, ... }
    """
    f = ROOT.TFile.Open(output_fname, "recreate")
    if not f or f.IsZombie():
        raise RuntimeError(f"Could not open output ROOT file: {output_fname}")
    names_list = []
    integrals = {}
    for result in results:
        # keep previous name-simplification behavior
        result.SetName(simplify_histo_name(result.GetName()))
        # save object
        f.WriteObject(result, result.GetName())
        names_list.append(result.GetName())
        try:
            integrals[result.GetName()] = float(result.Integral())
        except Exception:
            integrals[result.GetName()] = None

    # existing pseudodata creation (unchanged)
    if (
        "4j1b_ttbar_ME_var" in names_list
        and "4j1b_ttbar_PS_var" in names_list
        and "4j1b_wjets" in names_list
        and "4j2b_ttbar_ME_var" in names_list
        and "4j2b_ttbar_PS_var" in names_list
        and "4j2b_wjets" in names_list
    ):
        histogram_4j1b = f.Get("4j1b_wjets").Clone("4j1b_pseudodata")
        histogram_4j1b.Add(f.Get("4j1b_ttbar_PS_var"), 0.5)
        histogram_4j1b.Add(f.Get("4j1b_ttbar_ME_var"), 0.5)
        f.WriteObject(histogram_4j1b, "4j1b_pseudodata")

        histogram_4j2b = f.Get("4j2b_wjets").Clone("4j2b_pseudodata")
        histogram_4j2b.Add(f.Get("4j2b_ttbar_PS_var"), 0.5)
        histogram_4j2b.Add(f.Get("4j2b_ttbar_ME_var"), 0.5)
        f.WriteObject(histogram_4j2b, "4j2b_pseudodata")

    # Compose metadata dict and write as ROOT object for future read
    meta_out = {
        "histogram_names": names_list,
        "integrals": integrals,
        "lumi": LUMI,
        "by_process": metadata or {},
    }
    # write JSON as TObjString (robust and easy to read back)
    try:
        meta_str = json.dumps(meta_out, indent=None)
        meta_obj = ROOT.TObjString(meta_str)
        f.WriteObject(meta_obj, "AGC_metadata")
    except Exception as e:
        # best-effort: don't fail the whole job for metadata write failure
        print(f"WARNING: could not write AGC_metadata: {e}")

    f.Close()


def load_histos_from_file(fname: str) -> list[AGCResult]:
    """Load histograms from ROOT file into AGCResult objects.
    Also attempt to load AGC_metadata if present (returned as attribute .metadata on results list).
    """
    f = ROOT.TFile.Open(fname)  
    if not f or f.IsZombie():
        raise RuntimeError(f"Could not open ROOT file: {fname}")

    results = []
    keys = f.GetListOfKeys()
    for i in range(keys.GetEntries()):
        key = keys.At(i)
        obj = key.ReadObj()
        if not obj.InheritsFrom("TH1"):
            continue

        
        h = obj.Clone()
        h.SetDirectory(0)

        name = h.GetName()
        parts = name.split("_")
        if len(parts) >= 3:
            region = parts[0]
            process = parts[1]
            variation = "_".join(parts[2:])
        elif len(parts) == 2:
            region, process = parts
            variation = "nominal"
        else:
            
            continue

        results.append(
            AGCResult(
                histo=h,
                region=region,
                process=process,
                variation=variation,
                nominal_histo=h,
                should_vary=False,
            )
        )

    # Try to read metadata (if present)
    metadata = None
    try:
        meta_obj = f.Get("AGC_metadata")
        if meta_obj and hasattr(meta_obj, "GetString"):
            try:
                metadata = json.loads(str(meta_obj.GetString()))
            except Exception:
                metadata = None
    except Exception:
        metadata = None

    f.Close()

    # Attach metadata to results as attribute for convenience (caller can use it)
    # (we return a tuple-like structure only if metadata exists)
    if metadata is not None:
        # place metadata on returned list object (duck-typing)
        try:
            results.metadata = metadata  # type: ignore
        except Exception:
            # if cannot attach, ignore silently
            pass

    return results

# --- Compatibility helpers required by scale_results.py ---

# Integrated luminosity (used for scaling). Keep in sync with analysis.py
LUMI = 3378  # /pb

def _normalize_name(s: str) -> str:
    """Simple normalization used to match process names between JSON and callers."""
    return "".join(ch for ch in str(s).lower() if ch.isalnum())

def get_total_events(process: str) -> int:
    """
    Return total number of input events for a given process by summing 'nevts'
    fields in nanoaod_inputs.json for that process (across variations).
    Raises FileNotFoundError if nanoaod_inputs.json is missing.
    """
    json_path = Path("nanoaod_inputs.json")
    if not json_path.exists():
        raise FileNotFoundError("nanoaod_inputs.json not found (needed to compute total events)")

    with open(json_path) as f:
        data = json.load(f)

    target = _normalize_name(process)
    total = 0
    found = False
    for pname, pdata in data.items():
        if _normalize_name(pname) != target:
            continue
        found = True
        for variation, meta in pdata.items():
            for fmeta in meta.get("files", []):
                try:
                    total += int(fmeta.get("nevts", 0) or 0)
                except Exception:
                    # be robust if nevts is missing or not an int
                    pass

    if not found:
        # If nothing matched exactly, try a looser matching (e.g. cleaned tokens)
        for pname, pdata in data.items():
            if target in _normalize_name(pname):
                for variation, meta in pdata.items():
                    for fmeta in meta.get("files", []):
                        try:
                            total += int(fmeta.get("nevts", 0) or 0)
                        except Exception:
                            pass

    return int(total)
