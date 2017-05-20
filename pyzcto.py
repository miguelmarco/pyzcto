#!/usr/bin/python

import sys
from PyQt5.QtCore import Qt, QProcess, QTimer
from PyQt5.QtWidgets import QWidget, QApplication, QDialog, QMainWindow, QTableWidgetItem, QHeaderView
from PyQt5.QtGui import QPicture, QPixmap,QImage, QBrush, QColor
from PyQt5.uic import loadUi
import requests
import simplejson
import qrcode
import time
import os
from decimal import Decimal

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
        self.tableWidget_ownaddresses.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tableWidget_otheraddresses.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tableWidget_traddr.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tableWidget_shaddr.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.transtable_input.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.transtable_output.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.pushButton_importmultisig.setEnabled(False)
        self.pushButton_importmultisig.clicked.connect(self.importmultisig)
        self.torconnectbutton.clicked.connect(self.torconnect)
        self.pushButton_newtr.clicked.connect(self.newtraddr)
        self.pushButton_newsh.clicked.connect(self.newshaddr)
        self.sendButton.clicked.connect(self.send)
        self.listaddresses_receive.currentItemChanged.connect(self.geneartereceiveqr)
        self.line_receiveamount.textChanged.connect(self.geneartereceiveqr)
        self.line_receivedesc.textChanged.connect(self.geneartereceiveqr)
        self.plainTextEdit_sendmultiple.textChanged.connect(self.check_is_send_correct)
        self.comboBox_sendaccounts.currentIndexChanged.connect(self.check_is_send_correct)
        self.line_sendaccount1.currentTextChanged.connect(self.check_is_send_correct)
        self.line_fee.textChanged.connect(self.check_is_send_correct)
        self.line_sendamount1.textChanged.connect(self.check_is_send_correct)
        self.line_sendmemo1.textChanged.connect(self.check_is_send_correct)
        self.transtable_input.clicked.connect(self.show_transaction_details)
        self.transtable_output.clicked.connect(self.show_transaction_details)
        self.pushButton_addotheraddress.clicked.connect(self.tableWidget_otheraddresses.insertRow,0)
        self.pushButton_deleteotheraddress.clicked.connect(self.removerowfromaccounts)
        self.tableWidget_otheraddresses.cellChanged.connect(self.updateotheraccounts)
        self.tableWidget_otheraddresses.cellChanged.connect(self.updatelinesendaccount)
        self.plainTextEdit_multisigkeys.textChanged.connect(self.generatemultisig)
        self.spinBox_multisign.valueChanged.connect(self.generatemultisig)
        self.plainTextEdit_spendscript.textChanged.connect(self.verifymultisig)
        self.plainTextEdit_to_address_ms.textChanged.connect(self.createmultisigtx)
        self.comboBox_from_addr_ms.currentTextChanged.connect(self.createmultisigtx)
        self.plainTextEdit_raw_ms_tx.textChanged.connect(self.parserawhex)
        self.pushButton_ms_sign.clicked.connect(self.signrawtransaction)
        self.pushButton_ms_broadcast.clicked.connect(self.broadcastrawtransaction)
        self.tableWidget_ownaddresses.horizontalHeader().sectionClicked.connect(self.tableWidget_ownaddresses.sortByColumn)
        self.pushButton_add_multisig_addr.clicked.connect(self.addmultisigaddrtolist)
        self.tabWidget.setCurrentIndex(0)
        self.utxos = []
        self.shreceived = []
        self.balances = {}
        self.addressesalias = {}
        self.otheralias = {}
        self.transactions = []
        self.receiveaddresses = []
        self.sendadrresses = []
        self.readaliasesfromfile()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(2000)
        self.update()
        self.show()

    def createmultisigtx(self):
        try:
            fromaddress = self.comboBox_from_addr_ms.currentText().split()[-1]
            fee = Decimal(self.lineEdit_ms_fee.text())
            destinations = {}
            totalout = fee
            for l in self.plainTextEdit_to_address_ms.toPlainText().splitlines():
                address = l.split(',')[0]
                amount = Decimal(l.split(',')[1])
                totalout += amount
                destinations[address]=amount
            txouts = self.callzcash('listunspent', [1, 999999999, [fromaddress]])
            totalin = Decimal('0')
            txins = []
            while totalin < totalout:
                txout = txouts.pop()
                if txout['spendable']:
                    totalin += txout['amount']
                    txid = txout['txid']
                    vout = txout['vout']
                    txins.append({'txid':txid, 'vout':vout})
            change = totalin-totalout
            destinations[fromaddress] = change
            rawtrans = self.callzcash('createrawtransaction',[txins, destinations])
            try:
                self.plainTextEdit_raw_ms_tx.textChanged.disconnect(self.parserawhex)
            except:
                pass
            self.plainTextEdit_raw_ms_tx.clear()
            self.plainTextEdit_raw_ms_tx.appendPlainText(rawtrans)
            self.plainTextEdit_raw_ms_tx.textChanged.connect(self.parserawhex)
        except:
            try:
                self.plainTextEdit_raw_ms_tx.textChanged.disconnect(self.parserawhex)
            except:
                pass
            self.plainTextEdit_raw_ms_tx.clear()
            self.plainTextEdit_raw_ms_tx.textChanged.connect(self.parserawhex)

    def signrawtransaction(self):
        rawtrans = self.plainTextEdit_raw_ms_tx.toPlainText()
        signed = self.callzcash('signrawtransaction', [rawtrans])
        try:
            self.plainTextEdit_raw_ms_tx.textChanged.disconnect(self.parserawhex)
        except:
            pass
        self.plainTextEdit_raw_ms_tx.clear()
        self.plainTextEdit_raw_ms_tx.appendPlainText(signed['hex'])
        self.plainTextEdit_raw_ms_tx.textChanged.connect(self.parserawhex)
        if signed['complete']:
            self.pushButton_ms_broadcast.setEnabled(True)
        else:
            self.pushButton_ms_broadcast.setEnabled(False)



    def importmultisig(self):
        n = self.spinBox_multisign.value()
        addresses = str(self.plainTextEdit_multisigkeys.toPlainText()).splitlines()
        self.pushButton_importmultisig.setEnabled(False)
        self.update()


    def generatemultisig(self):
        try:
            n = self.spinBox_multisign.value()
            addresses = str(self.plainTextEdit_multisigkeys.toPlainText()).splitlines()
            try:
                self.spinBox_multisign.valueChanged.disconnect(self.generatemultisig)
            except:
                pass
            self.spinBox_multisign.setMaximum(len(addresses))
            self.spinBox_multisign.valueChanged.connect(self.generatemultisig)
            try:
                self.plainTextEdit_spendscript.textChanged.disconnect(self.verifymultisig)
            except:
                pass
            res = self.callzcash('createmultisig',[n, addresses])
            self.lineEdit_multisigaddress.setText(res['address'])
            availableaddresses = self.callzcash('getaddressesbyaccount', [""])
            if res['address'] in availableaddresses:
                self.pushButton_importmultisig.setEnabled(False)
            else:
                self.pushButton_importmultisig.setEnabled(True)
            self.plainTextEdit_spendscript.clear()
            self.plainTextEdit_spendscript.appendPlainText(res['redeemScript'])
            self.plainTextEdit_spendscript.textChanged.connect(self.verifymultisig)
        except:
            try:
                self.plainTextEdit_spendscript.textChanged.disconnect(self.verifymultisig)
            except:
                pass
            self.lineEdit_multisigaddress.clear()
            self.pushButton_importmultisig.setEnabled(False)
            self.plainTextEdit_spendscript.clear()
            self.plainTextEdit_spendscript.textChanged.connect(self.verifymultisig)

    def parserawhex(self):
        self.pushButton_ms_broadcast.setEnabled(False)
        rawhex = self.plainTextEdit_raw_ms_tx.toPlainText()
        res = self.callzcash('decoderawtransaction', [rawhex])
        try:
            self.plainTextEdit_to_address_ms.textChanged.disconnect(self.createmultisigtx)
            self.comboBox_from_addr_ms.currentTextChanged.disconnect(self.createmultisigtx)
        except:
            pass
        self.plainTextEdit_to_address_ms.clear()
        self.updatesendlist()
        self.plainTextEdit_to_address_ms.textChanged.connect(self.createmultisigtx)
        self.comboBox_from_addr_ms.currentTextChanged.connect(self.createmultisigtx)
        try:
            inputaddreses = []
            for vin in res['vin']:
                inputaddreses += self.callzcash('gettxout', [vin['txid'], vin['vout']])['scriptPubKey']['addresses']
            if len(set(inputaddreses)) == 1:
                address = inputaddreses[0]
                tex = ''
                if address in self.balances:
                    tex += self.balances[address]+'\t'
                alias = self.aliasofaddress(address)
                if alias != address:
                    tex += alias +'\t'
                tex += address
                try:
                    self.comboBox_from_addr_ms.currentTextChanged.disconnect(self.createmultisigtx)
                except:
                    pass
                self.comboBox_from_addr_ms.setCurrentText(tex)
                self.comboBox_from_addr_ms.currentTextChanged.connect(self.createmultisigtx)
            outputs = res['vout']
            for output in outputs:
                adr = output['scriptPubKey']['addresses']
                if len(adr)>1:
                    try:
                        self.plainTextEdit_to_address_ms.textChanged.disconnect(self.createmultisigtx)
                        self.comboBox_from_addr_ms.currentTextChanged.disconnect(self.createmultisigtx)
                    except:
                        pass
                    self.plainTextEdit_to_address_ms.clear()
                    self.updatesendlist()
                    self.plainTextEdit_to_address_ms.textChanged.connect(self.createmultisigtx)
                    self.comboBox_from_addr_ms.currentTextChanged.connect(self.createmultisigtx)
                    return
                value = output['value']
                if adr[0] !=address:
                    try:
                        self.plainTextEdit_to_address_ms.textChanged.disconnect(self.createmultisigtx)
                        self.comboBox_from_addr_ms.currentTextChanged.disconnect(self.createmultisigtx)
                    except:
                        pass
                    self.plainTextEdit_to_address_ms.appendPlainText(adr[0]+','+str(value))
                    self.plainTextEdit_to_address_ms.textChanged.connect(self.createmultisigtx)
                    self.comboBox_from_addr_ms.currentTextChanged.connect(self.createmultisigtx)
        except:
            pass

    def verifymultisig(self):
        try:
            script = str(self.plainTextEdit_spendscript.toPlainText())
            res = self.callzcash('decodescript', [script])
            try:
                self.plainTextEdit_multisigkeys.textChanged.disconnect(self.generatemultisig)
            except:
                pass
            self.plainTextEdit_multisigkeys.clear()
            for l in res['addresses']:
                self.plainTextEdit_multisigkeys.appendPlainText(l)
            self.plainTextEdit_multisigkeys.textChanged.connect(self.generatemultisig)
            self.spinBox_multisign.valueChanged.disconnect(self.generatemultisig)
            self.spinBox_multisign.setMaximum(len(res['addresses']))
            self.spinBox_multisign.setValue(res['reqSigs'])
            self.spinBox_multisign.valueChanged.connect(self.generatemultisig)
            self.lineEdit_multisigaddress.setText(res['p2sh'])
            availableaddresses = self.callzcash('getaddressesbyaccount', [""])
            if res['p2sh'] in availableaddresses:
                self.pushButton_importmultisig.setEnabled(False)
            else:
                self.pushButton_importmultisig.setEnabled(True)
        except:
            self.lineEdit_multisigaddress.clear()
            self.pushButton_importmultisig.setEnabled(False)
            try:
                self.plainTextEdit_multisigkeys.textChanged.disconnect(self.generatemultisig)
            except:
                pass
            self.plainTextEdit_multisigkeys.clear()
            self.plainTextEdit_multisigkeys.textChanged.connect(self.generatemultisig)

    def addmultisigaddrtolist(self):
        addr = self.comboBox__send_ms_addr.currentText().split()[-1]
        amount = self.lineEdit_send_ms_amount.text()
        self.plainTextEdit_to_address_ms.appendPlainText(addr+','+amount)

    def broadcastrawtransaction(self):
        hex = self.plainTextEdit_raw_ms_tx.toPlainText()
        self.callzcash('sendrawtransaction', [hex])
        self.pushButton_ms_broadcast.setEnabled(False)


    def updateotheraccounts(self):
        self.otheralias = {}
        r = self.tableWidget_otheraddresses.rowCount()
        for i in range(r):
            try:
                ad = self.tableWidget_otheraddresses.item(i,2).text()
            except:
                ad = '..'
            if len(ad)<3:
                ad = '..'
            typ = ''
            validate = 'validateaddress'
            if ad[0]=='z':
                typ = 'Shielded'
                validate = 'z_validateaddress'
            elif ad[1] in '1m':
                typ = 'Transparent'
            elif ad[1] in '23':
                typ = 'Multisig'
            try:
                valid = self.callzcash(validate, [ad])['isvalid']
                if not valid:
                    typ = 'Invalid'
            except:
                typ = ''
            if not  self.tableWidget_otheraddresses.item(i,0) or self.tableWidget_otheraddresses.item(i,0).text() != typ:
                item = QTableWidgetItem(typ)
                item.setTextAlignment(Qt.AlignRight)
                item.setFlags(Qt.ItemFlags(97))
                self.tableWidget_otheraddresses.setItem(i,0,item)
            alias = self.tableWidget_otheraddresses.item(i,1)
            if alias:
                self.otheralias[ad]=alias.text()
        with open('addresses.ext','w') as fd:
            for ad in self.otheralias:
                fd.write(ad+' '+self.otheralias[ad]+'\n')

    def removerowfromaccounts(self):
        self.tableWidget_otheraddresses.removeRow(self.tableWidget_otheraddresses.currentRow())
        self.updateotheraccounts()
        self.updatelinesendaccount()

    def show_transaction_details(self):
        table = self.sender()
        row = table.currentRow()
        txid = str(table.item(row, 3).text())
        data = self.callzcash('gettransaction', [txid])
        self.transtext.clear()
        self.transtext.appendPlainText(simplejson.dumps(data, indent=4))

    def get_balances(self):
        zaddresses = self.callzcash('z_listaddresses')
        unspent = self.callzcash('listunspent')
        traddresses = list(self.callzcash('getaddressesbyaccount', ['']))
        addresses = zaddresses + traddresses
        bals = {}
        for ad in addresses:
            bal = self.callzcash('z_getbalance', [ad])
            bal = str(bal)
            if bal == '0E-8':
                bal = '0.00000000'
            #bal += (14-len(str(bal)))*' '
            bals[ad]=bal
        return bals

    def get_utxos(self):
        unspent = reversed(sorted([(u['confirmations'],u['address'], u['amount']) for u in self.callzcash('listunspent')]))
        unspent = [(u[1], u[2], colorfromconfs(u[0])) for u in unspent]
        return unspent

    def get_shreceieved(self):
        shaddreses = self.callzcash('z_listaddresses')
        shtxs = []
        for shad in shaddreses:
            txs = self.callzcash('z_listreceivedbyaddress', [shad])
            for tx in txs:
                txdata = self.callzcash('gettransaction', [tx['txid']])
                memofield = bytearray.fromhex(tx['memo'])
                if memofield[0] == 246:
                    memofield = ''
                else:
                    memofield = memofield.decode().split('\x00')[0]
                shtxs.append((txdata['confirmations'], shad, tx['amount'], memofield))
        shtxs = [(t[1], t[2], t[3], colorfromconfs(t[0])) for t in reversed(sorted(shtxs))]
        return shtxs

    def get_aliases(self):
        aliases = {}
        rows = self.tableWidget_ownaddresses.rowCount()
        for r in range(rows):
            ad = str(self.tableWidget_ownaddresses.item(r,3).text())
            al = self.tableWidget_ownaddresses.item(r,2).text()
            if al:
                aliases[ad]=al
        return aliases

    def readaliasesfromfile(self):
        with open('addresses') as fd:
            lines = fd.readlines()
            for line in lines:
                address = line.split()[0]
                alias = line[len(address)+1:].replace('\n','')
                self.addressesalias[address]=alias
            self.updatelinesendaccount()
        otheralias = {}
        with open('addresses.ext') as fd:
            lines = fd.readlines()
            for line in lines:
                address = line.split()[0]
                alias = line[len(address)+1:].replace('\n','')
                otheralias[address]=alias
        self.tableWidget_otheraddresses.setRowCount(0)
        for ad in otheralias:
            self.tableWidget_otheraddresses.insertRow(0)
            alias = otheralias[ad]
            if alias == ad:
                alias = ''
            item = QTableWidgetItem(alias)
            item.setTextAlignment(Qt.AlignRight)
            self.tableWidget_otheraddresses.setItem(0,1,item)
            item = QTableWidgetItem(ad)
            self.tableWidget_otheraddresses.setItem(0,2,item)

    def aliasofaddress(self, address):
        if address in self.addressesalias:
            return self.addressesalias[address]
        elif address in self.otheralias:
            return self.otheralias[address]
        else:
            return address

    def savealiases(self):
        with open('addresses','w') as fd:
            for ad in self.addressesalias:
                fd.write(ad+' '+self.addressesalias[ad]+'\n')

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

    def updatelinesendaccount(self):
        self.line_sendaccount1.clear()
        self.comboBox__send_ms_addr.clear()
        self.line_sendaccount1.addItem('')
        self.comboBox__send_ms_addr.addItem('')
        for al in self.addressesalias:
            self.line_sendaccount1.addItem(self.aliasofaddress(al)+'\t'+al)
            self.comboBox__send_ms_addr.addItem(self.aliasofaddress(al)+'\t'+al)
        for al in self.otheralias:
            self.line_sendaccount1.addItem(self.otheralias[al]+'\t'+al)
            self.comboBox__send_ms_addr.addItem(self.otheralias[al]+'\t'+al)

    def get_send_data(self):
        send_data = []
        if self.tabWidget_send.currentIndex() == 0:
            try:
                sendaddr = str(self.line_sendaccount1.currentText()).split()[-1]
                availablefunds =  Decimal(str(self.comboBox_sendaccounts.currentText()).split()[0])
                sendamount = Decimal(str(self.line_sendamount1.text()))
                fee = Decimal(str(self.line_fee.text()))
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
                availablefunds =  Decimal(str(self.comboBox_sendaccounts.currentText()).split()[0])
                fee = Decimal(str(self.line_fee.text()))
                for line in lines.split('\n'):
                    if ',' in line:
                        parsedline = line.split(',')
                        address = parsedline[0].replace(' ','')
                        value = Decimal(parsedline[1].replace(' ',''))
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
                        value = Decimal(values['amount'])
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
            tocall = set([])
            transactions = self.gettransactions()
            if transactions != self.transactions:
                self.transactions = transactions
                tocall.add(self.updatehistorial)
            aliases = self.get_aliases()
            if self.tableWidget_ownaddresses.rowCount()>0 and self.addressesalias != aliases:
                self.addressesalias = aliases
                tocall.add(self.updatereceive)
                tocall.add(self.updatesendlist)
                tocall.add(self.updatetrs)
                tocall.add(self.updatehistorial)
                tocall.add(self.savealiases)
                tocall.add(self.updatelinesendaccount)
            utxos = self.get_utxos()
            if utxos != self.utxos:
                tocall.add(self.updatetrs)
                self.utxos = utxos
            shreceived = self.get_shreceieved()
            if shreceived != self.shreceived:
                self.shreceived = shreceived
                tocall.add(self.updatetrs)
            balances = self.get_balances()
            if balances != self.balances:
                self.balances = balances
                tocall.add(self.updatesendlist)
                tocall.add(self.updatereceive)
                tocall.add(self.updatealiases)
            for c in tocall:
                c.__call__()
            self.updatestatus()
            self.statusBar.showMessage('Conected to {}:{}'.format(self.line_host.text(), self.line_port.text()))
        except:
            self.statusBar.showMessage('Not connected to daemon. Please check settings')

    def updatesendlist(self):
        self.sendadrresses = []
        self.comboBox_sendaccounts.clear()
        self.comboBox__send_ms_addr.clear()
        self.comboBox_from_addr_ms.clear()
        self.comboBox_from_addr_ms.addItem('')
        self.comboBox__send_ms_addr.addItem('')
        for bal in self.balances:
            self.comboBox_sendaccounts.addItem(self.balances[bal]+ '\t' +self.aliasofaddress(bal))
            if self.aliasofaddress(bal) != bal:
                self.comboBox__send_ms_addr.addItem(self.balances[bal]+ '\t' +self.aliasofaddress(bal) + '\t' + bal)
            else:
                self.comboBox__send_ms_addr.addItem(self.balances[bal]+'\t\t' + bal)
            self.sendadrresses.append(bal)
            if not bal[0] == 'z' and not bal[1] in '1m':
                alias = self.aliasofaddress(bal)
                if alias == bal:
                    self.comboBox_from_addr_ms.addItem(self.balances[bal]+ '\t' + bal)
                else:
                    self.comboBox_from_addr_ms.addItem(self.balances[bal]+ '\t' +alias+ '\t' + bal)



    def send(self):
        params = self.get_send_data()
        if not params:
            return
        fromaddress = self.sendadrresses[self.comboBox_sendaccounts.currentIndex()]
        try:
            fee = Decimal(str(self.line_fee.text()))
        except:
            return
        op = self.callzcash('z_sendmany', [fromaddress, params, 1, fee])
        self.donetext.appendPlainText(op)
        self.sendButton.setEnabled(False)

    def updatestatus(self):
        opresults = self.callzcash('z_getoperationresult')
        if opresults:
            self.donetext.appendPlainText(simplejson.dumps(opresults,indent=4))
        opstatus = self.callzcash('z_getoperationstatus')
        if opstatus:
            opstr = simplejson.dumps(opstatus,indent=4)
            if str(self.statustext.toPlainText()) != opstr:
                self.statustext.clear()
                self.statustext.appendPlainText(opstr)
        else:
            self.statustext.clear()

    def newtraddr(self):
        self.listaddresses_receive.clear()
        self.updatereceive()
        self.update()

    def newshaddr(self):
        self.callzcash('z_getnewaddress')
        self.listaddresses_receive.clear()
        self.updatereceive()
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

    def gettransactions(self):
        trans = []
        transactions = self.callzcash('listtransactions', ['', 1000])
        for tx in transactions:
            if 'address' in tx:
                address = tx['address']
            else:
                address = False
            tx2 = [tx['category'], tx['txid'], tx['time'], address, tx['amount'], colorfromconfs(tx['confirmations'])]
            trans.append(tx2)
        return trans

    def updatehistorial(self):
        rw = 0
        self.transtable_input.setRowCount(0)
        self.transtable_output.setRowCount(0)
        for tx in self.transactions:
            if tx[0]=='receive':
                table = self.transtable_input
            elif tx[0] == 'send':
                table = self.transtable_output
            else:
                continue
            table.insertRow(rw)
            item = QTableWidgetItem(tx[1])
            item.setFlags(Qt.ItemFlags(97))
            item.setBackground(QBrush(QColor(tx[-1][0],tx[-1][1],tx[-1][2])))
            table.setItem(rw, 3, item)
            timet = time.strftime('%b %d %Y, %H:%M', time.localtime(tx[2]))
            item = QTableWidgetItem(timet)
            item.setFlags(Qt.ItemFlags(97))
            item.setBackground(QBrush(QColor(tx[-1][0],tx[-1][1],tx[-1][2])))
            table.setItem(rw, 0, item)
            if tx[2]:
                item = QTableWidgetItem(self.aliasofaddress(tx[3]))
                item.setFlags(Qt.ItemFlags(97))
                item.setBackground(QBrush(QColor(tx[-1][0],tx[-1][1],tx[-1][2])))
                table.setItem(rw, 1, item)
            item = QTableWidgetItem(str(tx[4]))
            item.setFlags(Qt.ItemFlags(97))
            item.setBackground(QBrush(QColor(tx[-1][0],tx[-1][1],tx[-1][2])))
            table.setItem(rw, 2, item)
        #self.transtable_input.resizeColumnsToContents()
        #self.transtable_output.resizeColumnsToContents()

    def updatetrs(self):
        self.tableWidget_traddr.setRowCount(0)
        trbalance = Decimal('0.0')
        shbalance = Decimal(self.callzcash('z_gettotalbalance')['private'])
        for us in self.utxos:
            self.tableWidget_traddr.insertRow(0)
            trbalance += us[1]
            item = QTableWidgetItem(self.aliasofaddress(us[0]))
            item.setFlags(Qt.ItemFlags(97))
            item.setBackground(QBrush(QColor(us[-1][0],us[-1][1],us[-1][2])))
            self.tableWidget_traddr.setItem(0, 0, item)
            item = QTableWidgetItem(str(us[1]))
            item.setFlags(Qt.ItemFlags(97))
            item.setTextAlignment(Qt.AlignRight)
            item.setBackground(QBrush(QColor(us[-1][0],us[-1][1],us[-1][2])))
            self.tableWidget_traddr.setItem(0, 1, item)
        self.label_transparent_balance.setText('Transparent balance: {}'.format(trbalance))
        #self.tableWidget_traddr.resizeColumnsToContents()
        self.tableWidget_shaddr.setRowCount(0)
        for tr in self.shreceived:
            self.tableWidget_shaddr.insertRow(0)
            item = QTableWidgetItem(self.aliasofaddress(tr[0]))
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
        #self.tableWidget_shaddr.resizeColumnsToContents()
        self.label_shielded_balance.setText('Shielded balance: {}'.format(shbalance))
        self.label_total_balance.setText('Total balance: {}'.format(shbalance+trbalance))

    def updatealiases(self):
        self.tableWidget_ownaddresses.setRowCount(0)
        for ad in self.balances:
            bal = self.balances[ad]
            self.tableWidget_ownaddresses.insertRow(0)
            item = QTableWidgetItem(bal)
            item.setTextAlignment(Qt.AlignRight)
            item.setFlags(Qt.ItemFlags(97))
            self.tableWidget_ownaddresses.setItem(0,0,item)
            typ = ''
            if ad[0]=='z':
                typ = 'Shielded'
            elif ad[1] in '1m':
                typ = 'Transparent'
            elif ad[1] in '23':
                typ = 'Multisig'
            item = QTableWidgetItem(typ)
            item.setTextAlignment(Qt.AlignRight)
            item.setFlags(Qt.ItemFlags(97))
            self.tableWidget_ownaddresses.setItem(0,1,item)
            alias = self.aliasofaddress(ad)
            if alias == ad:
                alias = ''
            item = QTableWidgetItem(alias)
            #item.setTextAlignment(Qt.AlignRight)
            self.tableWidget_ownaddresses.setItem(0,2,item)
            item = QTableWidgetItem(ad)
            item.setFlags(Qt.ItemFlags(97))
            self.tableWidget_ownaddresses.setItem(0,3,item)

    def updatereceive(self):
        self.listaddresses_receive.clear()
        self.receiveaddresses = []
        for ad in self.balances:
            bal = self.balances[ad]
            self.receiveaddresses= [ad]+self.receiveaddresses
            self.listaddresses_receive.insertItem(0, bal+'\t'+self.aliasofaddress(ad))

    def geneartereceiveqr(self):
        try:
            address = self.receiveaddresses[self.listaddresses_receive.currentIndex().row()]
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
        jsondata = simplejson.dumps({'version':'2', 'method': method, 'params': params, 'id': 0})
        r = requests.post(url, auth=(user,passwd), data=jsondata, timeout=timeout)
        return simplejson.loads(r.text, use_decimal=True)['result']

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
