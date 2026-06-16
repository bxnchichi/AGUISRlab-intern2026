from package.plotUtils import *


def main():
    Proccessed_column = "LPF_Fcz"
    folder = Path("Data/ForceBelowMat/CasesTakes")
    means = plotAlignedFolder(folder, 'save', Proccessed_column, Path("Data/ForceBelowMat/test")) #plot all files and get means

    # Plot means by contact surface and test piece
    # plotMeanByContactSurface(means, 'save', Proccessed_column, output_folder="Data/ForceBelowMat/test")
    # plotMeanByContactSurfaceCases(means, 'save', Proccessed_column, output_folder="Data/ForceBelowMat/test")
    # plotMeanByTestPiece(means, 'save', Proccessed_column, output_folder="Data/ForceBelowMat/test")
    # plotMeanByTestPieceCases(means, 'save', Proccessed_column, output_folder="Data/ForceBelowMat/test")

    # Plot 2 Signal aligned and compare
    # plotAligned2SignalFolder(folder, output = "Data/ForceBelowMat/test",force_col = 'LPF_Fcz', pos_col=Proccessed_column) 


if __name__ == "__main__":
    main()