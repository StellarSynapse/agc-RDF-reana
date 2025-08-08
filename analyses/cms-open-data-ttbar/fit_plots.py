import ROOT
import argparse
import os

def fit_plots(input_file, output_dir):
    ROOT.gStyle.SetPalette(ROOT.kRainBow)
    c = ROOT.TCanvas("c", "c", 2160, 2160)

    # Open merged histograms
    f = ROOT.TFile(input_file)
    
    # Fit for region 4j1b
    h_4j1b = f.Get("j4b1")  # Adjust histogram name as needed
    if h_4j1b and h_4j1b.GetEntries() > 0:
        h_4j1b.Fit("gaus", "Q", "", 120, h_4j1b.GetXmax())  # Example: Gaussian fit
        h_4j1b.Draw()
        x_axis = h_4j1b.GetXaxis()
        x_axis.SetRangeUser(120, x_axis.GetXmax())
        x_axis.SetTitleOffset(1.5)
        x_axis.CenterTitle()
        c.BuildLegend(0.65, 0.7, 0.9, 0.9)
        c.SaveAs(os.path.join(output_dir, "fitted_reg1.png"))
    else:
        print("Warning: No valid histogram 'j4b1' for fitting")

    # Fit for region 4j2b
    h_4j2b = f.Get("j4b2")  # Adjust histogram name as needed
    if h_4j2b and h_4j2b.GetEntries() > 0:
        h_4j2b.Fit("gaus", "Q", "", 0, 600)  # Example: Gaussian fit
        h_4j2b.Draw()
        x_axis = h_4j2b.GetXaxis()
        x_axis.SetRangeUser(0, 600)
        x_axis.SetTitleOffset(1.5)
        x_axis.CenterTitle()
        c.BuildLegend(0.65, 0.7, 0.9, 0.9)
        c.SaveAs(os.path.join(output_dir, "fitted_reg2.png"))
    else:
        print("Warning: No valid histogram 'j4b2' for fitting")

    f.Close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    fit_plots(args.input, args.output_dir)