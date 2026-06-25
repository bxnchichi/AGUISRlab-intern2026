import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression, RANSACRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy.optimize import curve_fit
from .linePlotUtils import *


R0 = 10000 #Ohm
Vin = 5000 #mVolt
Vmax = 4100 #mVolt
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#    █████████   █████████  █████   █████    ███████████                                                      
#   ███░░░░░███ ███░░░░░███░░███   ░░███    ░░███░░░░░███                                                     
#  ███     ░░░ ░███    ░░░  ░███    ░███     ░███    ░███ ████████   ██████   ██████   ██████   █████   █████ 
# ░███         ░░█████████  ░███    ░███     ░██████████ ░░███░░███ ███░░███ ███░░███ ███░░███ ███░░   ███░░  
# ░███          ░░░░░░░░███ ░░███   ███      ░███░░░░░░   ░███ ░░░ ░███ ░███░███ ░░░ ░███████ ░░█████ ░░█████ 
# ░░███     ███ ███    ░███  ░░░█████░       ░███         ░███     ░███ ░███░███  ███░███░░░   ░░░░███ ░░░░███
#  ░░█████████ ░░█████████     ░░███         █████        █████    ░░██████ ░░██████ ░░██████  ██████  ██████ 
#   ░░░░░░░░░   ░░░░░░░░░       ░░░         ░░░░░        ░░░░░      ░░░░░░   ░░░░░░   ░░░░░░  ░░░░░░  ░░░░░░  
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def csvToPanda(filepath):
    return pd.read_csv(filepath)

def AddColumnCSVvToOhm(csv):
    df = pd.read_csv(csv)
    df["Ohm_FSR1"] = VtoOhm(df["Volt_FSR1"])
    df["Ohm_FSR2"] = VtoOhm(df["Volt_FSR2"])
    df.to_csv(csv, index = False)
    print(df.columns)

def AddColumnCSVthershold(csv):
    df = pd.read_csv(csv)
    df["V1thers"] = (df["Volt_FSR1"]>250)*df["Volt_FSR1"]
    df["V2thers"] = (df["Volt_FSR2"]>500)*df["Volt_FSR2"]
    df.to_csv(csv, index = False)
    print(df.columns)

def AddColumnCalculatedForce(csv):
    df = pd.read_csv(csv)
    a = - 1.2677811420919507
    b = - 0.14258940729211392
    Vmax = 4100
    df["CalF1"] = 10**((1/a)*np.log10(Vmax/df["Volt_FSR1"]-1) - (b/a))

    a = -1.4307043411643339
    b = 0.20129777551613423
    Vmax = 3700
    df["CalF2"] = 10**((1/a)*np.log10(Vmax/df["Volt_FSR2"]-1) - (b/a))
    print(csv)
    df.to_csv(csv, index = False)
    print(df.columns)



#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#    █████████            ████                      ████             █████            
#   ███░░░░░███          ░░███                     ░░███            ░░███             
#  ███     ░░░   ██████   ░███   ██████  █████ ████ ░███   ██████   ███████    ██████ 
# ░███          ░░░░░███  ░███  ███░░███░░███ ░███  ░███  ░░░░░███ ░░░███░    ███░░███
# ░███           ███████  ░███ ░███ ░░░  ░███ ░███  ░███   ███████   ░███    ░███████ 
# ░░███     ███ ███░░███  ░███ ░███  ███ ░███ ░███  ░███  ███░░███   ░███ ███░███░░░  
#  ░░█████████ ░░████████ █████░░██████  ░░████████ █████░░████████  ░░█████ ░░██████ 
#   ░░░░░░░░░   ░░░░░░░░ ░░░░░  ░░░░░░    ░░░░░░░░ ░░░░░  ░░░░░░░░    ░░░░░   ░░░░░░  
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def VtoOhm(csv_col):
    return csv_col.apply(lambda x: (R0)*(Vin/x-1))

def logRegressCoeffient(x,y):

    # Fit y = a*ln(x) + b
    a, b = np.polyfit(np.log(x), y, 1)
    print(f"numpy fit log Funtion: y = {a:.4f}ln(x) + {b:.4f}")

    return a, b

def logDLregressCoeffient(x, y):
    # Deep learning model
    X = np.log(x).reshape(-1, 1)

    ransac = RANSACRegressor(
        estimator=LinearRegression(),
        random_state=0
    )

    ransac.fit(X, y)
    a = ransac.estimator_.coef_[0]
    b = ransac.estimator_.intercept_
    print(f"sklearn fit log Funtion: y = {a:.4f}ln(x) + {b:.4f}")
    return a, b

# Saturation model
def saturation_offset(x, A, B, C):
    return C + A * (1 - np.exp(-B * x))

