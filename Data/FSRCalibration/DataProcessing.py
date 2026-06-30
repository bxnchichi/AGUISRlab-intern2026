import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from Data.package.linePlotUtils import *
from Data.package.scatterPlotUtils import *

folder = Path("Data/FSRCalibration/AverageVoltageInRange1N")
output_folder = "Data/FSRCalibration/F-VscatterAvg"
# ScatterPlotFolder('save', folder, "AvgForce", "Average Voltage (V)", "ScatterRegresses")
# AddRColumnCSV("Data/FSRCalibration/TakenData/Sensor1index.csv")

# for filepath in sorted(folder.glob("*.csv")):
#     print(f"Processing {filepath.name}")
#     try:
#         AddColumnCalculatedForce(filepath)
#     except Exception as e:
#         print(f"Failed: {filepath.name}")

# print((R0)*(Vin/3500-1))

# Satuation Model

# ScatterPlotWith  XY("save", Path("Data/FSRCalibration/TryStaticData/TryStaticSensor1.csv"), "force_magnitude", "CalF1", outputFold="Data/FSRCalibration/CompareCal-MeasF")
# ScatterPlotWithXY("save", Path("Data/FSRCalibration/TryStaticData/TryStaticSensor2.csv"), "force_magnitude", "CalF2", outputFold="Data/FSRCalibration/CompareCal-MeasF")
# senNo = 6
# filepath = Path(f"Data/FSRCalibration/AverageVoltageInRange1N/{senNo}.csv")
# outputFolder = Path("Data/FSRCalibration/F-Vregress2")
# col1 = "Avg_force" 
# VoltList = ['SidePalm', 'ThumpPalm', 'UpperPalm', 'Middle', 'Index', 'Thump']
# col2 = f"V_{VoltList[senNo-1]}[mV]"
# ScatterPlotRegressions('save', filepath, col1, col2, outputFolder)

for i in range(6):
    try:
        print(f"Processing sensor {i+1} file")
        senNo = i + 1
        filepath = Path(f"Data/FSRCalibration/TryStaticData2/TryStaticSensor{senNo}.csv")
        # filepath = Path(f"Data/FSRCalibration/TestInfo/{senNo}testInfo.csv")
        
        # # Add Calculated Force Column
        # AddColumnCalculatedForce(filepath)
        
        outputFolder = Path("Data/FSRCalibration/F-Vregress2")
        # outputFolder.mkdir(parents=True, exist_ok=True)
        # outputCSV = Path(f"Data/FSRCalibration/AverageVoltageInRange1N/{senNo}.csv")
        col1 = "force_magnitude" 
        VoltList = ['SidePalm', 'ThumpPalm', 'UpperPalm', 'Middle', 'Index', 'Thump']
        # col2 = f"CalF{senNo}"
        col2 = f"V_{VoltList[i]}[mV]"
        ScatterPlotRegressions('save', filepath, col1, col2, outputFolder)
        # average_voltage_per_newton(filepath, col1, col2, output_csv=outputCSV)
        # ScatterPlotWithXY("save", filepath, col1, col2, outputFold=outputFolder)
    except Exception as e:
        print(f"Failed: {filepath.name}")
        print(e)
    print(" ")


# senNo = 5
# filepath = Path(f"Data/FSRCalibration/TryStaticData2/TryStaticSensor{senNo}.csv")
# AddColumnCalculatedForce(filepath)
# filepath = Path(f"Data/FSRCalibration/TryStaticData2/TryStaticSensor{senNo}.csv")
# outputFolder = Path("Data/FSRCalibration/CompareCal-MeasF2")
# col1 = "force_magnitude" 
# VoltList = ['SidePalm', 'ThumpPalm', 'UpperPalm', 'Middle', 'Index', 'Thump']
# col2 = f"CalF{senNo}"
# ScatterPlotWithXY("save", filepath, col1, col2, outputFold=outputFolder)

# AddColumnCalculatedForce("Data\FSRCalibration\TryStaticData\TryStaticSensor2.csv")

# for i in range(6):
#     print(i)


# for i in range(6):
#     csv = Path(f'Data/FSRCalibration/AverageVoltageInRange1N/{i+1}.csv')
#     addAverageForceColumn(csv, 'Force Min (N)', 'Force Max (N)')

























# Compare graph
# x = np.linspace(0, 40, 1000)
# y = -1.0000787584966178 + 3902.728860434641 * (1 - np.exp(-0.17583199786234122 * x))
# plt.plot(x, y, 'r', label="Index")
# y = -111.37632787257252 + 3907.3849637392896 * (1 - np.exp(-0.18717358345831095 * x))
# plt.plot(x, y, 'g', label="Middle")
# y = -122.23626935356464 + 4146.930071972312 * (1 - np.exp(-0.11265860241068042 * x))
# plt.plot(x, y, 'y', label="Thump")
# plt.xlabel("force_magnitude[N]")
# plt.ylabel("Measured Volt [mV]")
# plt.legend()
# visualizePlot('save', output_folder="Data/FSRCalibration", name="CompareSensor1SatReg")

# x = np.linspace(0, 40, 1000)
# y = -86.15219041845631 + 3986.422564043707 * (1 - np.exp(-0.2042827527074749 * x))
# plt.plot(x, y, 'r', label="Index")
# y = -276.53817968557235 + 4055.3662908517435 * (1 - np.exp(-0.168469254733811 * x))
# plt.plot(x, y, 'g', label="Middle")
# y = -86.36636572741574 + 3810.4338052947433 * (1 - np.exp(-0.11818608319072212 * x))
# plt.plot(x, y, 'y', label="Thump")
# plt.xlabel("force_magnitude[N]")
# plt.ylabel("Measured Volt [mV]")
# plt.legend()
# visualizePlot('save', output_folder="Data/FSRCalibration", name="CompareSensor2SatReg")