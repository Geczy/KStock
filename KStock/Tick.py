import resources.gfc as gfc
from resources.NASDAQ import tickCurrents
import pandas as pd
import logging, datetime, pytz


class Tick():
    def __init__(self, tick, purPrice):

        self.__dict__.update({
            'T' : tick,                     #Ticker Symbol
            'C' : '',                       #Current Price
            'CP' : [],                      #Price Change [$,%]
            'V' : '',                       #Volume
            'AV' : '',                      #Average Volume
            'D' : '',                       #Direction of change
            'PQ' : 0,                       #Proposed quantity
            'PC' : '',                      #Previous Close
            'TD' : [],                      #Todays Data [Low, High]
            'YD' : [],                      #Years Data [Low, High]
            'Q' : None,                     #Quantity, once purchased
            'AP' : None,                    #Average Price, once purchased
            'SL' : None,                    #Stop Loss, once purchased
            'tradeable' : True              #Whether we're going to day-trade
        })

        #Price Reversal Sell Counter
        self.sellRev = 0
        #Price Reversale Buy Counter
        self.buyRev = 0
        self.pPrice = 0
        self.prevProfit = 0 
        self.update(purPrice)


    def update(self, purPrice):
        '''
        Updates the ticker to its current values

        Args:
            None

        Returns:
            (bool): whether the fetch to nasdaq was successful
        '''
        data = tickCurrents(self.T)
        if data and type(data['LTP']) == float:
            self.__dict__.update({
                'C' : data['LTP'],
                'CP' : (data['C'], data['CP']),
                'V' : data['V'],
                'PC' : data['PC'],
                'TD' : [data['TL'], data['TH']],
                'YD' : [data['YL'], data['YH']],
                'D' : data['D'],
                'PQ' : int(purPrice / data['LTP'])
            })

            return True
        else: return False


    def sell(self, purPrice, tradeStrat, forced = False):
        '''
        Determines whether to sell the ticker based on the current strategy

        Args:
            record (list): tick current data
            tradeStrat (str): current trade strategy

        Returns:
            (bool): determination of whether to sell or not
        '''
        def _close():
            '''
            Sells the ticker by resetting the POS variables 
            Args:
                None

            Returns:
                None
            '''
            self.prevProfit = (self.Q * self.C) - (self.Q * self.AP)
            self.Q, self.AP, self.SL = None, None, None
            self.sellRev = 0
        
        if not self.update(purPrice):
            logging.info('{} Fetch Empty'.format(self.T))
            return False

        #If short trading or price swing trading, the logic will be the same
        #Waits for price reversal then sell if the price reversal
        #Continues for 2 unique updates
        if self.Q:

            if (self.C <= self.SL) or forced:
                print('{} Forced to Sell At {}'.format(self.T, self.C))
                _close()
                return True

            else:
                if self.C > self.AP:
                    if self.C < self.pPrice:
                        self.sellRev += 1
                    elif self.C > self.pPrice:
                        self.pPrice = self.C
                        self.sellRev = 0
                    else:
                        pass

            if self.sellRev == 3:
                logging.info('{} Reached Sell Criteria At {}'.format(self.T, self.C))
                return True

        return False


    def purchase(self, purPrice, tradeStrat, forced = False, rhood = False):
        '''
        Determines whether to purchase the ticker based on the current strategy

        Args:
            record (list): tick current data
            tradeStrat (str): current trade strategy

        Returns:
            (bool): determination of whether to buy or not
        '''
        def _open(rhood):
            '''
            Actually purchases the ticker by setting the POS variables accordingly
            Args:
                None

            Returns:
                None
            ''' 
            self.buyRev = 0
            if not rhood:
                self.Q, self.AP, self.SL = self.PQ, self.C, round(self.C - (self.C * 0.1), 2)
            else:
                self.Q, self.AP, self.SL = rhood
                self.tradeable = False
                

        if not self.update(purPrice):
            logging.info('{} Fetch Empty'.format(self.T))
            return False

        if forced:

            logging.info('{} Forced Purchase at {}'.format(self.T, self.C))
            _open(rhood)
            return True

        else:
            if tradeStrat == 'ST':
                #If Short Trading, wait for a price reversal
                #If the price dropped 3x in a row, buy
                if self.C < self.pPrice:
                    self.pPrice = self.C
                    self.buyRev = 0
                elif self.C > self.pPrice:
                    self.buyRev += 1
                else:
                    pass

                if self.buyRev == 2:
                    logging.info('{} Reached ST Buy Criteria At {}'.format(self.T, self.C))
                    _open(rhood)
                    return True

            if tradeStrat == 'PS':
                if (self.TD[1] - self.C) / self.C > 0.01:
                    if self.C < self.pPrice:
                        self.pPrice = self.C
                        self.buyRev = 0
                    elif self.C > self.pPrice:
                        self.pPrice = self.C
                        self.buyRev += 1
                    else:
                        pass

                    if self.buyRev == 3:
                        logging.info('{} Reached PS Buy Criteria At {}'.format(self.T, self.C))
                        _open(rhood)
                        return True
        return False


        
if __name__ == '__main__':
    tick = 'NVDA'
    x = Tick(tick, 1000)
    print(x.__dict__)