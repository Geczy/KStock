import logging, sys
logFormat = logging.Formatter('%(name)s _ %(levelname)s _ %(message)s')
rootLog = logging.getLogger()
rootLog.setLevel(logging.INFO)

fileHandler = logging.FileHandler('TradeLogs.log')
fileHandler.setFormatter(logFormat)
rootLog.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormat)
rootLog.addHandler(consoleHandler)

#logging.basicConfig(filename = 'TradeLogs.log', filemode = 'w', 
#       format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level = logging.INFO)

import os, datetime, pytz, holidays, json, requests, sys
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from PyQt5.QtWidgets import QMenu, QTableWidget
from PyQt5 import uic, QtCore, QtGui
from ObjList import ObjListTableModel, ObjListTable
from Robinhood import Robinhood, exceptions
import resources.gfc as gfc
from resources.NASDAQ import tickCurrents
from Helpers import *
import pyqtgraph as pg
from Tick import Tick
from Worker import *
import pandas as pd

TESTING = True

form, base = uic.loadUiType('ui/KStock.ui')

class MainWindow(base, form):
    def __init__(self):
        super(base, self).__init__()
        self.setupUi(self)

        testWin = InitTest(self)
        if not testWin.exec_(): 
            self.close()
            sys.exit()

        self.currStrat = 'ST'
        self.qTicks, self.hTicks = [], []
        self.graphData = [[],[]]
        self.qModel, self.hModel = None, None

        #Sets the eastern timezone
        self.tz = pytz.timezone('US/Eastern')

        #List of company names for use later
        self.comps = pd.read_csv('./resources/companyList.csv', sep = ',')[['Symbol', 'Name']]

        #The pool where all the hard calculations and GETS take place
        self.pool = QtCore.QThreadPool()
        logging.info('Max threads: ' + str(self.pool.maxThreadCount()))

        #Signal handling
        self.addQ.clicked.connect(self.addQueue)
        self.startBut.clicked.connect(self.tradeActs)
        self.pauseBut.clicked.connect(self.tradeActs)
        self.actionAPI.triggered.connect(self.api)

        #Create Context Menu if right clicked
        self.queue.setContextMenuPolicy(
            QtCore.Qt.CustomContextMenu)
        self.queue.customContextMenuRequested.connect(
            self.queueContext)

        #Graph options
        self.ePen = pg.mkPen(color = 'b', width = 2)
        self.graph.hideAxis('bottom')

        #Sets up the Robinhood API from the config file if it exists and is correct
        if os.path.isfile('core.cfg'):
            logging.info('Config File Found')
            with open('core.cfg', 'r') as fileIn:
                try:
                    data = json.load(fileIn)
                    self.rUser = data['API']['User']
                    self.rPass = data['API']['Password']
                    self.qTicks = [Tick(tick, self.purPrice.value()) for tick in data['Queue']]
                        
                    try:
                        self.trader = Robinhood()
                        self.trader.login(username = self.rUser, password = self.rPass)
                        logging.info('Successfully Logged Into Robinhood')
                        
                        self.startup()
                        self.update()
                        
                        #Starts both background threads
                        timer = TimeThread(self)
                        timer.update.connect(self.update)
                        timer.start()
                        

                    except (requests.exceptions.HTTPError, exceptions.LoginFailed):
                        logging.error('Unsuccessful Login For Robinhood')
                        self.warn('Login Fail')

                except json.decoder.JSONDecodeError as e:
                    logging.error(str(e))
                    self.warn('Corrupt')
                    self.rUser, self.rPass, self.qTicks = [], [], []
                    self.trader = None
        else:
            self.warn('No CFG')  
        

    def startup(self):
        '''
        Defines the appropriate columns and types for the tables
        Also defines the models for the tables

        Args:
            None

        Returns:
            None
        '''
        qproperties = [
            {'attr' : 'T', 'header' : 'Ticker'},
            {'attr' : 'C', 'header' : 'Price'},
            {'attr' : 'PQ', 'header' : 'Qty to Buy'},
        ]
        hproperties = [
            {'attr' : 'T', 'header' : 'Ticker'},
            {'attr' : 'C', 'header' : 'Price'},
            {'attr' : 'Q', 'header' : 'Quantity'},
            {'attr' : 'AP', 'header' : 'Avg Price'},
            {'attr' : 'SL', 'header' : 'Stop Loss'}
        ]

        #These models are neat because they actually contain the Tick objects, not just data
        #When adding to a table, you're adding the actual Tick to it
        self.qModel = ObjListTableModel(self.qTicks, qproperties, isRowObjects = True, isDynamic = True)
        self.hModel = ObjListTableModel(self.hTicks, hproperties, isRowObjects = True, isDynamic = True)

        self.holding.setModel(self.hModel)
        self.queue.setModel(self.qModel)


    def warn(self, warn):
        '''
        Calls a QDialog to warn about something

        Args:
            warn (str): warning to...uh...warn about

        Returns:
            None
        '''
        warnMessage = {
            'Login Fail' : 'Login Failed for Robinhood',
            'No CFG' : 'No .cfg File Found\nManually Input API Info in Settings > API',
            'Corrupt' : 'The .cfg File Seems to be Corrupt, Re-Input API Info',
            'Near Thresh' : 'Inching Close to Minimum Non-Margin Amount of {}'.format(self.marginSpin.value()),
            'Below Thresh' : 'Non-Margin Fell Below Minimum, Stopping Trading',
            'General' : 'Something Went Wrong With the Execution'
        }

        QMessageBox.critical(None, warn, warnMessage[warn], QMessageBox.Ok)


    def api(self):
        '''
        Sets up the API to RH if able, otherwise warns

        Args:
            None

        Returns:
            None
        '''
        api = Api(self)
        if api.exec_():
            self.rUser = api.user
            self.rPass = api.password
            logging.info('Successfully Created Keys and Config')
            self.trader = Robinhood()
            try:
                self.trader.login(username = self.rUser, password = self.rPass)
                logging.info('Successfully Logged Into Robinhood')
                if not self.qModel:
                    self.startup()
                self.update()
            except requests.exceptions.HTTPError:
                logging.error('Unsuccessful Login For Robinhood')
                self.warn('Login Fail')
                self.api()


    def afterHours(self):
        '''
        Determines whether the market is open (0930-1600, weekdays, non-federal holidays)

        Args:
            None

        Returns:
            (bool): True if market closed, else False
        '''
        us_holidays = holidays.US()
        now = datetime.datetime.now(self.tz)
        openTime = datetime.time(hour = 9, minute = 30, second = 0, tzinfo = self.tz)
        closeTime = datetime.time(hour = 16, minute = 0, second = 0, tzinfo = self.tz)
        return True if (now.strftime('%Y-%m-%d') in us_holidays or \
            ((now.time() < openTime) or (now.time() > closeTime))) else False


    def tradeActs(self):
        '''
        Disables/Enables Trading Start/Stop buttons
        Basically starts the whole trading process if `startBut` is disabled

        Args:
            None

        Returns:
            None
        '''
        if not TESTING:
            if not self.afterHours():
                self.startBut.setEnabled(True)
            else:
                self.startBut.setEnabled(False)
        else:
            self.startBut.setEnabled(not self.startBut.isEnabled())
        self.pauseBut.setEnabled(not self.startBut.isEnabled())

        if not self.startBut.isEnabled():
            logging.info('----Started Trading----')
        else:
            logging.info('----Paused Trading----')



    def queueContext(self, pos):
        '''
        Creates the context menu for the Queue

        Args:
            pos (QModelIndex): index of the selected row

        Returns:
            None
        '''
        if self.qModel.rowCount() > 0:
            menu = QMenu()
            buyX = menu.addAction('Buy Tick')
            delX = menu.addAction('Remove From Queue')

            action = menu.exec_(self.queue.mapToGlobal(pos))
            rowTick = self.qTicks[self.queue.rowAt(pos.y())]

            if action == delX:
                #Removes row from table
                logging.info('Removed {} From Queue'.format(rowTick.T))
                self.qModel.removeRow(self.qTicks.index(rowTick))
                self.qTicks.remove(rowTick)


            if action == buyX:
                reply = QMessageBox.question(
                    None, 
                    'Purchase?', 
                    'Purchase {} shares of {} for at {}'.format(rowTick.PQ, rowTick.T, rowTick.C),
                    QMessageBox.Yes, QMessageBox.No)

                if reply == QMessageBox.Yes:
                    try:
                        rowTick.purchase(purPrice = self.purPrice.value(), tradeStrat = self.currStrat, forced = True)
                        self.totalCost.setText('%.2f' % (float(self.totalCost.text()) - float(rowTick.Q * rowTick.AP)))
                        self.transTable.bought(rowTick)
                        self.hTicks.append(rowTick)
                        self.qTicks.remove(rowTick)

                        self.hModel.layoutChanged.emit()
                        self.queue.viewport().update()
                    except TypeError:
                        self.warn('General')




    def purchase(self, ticker):
        '''
        Purchases the stock by removing it from the Queue, placing it on the Holding table and 
        making the Robninhood call

        Args:
            ticker (Tick): Tick object of ticker we're actually purchasing

        Returns:
            None
        '''
        if not TESTING:
            self.trader.place_limit_buy_order(symbol = ticker.T, time_in_force = 'GFD', price = ticker.C, quantity = ticker.PQ)
            
        self.transTable.bought(ticker)
        self.hTicks.append(ticker)
        self.qTicks.remove(ticker)

        self.totalCost.setText('%.2f' % (float(self.totalCost.text()) - float(ticker.Q * ticker.AP)))


        return True


    def sell(self, ticker):
        '''
        Sells the stock by removing it from the Holding, placing it on the Queue, if re-buy and 
        making the Robninhood call

        Args:
            ticker (Tick): Tick object of ticker we're actually purchasing

        Returns:
            None
        '''
        if not TESTING:
            #makes robinhood call ....
            self.trader.place_limit_sell_order(symbol = ticker.T, time_in_force = 'GFD', price = ticker.C, quantity = ticker.PQ)

        logging.info(
            '----Sold {} shares of {} at {}----'.format(
                ticker.Q, ticker.T, ticker.C
        ))

        indprofit = float(ticker.Q * ticker.C) - float(ticker.Q * ticker.AP)      
        profitLabel = float(self.profitLabel.text()) + indprofit
           
        logging.info('----{} Profit: {}----'.format(ticker.T, round(indprofit, 2)))
        self.profitLabel.setText('%.2f' % (profitLabel))
        self.totalCost.setText('%.2f' % (float(self.totalCost.text()) + (ticker.Q * ticker.C)))

        if self.rebuy.isChecked():
            self.qTicks.append(ticker)
            self.qModel.layoutChanged.emit()
            #self.queue.viewport().update()

        self.hTicks.remove(ticker)
        self.hModel.layoutChanged.emit()
        
        return True


    def update(self):
        #The main update function, gets called every 5 seconds
        #Contains the child call functions

        def _success(worker):
            #Called when one of the workers is successfully completed
            return


        def _error(worker):
            #Called if there was an error
            logging.error('Error with the {}'.format(worker))


        def _holdCall():
            '''
            Performs all the necessaries for the Holdings table, is put in a worker
            and executes in the background

            Args:
                None

            Returns:
                None
            '''
            #I'm not happy with this yet so I'm leaving it out
            '''
            if not TESTING: 
                #Gathers all current Robinhood holdings, deems them untradable and is used just for visualization
                #Can be set to tradeable if desired
                for pos in self.trader.positions()['results']:
                    inst = self.trader.instrument(pos['instrument'].split('/')[-2])
                    if float(pos['quantity']) > 0:
                        ticker = Tick(inst['symbol'], self.purPrice.value())
                        ticker.purchase((pos['quantity'], pos['average_buy_price'], None))
                        self.hTicks.append(ticker)
                        self.hModel.layoutChanged.emit()
                        #self.holding.viewport().update()
            '''
            if not self.startBut.isEnabled():
                for tick in self.hTicks:
                    if tick.tradeable:
                        logging.info('Hold {}'.format(tick.T))
                        if tick.sell(self.purPrice.value(), self.currStrat):
                            self.sell(tick)
            else:
                for tick in self.qTicks:
                    tick.update(self.purPrice.value())



        def _queueCall():
            '''
            Performs all the necessaries for the Queue table, is put in a worker
            and executes in the background

            Args:
                None

            Returns:
                None
            '''
            if not self.startBut.isEnabled():
                for tick in self.qTicks:
                    logging.info('Queue {}'.format(tick.T))
                    if not TESTING:
                        if float(self.marginLabel.text()) - (ticker.C * ticker.PQ) < self.purLimit.value():
                            logging.info('====Purhcase of {} will exceed budget, cancelling purchase===='.format(ticker.T
                            ))
                            if tick.purchase(self.purPrice.value(), self.currStrat):
                                if self.purchase(tick):
                                    logging.info(
                                        '----Bought {} shares of {} at {}, SL: {}----'.format(
                                            tick.Q, tick.T, tick.AP, tick.SL
                                    )) 
                    else:
                        if tick.purchase(self.purPrice.value(), self.currStrat):
                            if self.purchase(tick):
                                logging.info(
                                    '----Bought {} shares of {} at {}, SL: {}----'.format(
                                        tick.Q, tick.T, tick.AP, tick.SL
                                ))
            else:
                for tick in self.qTicks:
                    tick.update(self.purPrice.value())

        #Determines the trading strategy, based on the time of day
        now = datetime.datetime.now(self.tz).time()
        opening = datetime.time(hour = 9, minute = 30, second = 0, tzinfo = self.tz)
        ten_fifteen = datetime.time(hour = 10, minute = 15, second = 0, tzinfo = self.tz)
        if opening < now < ten_fifteen:
            #Price Swing Strategy
            self.currStrat = 'PS'
        else:
            #Short Trading
            self.currStrat = 'ST'

        #Robinhood portfolio
        self.portfolio = self.trader.portfolios()

        #Set the Equity to current value depending on if it's aH or not
        if self.afterHours():
            self.holdLabel.setText('%.2f' % (float(self.portfolio['extended_hours_equity'])))

            #Disable Trading aH
            if not self.startBut.isEnabled():
                self.tradeActs()

        else:
            self.holdLabel.setText('%.2f' % (float(self.portfolio['equity'])))

            #Plt that stuff if it's during the trading day
            self.graphData[0].append(now.strftime('%H:%M:%S'))
            self.graphData[1].append(float(self.portfolio['equity']))
            xdict = dict(enumerate(self.graphData[0]))
            ax = self.graph.getAxis('bottom')
            ax.setTicks([xdict.items()])
            self.graph.plot(list(xdict.keys()), self.graphData[1], pen = self.ePen, clear = False)

        self.marginLabel.setText('%.2f' % (float(self.portfolio['withdrawable_amount'])))
        
        if not self.startBut.isEnabled():
            #If end of day approaching, close out all positions regardless of profit
            #To keep them until tomorrow, just turn off trading before 1658 (03:58 PM)
            if now > datetime.time(hour = 15, minute = 58, second = 0, tzinfo = self.tz):
                if self.hModel.rowCount() > 0:
                    logging.info('----Markets are about to close, selling all positions----')
                    for ticker in self.hTicks:
                        if ticker.tradeable:
                            self.sell(ticker)

        if not TESTING:
            #Safety-net for SEC guideline of >25000 on Non-Margin for day trading
            if self.marginSpin.value() < float(self.marginLabel.text()) < self.marginSpin.value() + 100:
                self.warn('Near Thresh')
            if float(self.marginLabel.text()) < self.marginSpin.value():
                logging.info('#### Non-Margin Fell Below Threshold ####')
                self.warn('Below Thresh')
                self.tradeActs()
        

        holdWorker = Worker(_holdCall)
        holdWorker.signals.finished.connect(lambda : _success('Hold'))
        holdWorker.signals.error.connect(lambda : _error('Hold'))

        self.pool.start(holdWorker)
        self.hModel.layoutChanged.emit()
        self.holding.viewport().update()

        #Only calls the update function if there's stuff in the table, saves memory
        if self.qModel.rowCount() > 0:
            queueWorker = Worker(_queueCall)
            queueWorker.signals.finished.connect(lambda : _success('Queue'))
            queueWorker.signals.error.connect(lambda : _error('Queue'))

            self.pool.start(queueWorker)
            self.queue.viewport().update()


    def addQueue(self, ticks = False):
        '''
        Adds a ticker to to the Queue, whether from the config file
        or the dialog

        Args:
            ticks (bool): whether adding ticks from the config file

        Returns:
            None
        '''

        def _add(ticker):
            '''
            Actually adds the ticker obj to the queue

            Args:
                ticker (str): ticker name to be added

            Returns:
                None
            '''
            if ticker not in [tick.T for tick in self.qTicks + self.hTicks]:
                self.qTicks.append(Tick(ticker, self.purPrice.value()))
                self.qModel.layoutChanged.emit()
                logging.info('Added ' + ticker + ' to Queue')


        if not ticks:
            tick = AddTick(self.comps['Symbol'].values, self)
            if tick.exec_():
                if tick.result() and tick.tickEdit.text():
                    if not TESTING:
                        if float(self.marginLabel.text()) > 25000:
                            _add(tick.tickEdit.text())

                            #Autosaves...duh
                            self.autosave()
                    else: 
                        _add(tick.tickEdit.text())
        else:
            for item in self.qTicks:
                _add(item)


    def autosave(self, close = False):
        '''
        Saves the RH user/pass and every tick in Queue

        Args:
            close (bool): whether the program is closing or not

        Returns:
            None
        '''    
        if self.rUser and self.rPass:
            if not close: logging.info('Autosaving...')
            with open('core.cfg', 'w') as fileOut:
                data = {
                    'API' : {'User' : self.rUser, 'Password' : self.rPass},
                    'Queue' : [tick.T for tick in self.qTicks if self.qTicks]
                }

                json.dump(data, fileOut)


    def closeEvent(self, event):
        '''
        Handles the closing event, calls autosave()

        Args:
            event (QEvent): close event

        Returns:
            None
        '''
        logging.info('Closing and Resubmitting Config File')
        try:
            self.autosave(True)
        except AttributeError:
            pass



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec_())