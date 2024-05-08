# -*- coding: utf-8 -*-
"""
Created on Sun Nov 21 12:36:55 2021.

@author: j2cle
"""

# %% import section
import numpy as np
import pandas as pd
import sims_fit_cls as sfc
import utilities as ut
# import General_functions as gf
# import Units_Primary3 as up
import Profile_Importer as pim
import warnings
from datetime import datetime as dt

warnings.simplefilter("ignore", np.RankWarning)
warnings.filterwarnings("ignore")


mypath = ut.root_path("work\\Data\\Analysis\\SIMS")
figpath = (
    mypath
    + "Fig_fits\\"
    + dt.now().strftime("%Y%m%d")
)
filepath = (
    mypath
    + "Files\\"
    + dt.now().strftime("%Y%m%d")
)
picklepath = (
    mypath
    + "Pickles\\"
    + dt.now().strftime("%Y%m%d")
)


# df_log = pd.read_excel(f'{mypath}/Sample Log for fitting.xlsx',
#                        index_col=0, skiprows=1).dropna(axis=0, how='all')

# if 0:
#     df_log.drop(['R-60 SF ROI'], inplace=True)


# %% Create the necesary objects
obj = {}
x_lim = 4
r_lim = 2

imp = pim.BulkImport(["Na_2+", "Na+"])
imp.to_data(set_sigma=1, num_bins=5) # devs=np.nan,
imp.to_obj(set_sigma=1,num_bins=5, save=True)#devs=np.nan,
for key, val in imp.objs.items():
    val.plots(prof_plt=0, map_plot=0, plt_type="raw_conc")
#%%
# obj = {}
jar = ut.PickleJar("Fit_and_Error")
redo = False
for key, val in imp.datas.items():
    if (
        redo
        or not ut.PickleJar("Fit_and_Error")
        .database["name"]
        .isin([f"{key}_Plot"])
        .any()
    ):
        if "conc" in key:
            params = [x for x in imp.params.keys() if "Na+" in x or "Na_2+" in x][0]
        else:
            params = key
        jar.database = (f"{key}_SIMS", pim.DataProfile(imp.params[params], val))

        # for sample in list(imp.datas.keys()):  # 0-4, tset, 0=90, 4-6 eset, 6-10 local, 10-14 init EVA, 15-29 MIMS, 29 man1, 30 80 old [31]:#
        # sample = df_log.index[x].split(' ')[0]
        # obj[sample] = {}
        prime = sfc.MatrixOps(
            jar.get_dill(f"{key}_SIMS"),
            "FitProfile",
            # xrange=['depth', 0, 75, 'index'],
            # yrange=['depth', 0, 75, 'index'],
            # size=75, min_range=1,
            xrange=["depth", 0, ut.Length(x_lim, "um").cm, "lin"],
            yrange=["depth", 0, ut.Length(x_lim, "um").cm, "lin"],
            size=75,
            min_range=r_lim,
            diff_pred=pd.Series((-18, -16, -14), index=("low", "mid", "high")),
            log_form=False,
        )

        prime.error_calc(
            get_best=False, log_form=True, instr="none", use_sample_w=True,
        )

        jar.database = (f"{key}_Prime", prime)

        jar.database = (f"{key}_Plot", sfc.Plotter(prime))
# del x
# del sample