def saturationParam(x, y):
    params, _ = curve_fit(
        saturation_offset,
        x,
        y,
        p0=[4000, 0.2, 0],
        bounds=(
            [0, 0, -np.inf],      # lower bounds
            [10000, 10, np.inf]   # upper bounds
        ),
        maxfev=10000
    )
    a, b, c = params
    print(f"Satuation Model Curve fit function: y = {c} + {a} * (1 - e^(-{b} * x))")
    return params

def log10Saturation(x, a, b):
    return Vmax/(10**(a*np.log10(x) + b) + 1)

def log10RegressCoeffient(x, y):
    params, _ = curve_fit(
        log10Saturation,
        x,
        y
    )
    a, b = params
    print(f"Satuation log 10 Model Curve fit function: log(({Vmax}-y)/y) = {a}log(x) + {b}")
    return params



# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  ███████████  ████            █████   
# ░░███░░░░░███░░███           ░░███    
#  ░███    ░███ ░███   ██████  ███████  
#  ░██████████  ░███  ███░░███░░░███░   
#  ░███░░░░░░   ░███ ░███ ░███  ░███    
#  ░███         ░███ ░███ ░███  ░███ ███
#  █████        █████░░██████   ░░█████ 
# ░░░░░        ░░░░░  ░░░░░░     ░░░░░  
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def ScatterPlot(command, csv, col1, col2, outputFold = None):
    # check if the columns exists
    df = csvToPanda(csv)
    # print("Start Plot")
    if col1 not in df.columns:
        print(f"{col1} not exist")
        print("Existing column name: ", df.columns)
        return
    if col2 not in df.columns:
        print(f"{col2} not exist")
        print("Existing column name: ", df.columns)
        return
    print(f"{col1} and {col2} exist")

    # Plot
    plt.scatter(df[col1], df[col2], s=10)
    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)
    visualizePlot(command, output_folder=outputFold, filepath=csv)

def ScatterPlotWithLog(command, csv, col1, col2, outputFold = None):
    # check if the columns exists
    df = csvToPanda(csv)
    # print("Start Plot")
    if col1 not in df.columns:
        print(f"{col1} not exist")
        print("Existing column name: ", df.columns)
        return
    if col2 not in df.columns:
        print(f"{col2} not exist")
        print("Existing column name: ", df.columns)
        return
    # print(f"{col1} and {col2} exist")


    # log fit try
    a, b = logRegressCoeffient(df[col1], df[col2])
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 500)
    y_fit = a * np.log(x_fit) + b
    # Plot
    plt.scatter(df[col1], df[col2], s=10)
    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)
    plt.plot(x_fit, y_fit, 'r', label="Log Regression")
    plt.legend()
    plt.ylim(bottom=0)
    visualizePlot(command, output_folder=outputFold, filepath=csv)

def ScatterPlotSatuationModel(command, csv, col1, col2, outputFold = None):
    # check if the columns exists
    df = csvToPanda(csv)
    # print("Start Plot")
    if col1 not in df.columns:
        print(f"{col1} not exist")
        print("Existing column name: ", df.columns)
        return
    if col2 not in df.columns:
        print(f"{col2} not exist")
        print("Existing column name: ", df.columns)
        return
    # print(f"{col1} and {col2} exist")

    a, b, c = saturationParam(df[col1], df[col2])
    # print(f"function: y = {c} + {a} * (1 - e^(-{b} * x))")
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 100)
    y_fit = c + a * (1 - np.exp(-b * x_fit))
    # Plot
    plt.scatter(df[col1], df[col2], s=10)
    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)
    plt.plot(x_fit, y_fit, 'r', label="Satuation Model")
    plt.legend()
    plt.ylim(bottom=0)
    visualizePlot(command, output_folder=outputFold, filepath=csv)

