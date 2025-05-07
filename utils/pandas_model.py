import pdb

import json
import re
import typing
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QTableView

from utils.collection_request import CollectionRequest


class BasePandasModel(QAbstractTableModel):
    """Base model interface Qt view"""

    def __init__(self, dataframe: pd.DataFrame, parent=None) -> None:
        QAbstractTableModel.__init__(self, parent)
        self.validData = False
        self._dataframe = dataframe.dropna(how="all").reset_index(drop=True)
        self.colors: Dict[Tuple[int, int], QColor] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        """Override method from QAbstractTableModel

        Return row count of the pandas DataFrame
        """
        if parent == QModelIndex():
            return len(self._dataframe)

        return 0

    def columnCount(self, parent=QModelIndex()) -> int:
        """Override method from QAbstractTableModel

        Return column count of the pandas DataFrame
        """
        if parent == QModelIndex():
            return len(self._dataframe.columns)
        return 0

    def data(self, index: QModelIndex, role=Qt.ItemDataRole) -> "str | QColor | None":
        """Override method from QAbstractTableModel

        Return data cell from the pandas DataFrame
        """
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            data = self._dataframe.iloc[index.row(), index.column()]
            return str(data) if not pd.isna(data) else ""
        if role == Qt.ItemDataRole.BackgroundRole:
            color = self.colors.get((index.row(), index.column()))
            if color is not None:
                return color

        return None

    def rows(self):
        for i, row in self._dataframe.iterrows():
            yield row

    def setData(self, index: QModelIndex, value: typing.Any, role: int = ...) -> bool:
        if role == Qt.ItemDataRole.EditRole:
            self._dataframe.iloc[index.row(), index.column()] = value
            self.dataChanged.emit(index, index)
            return True
        return False

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole
    ) -> "str | None":
        """Override method from QAbstractTableModel

        Return dataframe index as vertical header data and columns as horizontal header data.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._dataframe.columns[section])

            if orientation == Qt.Orientation.Vertical:
                return str(self._dataframe.index[section])

        return None

    def changeColor(self, row: int, column: int, color: QColor) -> None:
        ix = self.index(row, column)
        self.colors[(row, column)] = color
        self.dataChanged.emit(ix, ix, (Qt.ItemDataRole.BackgroundRole,))

    def resetColors(self) -> None:
        cells = list(self.colors.keys())
        self.colors = {}
        for row, col in cells:
            ix = self.index(row, col)
            self.dataChanged.emit(ix, ix, (Qt.ItemDataRole.BackgroundRole,))

    def _changeCellColors(
        self, column_index: int, row_indices, color=QColor(Qt.GlobalColor.red)
    ) -> None:
        for idx in row_indices:
            self.changeColor(idx, column_index, color)
    
    def _changeCellData(self, column_index: int, row_indices, value=None) -> None:
        for idx in row_indices:
            self.changeValue(idx, column_index, value)
    
    def changeValue(self, row: int, column: int, value) -> None:
        #self._dataframe.at[row, column] = self._dataframe.at[row, column].astype("object")
        self._dataframe.at[row,column] = value


class PuckPandasModel(BasePandasModel):
    """A model to interface a Qt view with pandas dataframe"""

    def setPuckLists(self, pucklist):
        self.puckList = pucklist

    def flags(self, index):
        return (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
        )

    def validateData(self, config) -> None:
        self.resetColors()
        if not self._matchMasterlist(self._dataframe, config):
            raise TypeError(
                "Pucks submitted do not match master list. Pucks not in whitelist or etched list are in yellow. Pucks in blacklist are in red"
            )
        '''
        sample information checkers
        
        '''

        if not self._checkSampleNames(self._dataframe):
            raise TypeError(
                'Invalid Sample names found. Only numbers, letters, dash ("-"),'
                ' and underscore ("_") are allowed. Total length of sample name cannot exceed 25'
                " Automatically changed invalid characters to underscore and highlighted in yellow"
            )

        if not self._checkEmptySamples(self._dataframe):
            raise TypeError("Empty sample names found")

        if not self._checkDuplicateSamples(self._dataframe):
            raise TypeError(
                "Duplicate sample names found. Added postfix and highlighted in yellow"
            )

        if not self._checkProposalNumbers(self._dataframe):
            raise TypeError("Invalid proposal numbers")

        if not self._checkDuplicatePuckPos(self._dataframe):
            raise TypeError("Duplicate Puck name and position combinations found")
        


        


        
        '''
        data collection checkers
        '''
        if not self._deltaphi_exposure_toltalphi_check(self._dataframe):
            raise TypeError(
                "Data collection parameters are invalid, missing values may have been replaced, check the cells highlighted in red and yellow"
            )
        
            

        '''
        automation checkers
        '''


        '''
        data processing checkers
        '''
        # if not error_check:
        #     raise TypeError(error_string)

        self.validData = True
    def preprocessData(self) -> None:
        # Note all column names are lowercase, good for comparison
        #IN NYX IMPORTER ADDING ALL THE COLUMNS THAT ARE REQUIRED
        required_columns_list = [
            "puckname",
            "position",
            "samplename",
            "proposalnum",
            "folder",
            "deltaphi",
            "exposure",
            "totalphi",
            "transmission",
            "targetresolution",
            "beamsize",
            "priority",
            "collectiontype",
            "model",
            "spacegroup",
            "cellparameters",
]
        required_columns = set(required_columns_list)
        self._dataframe.columns = self._dataframe.columns.str.lower()
        columns_absent = None
        self.resetColors()

        # Change current dataframe to only have required columns
        if not required_columns.issubset(self._dataframe.columns):
            columns_present = required_columns.intersection(self._dataframe.columns)
            columns_absent = required_columns - set(self._dataframe.columns)
            self._dataframe = self._dataframe[list(columns_present)]
            for col in columns_absent:
                self._dataframe.loc[:, col] = ""

        # Set data types for various columns. By this point all required columns should be present
        '''
        Setting sample information variables
        '''
        self._dataframe.loc[:, "position"].astype("Int64", errors="ignore")

        self._dataframe.loc[:, "proposalnum"].astype("Int64", errors="ignore")



        '''
        setting data collection variables
        '''
        self._dataframe.loc[:, "deltaphi"].astype("float" , errors="ignore")
        self._dataframe.loc[:, "exposure"].astype("float" , errors="ignore")
        self._dataframe.loc[:, "totalphi"].astype("float" , errors="ignore")
        self._dataframe.loc[:, "transmission"].astype("float" , errors="ignore")
        #self._dataframe.loc[:, "beamsize"] = pd.to_numeric(
        #    self._dataframe["beamsize"], errors="coerce"
        #).astype("float")
        self._dataframe.loc[:, "targetresolution"].astype("float" , errors="ignore")
        self._dataframe.loc[:, "beamsize"].astype("float" , errors="ignore")


        '''
        setting automation variables
        '''
        self._dataframe = self._dataframe.astype({"collectiontype": "str"} , errors="ignore")

        '''
        setting Data processing variables
        '''

        self._dataframe = self._dataframe.astype({"spacegroup": "str", "model": "str", "cellparameters": "str"} , errors="ignore")


        self._dataframe = self._dataframe[required_columns_list]

        # Remove all whitespaces from string columns
        for col in required_columns:
            self._dataframe[col] = self._dataframe[col].astype("string")
            if col != "samplename":
                self._dataframe[col] = self._dataframe[col].str.replace(r"\s+", "", regex=True)
            else:
                self._dataframe[col] = self._dataframe[col].str.replace(r"(\.|\s)+", "", regex=True)

        if columns_absent:
            raise TypeError(
                f"Missing column headers in excel file: {columns_absent}."
                " If data is present in the excel file, make sure column names are correct and import the file again."
                " Otherwise enter values into the empty column generated by the puck importer or validate the data again to fill some rows."
                "You still need to validate this data before submitting"
            )
        
        '''
        Filling empty values with defaults
        '''

        if not self._fill_data_collection_values(self._dataframe):
            absent_columns = "transmission, targetresolution, beamsize, collectiontype, spacegroup, model, cellparameters"
            raise TypeError(
                f"Empty Values in following columns: {absent_columns}."
                "Cells with added data have been highlighted in yellow."
                "Please check the cells to see if the values are acceptable"
                "You still need to validate this data before submitting"
            )
        


    def _checkProposalNumbers(self, data: pd.DataFrame) -> bool:
        proposalNumCol = "proposalnum"
        # Remove all letters from proposal numbers
        data[proposalNumCol] = data[proposalNumCol].astype("str")
        data[proposalNumCol] = data[proposalNumCol].str.replace(r"\D", "", regex=True)

        # Check if proposal numbers have 6 digits
        indices = data[proposalNumCol][~data[proposalNumCol].map(len).eq(6)].index
        col_index = data.columns.get_loc(proposalNumCol)
        if len(indices) > 0:
            self._changeCellColors(col_index, indices)
            return False

        if len(data[proposalNumCol].unique()) > 1:
            return False

        return True

    def _checkDuplicateSamples(self, data: pd.DataFrame) -> bool:
        column = "samplename"
        duplicate_rows = data[data[column].duplicated(keep=False)]
        duplicates = data[data.duplicated(column)]
        counter = (duplicates.groupby(column).cumcount() + 1).astype(str).str.zfill(3)
        data.loc[counter.index, column] += "_" + counter

        if len(duplicate_rows):
            column_index = data.columns.get_loc("samplename")
            self._changeCellColors(
                column_index, duplicate_rows.index, color=QColor(Qt.GlobalColor.yellow)
            )
            return False
        return True

    def _checkEmptySamples(self, data: pd.DataFrame) -> bool:
        column = "samplename"
        empty_rows = data[pd.isna(data[column])]
        if len(empty_rows):
            column_index = data.columns.get_loc("samplename")
            self._changeCellColors(column_index, empty_rows.index)
            return False
        return True

    def _checkDuplicatePuckPos(self, data: pd.DataFrame) -> bool:
        duplicate_rows = data[
            data.duplicated(subset=["puckname", "position"], keep=False)
        ]

        if len(duplicate_rows):
            column_index = data.columns.get_loc("puckname")
            self._changeCellColors(column_index, duplicate_rows.index)
            column_index = data.columns.get_loc("position")
            self._changeCellColors(column_index, duplicate_rows.index)
            return False
        return True

    def _checkSampleNames(self, data: pd.DataFrame) -> bool:
        sampleNameRegex = "[0-9a-zA-Z-_]{0,25}"
        non_matching_rows = data[~data["samplename"].str.fullmatch(sampleNameRegex)]
        # replacing non-matching characters
        data["samplename"] = data["samplename"].apply(
            lambda x: re.sub(r"[^0-9a-zA-Z-_]", "_", x) if isinstance(x, str) else ""
        )

        # truncate strings to the first 25 characters
        data["samplename"] = data["samplename"].apply(lambda x: x[:25])

        if len(non_matching_rows):
            column_index = data.columns.get_loc("samplename")
            self._changeCellColors(
                column_index,
                non_matching_rows.index,
                color=QColor(Qt.GlobalColor.yellow),
            )
            return False
        return True

    def _matchMasterlist(self, data: pd.DataFrame, config) -> bool:
        masterList = self.puckList
        enteredPucks = set(data["puckname"])
        column_index = data.columns.get_loc("puckname")

        missingPucks = set()
        allowedPucks = set()

        if not config.get("disable_whitelist", False):
            allowedPucks.update(set(masterList["whitelist"]))

        if not config.get("disable_etchedlist", False):
            allowedPucks.update(set(masterList["etched"]))

        if allowedPucks:
            missingPucks = enteredPucks - allowedPucks

            # data["puckname"].fillna('MISSING', inplace=True)
            indices = []
            for puck in missingPucks:
                if not pd.isnull(puck):
                    indices.extend(data.index[data["puckname"] == puck].tolist())
            self._changeCellColors(
                column_index, indices, color=QColor(Qt.GlobalColor.yellow)
            )

        disallowedPucks = set()
        if not config.get("disable_blacklist", False):
            disallowedPucks = enteredPucks.intersection(set(masterList["blacklist"]))
            indices = []
            for puck in disallowedPucks:
                indices.extend(data.index[data["puckname"] == puck].tolist())
            self._changeCellColors(column_index, indices)

        if missingPucks or disallowedPucks:
            return False
        return True

    def _deltaphi_exposure_toltalphi_check(self, data: pd.DataFrame) -> bool:
        columns = ['deltaphi', 'exposure', 'totalphi']
        data.apply(self._create_collection_request, axis=1)
            
        
        return True
    
    def _create_collection_request(self, row: pd.Series) -> CollectionRequest:
        #get data from row
        #print(row)
        return

        
    def _fill_data_collection_values(self, data: pd.DataFrame) -> bool:
        def checknan(value):
            if isinstance(value, str):
                return value == 'nan' or value == ''
            return  pd.isna(value)

        default_values = {'transmission': '20', 'targetresolution': '2.0', 'beamsize': '30', 
                          'deltaphi': '0.25', 'exposure': '0.05', 'totalphi': '180', 'collectiontype':'centering',
                          }
        error_check = True

        for column in default_values.keys():
            empty_rows = (data[column].map(checknan))
            if len(data[empty_rows]):
                column_index = data.columns.get_loc(column)
                #print('empty position in: {}, {}'.format(column_index, empty_rows.index))
                value = default_values[column]
                self._changeCellData(column, empty_rows.index,value)
                self._changeCellColors(column_index, empty_rows.index, QColor(Qt.GlobalColor.yellow))
                error_check = False
        return error_check


class DewarPandasModel(BasePandasModel):
    def flags(self, index):
        return (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
        )

    def setData(self, index: QModelIndex, value: typing.Any, role: int = ...) -> bool:
        if role == Qt.ItemDataRole.EditRole:
            if str(value).startswith("DEWAR"):
                self.addDewar(index, value)
            else:
                self.addDataToNextRow(index, value)
            self.dataChanged.emit(index, index)
            return True
        return False

    def addDewar(self, index: QModelIndex, value):
        tableView: QTableView = self.parent().tableView
        # If dewar column exists in the dataframe, jump to the first empty
        if value in self._dataframe.columns:
            first_empty_row = (
                self._dataframe[value].eq("").idxmax()
                if self._dataframe[value].eq("").any()
                else None
            )
            # if first_empty is none create a new row and go there
            if first_empty_row is None:
                self.addDataToNextRow(index, value)
            else:
                desired_index = tableView.model().index(
                    first_empty_row, self._dataframe.columns.get_loc(value)
                )
                tableView.setCurrentIndex(desired_index)
        else:
            self.addDataToNextColumn(index, value)

    def addDataToNextRow(self, index, value):
        tableView: QTableView = self.parent().tableView
        if len(self._dataframe.index) == index.row() + 1:
            self.beginInsertRows(QModelIndex(), index.row() + 1, index.row() + 1)
            self._dataframe = pd.concat(
                [
                    self._dataframe,
                    pd.Series(
                        ["" for i in range(len(self._dataframe.columns))],
                        index=self._dataframe.columns,
                    )
                    .to_frame()
                    .T,
                ],
                ignore_index=True,
            )
            self.endInsertRows()
        if (
            not self._dataframe[self._dataframe.columns[index.column()]]
            .isin([value])
            .any()
        ):
            self._dataframe.iloc[index.row(), index.column()] = value
            next_index = self.index(index.row() + 1, index.column())
            tableView.setCurrentIndex(next_index)

    def addDataToNextColumn(self, index, value):
        if index.row() == 0 and index.column() == 0:
            if None in self._dataframe.columns:
                self._dataframe.rename(columns={None: value}, inplace=True)
                self.layoutChanged.emit()
            else:
                self.addDewarColumn(index, value)
        else:
            self.addDewarColumn(index, value)

    def addDewarColumn(self, index, value):
        tableView: QTableView = self.parent().tableView
        # Add a column if we are running out of columns
        self.beginInsertColumns(QModelIndex(), index.column() + 1, index.column() + 1)
        self._dataframe[value] = ["" for i in range(len(self._dataframe.index))]
        self.endInsertColumns()
        desired_index = tableView.model().index(
            0, self._dataframe.columns.get_loc(value)
        )
        tableView.setCurrentIndex(desired_index)
