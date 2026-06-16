from package.plotUtils import *


def main():
    Proccessed_column = "force_magnitude"
    folder = Path("Data/ForceBelowMat/CasesTakes")
    # means = plotAlignedFolder(folder, 'save', Proccessed_column, Path("Data/ForceBelowMat/test")) #plot all files and get means

    # Plot means by contact surface and test piece
    # plotMeanByContactSurface(means, Proccessed_column)
    # plotMeanByContactSurfaceCases(means, Proccessed_column)
    # plotMeanByTestPiece(means, Proccessed_column)
    # plotMeanByTestPieceCases(means, Proccessed_column)

    # Plot 2 Signal aligned and compare
    plotAligned2SignalFolder(folder, output = "Data/ForceBelowMat/test",force_col = 'LPF_Fcz', pos_col=Proccessed_column) 


if __name__ == "__main__":
    main()