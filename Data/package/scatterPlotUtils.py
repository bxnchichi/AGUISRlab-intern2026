import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression, RANSACRegressor
from scipy.optimize import curve_fit
from .linePlotUtils import *

R0 = 10000 #Ohm
Vin = 5000 #mVolt

def csvToPanda(filepath):
    return pd.read_csv(filepath)

def VtoOhm(csv_col):
    return csv_col.apply(lambda x: (R0)*(Vin/x-1))

def AddRColumnCSV(csv):
    df = pd.read_csv(csv)
    df["Ohm_FSR1"] = VtoOhm(df["Volt_FSR1"])
    df["Ohm_FSR2"] = VtoOhm(df["Volt_FSR2"])
    df.to_csv(csv, index = False)
    print(df.columns)

def logRegressCoeffient(df, col1, col2):

    x = df[col1].values
    y = df[col2].values

    # Fit y = a*ln(x) + b
    a, b = np.polyfit(np.log(x), y, 1)
    print(f"numpy fit log Funtion: y = {a:.4f}ln(x) + {b:.4f}")

    return a, b

def logDLregressCoeffient(df, col1, col2):
    x = df[col1].values
    y = df[col2].values


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
    print(f"Satuation Model Curve fitfunction: y = {c} + {a} * (1 - e^(-{b} * x))")
    return params

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
    df = csvToPanda(csv)
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
    a, b = logRegressCoeffient(df, col1, col2)
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 500)
    y_fit = a * np.log(x_fit) + b
    # Plot
    df = csvToPanda(csv)
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
    df = csvToPanda(csv)
    plt.scatter(df[col1], df[col2], s=10)
    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)
    plt.plot(x_fit, y_fit, 'r', label="Satuation Model")
    plt.legend()
    plt.ylim(bottom=0)
    visualizePlot(command, output_folder=outputFold, filepath=csv)

def ScatterPlotRegressions(command, csv, col1, col2, outputFold = None):
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

    # Plot
    df = csvToPanda(csv)
    plt.scatter(df[col1], df[col2], s=10, alpha = 0.2)
    plt.title(csv.stem)
    plt.xlabel(col1)
    plt.ylabel(col2)

    # log numpy fit
    a, b = logRegressCoeffient(df, col1, col2)
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 500)
    y_fit = a * np.log(x_fit) + b
    plt.plot(x_fit, y_fit, 'r', label="numpy Log")

    # log sklearn fit
    a, b = logDLregressCoeffient(df, col1, col2)
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 500)
    y_fit = a * np.log(x_fit) + b
    plt.plot(x_fit, y_fit, 'g', label="sklearn Log")

    # Satuation Model
    a, b, c = saturationParam(df[col1], df[col2])
    # print(f"function: y = {c} + {a} * (1 - e^(-{b} * x))")
    x_fit = np.linspace(min(df[col1]), max(df[col1]), 100)
    y_fit = c + a * (1 - np.exp(-b * x_fit))
    plt.plot(x_fit, y_fit, 'y', label="Expo Curve")

    plt.legend()
    plt.ylim(bottom=0)
    visualizePlot(command, output_folder=outputFold, filepath=csv)

def ScatterPlotFolder(command, folder, col1, col2, graphcat):
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
                    ScatterPlotRegressions(command, filepath, col1, col2, outputFolder)
        except Exception as e:
            print(f"Failed: {filepath.name}")
        print(" ")







