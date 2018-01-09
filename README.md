# KStock


KStock is a Robinhood Day-Trading Bot written in Python >3.5. It uses the Robinhood API, as well as live data from NASDAQ.com to contiously monitor stocks and the users portfolio, determining when the most opportune time would be to sell/buy. I wanted to make this because I've seen countless queries about a stock trading bot but with no product. Hopefully this gets the ball rolling and with contributions, everyone starts making money on the market. 

For those of you wondering, no. This does not and will not have any cryptocurrency integration. There are plenty of other bots for that. There are a couple of crypto tickers you can play with that are just as volatile as the cryptos themselves. Have a look at MARA, RIOT, LFIN, LTEA, if you're interested. 

![Live Tab](https://i.imgur.com/OmlSyMB.png) ![Background Tab](https://i.imgur.com/tgm1lYh.png)

### Features

KStock features two Tabs: **Live**, **Backend**. 
* The Live tab features the current holdings of the user. It also features how much equity (both afterhours and intraday), how much cash on-hand they have, as well as the Non-Margin Limit. This can be set to anything above $25,000. Why $25,000? The SEC forbids anyone from placing four or more day trades within a five day swinging period, without $25,000 in hand. Robinhood shrunk that limitation to three trades in five days, but it's basically the same thing. If someone breaks that rule, they are suspended from day-trading for 90 days. KStock monitors both values and automatically stops trading if below the threshold. 
* The Backend Tab features the Suggesiton and Queue tables. The Suggestion tables monitors social media to determine the sentiment of the a stock. The Queue Table holds the list of stocks that are currently waiting to be bought, assuming they meet the criteria. 

The following features are currently working:

* Monitor current holdings in the users Robinhood portfolio
* Monitor three different sub-Reddits (/r/wallstreetbets, /r/stocks, /r/investing), parsing all the submissions and comments for talked about Tickers, and then using a custom Keras classifier to determine whether they are considering a SELL or a BUY on that stock.
* Monitor stocks that might be purchased, waiting for the most opportune time to purchase.
* Multiple trading strategies are automatically triggered depending on the time of day. If the markets just opened (09:15-10:15) it will use the Price Swing Strategy. The rest of the day, it's looking for volumetric income by Short Trading.
* Closes out all positions at the end of the day, regardless of their prices, swing trading isn't supported quite yet.

Things that are currently in testing:
* Stock Screener
* StockTwits integration

### Installation

KStock requires a few dependencies to get it up and running.
* PyQt5
* holidays
* pandas
* praw
* Tweepy
* Keras
* bs4
* html5lib
* [Robinhood](https://github.com/Jamonek/Robinhood)

All of the requiremens are covered in `requirements.txt`

```sh
$ pip3 install -r requirements.txt
```

To run:
```sh
$ python KStock.py
```

KStock was built on Ubuntu 16.04 with Python 3.5.2. 
Technically this can be run crossplatform, but I've heard tell that threading and multiprocessing using PyQt on Windows doesn't go over too well. KStock extensively uses multiprocessing, so you're more than free to try it out on Windows at your own risk.


### Development

Want to contribute? Bully for you!

Clone this repo and go for it. My commenting skills aren't the greatest but I tried to capture everything as best as I could.

There are a lot of people smarter than me in the world, so if you think you can improve on the trading logic, please contribute, I made the logic as more of a proof of concept than a permament model. The trading logic is found in `Tick.py`. 

### Todos

 - MORE TESTING
 - Add Night Mode
 - Integrate StockTwits and FinViz for screener and Suggestion Table expansion
 - Right-click stock on Suggestion Table to add to Queue
 - Custom Stock Screener inplace underneath Suggestion Table
 - Be able to handle swing trades

License
----

MIT


