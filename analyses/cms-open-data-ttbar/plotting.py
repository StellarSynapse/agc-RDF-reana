import ROOT
from ml import ml_features_config
from utils import AGCResult
import os


def save_plots(results: list[AGCResult]):
    import os
    # ensure results/ exists
    os.makedirs('results', exist_ok=True)

    width, height = 2160, 2160
    c = ROOT.TCanvas("c", "c", width, height)
    ROOT.gStyle.SetPalette(ROOT.kRainBow)

    def safe_configure(hstack, fname):
        if not hstack:
            print(f"Skipping {fname}: no histogram stack")
            return
        hstack.Draw("hist pfc plc")
        # configure axis
        axis = hstack.GetXaxis() if hasattr(hstack, 'GetXaxis') else None
        if axis:
            try:
                axis.SetTitleOffset(1.5)
                axis.CenterTitle()
                axis.SetRangeUser(120, axis.GetXmax())
            except BaseException:
                pass
        c.BuildLegend(0.65, 0.7, 0.9, 0.9)
        c.SaveAs(f"results/{fname}.png")

    # Region 1
    hlist = [r.histo for r in results if r.region == "4j1b" and r.variation == "nominal"]
    hs1 = ROOT.THStack("j4b1", ">=4 jets, 1 b-tag; H_{T} [GeV]")
    for h in hlist:
        if h:
            try:
                clone = h.Clone()
                clone.Rebin(2)
                hs1.Add(clone)
            except BaseException:
                pass
    safe_configure(hs1, 'reg1')

    # Region 2
    hlist = [r.histo for r in results if r.region == "4j2b" and r.variation == "nominal"]
    hs2 = ROOT.THStack("j4b2", ">=4 jets, 2 b-tag; m_{bjj} [GeV]")
    for h in hlist:
        if h:
            hs2.Add(h)
    safe_configure(hs2, 'reg2')

    # b-tag variations
    btag_vars = [
        "nominal",
        "btag_var_0_up",
        "btag_var_1_up",
        "btag_var_2_up",
        "btag_var_3_up",
    ]
    for var in btag_vars:
        hlist = [r.histo for r in results if r.region == "4j1b" and r.variation == var]
        hs = ROOT.THStack(f"btag_{var}", f"b-tag variation {var}; H_{{T}} [GeV]")
        for h in hlist:
            if h:
                hs.Add(h)
        safe_configure(hs, f'btag_{var}')


def save_ml_plots(results: list[AGCResult]):
    width = 2160
    height = 2160
    c = ROOT.TCanvas("c", "c", width, height)

    for i, feature in enumerate(ml_features_config):
        hlist = [r.histo for r in results if r.variation == "nominal" and r.region == feature]
        hs = ROOT.THStack("features", feature.title)
        for h in hlist:
            hs.Add(h)
        hs.Draw("hist pfc plc")
        c.BuildLegend()
        c.Print("features.pdf" + (i == 0) * "(" + (i + 1 == len(ml_features_config)) * ")")