def ScatterPlotRegressions(command, csv, col1, col2, outputFold = None, thresholdX = None, thresholdY =None):
        # check if the columns exists
    df = csvToPanda(csv)
    # print("Start Plot")
    if col1 not in df.columns:
        print(f"{col1} not exist")
        print("Existing column name: ", df.columns)
        return
    if col2 not in df.columns:
        print(f"{col2} not exist")
        print("Existing column name: ", df.columns)
        return
    # print(f"{col1} and {col2} exist")
    if thresholdX is not None:
        df = df[df[col1] >= thresholdX]
    
    if thresholdY is not None:
        df = df[df[col2] >= thresholdY]
        print(f"thresholdY={thresholdY}")
        print(df[col2].dtype)
    # Plot
    
    plt.scatter(df[col1], df[col2], s=10, alpha = 0.2, c="blue")
    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)

    # log numpy fit
    a, b = logRegressCoeffient(df[col1], df[col2])
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 500)
    y_fit = a * np.log(x_fit) + b
    plt.plot(x_fit, y_fit, 'r', label="numpy Log")

    # log sklearn fit
    a, b = logDLregressCoeffient(df[col1].values, df[col2].values)
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 500)
    y_fit = a * np.log(x_fit) + b
    plt.plot(x_fit, y_fit, 'g', label="sklearn Log")

    # Satuation Model
    a, b, c = saturationParam(df[col1], df[col2])
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 100)
    y_fit = c + a * (1 - np.exp(-b * x_fit))
    plt.plot(x_fit, y_fit, 'y', label="Expo Curve")

    # Log 10 from article Model
    a, b =log10RegressCoeffient(df[col1], df[col2])
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 100)
    y_fit = Vmax/(10**(a*np.log10(x_fit) + b) + 1)
    plt.plot(x_fit, y_fit, 'm', label=f"log10(Lim = {Vmax})")

    plt.legend()
    plt.ylim(bottom=0)
    visualizePlot(command, output_folder=outputFold, filepath=csv)

# def ScatterPlotWithXY(command, csv, col1, col2, outputFold = None):
#     df = csvToPanda(csv)
#     plt.scatter(df[col1], df[col2], s=10, alpha = 0.2, c="blue")
#     plt.title(csv.stem)
#     plt.xlabel(col1)
#     plt.ylabel(col2)

#     # plt x=y
#     x_fit = np.linspace(min(df[col1]), max(df[col1]), 100)
#     y_fit = x_fit
#     plt.plot(x_fit, y_fit, 'm', label="x=y")

#     plt.legend()
#     plt.ylim(0, 30)
#     visualizePlot(command, output_folder=outputFold, filepath=csv)

def ScatterPlotWithXY(command, csv, col1, col2, outputFold=None):

    df = csvToPanda(csv)

    actual = df[col1].values
    predicted = df[col2].values

    plt.figure(figsize=(8, 6))

    plt.scatter(
        actual,
        predicted,
        s=10,
        alpha=0.2,
        c="blue"
    )

    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)

    # x = y line
    min_val = min(actual.min(), predicted.min())
    max_val = max(actual.max(), predicted.max())

    x_fit = np.linspace(min_val, max_val, 100)

    plt.plot(
        x_fit,
        x_fit,
        'm',
        linewidth=2,
        label="x = y"
    )

    # Metrics
    mae = mean_absolute_error(actual, predicted)

    rmse = np.sqrt(
        mean_squared_error(actual, predicted)
    )

    r2 = r2_score(actual, predicted)

    # Avoid divide-by-zero in MAPE
    mask = actual != 0

    mape = np.mean(
        np.abs(
            (actual[mask] - predicted[mask])
            / actual[mask]
        )
    ) * 100

    metrics_text = (
        f"MAE  = {mae:.3f}\n"
        f"RMSE = {rmse:.3f}\n"
        f"MAPE = {mape:.2f}%\n"
        f"R²   = {r2:.4f}"
    )

    plt.text(
        0.05,
        0.95,
        metrics_text,
        transform=plt.gca().transAxes,
        verticalalignment='top',
        bbox=dict(
            boxstyle='round',
            facecolor='white',
            alpha=0.8
        )
    )

    plt.legend()

    visualizePlot(
        command,
        output_folder=outputFold,
        filepath=csv
    )

def ScatterPlotFolder(command, folder, col1, col2, graphcat, threX = None, threY = None):
    outputFolder = f"Data/FSRCalibration/{col1}-{col2}{graphcat}"
    if not folder.exists():
        print(f"Folder not found: {folder.resolve()}")
        return
    
    for filepath in sorted(folder.glob("*.csv")):
        print(f"Processing {filepath.name}")
        try:
            match graphcat:
                case "Scatter":
                    ScatterPlot(command, filepath, col1, col2, outputFolder)
                case "ScatterLog":
                    ScatterPlotWithLog(command, filepath, col1, col2, outputFolder)
                case "ScatterSat":
                    ScatterPlotSatuationModel(command, filepath, col1, col2, outputFolder)
                case "ScatterRegresses":
                    outputFolder = f"Data/FSRCalibration/{col1}-{col2}{graphcat}_thres({threX}, {threY})"
                    ScatterPlotRegressions(command, filepath, col1, col2, outputFolder, thresholdY=threY, thresholdX=threX)
                case "ScatterXY":
                    ScatterPlotWithXY(command, filepath, col1, col2, outputFolder)
        except Exception as e:
            print(f"Failed: {filepath.name}")
        print(" ")







