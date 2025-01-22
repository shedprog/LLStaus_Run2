import os, ROOT
import cmsstyle as CMS
from array import array
import json
import numpy as np
from argparse import ArgumentParser
from glob import glob
import re

ROOT.gROOT.SetBatch(ROOT.kTRUE)


parser = ArgumentParser(description="Plot 1D limits in brazilian flag style")
parser.add_argument("--input", help="Path to the directory containing the input files in the .json format")
parser.add_argument("--outdir", help="Output directory. If not given, output to the directory "
                    "where script is located", default='hist_output')
parser.add_argument("--lifetime", help="Fixed lifetime to filter the JSON files", required=True)
parser.add_argument("--theory", help="Theory cross section to be plotted, maxmix or massdeg", default='maxmix')

args = parser.parse_args()

if args.theory == 'maxmix':
    # maximally mixed cross section: 
    # stau-mass [GeV] : cross-section [fb]
    theory_xsec = { 
        50.0 : 1127.06,
        90.0 : 165.925,
        100.0 : 116.739, 
        125.0 : 54.4897, 
        150.0 : 28.8227,
        175.0 : 16.5604,
        200.0 : 10.127,
        225.0 : 6.5001,
        250.0 : 4.33539,
        275.0 : 2.98007,
        300.0 : 2.10096,
        350.0 : 1.11042,
        400.0 : 0.625364,
        450.0 : 0.369609,
        500.0 : 0.226902,
        550.0 : 0.143696,
        600.0 : 0.0933425
    }
else:
    # mass-degenerate cross section: 
    # stau-mass [GeV] : cross-section [fb]
    theory_xsec = {
        50.0 : 5368.16,
        90.0 : 526.345,
        100.0 : 365.721, 
        125.0 : 166.905,
        150.0 : 87.1162,
        175.0 : 49.7506,
        200.0 : 30.3144,
        225.0 : 19.4106,
        250.0 : 12.9203,
        275.0 : 8.8748,
        300.0 : 6.25417,
        350.0 : 3.30329,
        400.0 : 1.8592,
        450.0 : 1.09799,
        500.0 : 0.673633,
        550.0 : 0.425957,
        600.0 : 0.27635
    }

def read_json_files(input_dir, fixed_lifetime):
    exp0 = []
    exp_plus1 = []
    exp_plus2 = []
    exp_minus1 = []
    exp_minus2 = []
    obs = []
    masses = []

    for filename in glob(os.path.join(input_dir, "*.json")):
        if fixed_lifetime in filename:
            with open(os.path.join(input_dir, filename), 'r') as f:
                data = json.load(f)
                mass_match = re.search(r'MStau-(\d+)', filename)
                if mass_match:
                    mass = float(mass_match.group(1))
                    masses.append(mass)
                    for mass_key, values in data.items():
                        exp0.append(values["exp0"])
                        exp_plus1.append(values["exp+1"])
                        exp_plus2.append(values["exp+2"])
                        exp_minus1.append(values["exp-1"])
                        exp_minus2.append(values["exp-2"])
                        obs.append(values["obs"])
                        
    return masses, exp0, exp_plus1, exp_plus2, exp_minus1, exp_minus2, obs

# Read the JSON files and extract the required values
masses, exp0, exp_plus1, exp_plus2, exp_minus1, exp_minus2, obs = read_json_files(args.input, args.lifetime)

print(masses, exp0, exp_plus1, exp_plus2, exp_minus1, exp_minus2, obs)

# sort every erray by increase of mass
masses, exp0, exp_plus1, exp_plus2, exp_minus1, exp_minus2, obs = \
    zip(*sorted(zip(masses, exp0, exp_plus1, exp_plus2, exp_minus1, exp_minus2, obs)))
print(masses, exp0, exp_plus1, exp_plus2, exp_minus1, exp_minus2, obs)

# Convert lists to arrays
masses = np.array(masses)
exp0 = np.array(exp0)
exp_plus1 = np.array(exp_plus1)
exp_plus2 = np.array(exp_plus2)
exp_minus1 = np.array(exp_minus1)
exp_minus2 = np.array(exp_minus2)
obs = np.array(obs)

# multiply every limit by the cross section
exp0 = exp0 * np.array([theory_xsec[m] for m in masses])
exp_plus1 = exp_plus1 * np.array([theory_xsec[m] for m in masses])
exp_plus2 = exp_plus2 * np.array([theory_xsec[m] for m in masses])
exp_minus1 = exp_minus1 * np.array([theory_xsec[m] for m in masses])
exp_minus2 = exp_minus2 * np.array([theory_xsec[m] for m in masses])
obs = obs * np.array([theory_xsec[m] for m in masses])
theory_xsec_plot = np.array([theory_xsec[m] for m in masses]) 

