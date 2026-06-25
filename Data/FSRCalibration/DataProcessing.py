import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from Data.package.linePlotUtils import *
from Data.package.scatterPlotUtils import *

folder = Path("Data/FSRCalibration/TryStaticData")
# output_folder = "Data/FSRCalibration/scatterPlot"
# ScatterPlotFolder('save', folder, "force_magnitude", "CalF2", "ScatterXY")
# AddRColumnCSV("Data/FSRCalibration/TakenData/Sensor1index.csv")

# for filepath in sorted(folder.glob("*.csv")):
#     print(f"Processing {filepath.name}")
#     try:
#         AddColumnCalculatedForce(filepath)
#     except Exception as e:
#         print(f"Failed: {filepath.name}")

# print((R0)*(Vin/3500-1))

# Satuation Model

ScatterPlotWithXY("save", Path("Data/FSRCalibration/TryStaticData/TryStaticSensor1.csv"), "force_magnitude", "CalF1", outputFold="Data/FSRCalibration/CompareCal-MeasF")
ScatterPlotWithXY("save", Path("Data/FSRCalibration/TryStaticData/TryStaticSensor2.csv"), "force_magnitude", "CalF2", outputFold="Data/FSRCalibration/CompareCal-MeasF")



# AddColumnCalculatedForce("Data\FSRCalibration\TryStaticData\TryStaticSensor2.csv")






























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