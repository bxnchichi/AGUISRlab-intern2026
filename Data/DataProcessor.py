import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from Data.package.linePlotUtils import *
from Data.package.scatterPlotUtils import *

# folder = Path("Data/FinalDataCollection")
# while True:
#     if not folder.exists():
#         print(f"Folder not found: {folder.resolve()}")
#         break

#     for filepath in sorted(folder.glob("*.csv")):
#         print(f"Processing {filepath.name}")
#         try:
#             AddSumForceColumn(filepath)
#         except Exception as e:
#             print(f"Failed: {filepath.name}")
#             print(e)
#         print(" ")
#     break


filepath = Path("Data/FinalDataCollection/BenWood1.csv")
print(f"Processing {filepath.name}")
try:
    df = pd.read_csv(filepath)
    print(df.head())
    processingColumnNP, _, rising_edges, edge_length = detect_rising_edges(df, "SumForce", column="SumForce")
    print(f"Rising edges detected at indices: {rising_edges}")
    print(f"Minimum edge lengths: {edge_length}")

    # print(df.iloc[rising_edges[3]:rising_edges[3]+int(edge_length)])  # Display the first few rows of the processed DataFrame
    cutDF = []
    for i in range(len(rising_edges)):
        start_index = rising_edges[i]
        end_index = start_index + int(edge_length) - 20 # delete the last 30 points to avoid the end of the signal
        df_reindexed = df.iloc[start_index:end_index].reset_index(drop=True)
        # print(df_reindexed.head())  # Display the first few rows of the cut DataFrame
        cutDF.append(df_reindexed)
    print(f"Cut DataFrames created: {len(cutDF)} segments")

    for i, segment in enumerate(cutDF):
        plot2SignalAllCSV(segment, "SumForce", "pos_z[mm]")
except Exception as e:
    print(f"Failed: {filepath.name}")
    print(e)