# Create TGraphErrors for the expected and observed limits
# g_exp = ROOT.TGraphErrors(len(masses), array('d', masses), array('d', exp0))
# g_exp_plus1 = ROOT.TGraphErrors(len(masses), array('d', masses), array('d', exp_plus1))
# g_exp_plus2 = ROOT.TGraphErrors(len(masses), array('d', masses), array('d', exp_plus2))
# g_exp_minus1 = ROOT.TGraphErrors(len(masses), array('d', masses), array('d', exp_minus1))
# g_exp_minus2 = ROOT.TGraphErrors(len(masses), array('d', masses), array('d', exp_minus2))
# g_obs = ROOT.TGraphErrors(len(masses), array('d', masses), array('d', obs))

g_exp = ROOT.TGraphAsymmErrors(
    len(masses),
    array('d', masses),
    array('d', exp0),
)
g_exp_1sigma = ROOT.TGraphAsymmErrors(
    len(masses),
    array('d', masses),
    array('d', exp0),
    array('d', [0]*len(masses)),
    array('d', [0]*len(masses)),
    array('d', np.abs(exp_minus1-exp0)),
    array('d', np.abs(exp_plus1-exp0))
)
g_exp_2sigma = ROOT.TGraphAsymmErrors(
    len(masses),
    array('d', masses),
    array('d', exp0),
    array('d', [0]*len(masses)),
    array('d', [0]*len(masses)),
    array('d', np.abs(exp_minus2-exp0)),
    array('d', np.abs(exp_plus2-exp0))
)
g_theory = ROOT.TGraph(
    len(masses),
    array('d', masses),
    array('d', theory_xsec_plot)
)
g_obs = ROOT.TGraphAsymmErrors(
    len(masses),
    array('d', masses),
    array('d', obs),
)

# Styling
CMS.SetExtraText("Private work")
iPos = 0
canv_name = 'limitplot_cms_root'
CMS.SetLumi("")
CMS.SetEnergy("13")
CMS.ResetAdditionalInfo()
miny=min(min(exp_minus2),min(theory_xsec_plot))*0.1
maxy=max(max(exp_plus2),max(theory_xsec_plot))*10
canv = CMS.cmsCanvas(canv_name, min(masses)-20, max(masses)+20, miny, maxy, "m_{ #tilde{#tau}} [GeV]", "#sigma [fb]", square=CMS.kSquare, extraSpace=0.03, iPos=iPos)
# CMS.cmsDraw(g_exp, "3", fcolor=ROOT.TColor.GetColor("#85D1FBff"))
CMS.cmsDraw(g_exp_2sigma, "3L", fcolor=ROOT.TColor.GetColor("#85D1FBff"))
CMS.cmsDraw(g_exp_1sigma, "Same3L", fcolor=ROOT.TColor.GetColor("#FFDF7Fff"))
CMS.cmsDraw(g_exp, "SameL", lstyle=ROOT.kDashed, lcolor=ROOT.kBlack, lwidth=3)
CMS.cmsDraw(g_theory, "SameL", lstyle=ROOT.kDotted, lcolor=ROOT.kRed, lwidth=3)
# CMS.cmsDraw(g_obs, "LP")
leg = CMS.cmsLeg(0.56, 0.60, 0.95, 0.90, textSize=0.04)
# leg.AddEntry(g_obs, "Observed", "LP")
leg.AddEntry(g_exp, "Median expected", "L")
leg.AddEntry(g_exp_1sigma, "68% expected", "F")
leg.AddEntry(g_exp_2sigma, "95% expected", "F")
leg.AddEntry(g_theory, "Theory", "L")
if not os.path.exists(args.outdir):
    os.makedirs(args.outdir)
canv.SetLogy()
# extra text
text = ROOT.TLatex()
text.SetTextSize(0.04)
text.SetTextAlign(11)
lifetime_in_mm = float(args.lifetime.split('-')[1].replace('p', '.').replace('mm', ''))
print("lifetime -> ", lifetime_in_mm)
text.DrawLatex(100, .1,"pp#rightarrow#tilde{#tau}#bar{#tilde{#tau}}, #tilde{#tau}#rightarrow#tau#tilde{G}, #tilde{G} = 1 GeV, c#tau_{0}(#tilde{#tau}) = "+str(lifetime_in_mm)+" mm")
# text.DrawLatex(100, .13, "c#tau_{0}(#tilde{#tau}) = "+str(lifetime_in_mm)+" mm")

canv.SaveAs(args.outdir + f"/limitplot_cms_root_{args.lifetime}.pdf")