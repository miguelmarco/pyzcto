#!/usr/bin/python

import sys
from PyQt5.QtCore import Qt, QProcess, QTimer
from PyQt5.QtWidgets import QWidget, QApplication, QDialog, QMainWindow, QTableWidgetItem
from PyQt5.QtGui import QPicture, QPixmap,QImage, QBrush, QColor
from PyQt5.uic import loadUi
import requests
import json
import qrcode
import time
import os


defaults = {
    'zcashd_host': '127.0.0.1',
    'zcashd_port': '8232'
    }




class mainwindow(QMainWindow):
    def __init__(self, parent = None):
        QMainWindow.__init__(self)
        loadUi("pyzcto.ui", self)
        self.settings = {}
        self.load_settings()
        fd = open(os.path.expanduser('~/.zcash/zcash.conf'))
        fdl = fd.readlines()
        fd.close()
        userlines = [l for l in fdl if 'rpcuser' in l]
        passlines = [l for l in fdl if 'rpcpassword' in l]
        if not userlines or not passlines:
            raise Error('setup rpcuser and rpcpassword in zcash.conf')
        username = userlines[-1].replace(' ', '').split('=')[1]
        password = passlines[-1].replace(' ', '').split('=')[1]
        self.line_user.setText(username.replace('\n',''))
        self.line_password.setText(password.replace('\n',''))
        self.torproc = QProcess()
        self.torconnectbutton.clicked.connect(self.torconnect)
        self.pushButton_newtr.clicked.connect(self.newtraddr)
        self.pushButton_newsh.clicked.connect(self.newshaddr)
        self.sendButton.clicked.connect(self.send)
        self.listaddresses_receive.currentItemChanged.connect(self.geneartereceiveqr)
        self.line_receiveamount.textChanged.connect(self.geneartereceiveqr)
        self.line_receivedesc.textChanged.connect(self.geneartereceiveqr)
        self.plainTextEdit_sendmultiple.textChanged.connect(self.check_is_send_correct)
        self.comboBox_sendaccounts.currentIndexChanged.connect(self.check_is_send_correct)
        self.line_sendaccount1.textChanged.connect(self.check_is_send_correct)
        self.line_fee.textChanged.connect(self.check_is_send_correct)
        self.line_sendamount1.textChanged.connect(self.check_is_send_correct)
        self.line_sendmemo1.textChanged.connect(self.check_is_send_correct)
        self.tabWidget.setCurrentIndex(0)
        self.utxos = []
        self.shreceived = []
        self.balances = []
        self.recaddresses = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(2000)
        self.update()
        self.show()
        
    def load_settings(self):
        with open('pyzcto.conf','r') as fd:
            options = [l.split('#')[0].split() for l in fd.readlines()]
            for o in options:
                self.settings[o[0]] = o[1]
        self.line_host.setText(self.settings['zcashd_host'])
        self.line_port.setText(self.settings['zcashd_port'])
        
    def check_is_send_correct(self):
        if self.get_send_data():
            self.sendButton.setEnabled(True)
        else:
            self.sendButton.setEnabled(False)
    
    def get_send_data(self):
        send_data = []
        if self.tabWidget_send.currentIndex() == 0:
            try:
                sendaddr = str(self.line_sendaccount1.text())
                availablefunds =  float(str(self.comboBox_sendaccounts.currentText()).split()[0])
                sendamount = float(str(self.line_sendamount1.text()))
                fee = float(str(self.line_fee.text()))
                memo = str(self.line_sendmemo1.text())
                is_zaddr = sendaddr[0] == 'z'
                if memo:
                    encmemo = ''.join('{:x}'.format(ord(c)) for c in str(memo))
            except:
                return False
            if availablefunds < sendamount + fee:
                return False
            if (not is_zaddr) and memo:
                return False
            if is_zaddr:
                isvalid = self.callzcash('z_validateaddress', [sendaddr])
                if memo:
                    send_data.append({'address':sendaddr, 'amount': sendamount, 'memo': encmemo})
                else:
                    send_data.append({'address':sendaddr, 'amount': sendamount})
            else:
                if memo:
                    return False
                isvalid = self.callzcash('validateaddress', [sendaddr])
                send_data.append({'address':sendaddr, 'amount': sendamount})
            if not isvalid['isvalid']:
                return False
        elif self.tabWidget_send.currentIndex() == 1:
            lines = str(self.plainTextEdit_sendmultiple.toPlainText())
            if not lines:
                return False
            try:
                availablefunds =  float(str(self.comboBox_sendaccounts.currentText()).split()[0])
                fee = float(str(self.line_fee.text()))
                for line in lines.split('\n'):
                    if ',' in line:
                        parsedline = line.split(',')
                        address = parsedline[0].replace(' ','')
                        value = float(parsedline[1].replace(' ',''))
                        if len(parsedline)>2:
                            memo = parsedline[2]
                            if memo:
                                encmemo = ''.join('{:x}'.format(ord(c)) for c in str(memo))
                        else:
                            memo = False
                    else:
                        prot = line.split(':')
                        if len(prot)>2 or prot[0] != 'zcash':
                            return False
                        prot = prot[1].split('?')
                        address = prot[0]
                        values = {k.split('=')[0]:k.split('=')[1] for k in prot[1].split('&')}
                        value = float(values['amount'])
                        memo = 'message' in values and values['message']
                        if memo:
                            memo = values['message']
                            encmemo = ''.join('{:x}'.format(ord(c)) for c in str(memo))
                    if address[0] == 'z':
                        isvalid = self.callzcash('z_validateaddress', [address])
                    else:
                        isvalid = self.callzcash('validateaddress', [address])
                        if memo:
                            return False
                    if not isvalid['isvalid']:
                        return False
                    fee += value
                    if memo:
                        send_data.append({'address':address, 'amount':value, 'memo':encmemo})
                    else:
                        send_data.append({'address':address, 'amount':value})
            except:
                return False
            if fee > availablefunds:
                return False
        return send_data
    
    def update(self):
        try:
            self.updatetrs()
            #self.updatehistorial()
            self.updatereceive()
            self.updatesendlist()
            self.updatestatus()
            self.statusBar.showMessage('Conected to {}:{}'.format(self.line_host.text(), self.line_port.text()))
        except:
            self.statusBar.showMessage('Not connected to daemon. Please check settings')
     
    def updatesendlist(self):
        if self.tabWidget_send.currentIndex() == 0:
            zaddresses = self.callzcash('z_listaddresses')
            unspent = self.callzcash('listunspent')
            traddresses = list(set([us['address'] for us in unspent if us['spendable']]))
            addresses = zaddresses + traddresses
            bals = []
            for ad in addresses:
                bal = self.callzcash('z_getbalance', [ad])
                bal = str(bal) + '\t'
                #bal += (14-len(str(bal)))*' '
                bals.append(bal+ad)
            if bals != self.balances:
                self.balances = bals
                self.comboBox_sendaccounts.clear()
                for bal in bals:
                    self.comboBox_sendaccounts.addItem(bal)
            
    def send(self):
        params = self.get_send_data()
        if not params:
            return
        fromaddress = str(self.comboBox_sendaccounts.currentText()).split()[-1]
        try:
            fee = float(str(self.line_fee.text()))
        except:
            return
        op = self.callzcash('z_sendmany', [fromaddress, params, 1, fee])
        self.donetext.appendPlainText(op)
        self.sendButton.setEnabled(False)
    
        
    def updatestatus(self):
        opresults = self.callzcash('z_getoperationresult')
        if opresults:
            self.donetext.appendPlainText(str(opresults))
        opstatus = self.callzcash('z_getoperationstatus')
        self.statustext.clear()
        if opstatus:
            self.statustext.appendPlainText(str(opstatus))
    
    def newtraddr(self):
        self.callzcash('getnewaddress')
        self.listaddresses_receive.clear()
        self.update()

    def newshaddr(self):
        self.callzcash('z_getnewaddress')
        self.listaddresses_receive.clear()
        self.update()
        
        
    def torconnect(self):
        if self.torconnectbutton.text() == '&Connect':
            self.torproc.setProcessChannelMode(QProcess.MergedChannels)
            self.torproc.start('tor', ['-f', 'torrc'])
            self.torproc.readyReadStandardOutput.connect(self.updatetor)
            self.torproc.waitForStarted()
            self.torconnectbutton.setText('&Disconnect')
            while not os.path.isfile('./hidden_service/hostname'):
                time.sleep(0.5)
            fd = open('./hidden_service/hostname')
            oniondom = fd.readline()
            fd.close()

            username = str(self.line_user.text())
            password = str(self.line_password.text())
            img = qrcode.make(username+':'+password+'@'+oniondom)
            img.save('qrcode.png', 'PNG')
            qrc = QPixmap('qrcode.png')
            os.remove('qrcode.png')
            self.onionlabelname.setText(username+':'+password+'@'+oniondom)
            self.onionlabelname.show()
            self.onionlabel.setPixmap(qrc.scaled(self.onionlabel.size(), Qt.KeepAspectRatio))
            self.onionlabel.show()
        else:
            self.torproc.terminate()
            self.torproc.waitForFinished()
            self.torconnectbutton.setText('&Connect')
            self.onionlabel.hide()
            self.onionlabelname.hide()
        
    def updatetor(self):
        self.torconsole.appendPlainText(str(self.torproc.readAllStandardOutput()))
        
    def updatehistorial(self):
        transactions = self.callzcash('listtransactions', ['',1000])
        rw = 0
        for tx in transactions:
            if tx['category']=='receive':
                table = self.transtable_input
            elif tx['category'] == 'send':
                table = self.transtable_output
            else:
                continue
            table.insertRow(rw)
            item = QTableWidgetItem(tx['txid'])
            item.setFlags(Qt.ItemFlags(97))
            table.setItem(rw, 3, item)
            timet = time.strftime('%b %d %Y, %H:%M', time.localtime(tx['time']))
            item = QTableWidgetItem(timet)
            item.setFlags(Qt.ItemFlags(97))
            table.setItem(rw, 0, item)
            if 'address' in tx:
                item = QTableWidgetItem(tx['address'])
                item.setFlags(Qt.ItemFlags(97))
                table.setItem(rw, 1, item)
            item = QTableWidgetItem(str(tx['amount']))
            item.setFlags(Qt.ItemFlags(97))
            table.setItem(rw, 2, item)
        self.transtable_input.resizeColumnsToContents()
        self.transtable_output.resizeColumnsToContents()
        
    
    def updatetrs(self):
        unspent = reversed(sorted([(u['confirmations'],u['address'], u['amount']) for u in self.callzcash('listunspent')]))
        unspent = [(u[1], u[2], colorfromconfs(u[0])) for u in unspent]
        shaddreses = self.callzcash('z_listaddresses')
        shtxs = []
        shbalance = 0.0
        for shad in shaddreses:
            txs = self.callzcash('z_listreceivedbyaddress', [shad])
            shbalance += self.callzcash('z_getbalance', [shad])
            for tx in txs:
                txdata = self.callzcash('gettransaction', [tx['txid']])
                memofield = bytearray.fromhex(tx['memo'])
                if memofield[0] == 246:
                    memofield = ''
                else:
                    memofield = memofield.decode().split('\x00')[0]
                shtxs.append((txdata['confirmations'], shad, tx['amount'], memofield))
        shtxs = [(t[1], t[2], t[3], colorfromconfs(t[0])) for t in reversed(sorted(shtxs))]
        if unspent != self.utxos or shtxs != self.shreceived:
            self.utxos = unspent
            self.tableWidget_traddr.setRowCount(0)
            trbalance = 0.0
            for us in self.utxos:
                self.tableWidget_traddr.insertRow(0)
                trbalance += us[1]
                item = QTableWidgetItem(us[0])
                item.setFlags(Qt.ItemFlags(97))
                item.setBackground(QBrush(QColor(us[-1][0],us[-1][1],us[-1][2])))
                self.tableWidget_traddr.setItem(0, 0, item)
                item = QTableWidgetItem(str(us[1]))
                item.setFlags(Qt.ItemFlags(97))
                item.setTextAlignment(Qt.AlignRight)
                item.setBackground(QBrush(QColor(us[-1][0],us[-1][1],us[-1][2])))
                self.tableWidget_traddr.setItem(0, 1, item)
            self.label_transparent_balance.setText('Transparent balance: {}'.format(trbalance))
            self.tableWidget_traddr.resizeColumnsToContents()
            self.shreceived = shtxs
            self.tableWidget_shaddr.setRowCount(0)
            for tr in shtxs:
                self.tableWidget_shaddr.insertRow(0)
                item = QTableWidgetItem(tr[0])
                item.setFlags(Qt.ItemFlags(97))
                if len(tr[2])>1:
                    item.setToolTip(tr[2])
                item.setBackground(QBrush(QColor(tr[-1][0],tr[-1][1],tr[-1][2])))
                self.tableWidget_shaddr.setItem(0, 0, item)
                item = QTableWidgetItem(str(tr[1]))
                item.setFlags(Qt.ItemFlags(97))
                item.setTextAlignment(Qt.AlignRight)
                if len(tr[2])>1:
                    item.setToolTip(tr[2])
                item.setBackground(QBrush(QColor(tr[-1][0],tr[-1][1],tr[-1][2])))
                self.tableWidget_shaddr.setItem(0, 1, item)
            self.tableWidget_shaddr.resizeColumnsToContents()
            self.label_shielded_balance.setText('Shielded balance: {}'.format(shbalance))
            self.label_total_balance.setText('Total balance: {}'.format(shbalance+trbalance))
    
    def updatereceive(self):
        shaddresses = self.callzcash('z_listaddresses')
        traddresses = self.callzcash('getaddressesbyaccount', [''])
        addresses = [str(self.callzcash('z_getbalance',[a]))+'\t' + a for a in traddresses+shaddresses]
        if self.recaddresses != addresses:
            self.recaddresses = addresses
            for ad in addresses:
                self.listaddresses_receive.insertItem(0, ad)
                
    def geneartereceiveqr(self):
        try:
            address = self.listaddresses_receive.currentItem().text()
        except:
            address = ''
        amount = self.line_receiveamount.text()
        comment = self.line_receivedesc.text()
        if address and amount:
            if comment:
                try:
                    string = 'zcash:{}?amount={}&message={}'.format(address,amount,comment)
                except:
                    self.label_qrreceive.hide()
                    self.label_textreceive.hide()
                    return
            else:
                string = 'zcash:{}?amount={}'.format(address,amount)
            img = qrcode.make(string)
            img.save('qrcode.png', 'PNG')
            qrc = QPixmap('qrcode.png')
            os.remove('qrcode.png')
            self.label_textreceive.setText(string)
            self.label_textreceive.show()
            self.label_qrreceive.setPixmap(qrc.scaled(self.onionlabel.size(), Qt.KeepAspectRatio))
            self.label_qrreceive.show()
        else:
            self.label_qrreceive.hide()
            self.label_textreceive.hide()
        
        

    def callzcash(self, method, params = []):
        url='http://'+str(self.line_host.text()) + ':' + str(self.line_port.text())
        user = str(self.line_user.text())
        passwd = str(self.line_password.text())
        user = user.encode('utf8')
        passwd = passwd.encode('utf8')
        timeout = 600
        jsondata = json.dumps({'version':'2', 'method': method, 'params': params, 'id': 0})
        r = requests.post(url, auth=(user,passwd), data=jsondata, timeout=timeout)
        return r.json()['result']

def colorfromconfs(confs):
    if confs>25:
        return (205,255,205)
    else:
        return (255 - 2*confs, 205+2*confs, 205)
        
if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = mainwindow()
    app.aboutToQuit.connect(window.torproc.terminate)
    sys.exit(app.exec_())
