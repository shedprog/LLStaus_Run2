import ROOT
ROOT.gROOT.SetBatch(True)
import itertools
import numpy as np
import os
import shutil

from .utils import *

def plot_predict_sys(dirname, config, xsec, cutflow, output_path):
    
    def read_hist(file, data_name, sys):
        hist = file.Get(data_name+"/"+sys+"/hist")
        if not hist:
            raise ValueError(f"Histogram not found! {file} {data_name}/{sys}/hist")
        hist.SetDirectory(0)
        return hist
    
    def rebin_hist(hist, rebin_setup, overflow = False):
        if type(rebin_setup) == list:
            hist = hist.Rebin(len(rebin_setup)-1, hist.GetName()+"_rebin", np.array(rebin_setup, dtype=np.double))
        else: 
            hist.Rebin(rebin_setup)
        # copy underflow and overflow to the last and first bins
        if overflow:
            hist.SetBinContent(1, hist.GetBinContent(0)+hist.GetBinContent(1))
            hist.SetBinContent(hist.GetNbinsX(), hist.GetBinContent(hist.GetNbinsX())+hist.GetBinContent(hist.GetNbinsX()+1))
            # add errors in quadrature
            hist.SetBinError(1, np.sqrt(hist.GetBinError(0)**2+hist.GetBinError(1)**2))
            hist.SetBinError(hist.GetNbinsX(), np.sqrt(hist.GetBinError(hist.GetNbinsX())**2+hist.GetBinError(hist.GetNbinsX()+1)**2))
        return hist
    
    include_sys = True
    systematics_pred = config["systematics_pred"]
    systematics_mc = config["systematics_mc"]
    
    for prediction_bin, data_bin in zip(config["prediction_hist"]["predictions"], config["prediction_hist"]["bin_data"]):
        for hist in config["prediction_hist"]["hists"]:

            print("Prediction bin:", prediction_bin, "Histogram:", hist)
            
            # Extracting histogram information
            x_min, x_max, rebin_setup, overflow, bin_labels = \
                config["prediction_hist"]["hists"][hist]
            cut = config["prediction_hist"]["cut"]
            
            # ----------------------------------------------
            # ---- Part to assign prediction histogram -----
            # ----------------------------------------------
            path_predict = dirname+"/"+cut+"_"+hist+"_yield_"+prediction_bin+".root"
            print(path_predict)
            file_predict = ROOT.TFile.Open(path_predict, 'read')
            hist_prediction = None
            hist_prediction_sys = {sys: {direction: None for direction in systematics_pred[sys]} for sys in systematics_pred}
            for data_group in config["Data"].keys():
                for data_name in config["Labels"][data_group]:

                    _hist_predict = read_hist(file_predict, data_name, "nominal")
                    if hist_prediction == None:
                        hist_prediction = _hist_predict
                    else:
                        hist_prediction.Add(_hist_predict)
                        
                    if include_sys:
                        for sys in systematics_pred:
                            for direction in systematics_pred[sys]:
                                _hist_predict_sys = read_hist(file_predict, data_name, systematics_pred[sys][direction])
                                if hist_prediction_sys[sys][direction] is None:
                                    hist_prediction_sys[sys][direction] = _hist_predict_sys
                                else:
                                    hist_prediction_sys[sys][direction].Add(_hist_predict_sys)

                                
            hist_prediction = rebin_hist(hist_prediction, rebin_setup, overflow)
            if include_sys:
                for sys in systematics_pred:
                    for direction in systematics_pred[sys]:
                        hist_prediction_sys[sys][direction] = rebin_hist(hist_prediction_sys[sys][direction], rebin_setup, overflow)
                        
            # calculate sum of the difference between the nominal and the systematic histograms
            if include_sys:
                up_error = np.zeros(hist_prediction.GetNbinsX() + 2)  # create also for the underflow and overflow
                down_error = np.zeros(hist_prediction.GetNbinsX() + 2)  # create also for the underflow and overflow
                for bin_i in range(0, hist_prediction.GetNbinsX() + 2):
                    down_error[bin_i] = up_error[bin_i] = hist_prediction.GetBinError(bin_i) ** 2
                    # sum up "up" and "down" variations if they have possitive shifts
                    delta_up_sum = 0
                    delta_down_sum = 0
                    
                    for sys in systematics_pred:
                        delta_up = hist_prediction_sys[sys]["up"].GetBinContent(bin_i) - hist_prediction.GetBinContent(bin_i)
                        delta_down = hist_prediction_sys[sys]["down"].GetBinContent(bin_i) - hist_prediction.GetBinContent(bin_i)
                        
                        if delta_up > 0: delta_up_sum += delta_up ** 2
                        else: delta_down_sum += delta_up ** 2
                        
                        if delta_down < 0: delta_down_sum += delta_down ** 2
                        else: delta_up_sum += delta_down ** 2
                    
                    up_error[bin_i] = np.sqrt( delta_up_sum )
                    down_error[bin_i] = np.sqrt( delta_down_sum )

                # Create TGraphAsymmErrors
                prediction_gr = ROOT.TGraphAsymmErrors(hist_prediction.GetNbinsX())
                for bin_i in range(0, hist_prediction.GetNbinsX() + 2):
                    prediction_gr.SetPoint(bin_i, hist_prediction.GetBinCenter(bin_i), hist_prediction.GetBinContent(bin_i))
                    prediction_gr.SetPointEYhigh(bin_i, up_error[bin_i])
                    prediction_gr.SetPointEYlow(bin_i, down_error[bin_i])
                    prediction_gr.SetPointEXhigh(bin_i, hist_prediction.GetBinWidth(bin_i) / 2)
                    prediction_gr.SetPointEXlow(bin_i, hist_prediction.GetBinWidth(bin_i) / 2)
            else:
                prediction_gr = None
                
            hist_prediction.SetMarkerStyle(21)
            hist_prediction.SetMarkerColor(423)
            hist_prediction.SetLineColor(423)
            hist_prediction.SetFillColor(423)
            hist_prediction.SetLineWidth(0)
            hist_prediction.SetTitle(f"Fake bkgr. ({str(prediction_bin)})")
            
            print("Prediction:")
            print(hist_prediction.Print("all"))
            print("Prediction sys:")
            print(up_error)
            print(down_error)
            # exit()
            hists_main = [hist_prediction]
            
            signal_hists = []
            # -----------------------------------------------
            # ---- Part to assign true (data) histogram -----
            # -----------------------------------------------
            path_data = dirname+"/"+cut+"_"+hist+"_pass.root"
            # path_data = dirname+"/"+cut+"_"+hist+".root"
            print(path_data)
            file_n_pass_sig = ROOT.TFile.Open(path_data, 'read')
            file_n_pass = ROOT.TFile.Open(path_data, 'read')

            if config["prediction_hist"]["plot_unblind"]:
                hist_data = None
                for data_group in config["Data"].keys():
                    for data_name in config["Labels"][data_group]:
                        _hist_data = read_hist(file_n_pass, data_name, "nominal/"+data_bin)
                        if hist_data == None:
                            hist_data = _hist_data
                        else:
                            hist_data.Add(_hist_data)

                hist_data = rebin_hist(hist_data, rebin_setup, overflow)
                hist_data.SetDirectory(0)
                hist_data.SetMarkerStyle(8)
                hist_data.SetMarkerSize(1)
                hist_data.SetMarkerColor(1)
                hist_data.SetLineWidth(3)
                hist_data.SetTitle(f"Data ({(str(data_bin))})")
                signal_hists.append(hist_data)
                # print("Data:")
                # print(hist_data.Print("all"))            

            # -----------------------------------------------
            # ---- Part to assign signal histogram ----------
            # -----------------------------------------------
            if config["prediction_hist"]["plot_signal"]:
                for _group_idx, _group_name in enumerate(config["Signal_samples"]):
                    # Accumulate the dataset for the particular data group as specified in config "Labels".
                    hist_signal_sys = {sys: {direction: None for direction in systematics_mc[sys]} for sys in systematics_mc}
                    for _dataset_idx, _histogram_data in enumerate(config["Labels"][_group_name]):
                        print("Adding signal dataset:", _histogram_data)
                        _hist = read_hist(file_n_pass_sig, _histogram_data, "nominal/"+data_bin)
                        N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                        scale =  xsec[_histogram_data] * config["luminosity"] / N
                        for bin_i in range(0, _hist.GetNbinsX()+2):
                            _hist.SetBinContent(bin_i, _hist.GetBinContent(bin_i)*scale)
                            _hist.SetBinError(bin_i, _hist.GetBinError(bin_i)*scale)
                            # add 20% uncertainty to the signal:
                            # error = np.sqrt(_hist.GetBinError(bin_i)**2 + (_hist.GetBinContent(bin_i)*0.2)**2)
                            # _hist.SetBinError(bin_i, error)
                        if _dataset_idx == 0:
                            signal_hists.append(_hist)
                        else:
                            signal_hists[-1].Add(_hist)
                        
                        if include_sys:
                            for sys in systematics_mc:
                                for direction in systematics_mc[sys]:
                                    _hist_sys = read_hist(file_n_pass_sig, _histogram_data, systematics_mc[sys][direction]+"/"+data_bin)
                                    for bin_i in range(0, _hist_sys.GetNbinsX()+2):
                                        _hist_sys.SetBinContent(bin_i, _hist_sys.GetBinContent(bin_i)*scale)
                                        _hist_sys.SetBinError(bin_i, _hist_sys.GetBinError(bin_i)*scale)
                                    if hist_signal_sys[sys][direction] is None:
                                        hist_signal_sys[sys][direction] = _hist_sys
                                    else:
                                        hist_signal_sys[sys][direction].Add(_hist_sys)
                        
                    if include_sys:
                        for sys in systematics_mc:
                            for direction in systematics_mc[sys]:
                                hist_signal_sys[sys][direction] = rebin_hist(hist_signal_sys[sys][direction], rebin_setup, overflow)

        
                        
                        for bin_i in range(0, signal_hists[-1].GetNbinsX() + 2):
                            down_error = up_error = signal_hists[-1].GetBinError(bin_i) ** 2
                            # sum up "up" and "down" variations if they have possitive shifts
                            delta_up_sum = 0
                            delta_down_sum = 0
                            
                            for sys in systematics_mc:
                                delta_up = hist_signal_sys[sys]["up"].GetBinContent(bin_i) - signal_hists[-1].GetBinContent(bin_i)
                                delta_down = hist_signal_sys[sys]["down"].GetBinContent(bin_i) - signal_hists[-1].GetBinContent(bin_i)
                                
                                if delta_up > 0: delta_up_sum += delta_up ** 2
                                else: delta_down_sum += delta_up ** 2
                                
                                if delta_down < 0: delta_down_sum += delta_down ** 2
                                else: delta_up_sum += delta_down ** 2
                            
                            up_error = np.sqrt( delta_up_sum )
                            down_error = np.sqrt( delta_down_sum )
                            
                            # symetrize the errors as squire root of the sum of the squares
                            error = np.sqrt( up_error ** 2 + down_error ** 2 )    
                            
                            signal_hists[-1].SetBinError(bin_i, error)
                                    
                    signal_hists[-1] = rebin_hist(signal_hists[-1], rebin_setup, overflow)
                    color_setup = config["Signal_samples"][_group_name]  
                    line_color = color_setup[1]
                    fill_color = color_setup[0]
                    line_style = color_setup[2]
                    signal_hists[-1].SetLineStyle(line_style)
                    signal_hists[-1].SetMarkerSize(0)
                    signal_hists[-1].SetLineWidth(2)
                    signal_hists[-1].SetLineColor(line_color)
                    signal_hists[-1].SetFillColor(fill_color)
                    signal_hists[-1].SetTitle(_group_name)

            assert(signal_hists.__len__() > 0)

            if bin_labels == None:
                x_axis_title = hist_prediction.GetXaxis().GetTitle()
                x_axis_title = x_axis_title.replace("$", "")
            else:
                x_axis_title = bin_labels
            
            year = config["year"]
            lumi = config["luminosity"]
           
            root_plot1D(
                l_hist = hists_main,
                l_hist_overlay = signal_hists,
                asym_error = prediction_gr,
                # l_hist_overlay = [hist_data] if config["prediction_hist"]["plot_unblind"] else [],
                outfile = output_path + "/" + hist + "_" + prediction_bin + ".png",
                xrange = [x_min, x_max],
                yrange = (0.01,  1000*hist_prediction.GetMaximum()),
                logx = False, logy = True,
                logx_ratio = False, logy_ratio = False,
                include_overflow = False,
                xtitle = x_axis_title,
                ytitle = "Events",
                xtitle_ratio = x_axis_title,
                ytitle_ratio = "Data/Pred.",
                centertitlex = True, centertitley = True,
                centerlabelx = False, centerlabely = False,
                gridx = True, gridy = True,
                ndivisionsx = None,
                stackdrawopt = "",
                ratio_mode = "DATA",
                normilize = False,
                normilize_overlay = False,
                legendpos = "UL",
                legendtitle = f"",
                legendncol = 2,
                legendtextsize = 0.030,
                legendwidthscale = 2.0,
                legendheightscale = 4.0,
                # lumiText = "(13 TeV)",
                lumiText = f"{year}, {lumi} fb^{'{'}-1{'}'}",
                CMSextraText = "Private Work",
                # CMSextraText = "",
                yrange_ratio = (0.0, 2.0),
                ndivisionsy_ratio = (5, 5, 0),
                signal_to_background_ratio = True,
                draw_errors = False
            )

