import getpass
import grp
import json
import logging
import os
import sys
import time
import traceback
from enum import Enum
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import yaml
from qtpy import QtWidgets
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor, QIcon
from gui.dialog.dewar import DewarDialog

from gui.config import ConfigurationWindow
from gui.custom_table import DewarTableWithCopy, TableWithCopy
from utils.db_lib import DBConnection
from utils.pandas_model import DewarPandasModel, PuckPandasModel

logger = logging.getLogger(__name__)
logfile_path = Path("~/.puckimporter/puckimporter.log").expanduser()
logfile_path.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(logfile_path)
file_handler.setLevel(logging.INFO)


class Mode(Enum):
    MANUAL = "Manual"
    AUTOMATED = "Automated"


class ControlMain(QtWidgets.QMainWindow):
    def __init__(self, *args, config_path, **kwargs):
        self.config_path = config_path
        try:
            with self.config_path.open("r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"TypeError: {traceback.format_exc()}")
            print(
                f"Exception occured while reading config file {self.config_path}: {e}"
            )
            raise e
        self.config = config
        super().__init__(*args, **kwargs)
        self.setWindowTitle(f"Import Pucks at {self.config.get('beamline', '99id1')}")
        self.tableView = self._createTableView()
        self.setCentralWidget(self.tableView)
        self._createActions()
        self._createMenuBar()
        self.model = None
        self.mode = Mode.MANUAL
        self.resize(QtWidgets.QDesktopWidget().availableGeometry().size() * 0.7)  # type: ignore
        self.validatePuckLists()
        self.status_bar = self.statusBar()
        self.mode_status = QtWidgets.QLabel(f"MODE: {self.mode.value}")
        self.status_bar.addPermanentWidget(self.mode_status)
        # Default mode to start the application
        self._set_mode(Mode.MANUAL)
        self.all_pucks = []

    def validatePuckLists(self):
        pucklist_path = Path(self.config["list_path"])
        if not pucklist_path.exists():
            self.showModalMessage(
                "Error",
                f"Puck list file {pucklist_path} not found. White list and black list are empty",
            )
            self.pucklists = {"blacklist": [], "whitelist": [], "etched": []}
        else:
            self.parsePuckList(pucklist_path)

    def parsePuckList(self, path: Path):
        parse_excel = False
        if path.suffix == ".json":
            with path.open("r") as f:
                self.pucklists = json.load(f)
                for label in ["whitelist", "blacklist", "etched"]:
                    if label not in self.pucklists.keys():
                        self.pucklists[label] = []
        elif path.suffix == ".xlsx":
            engine = "openpyxl"
            parse_excel = True
        elif path.suffix == ".xls":
            engine = "xlrd"
            parse_excel = True

        if parse_excel:
            self.pucklists = {}
            reader = pd.ExcelFile(path, engine=engine)
            self.pucklists["etched"] = self.get_sheet_data(reader, "etched")
            self.pucklists["whitelist"] = self.get_sheet_data(reader, "white_list")
            self.pucklists["blacklist"] = self.get_sheet_data(reader, "black_list")

    def get_sheet_data(self, reader: pd.ExcelFile, sheet):
        df = reader.parse(
            sheet_name=sheet,
            header=None,
        )
        if len(df.columns) > 0:
            return df.iloc[:, 0].to_list()
        else:
            return []

    def _createActions(self):
        # File menu actions
        self.saveExcelAction = QtWidgets.QAction("&Save table as Excel file", self)
        self.saveExcelAction.triggered.connect(self.saveExcel)
        self.exitAction = QtWidgets.QAction("&Exit", self)
        self.exitAction.triggered.connect(QtWidgets.QApplication.quit)
        self.FillDewarAction = QtWidgets.QAction("&Fill Dewar", self)
        self.FillDewarAction.triggered.connect(self.openDewar)

        # Puck menu actions
        self.importExcelAction = QtWidgets.QAction("&Import Excel file", self)
        self.importExcelAction.triggered.connect(self.importExcel)
        self.validateExcelAction = QtWidgets.QAction(
            "&Validate imported Excel file", self
        )
        self.validateExcelAction.triggered.connect(self.validateExcel)
        self.submitPuckDataAction = QtWidgets.QAction("&Submit Puck data", self)
        self.submitPuckDataAction.triggered.connect(self.submitPuckData)
        self.configWindowAction = QtWidgets.QAction("&Configuration", self)
        self.configWindowAction.triggered.connect(self.openConfigWindow)
        self.manualModeAction = QtWidgets.QAction("&Manual", self)
        self.manualModeAction.triggered.connect(lambda: self._set_mode(Mode.MANUAL))
        self.manualModeAction.setCheckable(True)
        self.manualModeAction.setChecked(True)
        self.automatedModeAction = QtWidgets.QAction("&Automated", self)
        self.automatedModeAction.triggered.connect(
            lambda: self._set_mode(Mode.AUTOMATED)
        )
        self.automatedModeAction.setCheckable(True)
        self.automatedModeAction.setChecked(False)

        # Shipping Dewar menu
        self.beginDewarScanAction = QtWidgets.QAction("&Begin Dewar Scan", self)
        self.beginDewarScanAction.triggered.connect(self.setupDewarScan)

    def _set_mode(self, mode):
        self.mode = mode
        self.mode_status.setText(f"MODE: {self.mode.value}")
        if self.mode == Mode.AUTOMATED:
            self.manualModeAction.setChecked(False)
            self.automatedModeAction.setChecked(True)
            self.owner = "mx"
        elif self.mode == Mode.MANUAL:
            self.manualModeAction.setChecked(True)
            self.automatedModeAction.setChecked(False)
            self.owner = getpass.getuser()

    def setupDewarScan(self):
        empty_frame = {None: [""]}
        data = pd.DataFrame.from_dict(empty_frame)
        self.model = DewarPandasModel(data, parent=self)
        self.tableView = self._createTableView()
        self.setCentralWidget(self.tableView)
        self.tableView.setModel(self.model)
        self.tableView.resizeColumnsToContents()
        next_index = self.model.index(0, 0)
        self.tableView.setCurrentIndex(next_index)

    def saveExcel(self):
        filepath, _ = QtWidgets.QFileDialog().getSaveFileName(self, "Save file")
        if filepath:
            filepath = Path(filepath)
            if not filepath.suffix:
                filepath = filepath.parent / (filepath.name + ".xlsx")
            engine = "openpyxl"
            if filepath.suffix == "xls":
                engine = "xlrd"

            if self.model:
                self.model._dataframe.to_excel(filepath, engine=engine, index=False)

    def openDewar(self):
        self.sub = DewarDialog(self)
        self.sub.show()  
        return

    def identify_excel_format(self, file_path):
        with open(file_path, "rb") as f:
            header = f.read(8)

        xls_header = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
        xlsx_header = b"\x50\x4B\x03\x04"

        if header[:8] == xls_header:
            return "xlrd"
        elif header[:4] == xlsx_header[:4]:
            return "openpyxl"
        else:
            return None

    def importExcel(self):
        dialog = QtWidgets.QFileDialog()
        if self.config.get("open_in_work_dir", True):
            dialog.setDirectory(os.getcwd())
        filename, _ = dialog.getOpenFileName(
            self, "Import file", filter="Excel (*.xls *.xlsx)"
        )
        required_columns_list = [
            "puckname",
            "position",
            "samplename",
            "model",
            "sequence",
            "proposalnum",
        ]
        if filename:
            engine = self.identify_excel_format(filename)
            excel_file = pd.ExcelFile(filename, engine=engine)
            for sheet_name in excel_file.sheet_names:
                data = excel_file.parse(sheet_name)
                if data.empty:
                    continue
                # Check if any row besides header row contains "puckname"
                rows = (data.applymap(lambda x: str(x).lower() == "puckname")).any(
                    axis=1
                )

                required_columns = set(required_columns_list)
                header_correct = required_columns.issubset(
                    (
                        col.strip().lower()
                        for col in data.columns
                        if isinstance(col, str)
                    )
                )
                if not rows.all() and not header_correct:
                    import_offset = data.loc[rows].first_valid_index()
                    if isinstance(import_offset, (int, np.integer)):
                        data = excel_file.parse(
                            sheet_name=sheet_name, skiprows=import_offset + 1
                        )
                data.rename(
                    columns={
                        col: col.strip().lower()
                        for col in data.columns
                        if isinstance(col, str)
                    },
                    inplace=True,
                )
                # Check headers again after offset
                header_correct = required_columns.issubset(
                    (
                        col.strip().lower()
                        for col in data.columns
                        if isinstance(col, str)
                    )
                )
                if header_correct:
                    self.model = PuckPandasModel(data)
                    self.model.setPuckLists(self.pucklists)
                    self.validateExcel()
                    self.tableView.setModel(self.model)
                    break
            self.tableView.resizeColumnsToContents()

    def validateExcel(self):
        if not isinstance(self.model, PuckPandasModel):
            return
        try:
            self.model.preprocessData()
            self.model.validateData(self.config)
            self.showModalMessage("Success", "Validated excel sucessfully")

        except TypeError as e:
            logger.error(f"TypeError: {traceback.format_exc()}")
            self.showModalMessage("Error", e)

    def showModalMessage(self, title, message):
        self.msg = QtWidgets.QMessageBox()
        self.msg.setText(str(message))
        self.msg.setModal(True)
        self.msg.setWindowTitle(title)
        self.msg.show()

    def submitPuckData(self):
        try:
            if isinstance(self.model, PuckPandasModel):
                self.model.preprocessData()
                self.model.validateData(self.config)
        except Exception as e:
            logger.error(f"TypeError: {traceback.format_exc()}")
            self.showModalMessage(
                "Error", f"Data not validated, will not upload.\nException: {e}"
            )
            return

        if isinstance(self.model, PuckPandasModel):
            beamline_id = self.config.get("beamline", "99id1").lower()
            dbConnection = DBConnection(
                beamline_id=beamline_id,
                host=self.config.get(
                    "database_host", os.environ.get("MONGODB_HOST", "localhost")
                ),
                owner=self.owner,
            )
            self.progress_dialog = QtWidgets.QProgressDialog(
                "Uploading Puck data...",
                "Cancel",
                0,
                self.model.rowCount(),
                self,
            )
            # self.progress_dialog.setModal(True)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            prevPuckName = None
            puck_id = None
            self.currentPucks = set()
            self.progress_dialog.show()
            self.progress_dialog.setValue(0)
            time.sleep(
                0.25
            )  # Dumb sleep because progress dialog doesn't initialize fast enough
            for i, row in enumerate(self.model.rows()):
                print(f"Processing row {i}")
                self.progress_dialog.setValue(i + 1)
                if self.progress_dialog.wasCanceled():
                    break
                # Check if puck exists, otherwise create one
                if row["puckname"] != prevPuckName:
                    if puck_id is not None:
                        puck_id['proposal_number'] = propNum
                        self.all_pucks.append(puck_id)
                    puck_id = dbConnection.getOrCreateContainerID(
                        row["puckname"], 16, "16_pin_puck"
                    )
                    prevPuckName = row["puckname"]

                # Create sample
                sampleName: str = row["samplename"]
                model = row["model"]
                seq = row["sequence"]
                propNum = row["proposalnum"]
                sampleID = dbConnection.createSample(
                    str(sampleName),
                    "pin",
                    model=None if pd.isna(model) else str(model),
                    sequence=None if pd.isna(seq) else str(seq),
                    proposalID=propNum,
                    container=puck_id['name'],
                )
                if puck_id['name'] not in self.currentPucks:
                    #dbConnection.emptyContainer(puck_id)
                    self.currentPucks.add(puck_id['name'])
                puck_id[int(row["position"]) - 1] = sampleID
                #dbConnection.insertIntoContainer(
                #    puck_id, int(row["position"]) - 1, sampleID
                #)
            puck_id['proposal_number'] = propNum
            self.all_pucks.append(puck_id)
            print(self.all_pucks)
            dbConnection.sendToRedis('allpuckData', str(self.all_pucks))
        else:
            self.showModalMessage("Error", "Invalid data, will not upload to database")

    def _createMenuBar(self):
        menuBar = self.menuBar()
        # Creating menus using a QMenu object
        fileMenu = QtWidgets.QMenu("&File", self)
        dataMenu = QtWidgets.QMenu("&Puck Import", self)
        dewarScanMenu = QtWidgets.QMenu("&Shipping Dewar", self)
        menuBar.addMenu(fileMenu)
        menuBar.addMenu(dataMenu)
        fileMenu.addActions([self.saveExcelAction, self.FillDewarAction, self.exitAction])

        dataMenu.addActions(
            [
                self.importExcelAction,
                self.validateExcelAction,
                self.submitPuckDataAction,
            ]
        )
        modeSubMenu = dataMenu.addMenu("Mode")
        modeSubMenu.addActions([self.manualModeAction, self.automatedModeAction])

        if self.config["admin_group"] in [
            grp.getgrgid(g).gr_name for g in os.getgroups()
        ]:
            dataMenu.addAction(self.configWindowAction)
            menuBar.addMenu(dewarScanMenu)
            dewarScanMenu.addAction(self.beginDewarScanAction)

    def _createTableView(self, dewar=False):
        # view = QtWidgets.QTableView()
        if dewar:
            view = DewarTableWithCopy()
        else:
            view = TableWithCopy()
        view.resize(1200, 1200)
        view.horizontalHeader().setStretchLastSection(True)
        view.setAlternatingRowColors(True)
        view.setSelectionMode(QtWidgets.QTableView.SelectionMode.ExtendedSelection)
        return view

    def openConfigWindow(self):
        self.configWindow = ConfigurationWindow(
            config=self.config, puck_list=self.pucklists
        )
        self.config = self.configWindow.config
        with self.config_path.open("w") as f:
            yaml.safe_dump(self.config, f)


def start_app(config_path):
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(Path.cwd() / Path("gui/assets/icon.png"))))
    ex = ControlMain(config_path=config_path)
    ex.show()
    sys.exit(app.exec_())
