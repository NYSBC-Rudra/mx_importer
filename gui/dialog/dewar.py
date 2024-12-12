import functools
import typing

from qtpy import QtWidgets
from utils.db_lib import DBConnection
from gui.dialog.puck_dialog import PuckDialog



class DewarDialog(QtWidgets.QDialog):
    def __init__(self, parent: "ControlMain"):
        super(DewarDialog, self).__init__(parent)
        self.pucksPerDewarSector = 4
        self.dewarSectors = 7
        #self.action = action
        self.action = "remove"
        self.parent = parent
        self.connection = DBConnection()
        self.initData()
        self.initUI()

    def initData(self):
        dewarObj = self.connection.getFromRedis('NyxDewar')
        print(dewarObj)
        #making dewar object if not present
        if dewarObj == '':
            dewarObj = {"content": [""] * (self.pucksPerDewarSector * self.dewarSectors), 'name': 'NyxDewar', 'pucks':[]}
            dewarObj = str(dewarObj)
            self.connection.sendToRedis('NyxDewar',dewarObj)
        dewarObj = eval(dewarObj)
        puckLocs = dewarObj["content"]
        #[''*28]
        self.data = []
        self.dewarPos = None
        #max 29 values in dewar object
        for i in range(len(puckLocs)):
            if puckLocs[i] != "":
                puck_name = puckLocs[i]['name']
                #owner = db_lib.getContainerByID(puckLocs[i])["owner"]
                self.data.append(puck_name)
            else:
                self.data.append("Empty")
        #logger.info(self.data)

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        headerLabelLayout = QtWidgets.QHBoxLayout()
        aLabel = QtWidgets.QLabel("A")
        aLabel.setFixedWidth(15)
        headerLabelLayout.addWidget(aLabel)
        bLabel = QtWidgets.QLabel("B")
        bLabel.setFixedWidth(10)
        headerLabelLayout.addWidget(bLabel)
        cLabel = QtWidgets.QLabel("C")
        cLabel.setFixedWidth(15)
        headerLabelLayout.addWidget(cLabel)
        dLabel = QtWidgets.QLabel("D")
        dLabel.setFixedWidth(10)
        headerLabelLayout.addWidget(dLabel)
        layout.addLayout(headerLabelLayout)
        self.allButtonList = [None] * (self.dewarSectors * self.pucksPerDewarSector)
        for i in range(0, self.dewarSectors):
            rowLayout = QtWidgets.QHBoxLayout()
            numLabel = QtWidgets.QLabel(str(i + 1))
            rowLayout.addWidget(numLabel)
            for j in range(0, self.pucksPerDewarSector):
                dataIndex = (i * self.pucksPerDewarSector) + j
                self.allButtonList[dataIndex] = QtWidgets.QPushButton(
                    #(str(self.data[dataIndex]))
                    '{}: {}'.format(str(dataIndex+1),str(self.data[dataIndex]))
                )
                self.allButtonList[dataIndex].clicked.connect(
                    functools.partial(self.on_button, str(dataIndex))
                )
                rowLayout.addWidget(self.allButtonList[dataIndex])
            layout.addLayout(rowLayout)
        cancelButton = QtWidgets.QPushButton("Done")
        cancelButton.clicked.connect(self.containerCancelCB)
        layout.addWidget(cancelButton)
        self.setLayout(layout)

    def on_button(self, n):
        
        if 'Empty' in self.allButtonList[int(n)].text():
            self.dewarPos = n
            #db_lib.removePuckFromDewar(daq_utils.beamline, int(n))
            #print(self.parent.all_pucks)
            #self.puck_window = PuckDialog(self, self.parent.all_pucks, int(n))
            chosen_puck = PuckDialog.getPuckName(self,self.parent.all_pucks,int(n))[0]
            self.fillContainerPosition(int(self.dewarPos), chosen_puck)

        else:
            self.dewarPos = n
            self.removePuckFromDewar(int(self.dewarPos))
            self.allButtonList[int(n)].setText("Empty")


    def containerCancelCB(self):
        self.dewarPos = 0
        self.reject()

    def fillContainerPosition(self, position, puckName):
        #finding correct puck from all pucks
        possible_pucks = [puck for puck in self.parent.all_pucks if puck["name"] == puckName]
        if len(possible_pucks) == 0 or len(possible_pucks) > 1:
            QtWidgets.QMessageBox.warning(self, "Error", "{} of {} found in list".format(len(possible_pucks), puckName))
            return
        puck = possible_pucks[0]
        dewarObj = self.connection.getFromRedis('NyxDewar')
        dewarObj = eval(dewarObj)
        print(dewarObj['content'])
        dewarObj['content'][int(position)] = puck
        dewarObj['pucks'].append(puckName)
        print('sending dewar to redis \n {}'.format(dewarObj))
        self.connection.sendToRedis('NyxDewar',str(dewarObj))
        self.allButtonList[position].setText(puckName)



    def removePuckFromDewar(self, position):
        dewarObj = self.connection.getFromRedis('NyxDewar')
        dewarObj = eval(dewarObj)
        puckname = dewarObj['content'][position]['name']
        dewarObj['content'][position] = ''
        dewarObj['pucks'].remove(puckname)
        return




    #@staticmethod
    #def getDewarPos(parent=None, action="add"):
    #    dialog = DewarDialog(parent, action)
    #    result = dialog.exec_()
    #    return (dialog.dewarPos, result == QtWidgets.QDialog.Accepted)
