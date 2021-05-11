# -*- coding: utf-8 -*-
"""
Created on Tue Feb  9 10:21:22 2021

@author: Tfahry

Connection Macro Main module

Top-level Connection Macro module containing the the GUI and main program loop.

To set up the environment before compiling:
conda env create -f environment.yml
conda activate connectionmacro

To compile:
pyinstaller --clean --onefile --noconsole main.py -n ConnectionMacro.exe

To update the GUI if you edit the ConnectionMacroUI.ui:
pyuic5 '.\qt\ConnectionMacroUI.ui' -o ConnectionMacroUI.py'

"""

import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QTableWidgetItem
from PyQt5 import QtCore

from ConnectionMacroUI import Ui_MainWindow

from connectionGenerator import GenerateConnections, AddConnections, highlightExcel
import UnitDiagramReader
from RSXParser import read, write
from NRFunctions import ResultType, hashfile
from copy import deepcopy


class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setupUi(self)
        self.tableWidget.setColumnWidth(0, 45)
        self.tableWidget_2.setColumnWidth(0, 45)
        
        self.connectSignalsSlots()
        self.result = ResultType()
        
        self.statusBar.showMessage('Connection Macro pre-alpha build MAY07')
        
        self.available_ud_readers = [cls.__name__ for cls in UnitDiagramReader.Reader.__subclasses__()]
        
        for reader in self.available_ud_readers:
            self.udselector.addItem(reader)
        
        if getattr(sys, 'frozen', False):
            self.frozen = True
            self.debugbutton.setVisible(False)
            self.lineEdit.setText('')
            self.lineEdit_2.setText('')
    
    def cellChangedSlot(self, item):
        self.tableWidget.blockSignals(True)
        columnsOfSelectedCells = set([cell.column() for cell in self.tableWidget.selectedItems()])
        
        if item in self.tableWidget.selectedItems():
            if len(columnsOfSelectedCells) == 1:                #only allow changing multiple cells if they are all in the same column
                if columnsOfSelectedCells.pop() == 0:           #if it's the 0th column, we check and propogate the checkState to the highlightedCells.
                    checkState = item.checkState()
                    for highlightedCell in self.tableWidget.selectedItems():
                        highlightedCell.setCheckState(checkState)
                else:                                           #if it's any other column, check and propagate the text() value.
                    text = item.text()
                    for highlightedCell in self.tableWidget.selectedItems():
                        highlightedCell.setText(text)
                    
        self.tableWidget.blockSignals(False)
        
    def connectSignalsSlots(self):
        pass
    
    def debugbutton_clicked(self):
        pass
    
    def rsxbrowse_clicked(self):
        self.options = QFileDialog.Options()
        self.pathToRSX, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*)", 
                                                        options=self.options)       
        if self.pathToRSX:
            self.lineEdit.setText(self.pathToRSX)
    def udbrowse_clicked(self):
        self.options = QFileDialog.Options()
        self.pathToUD, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*)", 
                                                       options=self.options)
        if self.pathToUD:
            self.lineEdit_2.setText(self.pathToUD)
            
    #FIXME findUniqueEntry throws '24:02:01' error from dec19 unit diagram
    #TODO minimum and maximum times
    #TODO make failed conns exportable
    #TODO more meaningful error messages
    #TODO dropdown for Activity column in UI
    def generate_clicked(self): #try not to raise exceptions after setData
        self._tree = read(self.lineEdit.text())
        self.tree = deepcopy(self._tree)
        self.diagram = getattr(UnitDiagramReader,self.udselector.currentText())(self.lineEdit_2.text())
        self.tiploc = self.tiplocbox.text()
        self.stationname = self.stationnamebox.text()
        self.console.append(f'Looking for connections at {self.tiploc}...')
        self.result = GenerateConnections(tree=self.tree, DiagramObject=self.diagram, stationID=self.tiploc, 
                                          stationName = self.stationname)
        self.console.append(f'Found {self.result.made.count} connections out of {self.result.tried.count} in diagram. Rejected {self.result.duplicate.count} duplicates and failed {self.result.failed.count}.')

        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), f'Made [{self.result.made.count}]')
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), f'Duplicates in {self.lineEdit.text().split("/")[-1]} (will not add) [{self.result.duplicate.count}]')
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), f'Falied [{self.result.failed.count}]')
        
        self.tableWidget.blockSignals(True)
        self.setData(self.tableWidget,self.result.made.get, checkboxes=(True))
        self.tableWidget.blockSignals(False)
        self.setData(self.tableWidget_2,self.result.duplicate.get)
        self.setFailed(self.tableWidget_3,self.result.failed.get)
        
        if self.highlightbox.checkState(): 
            if self.diagram.hasExcelRows:
                highlightExcel(self.diagram, self.result)
            else:
                self.console.append('Excel highlighting not supported for diagram type.')
        
        self.saveButton.setDisabled(False)

    def setData(self, widget, data, checkboxes = False):
        widget.setRowCount(len(data))
        for row, item in enumerate(data):            
            
            columnMap = {0:'', #checkbox placeholder
                         1:'transitionTime',
                         2:'operation',
                         3:'stationId',
                         5:'trainDeparture'}
            for key in list(columnMap.keys())[1:]:
                columnMap[key] = item['conn'].attrib[columnMap[key]]
            columnMap[4] = item['row'][1]
            columnMap[6] = item['row'][3]
            columnMap[7] = item['row'][4]
            columnMap[8] = item['excelRow']
            for key in columnMap.keys():
                newitem = QTableWidgetItem(columnMap[key])
                if key == 0 and checkboxes:
                    newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
                    newitem.setCheckState(QtCore.Qt.Checked)                           
                if key not in [0,1,2]:
                    newitem.setFlags(newitem.flags() ^ QtCore.Qt.ItemIsEditable)
                widget.setItem(row, key, newitem)
             
    def setFailed(self, widget, data):
        widget.setRowCount(len(data))
        columnMap = {}
        for row, item in enumerate(data):
            columnMap[0] = item['error']            
            columnMap[1] = item['row'][0]
            columnMap[2] = item['row'][1]
            columnMap[3] = item['row'][2]
            columnMap[4] = item['row'][3]
            columnMap[5] = item['row'][4]
            columnMap[6] = item['excelRow']

            for key in columnMap.keys():
                newitem = QTableWidgetItem(columnMap[key])
                widget.setItem(row, key, newitem)
    
        
    def savebutton_clicked(self):
        self.options = QFileDialog.Options()
        self.pathToSave, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()","","RailSys RSX file (*.rsx)", 
                                                         options=self.options)
        
        if self.pathToSave:
            #make a copy of the tree object and regenerate the Result object since any previous run of the AddConnections function
            #would have modified the elements inside self.result 
            self.tree = deepcopy(self._tree)
            self.result = GenerateConnections(tree=self.tree, DiagramObject=self.diagram, stationID=self.tiploc, 
                                          stationName = self.stationname)
            
            #Update self.result object with values from Transition Time and Activity columns in self.tablewidget.
            rows_to_be_removed = []
            for row_num in range(self.tableWidget.rowCount()):
                self.result.made._contents[row_num]['conn'].attrib['transitionTime'] = self.tableWidget.item(row_num,1).text()
                self.result.made._contents[row_num]['conn'].attrib['operation'] = self.tableWidget.item(row_num,2).text()
                
                if not self.tableWidget.item(row_num,0).checkState(): #if row is not checked
                    rows_to_be_removed.append(row_num)
                
            for row_to_be_removed in sorted(rows_to_be_removed, reverse = True): #reverse = we start from the bottom so that the list indexes aren't thrown off
                    del self.result.made._contents[row_to_be_removed]
            
            AddConnections(self.result)
            write(tree = self.tree, filename = self.pathToSave)

            self.console.append(f'\nAdded {self.result.made.count} connections into \n{self.pathToSave} and saved. (hash {hashfile(self.pathToSave)})')
            #black-kilo-triple-social-quebec-quiet

            
def excepthook(type, value, tb):
    win.console.append('******  Error  *********')
    win.console.append(str(type))      
    win.console.append(str(value))      
    win.console.append(str(tb.tb_frame))
    
if __name__ =='__main__':
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())
    

