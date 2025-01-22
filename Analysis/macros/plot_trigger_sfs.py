
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



#   KEY: TH1D     h1_eff_mc;1     MC
#   KEY: TH1D     h1_eff_data;1   Data
#   KEY: TH1D     h1_sf;1 Data

files = {
    "2017 (13TeV)" : "./trigger_sf_study/2017/trigger-eff-sfs_MET.root",
    "2018 (13TeV)" : "./trigger_sf_study/2018/trigger-eff-sfs_MET.root",
    "2016preVFP (13TeV)" : "./trigger_sf_study/2016_preVFP/trigger-eff-sfs_MET.root",
    "2016postVFP (13TeV)" : "./trigger_sf_study/2016_postVFP/trigger-eff-sfs_MET.root"
}

output_dir = "trigger_sfs"

for hist_name in files.keys():
    
    try: os.stat(output_dir)
    except: os.mkdir(output_dir)

    file = ROOT.TFile.Open(files[hist_name], 'read')
    hist_data = file.Get("h1_eff_data")
    hist_data.SetDirectory(0)
    # hist_data.Rebin(10)
    hist_data.SetMarkerStyle(20)
    hist_data.SetMarkerSize(1)
    hist_data.SetMarkerColor(1)
    hist_data.SetLineColor(4)
    hist_data.SetLineStyle(1)
    hist_data.SetLineWidth(1)
    hist_data.SetFillColor(0)
    hist_data.SetTitle("Data")
    # hist_data.Print("all")

    file_data = ROOT.TFile.Open(files[hist_name], 'read')
    hist_prediction = file_data.Get("h1_eff_mc")
    hist_prediction.SetDirectory(0)
    # hist_prediction.Rebin(10)
    hist_prediction.SetMarkerStyle(20)
    hist_prediction.SetMarkerSize(1)
    hist_prediction.SetMarkerColor(2)
    hist_prediction.SetLineColor(2)
    hist_prediction.SetLineStyle(1)
    hist_prediction.SetLineWidth(1)
    hist_prediction.SetFillColor(0)
    hist_prediction.SetTitle("Monte Carlo")

    root_plot1D(
        l_hist = [hist_prediction],
        l_hist_overlay = [hist_data],
        outfile = f"{output_dir}/{hist_name}.pdf",
        xrange = (0, 500),
        yrange = (0, hist_data.GetMaximum()*1.5),
        # yrange = (0.0, 0.2),
        logx = False, logy = False,
        logx_ratio = False, logy_ratio = False,
        include_overflow = False,
        # xtitle = "Jet pt (GeV)",
        xtitle = "p_{T}^{miss} [GeV]",
        ytitle = "Efficiency",
        # xtitle_ratio = "Jet pt (GeV)",
        xtitle_ratio = "p_{T}^{miss} [GeV]",
        ytitle_ratio = "Data/MC",
        centertitlex = True, centertitley = True,
        centerlabelx = False, centerlabely = False,
        gridx = True, gridy = True,
        ndivisionsx = None,
        stackdrawopt = "nostack",
        # normilize = True,
        normilize_overlay = False,
        legendpos = "UR",
        legendtitle = "",
        legendncol = 1,
        legendtextsize = 0.05,
        legendwidthscale = 1.7,
        legendheightscale = 2.0,
        # lumiText = f"{year} (13 TeV)",
        lumiText = f"{hist_name}",
        CMSextraText = " Private Work",
        signal_to_background_ratio = True,
        ratio_mode = "B",
        yrange_ratio = (0.5, 1.5),
        ndivisionsy_ratio = (5, 4, 0),
        draw_errors = False
    )
    
