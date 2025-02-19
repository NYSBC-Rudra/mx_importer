import typing

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from utils.db_lib import DBConnection

import json


class PuckDialog(QtWidgets.QDialog):
    def __init__(self, parent, pucklist, container_position=0 ):
        super(PuckDialog, self).__init__(parent)
        self.parent = parent
        self.all_pucks = pucklist
        self.position = container_position
        print("in puck_dialog, position= {}".format(self.position))
        print("in puck_dialog, all pucks importing = {}".format(self.all_pucks))
        self.redis_connection = DBConnection()
        our_button = self.parent.allButtonList[int(self.position)]
        self.initData()
        self.initUI()

    def initData(self):
        puckListUnsorted = self.all_pucks
        puckList = sorted(puckListUnsorted, key=lambda i: i["name"], reverse=False)
        dewarObj = self.redis_connection.getFromRedis('NyxDewar')
        dewarObj = json.loads(dewarObj)
        #dewarObj = json.loads(dewarObj)
        print(dewarObj)
        pucksInDewar = set(dewarObj["pucks"])
        self.model = QtGui.QStandardItemModel(self)
        self.proxyModel = QtCore.QSortFilterProxyModel(self)
        labels = ["Name"]
        self.model.setHorizontalHeaderLabels(labels)
        self.puckName = None
        for puck in puckList:
            if puck["name"] not in pucksInDewar:
                item = QtGui.QStandardItem(puck["name"])
                # Adding meta data to the puck. Each piece of meta data is identified using
                # an int value, in this case is Qt.UserRole for puck modified time. This metadata is used
                # to sort pucks
                #item.setData(puck.get("modified_time", 0), Qt.UserRole)
                self.model.appendRow(item)

    def initUI(self):
        self.tv = QtWidgets.QListView(self)

        self.tv.doubleClicked[QtCore.QModelIndex].connect(self.containerOKCB)
        behavior = QtWidgets.QAbstractItemView.SelectRows
        self.tv.setSelectionBehavior(behavior)
        self.proxyModel.setSourceModel(self.model)
        self.proxyModel.setSortRole(Qt.UserRole)
        self.proxyModel.sort(0, order=Qt.DescendingOrder)
        self.tv.setModel(self.proxyModel)
        self.label = QtWidgets.QLabel(self)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        self.buttons.buttons()[0].clicked.connect(self.containerOKCB)
        self.buttons.buttons()[1].clicked.connect(self.containerCancelCB)
        self.searchBox = QtWidgets.QLineEdit(self)
        self.searchBox.setPlaceholderText("Filter pucks...")
        self.searchBox.textChanged.connect(self.filterPucks)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.searchBox)
        layout.addWidget(self.tv)
        layout.addWidget(self.label)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

    def filterPucks(self, a0: str):
        self.proxyModel.setFilterFixedString(a0)

    def containerOKCB(self):
        indexes = self.tv.selectedIndexes()
        if indexes:
            text = indexes[0].data()
            self.label.setText(text)
            self.puckName = text
            self.accept()
        else:
            text = ""
            self.puckName = text
            self.reject()

    def containerCancelCB(self):
        text = ""
        self.reject()
        self.puckName = text

    @staticmethod
    def getPuckName(parent=None, pucklist=[], container_position=0 ):
        dialog = PuckDialog(parent,pucklist, container_position=0 )
        result = dialog.exec_()
        return (dialog.puckName, result == QtWidgets.QDialog.Accepted)