# %% Automated Run
auto_show = False
for check in imp.datas.keys():
    data_dict = {}
    obj = jar.get_dill(f"{check}_Plot")
    try:
        if len(check.split("-")) > 2:
            label = "-".join(check.split("-")[1:])
        else:
            label = check.split("-")[1]
        res_init = obj.family_df
        res_init_obj = obj
        data_dict["res_init"] = res_init

        obj.map_plot(
            name=str(label + ": Error Evaluation"),  # log10(Data) & Weighted
            info=["start_loc", "depth_range", "error"],
            zscale="linlog",
            xlimit=[0, x_lim],
            ylimit=[0, x_lim],
            zlimit=[5e-4, 1],
            levels=10,
            xname="Start location (\u03BCm)",  # u=\u03BC
            yname="Range (\u03BCm)",
            zname="Error",
            ztick={
                "base": 10,
                "labelOnlyBase": False,
                "minor_thresholds": (2, 2e-5),
                "linthresh": 100,
            },
            corner_mask=True,
            save=figpath,
            show=auto_show,
        )

        topo_results, res_lists, mins_summary = obj.pks_generate(
            stop_max=min(5, x_lim),  # stop location max. init 2.5
            start_max=3,  # start location max (um). init 2
            start_min=2,  # start index min. init 2
            range_min=5,
            overlap=True,
        )
        data_dict = {**data_dict, **res_lists}
        data_dict["mins_summary"] = mins_summary

        res_auto = obj.auto_focus()
        data_dict["res_auto"] = res_auto

        peak = 0
        focus_stats, focii = obj.pks_analyze(
            peak=peak,
            min_start=2,  # (4) lower bound of starts
            max_start=20,  # (12) upper bound of starts
            min_range=4,  # (8) minimum range
            peak_range=20,  # (20) the range to evaluate the system at (auto = best range at the peak)
            max_range=60,  # 100 maximum range to allow
            # pair_set='all',
            # old_range=True,
        )
        res_man = obj.focus_report(peak)
        data_dict["res_man"] = res_man

        plot_df = res_man.copy()
        pairs = [peak]  # use list of lists or list of ints
        if len(np.shape(pairs)) > 1 and isinstance(pairs[0][0], (float, np.float)):
            pair_df = pd.DataFrame(pairs, columns=["diff", "conc"])
        elif len(pairs) >= 1 and isinstance(pairs[0], (int, np.integer)):
            pair_df = pd.DataFrame(
                plot_df.loc[pairs, ["diff", "conc"]].reset_index(),
                columns=["diff", "conc"],
            )
        else:
            pair_df = pd.DataFrame(plot_df[["diff", "conc"]], columns=["diff", "conc"])
        prof_data = pd.DataFrame(columns=["depth", "data", "vals"])
        for n in range(len(pair_df)):
            prof = sfc.PredProfile(
                jar.get_dill(f"{check}_SIMS"),
                pair_df.loc[n, "diff"],
                pair_df.loc[n, "conc"],
            ).data

            if len(pair_df) == 1:
                prof["data"] = "Fit"
            else:
                prof["data"] = "Fit " + str(n + 1)
            if len(prof_data) == 0:
                prof_data = pd.concat(
                    [
                        prof_data,
                        prof[["depth", "data", "SIMS"]].rename(
                            columns={"SIMS": "vals"}
                        ),
                    ],
                    ignore_index=True,
                )
                prof_data["data"] = "SIMS"
            prof_data = pd.concat(
                [
                    prof_data,
                    prof[["depth", "data", "pred"]].rename(columns={"pred": "vals"}),
                ],
                ignore_index=True,
            )
        prof_data["depth"] = ut.Length(prof_data["depth"], "cm").um

        data_dict["prof_data"] = prof_data

        plot_obj = sfc.Plotter()
        plot_obj.prof_plot(
            name=f"{label}: Valley {peak} fit",
            data_in=prof_data,
            x="depth",
            y="vals",
            xscale="linear",
            yscale="log",
            xlimit=[0, x_lim],
            ylimit=[1e15, 1e20],
            xname="Depth",
            yname="Concentration",
            save=figpath,
            show=auto_show,
            # hline=0,
            hue="data",
            legend=True,
            palette="kindlmann",
            # markers=False,
            edgecolor="none",
            # hue_norm=(0, len(inflect)),
        )

        d_vs_c_data = res_lists["by_range"][["start_loc", "diff", "conc"]][
            res_lists["by_range"]["diff"] < 1e-12
        ]

        d_vs_c_data["diff_norm"] = d_vs_c_data["diff"] / res_man.loc[peak, "diff"]
        d_vs_c_data["conc_norm"] = d_vs_c_data["conc"] / res_man.loc[peak, "conc"]

        data_dict["d_vs_c_data"] = d_vs_c_data

        jar.to_dill(f"{check}_Plot", obj)

        data_dict = {**data_dict, **obj.focus_dict, **obj.focii_dict}
        ut.save(data_dict, filepath, check + "_res init")
    except Exception:
        pass