def plot_predict(dirname, config, xsec, cutflow, output_path):
    
    for prediction_bin, data_bin in zip(config["prediction_hist"]["predictions"], config["prediction_hist"]["bin_data"]):
        for hist in config["prediction_hist"]["hists"]:

            print("Prediction bin:", prediction_bin, "Histogram:", hist)
            
            # Extracting histogram information
            x_min, x_max, rebin_setup, overflow, bin_labels = \
                config["prediction_hist"]["hists"][hist]
            cut = config["prediction_hist"]["cut"]
            # ----------------------------------------------
            # ---- Part to assign prediction histogram -----
            # ----------------------------------------------
            path_predict = dirname+"/"+cut+"_"+hist+"_yield_"+prediction_bin+".root"
            print(path_predict)
            file_predict = ROOT.TFile.Open(path_predict, 'read')
            # print(file_predict.ls())
            hist_prediction = None
            isDATA = False
            # for data_group in config["Data"].keys():
            #     for data_name in config["Labels"][data_group]:

            for _group_idx, _group_name in enumerate(config["Labels"].keys()):
                # Do not include signal samples in the prediction
                # if _group_name in config["Signal_samples"]:
                #     continue
                if not( _group_name in config["Data"]): continue
                # Accumulate the dataset for the particular data group as specified in config "Labels".
                for _idx, data_name in enumerate(config["Labels"][_group_name]):

                    print("Extract prediction:", data_name)
                    # open_tag = data_name+"/nominal/hist"
                    # open_tag = data_name+"/hist"
                    if config["include_systematics"]:
                        open_tag = data_name+"/nominal/hist"
                    else:
                        open_tag = data_name+"/hist"
                    _hist_predict = file_predict.Get(open_tag)
                    if not _hist_predict:
                        print("Warning: Histogram not found! ", end='')
                        print("Histogram->", file_predict, open_tag)
                        continue
                    _hist_predict.SetDirectory(0)

                    if _group_name in config["Data"]:
                        isDATA = True
                        pass
                    else:
                        if isDATA: raise("Can not combine data and MC")

                        if config["DY_stitching_applied"] and (
                                "DYJetsToLL_M-50" in data_name or
                                "DY1JetsToLL_M-50" in data_name or
                                "DY2JetsToLL_M-50" in data_name or
                                "DY3JetsToLL_M-50" in data_name or
                                "DY4JetsToLL_M-50" in data_name ):
                            # print("Stitching:", data_name)
                            _hist_predict.Scale(config["luminosity"])
                        elif config["W_stitching_applied"] and (
                                ("WJetsToLNu" in data_name and (not "TTWJets" in data_name)) or
                                "W1JetsToLNu" in data_name or
                                "W2JetsToLNu" in data_name or
                                "W3JetsToLNu" in data_name or
                                "W4JetsToLNu" in data_name ):
                            # print("Stitching:", data_name)
                            _hist_predict.Scale(config["luminosity"])
                        else:
                            # N = cutflow[_histogram_data]["all"]["NanDrop"] #After Nan dropper
                            N = cutflow[data_name]["all"]["BeforeCuts"]
                            _hist_predict.Scale( (xsec[data_name] * config["luminosity"]) / N)

                    if hist_prediction == None:
                        hist_prediction = _hist_predict
                    else:
                        hist_prediction.Add(_hist_predict)
            print(hist_prediction) 
            if type(rebin_setup) == list:
                hist_prediction = hist_prediction.Rebin(len(rebin_setup)-1, hist_prediction.GetName()+"_rebin", np.array(rebin_setup, dtype=np.double))
            else: 
                hist_prediction.Rebin(rebin_setup)
                
            hist_prediction.SetMarkerStyle(21)
            hist_prediction.SetMarkerColor(423)
            hist_prediction.SetLineColor(423)
            hist_prediction.SetFillColor(423)
            hist_prediction.SetLineWidth(0)
            hist_prediction.SetTitle(f"Fake bkgr. ({str(prediction_bin)})")
            # hist_prediction.SetTitle(f"MC predict. ({str(prediction_bin)})")
            
            # print("Prediction:")
            # print(hist_prediction.Print("all"))
            hists_main = [hist_prediction]
            
            signal_hists = []
            # -----------------------------------------------
            # ---- Part to assign true (data) histogram -----
            # -----------------------------------------------
            path_data = dirname+"/"+cut+"_"+hist+"_pass.root"
            print(path_data)
            file_n_pass_sig = ROOT.TFile.Open(path_data, 'read')
            file_n_pass = ROOT.TFile.Open(path_data, 'read')
            # print(file_n_pass_sig.ls())
            # print(file_n_pass.ls())
            if config["prediction_hist"]["plot_unblind"]:
                hist_data = None
                isDATA = False
                # for data_group in config["Data"].keys():
                #     for data_name in config["Labels"][data_group]:

                for _group_idx, _group_name in enumerate(config["Labels"].keys()):
                    # if (not _group_name in config["MC_bkgd"]) and (not _group_name in config["Signal_samples"]):
                    #     continue
                    if not( _group_name in config["Data"]): continue
                    # Accumulate the dataset for the particular data group as specified in config "Labels".
                    for _idx, data_name in enumerate(config["Labels"][_group_name]):

                        # print(file_n_pass.ls())
                        # print(data_name+"_"+data_bin)
                        if isinstance(data_bin, str):
                            # open_tag = data_name+"/nominal/"+data_bin+"/hist"
                            if config["include_systematics"]:
                                open_tag = data_name+"/nominal/"+data_bin+"/hist"
                            else:
                                open_tag = data_name+"/"+data_bin+"/hist"
                            _hist_data = file_n_pass.Get(open_tag)
                        elif isinstance(data_bin, int):
                            _hist_data = file_n_pass.Get(data_name)
                            _hist_data = _hist_data.ProjectionX(data_name+"_proj", data_bin, data_bin)
                        if not _hist_data:
                            print("Warning: Histogram not found! ", end='')
                            print("Histogram->", file_n_pass, open_tag)
                            continue
                        _hist_data.SetDirectory(0)

                        if _group_name in config["Data"]:
                            isDATA = True
                            pass
                        else:
                            if isDATA: raise("Can not combine data and MC")

                            if config["DY_stitching_applied"] and (
                                    "DYJetsToLL_M-50" in data_name or
                                    "DY1JetsToLL_M-50" in data_name or
                                    "DY2JetsToLL_M-50" in data_name or
                                    "DY3JetsToLL_M-50" in data_name or
                                    "DY4JetsToLL_M-50" in data_name ):
                                # print("Stitching:", data_name)
                                _hist_data.Scale(config["luminosity"])
                            elif config["W_stitching_applied"] and (
                                    ("WJetsToLNu" in data_name and (not "TTWJets" in data_name)) or
                                    "W1JetsToLNu" in data_name or
                                    "W2JetsToLNu" in data_name or
                                    "W3JetsToLNu" in data_name or
                                    "W4JetsToLNu" in data_name ):
                                # print("Stitching:", data_name)
                                _hist_data.Scale(config["luminosity"])
                            else:
                                # N = cutflow[_histogram_data]["all"]["NanDrop"] #After Nan dropper
                                N = cutflow[data_name]["all"]["BeforeCuts"]
                                _hist_data.Scale( (xsec[data_name] * config["luminosity"]) / N)

                       
                        if hist_data == None:
                            hist_data = _hist_data
                        else: hist_data.Add(_hist_data)
                        
                if type(rebin_setup) == list:
                    hist_data = hist_data.Rebin(len(rebin_setup)-1, hist_data.GetName()+"_rebin", np.array(rebin_setup, dtype=np.double))
                else: 
                    hist_data.Rebin(rebin_setup)
                hist_data.SetDirectory(0)
                hist_data.SetMarkerStyle(8)
                hist_data.SetMarkerSize(1)
                hist_data.SetMarkerColor(1)
                hist_data.SetLineWidth(3)
                hist_data.SetTitle(f"Data ({(str(data_bin))})")
                # hist_data.SetTitle(f"MC yield ({(str(data_bin))})")
                signal_hists.append(hist_data)
                # print("Data:")
                # print(hist_data.Print("all"))            

            # -----------------------------------------------
            # ---- Part to assign signal histogram ----------
            # -----------------------------------------------
            if config["prediction_hist"]["plot_signal"]:
                for _group_idx, _group_name in enumerate(config["Signal_samples"]):
                    # Accumulate the dataset for the particular data group as specified in config "Labels".
                    for _dataset_idx, _histogram_data in enumerate(config["Labels"][_group_name]):
                        print("Adding signal dataset:", _histogram_data)
                        if isinstance(data_bin, str):
                            # open_tag = _histogram_data+"/nominal/"+data_bin+"/hist"
                            if config["include_systematics"]:
                                open_tag = _histogram_data+"/nominal/"+data_bin+"/hist"
                            else:
                                open_tag = _histogram_data+"/"+data_bin+"/hist"
                            _hist = file_n_pass_sig.Get(open_tag)
                        elif isinstance(data_bin, int):
                            _hist = file_n_pass_sig.Get(_histogram_data)
                            _hist = _hist.ProjectionX(_histogram_data+"_proj", data_bin, data_bin)
                        _hist.SetDirectory(0)
                        N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                        scale =  xsec[_histogram_data] * config["luminosity"] / N
                        # _hist.Scale( (xsec[_histogram_data] * config["luminosity"]) / N)
                        for bin_i in range(0, _hist.GetNbinsX()+2):
                            _hist.SetBinContent(bin_i, _hist.GetBinContent(bin_i)*scale)
                            _hist.SetBinError(bin_i, _hist.GetBinError(bin_i)*scale)
                        if _dataset_idx == 0:
                            signal_hists.append(_hist)
                        else:
                            signal_hists[-1].Add(_hist)
                    if type(rebin_setup) == list:
                        signal_hists[-1] = signal_hists[-1].Rebin(len(rebin_setup)-1, signal_hists[-1].GetName()+"_rebin", np.array(rebin_setup, dtype=np.double))
                    else: 
                        signal_hists[-1].Rebin(rebin_setup)
                    color_setup = config["Signal_samples"][_group_name]  
                    line_color = color_setup[1]
                    fill_color = color_setup[0]
                    line_style = color_setup[2]
                    signal_hists[-1].SetLineStyle(line_style)
                    signal_hists[-1].SetMarkerSize(0)
                    signal_hists[-1].SetLineWidth(2)
                    signal_hists[-1].SetLineColor(line_color)
                    signal_hists[-1].SetFillColor(fill_color)
                    signal_hists[-1].SetTitle(_group_name)

            # print(signal_hists)

            # remove $ char from the title name
            if bin_labels == None:
                x_axis_title = hist_prediction.GetXaxis().GetTitle()
                x_axis_title = x_axis_title.replace("$", "")
            else:
                x_axis_title = bin_labels

            year = config["year"]
            lumi = config["luminosity"]

            root_plot1D(
                l_hist = hists_main,
                l_hist_overlay = signal_hists,
                # l_hist_overlay = [hist_data] if config["prediction_hist"]["plot_unblind"] else [],
                outfile = output_path + "/" + hist + "_" + prediction_bin + ".png",
                xrange = [x_min, x_max],
                yrange = (0.01,  1000*hist_prediction.GetMaximum()),
                logx = False, logy = True,
                logx_ratio = False, logy_ratio = False,
                include_overflow = overflow,
                xtitle = x_axis_title,
                ytitle = "Events",
                xtitle_ratio = x_axis_title,
                ytitle_ratio = "Data / Pred.",
                centertitlex = True, centertitley = True,
                centerlabelx = False, centerlabely = False,
                gridx = True, gridy = True,
                ndivisionsx = None,
                stackdrawopt = "",
                ratio_mode = "DATA",
                normilize = False,
                normilize_overlay = False,
                legendpos = "UL",
                legendtitle = f"",
                legendncol = 2,
                legendtextsize = 0.040,
                legendwidthscale = 2.0,
                legendheightscale = 4.0,
                # lumiText = f"{year}, {lumi} fb^{-1} (13 TeV)",
                lumiText = f"{year}, {lumi} fb^{'{'}-1{'}'}",
                CMSextraText = "Private work",
                # lumiText = "(13 TeV)",
                yrange_ratio = (0.0, 2.0),
                ndivisionsy_ratio = (5, 5, 0),
                signal_to_background_ratio = True,
                draw_errors = True
            )

