import os, ROOT
import cmsstyle as CMS
from array import array
import json
import numpy as np
from argparse import ArgumentParser
from glob import glob
import re

ROOT.gROOT.SetBatch(ROOT.kTRUE)

# maximally mixed cross section: 
# stau-mass [GeV] : cross-section [fb]
theory_xsec = { 
    50: 943.29,
    100: 102.77,
    150: 25.53,
    200: 9,
    250: 3.85,
    300: 1.87,
    350: 0.99,
    400: 0.56,
    450: 0.33,
    500: 0.2
}

# mass-degenerate cross section: 
# stau-mass [GeV] : cross-section [fb]
# theory_xsec = {
#     50 : 1000*5.368,     
#     80 : 1000*0.8014,    
#     100 : 1000*0.3657,    
#     120 : 1000*0.1928,    
#     125 : 1000*0.1669,    
#     140 : 1000*0.1116,    
#     150 : 1000*0.08712,   
#     160 : 1000*0.06896,   
#     175 : 1000*0.04975,   
#     180 : 1000*0.04485,   
#     200 : 1000*0.03031,   
#     220 : 1000*0.02115,   
#     225 : 1000*0.01941,   
#     240 : 1000*0.01514,   
#     250 : 1000*0.01292,   
#     260 : 1000*0.01108,   
#     275 : 1000*0.008875,  
#     280 : 1000*0.008259,  
#     300 : 1000*0.006254,  
#     320 : 1000*0.004802,  
#     340 : 1000*0.003732,  
#     360 : 1000*0.002931,  
#     380 : 1000*0.002325,  
#     400 : 1000*0.001859,  
#     440 : 1000*0.001216,  
#     500 : 1000*0.0006736, 
#     600 : 1000*0.0002763, 
#     700 : 1000*0.0001235, 
#     800 : 1000*5.863E-05, 
#     900 : 1000*2.918E-05,
#     1000 : 1000*1.504E-05 
# }
# extrapolate liniarly theory mases from 90 with 10 GeV steps
for i in range(90, 1000, 10):
    if i not in theory_xsec:
        # take the closest masses
        masses_below = [m for m in theory_xsec if m < i]
        masses_above = [m for m in theory_xsec if m > i]
        if masses_below and masses_above:
            mass1 = max(masses_below)
            mass2 = min(masses_above)
            xsec1 = theory_xsec[mass1]
            xsec2 = theory_xsec[mass2]
            theory_xsec[i] = xsec1 + (xsec2 - xsec1) / (mass2 - mass1) * (i - mass1)

parser = ArgumentParser(description="Plot 1D limits in brazilian flag style")
parser.add_argument("--input", help="Path to the directory containing the input files in the .json format")
parser.add_argument("--outdir", help="Output directory. If not given, output to the directory "
                    "where script is located", default='hist_output')
parser.add_argument("--lifetime", help="Fixed lifetime to filter the JSON files", required=True)

args = parser.parse_args()

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
CMS.SetExtraText("Work in progress")
iPos = 0
canv_name = 'limitplot_cms_root'
CMS.SetLumi("")
CMS.SetEnergy("13")
CMS.ResetAdditionalInfo()
miny=min(min(exp0),min(theory_xsec_plot))*0.1
maxy=max(max(exp0),max(theory_xsec_plot))*4
canv = CMS.cmsCanvas(canv_name, min(masses)-20, max(masses)+20, miny, maxy, "m_{ #tilde{#tau}} [GeV]", "#sigma [fb]", square=CMS.kSquare, extraSpace=0.03, iPos=iPos)
# CMS.cmsDraw(g_exp, "3", fcolor=ROOT.TColor.GetColor("#85D1FBff"))
CMS.cmsDraw(g_exp_2sigma, "3L", fcolor=ROOT.TColor.GetColor("#85D1FBff"))
CMS.cmsDraw(g_exp_1sigma, "Same3L", fcolor=ROOT.TColor.GetColor("#FFDF7Fff"))
CMS.cmsDraw(g_exp, "SameL", lstyle=ROOT.kDashed, lcolor=ROOT.kBlack, lwidth=3)
CMS.cmsDraw(g_theory, "SameL", lstyle=ROOT.kDotted, lcolor=ROOT.kRed, lwidth=3)
CMS.cmsDraw(g_obs, "LP")
leg = CMS.cmsLeg(0.56, 0.60, 0.95, 0.90, textSize=0.04)
leg.AddEntry(g_obs, "Observed", "LP")
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