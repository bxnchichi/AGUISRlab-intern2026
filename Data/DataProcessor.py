import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from Data.package.linePlotUtils import *
from Data.package.scatterPlotUtils import *


folder = Path("Data/FinalDataCollection/Smoothen")
while True:
    if not folder.exists():
        print(f"Folder not found: {folder.resolve()}")
        break

    for filepath in sorted(folder.glob("*.csv")):
        print(f"Processing {filepath.name}")
        try:
            AddSumForceColumn(filepath)
        except Exception as e:
            print(f"Failed: {filepath.name}")
            print(e)
        print(" ")
    break


# All_Data = {}

# filepath = Path("Data/FinalDataCollection/Smoothen/HannahFoam2.csv")
# print(f"Processing {filepath.name}")
# try:
#     df = pd.read_csv(filepath)
#     # print(df.head())

#     # For HeatMap (contact area usage)
#     processingColumnNP, _, rising_edges, edge_length1 = detect_rising_edges(df, "SumForce", column="SumForce")
#     print(f"Rising edges detected at indices: {rising_edges}")
#     print(f"Minimum edge lengths: {edge_length1}")

#     # print(df.iloc[rising_edges[3]:rising_edges[3]+int(edge_length)])  # Display the first few rows of the processed DataFrame
#     cutDFforHeatMap = []
#     for i, value in enumerate(rising_edges):
#         start_index = value
#         end_index = start_index + edge_length1[i] # delete the last 20 points to avoid the end of the signal
#         df_reindexed = df.iloc[start_index:end_index].reset_index(drop=True)
#         # print(df_reindexed.head())  # Display the first few rows of the cut DataFrame
#         cutDFforHeatMap.append(df_reindexed)
#     print(f"Cut DataFrames created: {len(cutDFforHeatMap)} segments")

    

#     # For detecting force application time
#     touching_points, edge_length2 = detect_touching_point(df, "pos_z[mm]")
#     print(f"Touching points detected at indices: {touching_points}")
#     print(f"Minimum edge lengths: {edge_length2}")

#     cutDFforForceTime = []
#     for i, value in enumerate(touching_points):
#         start_index = value
#         end_index = start_index + edge_length2[i]# delete the last 20 points to avoid the end of the signal
#         df_reindexed = df.iloc[start_index:end_index].reset_index(drop=True)
#         # print(df_reindexed.head())  # Display the first few rows of the cut DataFrame
#         cutDFforForceTime.append(df_reindexed)
#     print(f"Cut DataFrames created: {len(cutDFforForceTime)} segments")

#     # for i, segment in enumerate(cutDFforForceTime):
#     #     plot2SignalAllCSV(segment, "SumForce", "pos_z[mm]")

#     All_Data[filepath.name] = {
#         # Convert every DataFrame inside the 'ForHeatMap' list
#         'ForHeatMap': cutDFforHeatMap,

#         # Convert every DataFrame inside the 'ForForceTime' list
#         'ForForceTime': cutDFforForceTime
#     }
#     print(len(All_Data[filepath.name]['ForForceTime']))

#     for i, segment in enumerate(All_Data[filepath.name]['ForForceTime']):
#         plot2SignalAllCSV(segment, "SumForce", "pos_z[mm]")


# except Exception as e:
#     print(f"Failed: {filepath.name}")
#     print(e)



# All_Data = {}
# folder = Path("Data/FinalDataCollection/Smoothen")
# while True:
#     if not folder.exists():
#         print(f"Folder not found: {folder.resolve()}")
#         break

#     for filepath in sorted(folder.glob("*.csv")):
#         print(f"Processing {filepath.name}")
#         try:
#             df = pd.read_csv(filepath)
#             # print(df.head())

#             # For HeatMap (contact area usage)
#             processingColumnNP, _, rising_edges, edge_length1 = detect_rising_edges(df, "SumForce", column="SumForce")
#             print(f"Rising edges detected at indices: {rising_edges}")
#             print(f"Minimum edge lengths: {edge_length1}")

#             # print(df.iloc[rising_edges[3]:rising_edges[3]+int(edge_length)])  # Display the first few rows of the processed DataFrame
#             cutDFforHeatMap = []
#             for i, value in enumerate(rising_edges):
#                 start_index = value
#                 end_index = start_index + edge_length1[i] # delete the last 20 points to avoid the end of the signal
#                 df_reindexed = df.iloc[start_index:end_index].reset_index(drop=True)
#                 # print(df_reindexed.head())  # Display the first few rows of the cut DataFrame
#                 cutDFforHeatMap.append(df_reindexed)
#             print(f"Cut DataFrames created: {len(cutDFforHeatMap)} segments")



#             # For detecting force application time
#             touching_points, edge_length2 = detect_touching_point(df, "pos_z[mm]")
#             print(f"Touching points detected at indices: {touching_points}")
#             print(f"Minimum edge lengths: {edge_length2}")

#             cutDFforForceTime = []
#             for i, value in enumerate(touching_points):
#                 start_index = value
#                 end_index = start_index + edge_length2[i]# delete the last 20 points to avoid the end of the signal
#                 df_reindexed = df.iloc[start_index:end_index].reset_index(drop=True)
#                 # print(df_reindexed.head())  # Display the first few rows of the cut DataFrame
#                 cutDFforForceTime.append(df_reindexed)
#             print(f"Cut DataFrames created: {len(cutDFforForceTime)} segments")

#             # for i, segment in enumerate(cutDFforForceTime):
#             #     plot2SignalAllCSV(segment, "SumForce", "pos_z[mm]")

#             All_Data[filepath.name] = {
#                 # Convert every DataFrame inside the 'ForHeatMap' list
#                 'ForHeatMap': cutDFforHeatMap,

#                 # Convert every DataFrame inside the 'ForForceTime' list
#                 'ForForceTime': cutDFforForceTime
#             }
#             print(len(All_Data[filepath.name]['ForForceTime']))

#             # for i, segment in enumerate(All_Data[filepath.name]['ForForceTime']):
#             #     plot2SignalAllCSV(segment, "SumForce", "pos_z[mm]")
#             print(" ")


#         except Exception as e:
#             print(f"Failed: {filepath.name}")
#             print(e)
#             print(" ")
#     print(len(All_Data))
#     break