def plot_predict2D(dirname, config, xsec, cutflow, output_path):
    
    ROOT.gInterpreter.Declare('#include "utils/histogram2d.cpp"')
    
    for prediction_bin, data_bin in zip(config["prediction_hist2D"]["predictions"], config["prediction_hist2D"]["bin_data"]):
        for hist in config["prediction_hist2D"]["hists"]:

            # ~~~~~~~~~~~~~~~ Prediction 
            print("Prediction bin:", prediction_bin, "Histogram:", hist)
            # Extracting histogram information
            axis_rebin, overflow, bin_labels = \
                config["prediction_hist2D"]["hists"][hist]
            cut = config["prediction_hist2D"]["cut"]
            path_predict = dirname+"/"+cut+"_"+hist+"_"+prediction_bin+".root"
            print(path_predict)
            file_predict = ROOT.TFile.Open(path_predict, 'read')
            hist_prediction = None
            for data_group in config["Data"].keys():
                for data_name in config["Labels"][data_group]:
                    print("Extract prediction:", data_name)
                    if hist_prediction == None:
                        hist_prediction = file_predict.Get(data_name+"/hist")
                    else:
                        hist_prediction.Add(file_predict.Get(data_name+"/hist"))
            print(hist_prediction)
            x_axis = axis_rebin["x_axis"]
            y_axis =  np.array(axis_rebin["y_axis"], dtype=np.double)
            xmin, xmax = float(x_axis[0][0]), float(x_axis[0][-1])
    
            hist_prediction_nonunif = ROOT.Histogram_2D("nonunif_pred", y_axis, xmin, xmax)
            for i in range(len(x_axis)):
                hist_prediction_nonunif.add_x_binning_by_index(i, np.array(x_axis[i], dtype=np.double))
            
            try:
                hist_prediction_nonunif.th2d_add(hist_prediction)
            except:
                print("Error is inside project nonunif histograms")
                print("Error: can not add histogram because of the inconsistency")
                del hist_prediction_nonunif
                exit()
            hist_prediction_nonunif.print("")
            hist_prediction_nonunif_th2 = hist_prediction_nonunif.get_weights_th2d_simpl("hist_prediction_nonunif_th2",
                                                                                         "hist_prediction_nonunif_th2")
            del hist_prediction_nonunif
            
            ## ~~~~~~~~~~~~~~~ Signal
            path_data = dirname+"/"+cut+"_"+hist+"_pass.root"
            print(path_data)
            file_n_pass_sig = ROOT.TFile.Open(path_data, 'read')
            _signal_name = config["prediction_hist2D"]["signal_model"]
            signal_hists = None
            for _dataset_idx, _histogram_data in enumerate(config["Labels"][_signal_name]):
                print("Adding signal dataset:", _histogram_data)
                print("reading:", _histogram_data+"/nominal/"+data_bin+"/hist")
                _hist = file_n_pass_sig.Get(_histogram_data+"/nominal/"+data_bin+"/hist")
                _hist.SetDirectory(0)
                N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                scale =  xsec[_histogram_data] * config["luminosity"] / N
                _hist.Scale(scale)
                if signal_hists == None:
                    signal_hists = _hist
                else:
                    signal_hists.Add(_hist)
                    
            hist_sig_nonunif = ROOT.Histogram_2D("nonunif_sig", y_axis, xmin, xmax)
            for i in range(len(x_axis)):
                hist_sig_nonunif.add_x_binning_by_index(i, np.array(x_axis[i], dtype=np.double))
            
            try:
                hist_sig_nonunif.th2d_add(signal_hists)
            except:
                print("Error is inside project nonunif histograms")
                print("Error: can not add histogram because of the inconsistency")
                del hist_sig_nonunif
                exit()
            hist_sig_nonunif.print("")
            hist_sig_nonunif_th2 = hist_sig_nonunif.get_weights_th2d_simpl("hist_sig_nonunif_th2",
                                                                           "hist_sig_nonunif_th2")
            del hist_sig_nonunif
            
            root_plots2D_simple(
                    hist_prediction_nonunif_th2,
                    outfile = output_path + "/" + hist + "_" + prediction_bin +"_predict"+ ".pdf",
                    yrange=(y_axis[0], y_axis[-1]),
                    xrange=(x_axis[0][0], x_axis[0][-1]),
                    logx = False, logy = False, logz = False,
                    title = "",
                    # xtitle = "p^{miss}_{T} [GeV]", ytitle = "m_{T2} [GeV]",
                    # xtitle = "p^{miss}_{T} [GeV]", ytitle = "#Sigma m_{T} [GeV]",
                    xtitle = bin_labels[0], ytitle = bin_labels[1],
                    centertitlex = True, centertitley = True,
                    centerlabelx = False, centerlabely = False,
                    gridx = False, gridy = False,
                    CMSextraText = "Private work (Prediction)",
                    lumiText = "(13 TeV)",
                )
            
            root_plots2D_simple(
                    hist_sig_nonunif_th2,
                    outfile = output_path + "/" + hist + "_" + prediction_bin +"_signal"+ ".pdf",
                    yrange=(y_axis[0], y_axis[-1]),
                    xrange=(x_axis[0][0], x_axis[0][-1]),
                    logx = False, logy = False, logz = False,
                    title = "",
                    # xtitle = "p^{miss}_{T} [GeV]", ytitle = "m_{T2} [GeV]",
                    # xtitle = "p^{miss}_{T} [GeV]", ytitle = "#Sigma m_{T} [GeV]",
                    xtitle = bin_labels[0], ytitle = bin_labels[1],
                    centertitlex = True, centertitley = True,
                    centerlabelx = False, centerlabely = False,
                    gridx = False, gridy = False,
                    CMSextraText = f"Private work ({_signal_name})",
                    lumiText = "(13 TeV)",
                )
            
            hist_prediction_nonunif_th2.Add(hist_sig_nonunif_th2)
            hist_sig_nonunif_th2.Divide(hist_prediction_nonunif_th2)
            root_plots2D_simple(
                    hist_sig_nonunif_th2,
                    outfile = output_path + "/" + hist + "_" + prediction_bin +"_RATIO"+ ".pdf",
                    yrange=(y_axis[0], y_axis[-1]),
                    xrange=(x_axis[0][0], x_axis[0][-1]),
                    logx = False, logy = False, logz = False,
                    title = "",
                    # xtitle = "p^{miss}_{T} [GeV]", ytitle = "m_{T2} [GeV]",
                    # xtitle = "p^{miss}_{T} [GeV]", ytitle = "#Sigma m_{T} [GeV]",
                    xtitle = bin_labels[0], ytitle = bin_labels[1],
                    centertitlex = True, centertitley = True,
                    centerlabelx = False, centerlabely = False,
                    gridx = False, gridy = False,
                    CMSextraText = f"Private work ( S/(S+B) )",
                    lumiText = "(13 TeV)",
                )

