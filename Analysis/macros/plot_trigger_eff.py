import os
import json
from argparse import ArgumentParser
import re
import ROOT
import itertools

from pepper import Config

import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(parent_dir)
from utils.plotter import plot1D, plot2D
from utils.utils import ColorIterator, root_plot1D, root_plot2D


before_trg = "/nfs/dust/cms/user/mykytaua/softLLSTAU/LLStaus_Run2/Analysis/output_iteration_6/2018/output_signal/signal_v4_plots/hists/Cut_000_BeforeCuts_gen-met-pt.root"
after_trg = "/nfs/dust/cms/user/mykytaua/softLLSTAU/LLStaus_Run2/Analysis/output_iteration_6/2018/output_signal/signal_v4_plots/hists/Cut_001_Trigger_gen-met-pt.root"

hists = [
    "SMS-TStauStau_MStau-100_ctau-100mm_mLSP-1",
    "SMS-TStauStau_MStau-200_ctau-100mm_mLSP-1",
    "SMS-TStauStau_MStau-300_ctau-100mm_mLSP-1",
    "SMS-TStauStau_MStau-400_ctau-100mm_mLSP-1",
    "SMS-TStauStau_MStau-500_ctau-100mm_mLSP-1",
    "SMS-TStauStau_MStau-600_ctau-100mm_mLSP-1"
]
output_dir = "trigger_eff"

for hist_name in hists:
    
    try: os.stat(output_dir)
    except: os.mkdir(output_dir)

    file = ROOT.TFile.Open(before_trg, 'read')
    hist_data = file.Get(hist_name+"/nominal/hist")
    # hist_data.Scale(Inclusive_scale)
    hist_data.SetDirectory(0)
    hist_data.Rebin(10)
    hist_data.SetMarkerStyle(22)
    hist_data.SetMarkerSize(2)
    hist_data.SetMarkerColor(4)
    hist_data.SetLineColor(4)
    hist_data.SetFillColor(0)
    hist_data.SetLineWidth(2)
    hist_data.SetTitle("Before trigger")
    # hist_data.Print("all")

    file_data = ROOT.TFile.Open(after_trg, 'read')
    hist_prediction = file_data.Get(hist_name+"/nominal/hist")
    hist_prediction.SetDirectory(0)
    hist_prediction.Rebin(10)
    hist_prediction.SetMarkerStyle(21)
    hist_prediction.SetMarkerSize(2)
    hist_prediction.SetMarkerColor(2)
    hist_prediction.SetLineColor(2)
    hist_prediction.SetFillColor(0)
    hist_prediction.SetLineWidth(2)
    ratio_of_events = hist_prediction.GetEntries()/hist_data.GetEntries()
    hist_prediction.SetTitle("After trigger (fraction: {:.2f})".format(ratio_of_events))
    # sum_hist.Print("all")

    Parslifetime = re.search(r"ctau-(\d+)mm", hist_name).group(1)
    lifetime = int(Parslifetime)

    Parsmass = re.search(r"MStau-(\d+)", hist_name).group(1)
    mass = int(Parsmass)

    root_plot1D(
        l_hist = [hist_data],
        l_hist_overlay = [hist_prediction],
        outfile = f"{output_dir}/{hist_name}.pdf",
        xrange = (0, 500),
        yrange = (0, hist_data.GetMaximum()*1.5),
        # yrange = (0.0, 0.2),
        logx = False, logy = False,
        logx_ratio = False, logy_ratio = False,
        include_overflow = False,
        # xtitle = "Jet pt (GeV)",
        xtitle = "generator-level p_{T}^{miss} [GeV]",
        ytitle = "Events",
        # xtitle_ratio = "Jet pt (GeV)",
        xtitle_ratio = "generator-level p_{T}^{miss} [GeV]",
        ytitle_ratio = "eff.",
        centertitlex = True, centertitley = True,
        centerlabelx = False, centerlabely = False,
        gridx = True, gridy = True,
        ndivisionsx = None,
        stackdrawopt = "nostack",
        # normilize = True,
        normilize_overlay = False,
        legendpos = "UR",
        legendtitle = "m(#tilde{#tau}) = "+str(mass)+" GeV, c#tau_{0} = "+str(lifetime)+" mm",
        legendncol = 1,
        legendtextsize = 0.05,
        legendwidthscale = 1.7,
        legendheightscale = 1.5,
        # lumiText = f"{year} (13 TeV)",
        lumiText = f"(13 TeV)",
        CMSextraText = "Private Work",
        signal_to_background_ratio = True,
        ratio_mode = "B",
        yrange_ratio = (0.0, 1.0),
        ndivisionsy_ratio = (5, 5, 0),
        draw_errors = False
    )