def plot1D(histfiles, histnames, config, xsec, cutflow, output_path, isData):

    categories_list = list(itertools.product(*config["Categories"]))
    # categories_list = [f"{cat1}_{cat2}_{cat3}" for cat1,cat2,cat3 in categories_list]
    categories_list = ["/".join(cat) for cat in categories_list]
    # categories_list = [""]
    
    for _ci, _categ in enumerate(categories_list):

        output = output_path + "/" + _categ

        for _histfile, _histname in zip(histfiles,histnames):
            
            if not _histname in config["SetupBins"]:
                continue

            # print([cut in str(_histfile) for cut in config["cuts"]])
            if not any([cut in str(_histfile) for cut in config["cuts"]]):
                continue

            # print("OPEN:", _histfile)
            file = ROOT.TFile.Open(str(_histfile), 'read')

            _histograms = {"background":[], "signal":[], "data":[]}
            for _group_idx, _group_name in enumerate(config["Labels"].keys()):

                if _group_name in config["Signal_samples"]:
                    isSignal = "signal" 
                elif _group_name in config["Data"]:
                    isSignal = "data" 
                else:
                    isSignal = "background"
                
                has_group_entry = False
                # Accumulate the dataset for the particular data group as specified in config "Labels".
                for _idx, _histogram_data in enumerate(config["Labels"][_group_name]):
                    
                    print("Reading data:", _histogram_data + "_" + _categ)

                    # if category is enforced then change select it
                    _read_category = _categ
                    if "force_category" in config:
                        if _group_name in config["force_category"]:
                            print(config["force_category"][_group_name])
                            print("/".join(config["force_category"][_group_name]))
                            _read_category = "/".join(config["force_category"][_group_name])

                    try:
                        hist = read_hist_path(
                            file,
                            _histogram_data,
                            "nominal" if config["include_systematics"] else None,
                            _read_category if not _read_category=="" else None,
                        )
                    except Exception as e:
                        print("Failed to read the file!")
                        print("Error message: ", str(e))
                        continue
                    
                    if config["include_systematics"]:
                        for syst in config["systematics"]:
                            try:
                                hist_up = read_hist_path(
                                    file, 
                                    _histogram_data, 
                                    config["systematics"][syst]["up"], 
                                    _read_category if not _read_category=="" else None)
                                hist_down = read_hist_path(
                                    file,
                                    _histogram_data,
                                    config["systematics"][syst]["down"],
                                    _read_category if not _read_category=="" else None)
                            except Exception as e:
                                print("Failed to read systematic!")
                                print("Error message: ", str(e))
                                continue
                            # Symmetrize the uncertainties
                            for i in range(0, hist.GetNbinsX() + 2):
                                unc_up = hist_up.GetBinContent(i) - hist.GetBinContent(i)
                                unc_down = hist_down.GetBinContent(i) - hist.GetBinContent(i)
                                sym_unc = 0.5 * (abs(unc_up) + abs(unc_down))

                                # Add the symmetrized uncertainties in quadrature to the existing bin error
                                current_error = hist.GetBinError(i)
                                total_error = np.sqrt(current_error**2 + sym_unc**2)
                                hist.SetBinError(i, total_error)

                    if isSignal != "data": # Scaling of the MC to the lumi and xsection
                        if config["DY_stitching_applied"] and (
                                "DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY1JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY2JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY3JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY4JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data ):
                            print("Stitching:", _histogram_data)
                            # lo_div_nlo = 6077.22/6233.55
                            hist.Scale(config["luminosity"])
                            # hist.Scale(0.94) # normalisation factor (measured in Z->mumu region) = 0.87
                            print(_histogram_data, hist.Integral())
                            
                            # if some of the MC give zero contribution in bin one-sided Poisson error is used
                            # if not config["include_systematics"]:
                            #     for i in range(0, hist.GetNbinsX() + 2):
                            #         if hist.GetBinContent(i) == 0:
                            #             N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                            #             alpha = (xsec[_histogram_data] * config["luminosity"]) / N
                            #             hist.SetBinError(i, -np.log((1 - 0.6827)/2) * alpha)
                            
                            # for i in range(0, hist.GetNbinsX() + 2):
                            #     hist.SetBinError(i, 
                            #         np.sqrt(hist.GetBinError(i)**2 + (0.15 * hist.GetBinContent(i))**2)
                            #     )
                        elif config["W_stitching_applied"] and (
                                ("WJetsToLNu" in _histogram_data and (not "TTWJets" in _histogram_data)) or
                                "W1JetsToLNu" in _histogram_data or
                                "W2JetsToLNu" in _histogram_data or
                                "W3JetsToLNu" in _histogram_data or
                                "W4JetsToLNu" in _histogram_data ):
                            # print("Stitching:", _histogram_data)
                            hist.Scale(config["luminosity"])
                            # hist.Scale(0.50)
                        elif _histogram_data == "QCD-pred":
                            if not config["include_systematics"]:
                                for i in range(0, hist.GetNbinsX() + 2):
                                    # Set error 10% for QCD-pred
                                    hist.SetBinError(i, 0.1 * hist.GetBinContent(i))
                        else:
                            # N = cutflow[_histogram_data]["all"]["NanDrop"] #After Nan dropper
                            N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                            hist.Scale( (xsec[_histogram_data] * config["luminosity"]) / N)
                            print(_histogram_data, hist.Integral())
                            
                    # because QCD-pred is already rebinned,
                    # because if it is not rebinned on the QCD-pred step then the binn is too small
                    # this leads to a lot of negative values in the histogram
                    if not _histogram_data == "QCD-pred": 
                        if _histname in config["SetupBins"]:
                            rebin_setup = config["SetupBins"][_histname][2]
                            if type(rebin_setup) == list:
                                hist = hist.Rebin(len(rebin_setup)-1, hist.GetName()+"_rebin", np.array(rebin_setup, dtype=np.double))
                            else: 
                                hist.Rebin(rebin_setup)
                                
                    if config["SetupBins"][_histname][4]:
                        if type(config["SetupBins"][_histname][4]) == list:
                            for bin_i, label in enumerate(config["SetupBins"][_histname][4]):
                                hist.GetXaxis().SetBinLabel(bin_i, label)
                                hist.GetXaxis().SetTitle("")
                        elif type(config["SetupBins"][_histname][4]) == str:
                            print("Set title:", config["SetupBins"][_histname][4])
                            hist.GetXaxis().SetTitle(config["SetupBins"][_histname][4])
          
                    if not has_group_entry:
                        # print("Append:", _histogram_data)
                        _histograms[isSignal].append(hist)
                        has_group_entry = True
                    else:
                        # print("Add:", _histogram_data)
                        _histograms[isSignal][-1].Add(hist)

                if has_group_entry: # if there is at least one histogram in input
                    
                    if isSignal == "signal":
                        color_setup = config["Signal_samples"][_group_name]  
                        fill_color = color_setup[0]
                        line_color = color_setup[1]
                        line_style = color_setup[2]
                        _histograms[isSignal][-1].SetLineStyle(line_style)
                        _histograms[isSignal][-1].SetMarkerSize(0)
                        _histograms[isSignal][-1].SetLineWidth(4)
                        _histograms[isSignal][-1].SetLineColor(line_color)
                        _histograms[isSignal][-1].SetFillColor(fill_color)
                    elif isSignal == "data":
                        color_setup = config["Data"][_group_name]  
                        fill_color = color_setup[0] 
                        line_color = color_setup[1]
                        _histograms[isSignal][-1].SetMarkerStyle(8)
                        _histograms[isSignal][-1].SetMarkerSize(1)
                        _histograms[isSignal][-1].SetLineWidth(1)
                        _histograms[isSignal][-1].SetLineColor(line_color)
                        _histograms[isSignal][-1].SetFillColor(fill_color)
                    else:
                        color_setup = config["MC_bkgd"][_group_name]  
                        line_color = color_setup[1]
                        fill_color = color_setup[0]
                        _histograms[isSignal][-1].SetMarkerSize(0)
                        _histograms[isSignal][-1].SetLineWidth(4)
                        _histograms[isSignal][-1].SetLineColor(ROOT.TColor.GetColor(line_color))
                        _histograms[isSignal][-1].SetFillColor(ROOT.TColor.GetColor(fill_color)) 
                    
                    # _histograms[isSignal][-1].SetLineColor(line_color)
                    # _histograms[isSignal][-1].SetFillColor(line_color)
                    _histograms[isSignal][-1].SetTitle(_group_name)
                    print("Set title:", _group_name)
            # exit()
            # get maximum for the y-scale
            y_max = 0
            if not _histograms["background"].__len__() == 0:
                y_max = _histograms["background"][0].GetMaximum()
                for _h in _histograms["background"]:
                    y_max = max(y_max,_h.GetMaximum())
            # define y_max from data
            if not _histograms["data"].__len__() == 0:
                y_max = max(y_max,_histograms["data"][0].GetMaximum())

            # sort histogram from min to max
            _histograms_background_entries = []
            _histograms_background_sorted = []
            for _h in _histograms["background"]:
                _histograms_background_entries.append(_h.Integral())
            _sorted_hist = np.argsort(_histograms_background_entries)
            for _idx in _sorted_hist:
                _histograms_background_sorted.append(_histograms["background"][_idx])

            # read the binning if available:
            if _histname in config["SetupBins"]:
                xrange_min = config["SetupBins"][_histname][0]
                xrange_max = config["SetupBins"][_histname][1]
                overflow =  bool(config["SetupBins"][_histname][3])
                units = config["SetupBins"][_histname][5]
                print("overflow:", overflow)
            else:
                xrange_min = _histograms["background"][0].GetXaxis().GetXmin()
                xrange_max = _histograms["background"][0].GetXaxis().GetXmax()
                overflow =  True
            
            # get bin width
            if not _histograms["background"].__len__() == 0:
                bin_width = round(_histograms["background"][0].GetXaxis().GetBinWidth(1), 4)
            else:
                bin_width = round(_histograms["data"][0].GetXaxis().GetBinWidth(1), 4)

            year = config["year"]
            lumi = config["luminosity"]
            print(_histograms_background_sorted)
            print(_histograms["data"])
            if isData:
                root_plot1D(
                    l_hist = _histograms_background_sorted,
                    l_hist_overlay = _histograms["data"],
                    outfile = output + "/" + os.path.splitext(os.path.basename(_histfile))[0] + ".png",
                    xrange = [xrange_min, xrange_max],
                    # yrange = (0.0,  2.0*y_max), 
                    # logx = False, logy = False,
                    yrange = (1.0,  100*y_max),
                    logx = False, logy = True,
                    logx_ratio = False, logy_ratio = False,
                    include_overflow = overflow,
                    xtitle = _histograms["background"][0].GetXaxis().GetTitle(),
                    ytitle = f"Events / {bin_width} {units}",
                    xtitle_ratio = _histograms["background"][0].GetXaxis().GetTitle(),
                    ytitle_ratio = "DATA / MC",
                    centertitlex = True, centertitley = True,
                    centerlabelx = False, centerlabely = False,
                    gridx = True, gridy = True,
                    ndivisionsx = None,
                    stackdrawopt = "",
                    # normilize = True,
                    normilize_overlay = False,
                    legendpos = "UL",
                    legendtitle = f"",
                    legendncol = 3,
                    legendtextsize = 0.037,
                    legendwidthscale = 1.9,
                    legendheightscale = 0.46,
                    lumiText = f"{year}, {lumi} fb^{'{'}-1{'}'}",
                    signal_to_background_ratio = True,
                    ratio_mode = "DATA",
                    CMSextraText = "Internal",
                    # ndivisionsy_ratio = (4, 2, 0),
                    ndivisionsy_ratio = (4, 5, 0),
                    yrange_ratio = (0.0, 2.0),
                    # yrange_ratio = (0.0, 1.2),
                    draw_errors = True
                )
            
            else:
                root_plot1D(
                    l_hist = _histograms_background_sorted,
                    l_hist_overlay = _histograms["signal"],
                    # l_hist = _histograms["data"],
                    # l_hist_overlay = _histograms["signal"],
                    outfile = output + "/" + os.path.splitext(os.path.basename(_histfile))[0] + ".png",
                    xrange = [xrange_min, xrange_max],
                    # yrange = (0.0,  2.0*y_max), 
                    # logx = False, logy = False,
                    yrange = (0.01,  100*y_max),
                    logx = False, logy = True,
                    logx_ratio = False, logy_ratio = False,
                    include_overflow = overflow,
                    xtitle = _histograms["data"][0].GetXaxis().GetTitle(),
                    ytitle = f"Events / {bin_width} {units}",
                    xtitle_ratio = _histograms["data"][0].GetXaxis().GetTitle(),
                    ytitle_ratio = "DATA / MC",
                    centertitlex = True, centertitley = True,
                    centerlabelx = False, centerlabely = False,
                    gridx = True, gridy = True,
                    ndivisionsx = None,
                    stackdrawopt = "",
                    # normilize = True,
                    normilize_overlay = False,
                    legendpos = "UL",
                    legendtitle = f"",
                    legendncol = 3,
                    legendtextsize = 0.015,
                    legendwidthscale = 2.1,
                    legendheightscale = 0.46,
                    lumiText = f"{year}, {lumi} fb^{-1} (13 TeV)",
                    signal_to_background_ratio = False,
                    ratio_mode = "DATA",
                    CMSextraText = "Internal",
                    # ndivisionsy_ratio = (4, 2, 0),
                    ndivisionsy_ratio = (4, 5, 0),
                    yrange_ratio = (0.0, 2.0),
                    # yrange_ratio = (0.0, 1.2),
                    draw_errors = True
                )
                # root_plot1D(
                #     l_hist = _histograms_background_sorted,
                #     l_hist_overlay = _histograms["signal"],
                #     outfile = output + "/" + os.path.splitext(os.path.basename(_histfile))[0] + ".png",
                #     xrange = [xrange_min, xrange_max],
                #     yrange = (0.001,  1000*y_max),
                #     # yrange = (0.0,  1.5*y_max),
                #     logx = False, logy = True,
                #     logx_ratio = False, logy_ratio = True,
                #     include_overflow = overflow,
                #     xtitle = _histograms["background"][0].GetXaxis().GetTitle(),
                #     ytitle = "Events",
                #     xtitle_ratio = _histograms["background"][0].GetXaxis().GetTitle(),
                #     ytitle_ratio = "S/#sqrt{S+B}",
                #     centertitlex = True, centertitley = True,
                #     centerlabelx = False, centerlabely = False,
                #     gridx = True, gridy = True,
                #     ndivisionsx = None,
                #     stackdrawopt = "",
                #     # normilize = True,
                #     normilize_overlay = False,
                #     legendpos = "UL",
                #     legendtitle = f"",
                #     legendncol = 3,
                #     legendtextsize = 0.025,
                #     legendwidthscale = 2.1,
                #     legendheightscale = 0.46,
                #     lumiText = "(13 TeV)",
                #     signal_to_background_ratio = True,
                #     ratio_mode = "SB",
                #     yrange_ratio = (0.1, 1E5),
                #     draw_errors = False
                # )

def doQCDprediction(histfiles, histnames, config, xsec, cutflow, output_path, isData,  histfile_json):

    # categories_list = list(itertools.product(*config["Categories"]))
    # categories_list = [f"{cat1}_{cat2}_{cat3}" for cat1,cat2,cat3 in categories_list]
    # categories_list = ["_".join(cat) for cat in categories_list]
    # categories_list = [""]
    
    def generate_combinations(items):
        """ Generate all combinations if there are nested lists """
        return ["/".join(map(str, combo)) for combo in itertools.product(*[x if isinstance(x, list) else [x] for x in items])]

    if config["QCD-prediction"]["mode"] == "prediction":
        prediction = config["QCD-prediction"]["categories"]["prediction_cat"]
        output_names = config["QCD-prediction"]["output_dataset_name"]
        # Generate combinations for categories and output names
        categ_combinations = generate_combinations(prediction)
        output_name_combinations = generate_combinations(output_names)
        print("Categories:",categ_combinations,"output:",output_name_combinations)
    elif config["QCD-prediction"]["mode"] == "factor":
        numerator = "/".join(config["QCD-prediction"]["categories"]["numerator"])
        denominator = "/".join(config["QCD-prediction"]["categories"]["denominator"])
        categ_combinations = [numerator, denominator]
        print("Categories:",categ_combinations)
    else:
        raise ValueError("Mode for prediction QCD is not known")

    # exit()
    for _histfile, _histname in zip(histfiles,histnames):
        
        # print(_histname in config["QCD-prediction"]["hists"])
        if not _histname in config["QCD-prediction"]["hists"]:
            continue

        hist_qcd = {}
        if not any([cut in str(_histfile) for cut in config["cuts"]]):
            continue
        
        for _categ_idx, _categ in enumerate(categ_combinations):

            if config["QCD-prediction"]["mode"] == "prediction":
                output = output_path + "/" + _categ

            # print("OPEN:", _histfile)
            file = ROOT.TFile.Open(str(_histfile), 'read')

            _histograms = {"background":[], "data":[]}
            for _group_idx, _group_name in enumerate(config["Labels"].keys()):
                
                if _group_name == config["QCD-prediction"]["data_name"]:
                    isSignal = "data" 
                elif _group_name in config["QCD-prediction"]["substructed_mc"]:
                    isSignal = "background"
                else:
                    raise ValueError(f"Bad samples ({_group_name}) in QCD prediction function")
                
                has_group_entry = False
                # Accumulate the dataset for the particular data group as specified in config "Labels".
                for _idx, _histogram_data in enumerate(config["Labels"][_group_name]):
                    
                    # Rescaling according to cross-section and luminosity
                    print("Reading data:", _histogram_data + "/" + _categ)
                    try:
                        hist = read_hist_path(
                            file,
                            _histogram_data,
                            # "nominal" if config["include_systematics"] else None,
                            _categ if not _categ=="" else None,
                        )
                    except Exception as e:
                        print("Failed to read the file!")
                        print("Error message: ", str(e))
                        continue
                    
                    if isSignal != "data": # Scaling of the MC to the lumi and xsection
                        if config["DY_stitching_applied"] and (
                                "DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY1JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY2JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY3JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data or
                                "DY4JetsToLL_M-50_MatchEWPDG20_TuneCP5_13TeV-madgraphMLM-pythia8" in _histogram_data ):
                            print("Stitching:", _histogram_data)
                            hist.Scale(config["luminosity"])
                        elif config["W_stitching_applied"] and (
                                ("WJetsToLNu" in _histogram_data and (not "TTWJets" in _histogram_data)) or
                                "W1JetsToLNu" in _histogram_data or
                                "W2JetsToLNu" in _histogram_data or
                                "W3JetsToLNu" in _histogram_data or
                                "W4JetsToLNu" in _histogram_data ):
                            print("Stitching:", _histogram_data)
                            hist.Scale(config["luminosity"])
                        else:
                            # N = cutflow[_histogram_data]["all"]["NanDrop"] #After Nan dropper
                            N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                            hist.Scale( (xsec[_histogram_data] * config["luminosity"]) / N)

                    if _histname in config["SetupBins"]:
                        rebin_setup = config["SetupBins"][_histname][2]
                        if type(rebin_setup) == list:
                            hist = hist.Rebin(len(rebin_setup)-1, hist.GetName()+"_rebin", np.array(rebin_setup, dtype=np.double))
                        else: 
                            hist.Rebin(rebin_setup)
                            
            
                    if not has_group_entry:
                        # print("Append:", _histogram_data)
                        _histograms[isSignal].append(hist)
                        has_group_entry = True
                    else:
                        # print("Add:", _histogram_data)
                        _histograms[isSignal][-1].Add(hist)
                        
            histQCD = _histograms["data"][0].Clone()
            for _h in _histograms["background"]:
                histQCD.Add(_h, -1)
            
            if config["QCD-prediction"]["mode"] == "prediction":
                
                # check or negative values:
                for i in range(histQCD.GetNbinsX()+1):
                    # multiply content and error on factor
                    factor = config["QCD-prediction"]["factor"]
                    histQCD.SetBinContent(i, histQCD.GetBinContent(i)*factor)
                    histQCD.SetBinError(i, histQCD.GetBinError(i)*factor)
                    if histQCD.GetBinContent(i) < 0:
                        print(f"Negative values in bin {i}({histQCD.GetBinContent(i)}) the QCD prediction - will set to 0")
                        histQCD.SetBinContent(i, 0)
                        # raise ValueError("Negative values in the QCD prediction - will set to 0")
                histQCD.Print("all")
                print(output_name_combinations[_categ_idx])

                new_file_path = output_path + "/" + os.path.basename(_histfile)

                if _categ_idx == 0:
                    new_file = ROOT.TFile.Open(new_file_path, "RECREATE")

                    def copy_directory_contents(original_dir, new_dir):
                        original_dir.cd()
                        for key in ROOT.gDirectory.GetListOfKeys():
                            obj = key.ReadObj()
                            if obj.InheritsFrom("TH1"):
                                new_dir.cd()
                                obj_clone = obj.Clone()
                                obj_clone.Write()
                            elif obj.InheritsFrom("TDirectoryFile"):
                                new_subdir = new_dir.mkdir(obj.GetName())
                                copy_directory_contents(obj, new_subdir)
                        new_dir.cd()

                    # Copy all contents from the original file
                    copy_directory_contents(file, new_file) 
                    # pass
                else:
                    new_file = ROOT.TFile.Open(new_file_path, "UPDATE")
                    
                # Set directory for the current category
                current_dir = new_file
                for name in output_name_combinations[_categ_idx].split("/"):
                    print("Get directory:", name)
                    next_dir = current_dir.GetDirectory(name)
                    if not next_dir:
                        # Directory does not exist, so create it
                        print(f"Creating directory: {name}")
                        next_dir = current_dir.mkdir(name, name)
                        if not next_dir:
                            raise Exception(f"Failed to create directory {name}")
                    next_dir.cd()
                    current_dir = next_dir

                # Set the histogram directory to the current category and write
                histQCD.SetDirectory(current_dir)
                histQCD.SetName("hist")
                histQCD.Write()

                file.Close()
                new_file.Close()
                
            elif config["QCD-prediction"]["mode"] == "factor":
                hist_qcd[_categ] = OverflowIntegralTHN(histQCD)
        
        if config["QCD-prediction"]["mode"] == "prediction":
            # copy histogram file /hists.json to the output directory
            shutil.copy(histfile_json, output_path + "/hists.json")
        elif config["QCD-prediction"]["mode"] == "factor":
            nom = hist_qcd[numerator]
            den = hist_qcd[denominator]
            print(_histname)
            print(nom, den, nom/den)
            
def plotBrMC(hist_path, config, xsec, cutflow, output_path, is_per_flavour=False):
    
    '''
    This code is used to plot the MC branching ratio reading 2D histogram
    and projecting it to the x-axis for bin 1 bin2 and bin 3 which coorespond to
    0-tight, 1--tight and 2-tight region
    '''
    print(hist_path)
    
    _histograms = {}
    if is_per_flavour:
        flavours = config["mixing_hists"]["flavours"]
        file = ROOT.TFile.Open(hist_path+"_0.root", 'read') 
        file2 = ROOT.TFile.Open(hist_path+"_1.root", 'read')
        # print(file.ls())
        # print(file2.ls())
    else:
        file = ROOT.TFile.Open(hist_path+".root", 'read') 
        flavours = [None]

    for flav in flavours:
        for _group_idx, _group_name in enumerate(config["Labels"].keys()):

            if _group_name in config["Signal_samples"]:
                raise ValueError("Signal samples are not allowed in this plotter")
            elif _group_name in config["Data"]:
                raise ValueError("Data samples are not allowed in this plotter")

            # has_group_entry = False
            # Accumulate the dataset for the particular data group as specified in config “Labels”.
            for _idx, _histogram_data in enumerate(config["Labels"][_group_name]):
                
                if is_per_flavour:
                    print("Reading hist:", f"{_histogram_data}/{flav}/hist")
                    hist = file.Get(f"{_histogram_data}/{flav}/hist")
                    hist2 = file2.Get(f"{_histogram_data}/{flav}/hist")
                else:
                    print("Reading hist:", _histogram_data)
                    hist = file.Get(_histogram_data+"/hist")
                
                if not hist:
                    print("Warning: Histogram not found! ", end='')
                    print("Histogram->", file, _histogram_data)
                    continue
                
                if is_per_flavour:
                    hist.Add(hist2)
                # hist = hist2

                if config["DY_stitching_applied"] and (
                        "DYJetsToLL_M-50" in _histogram_data or
                        "DY1JetsToLL_M-50" in _histogram_data or
                        "DY2JetsToLL_M-50" in _histogram_data or
                        "DY3JetsToLL_M-50" in _histogram_data or
                        "DY4JetsToLL_M-50" in _histogram_data ):
                    # print("Stitching:", _histogram_data)
                    hist.Scale(config["luminosity"])
                elif config["W_stitching_applied"] and (
                        ("WJetsToLNu" in _histogram_data and (not "TTWJets" in _histogram_data)) or
                        "W1JetsToLNu" in _histogram_data or
                        "W2JetsToLNu" in _histogram_data or
                        "W3JetsToLNu" in _histogram_data or
                        "W4JetsToLNu" in _histogram_data ):
                    # print("Stitching:", _histogram_data)
                    hist.Scale(config["luminosity"])
                else:
                    # N = cutflow[_histogram_data]["all"]["NanDrop"] #After Nan dropper
                    N = cutflow[_histogram_data]["all"]["BeforeCuts"]
                    hist.Scale( (xsec[_histogram_data] * config["luminosity"]) / N)

                if is_per_flavour:
                    _group_name = flav

                if not _group_name in _histograms.keys():
                    print("Append:", _histogram_data)
                    _histograms[_group_name] = hist
                else:
                    print("Add:", _histogram_data)
                    _histograms[_group_name].Add(hist)
                    
                if _group_name in _histograms.keys(): # if there is at least one histogram in input
                
                    color_setup = config["MC_bkgd"][_group_name]  
                    line_color = color_setup[1]
                    fill_color = color_setup[0]
                    _histograms[_group_name].SetMarkerSize(0)
                    _histograms[_group_name].SetLineWidth(4)
                    
                    _histograms[_group_name].SetLineColor(line_color)
                    _histograms[_group_name].SetFillColor(fill_color)
                    _histograms[_group_name].SetTitle(_group_name)
                    print("Set title:", _group_name)
            
            # _histograms[isSignal][-1].SetLineColor(line_color)
            # _histograms[isSignal][-1].SetFillColor(fill_color)
            # _histograms[isSignal][-1].SetLineWidth(2)
            # _histograms[isSignal][-1].SetMarkerSize(0)
            # _histograms[isSignal][-1].SetTitle(_group_name)
    
    
    # get maximum for the y-scale
    _histograms_values = list(_histograms.values())
    print(_histograms_values)
    y_max =_histograms_values[0].GetMaximum()
    for _h in _histograms_values:
        y_max = max(y_max,_h.GetMaximum())

    # sort histogram from min to max
    _histograms_background_entries = []
    _histograms_background_sorted = []
    for _h in _histograms_values:
        _histograms_background_entries.append(_h.Integral())
    _sorted_hist = np.argsort(_histograms_background_entries)
    for _idx in _sorted_hist:
        _histograms_background_sorted.append(_histograms_values[_idx])

    
    # read the binning if available:
    # if _histname in config["SetupBins"]:
    #     xrange_min = config["SetupBins"][_histname][0]
    #     xrange_max = config["SetupBins"][_histname][1]
    #     overflow =  bool(config["SetupBins"][_histname][3])
    # else:
    xrange_min =_histograms_values[0].GetXaxis().GetXmin()
    # xrange_max = _histograms["background"][0].GetXaxis().GetXmax()
    xrange_max = 53
    overflow =  True

    score_pass_finebin = config["mixing_hists"]["labels"]
    
    for bin_filled in [0, 1, 2]:
        # two loose region
        two_loose_hists = []
        for _h in _histograms_background_sorted:
            for bin_i, label in enumerate(score_pass_finebin):
                _h.GetXaxis().SetBinLabel(bin_i+1, ">"+str(label))
                _h.GetXaxis().SetTitle("")
            two_loose_hists.append(_h.ProjectionX(_h.GetTitle()+"_proj", 2+bin_filled, 2+bin_filled))
            print(two_loose_hists[-1].GetTitle(), two_loose_hists[-1].Integral())
        
        root_plot1D(
                l_hist = two_loose_hists,
                l_hist_overlay = two_loose_hists,
                outfile = output_path + "/" +  f"mixMC_plot_bin{bin_filled}.png",
                xrange = [xrange_min, xrange_max],
                yrange = (0.001,  1000*y_max),
                # yrange = (0.0,  1.5*y_max),
                logx = False, logy = True,
                include_overflow = overflow,
                xtitle = _histograms_values[0].GetXaxis().GetTitle(),
                ytitle = "events",
                xtitle_ratio = _histograms_values[0].GetXaxis().GetTitle(),
                ytitle_ratio = "%",
                centertitlex = True, centertitley = True,
                centerlabelx = False, centerlabely = False,
                gridx = False, gridy = False,
                ndivisionsx = None,
                stackdrawopt = "",
                # normilize = True,
                normilize_overlay = False,
                legendpos = "UR",
                legendtitle = f"",
                legendncol = 3,
                legendtextsize = 0.025,
                legendwidthscale = 1.9,
                legendheightscale = 0.26,
                lumiText = "2018 (13 TeV)",
                signal_to_background_ratio = True,
                ratio_mode = "percentage",
                logx_ratio = False, logy_ratio = False,
                yrange_ratio = (0, 1),
                draw_errors = True
            )

def plot2D(histfiles, histnames, config, xsec, cutflow, output_path):

    categories_list = list(itertools.product(*config["Categories"]))
    categories_list = [f"{cat1}_{cat2}" for cat1,cat2 in categories_list]

    for _ci, _categ in enumerate(categories_list):

        output = output_path + "/" + _categ

        for _histfile, _histname in zip(histfiles,histnames):

            # The plots are done for specific triggers specified in config.
            if not any([cut in str(_histfile) for cut in config["cuts"]]):
                continue

            file = ROOT.TFile.Open(str(_histfile), 'read')

            _histograms = {"background":[], "signal":[]}
            for _group_idx, _group_name in enumerate(config["Labels"].keys()):

                isSignal = "signal" if _group_name in config["Signal_samples"] else "background"
                
                # Accumulate the dataset for the particular data group as specified in config “Labels”.
                for _idx, _histogram_data in enumerate(config["Labels"][_group_name]):
                    
                    # Rescaling according to cross-section and luminosity
                    # print("Reading hist:", _histogram_data + "_" + _categ)
                    hist = file.Get(_histogram_data + "_" + _categ)
                    N = cutflow[_histogram_data]["all"]["Before cuts"] #After Nan dropper
                    hist.Scale( (xsec[_histogram_data] * config["luminosity"]) / N)

                    if _histname in config["SetupBins"]:
                        hist.Rebin2D(config["SetupBins"][_histname][4], config["SetupBins"][_histname][5])
                    
                    if _idx == 0:
                        _histograms[isSignal].append(hist)
                    else:
                        _histograms[isSignal][-1].Add(hist)

                if isSignal == "signal":
                    color_setup = config["Signal_samples"][_group_name]  
                    line_color = color_setup[1]
                    fill_color = color_setup[0]
                    _histograms[isSignal][-1].SetLineStyle(2)
                else:
                    color_setup = config["MC_bkgd"][_group_name]  
                    line_color = color_setup[1]
                    fill_color = color_setup[0]
                
                # _histograms[isSignal][-1].SetLineColor(line_color)
                # _histograms[isSignal][-1].SetFillColor(fill_color)
                # _histograms[isSignal][-1].SetLineWidth(2)
                # _histograms[isSignal][-1].SetMarkerSize(0)
                # _histograms[isSignal][-1].SetTitle(_group_name)
            
            # get maximum for the y-scale
            y_max = _histograms["background"][0].GetMaximum()
            for _h in _histograms["background"]:
                y_max = max(y_max,_h.GetMaximum())

            # sort histogram from min to max
            _histograms_background_entries = []
            _histograms_background_sorted = []
            for _h in _histograms["background"]:
                _histograms_background_entries.append(_h.Integral())
            _sorted_hist = np.argsort(_histograms_background_entries)
            for _idx in _sorted_hist:
                _histograms_background_sorted.append(_histograms["background"][_idx])

            # read the binning if available:
            if _histname in config["SetupBins"]:
                xrange_min = config["SetupBins"][_histname][0]
                xrange_max = config["SetupBins"][_histname][1]
                yrange_min = config["SetupBins"][_histname][2]
                yrange_max = config["SetupBins"][_histname][3]
                text_colz = config["SetupBins"][_histname][6]
                log_z = config["SetupBins"][_histname][7]
            else:
                xrange_min = _histograms["background"][0].GetXaxis().GetXmin()
                xrange_max = _histograms["background"][0].GetXaxis().GetXmax()
                yrange_min = _histograms["background"][0].GetYaxis().GetXmin()
                yrange_max = _histograms["background"][0].GetYaxis().GetXmax()
                text_colz = False
                log_z = True

            root_plot2D(
                l_hist = _histograms_background_sorted,
                l_hist_overlay = _histograms["signal"],
                outfile = output + "/" + os.path.splitext(os.path.basename(_histfile))[0] + ".png",
                xrange = [xrange_min, xrange_max],
                yrange = [yrange_min, yrange_max],
                # yrange = (1,  1.1*y_max),
                logx = False, logy = False, logz = log_z,
                # ytitle = _histograms["signal"][0].GetYaxis().GetTitle(),
                xtitle = _histograms["background"][0].GetXaxis().GetTitle(),
                ytitle = _histograms["background"][0].GetYaxis().GetTitle(),
                centertitlex = True, centertitley = True,
                centerlabelx = False, centerlabely = False,
                gridx = True, gridy = True,
                ndivisionsx = None,
                stackdrawopt = "",
                ratio_mode="SB",
                # normilize = True,
                normilize_overlay = False,
                legendpos = "UR",
                legendtitle = f"",
                legendncol = 3,
                legendtextsize = 0.03,
                legendwidthscale = 1.9,
                legendheightscale = 0.4,
                lumiText = "2018 (13 TeV)",
                signal_to_background_ratio = True,
                text_colz = text_colz,
            )
