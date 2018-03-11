from bs4 import BeautifulSoup
from urllib.request import urlopen
import re
from socket import timeout

def clean(s):
    s = re.sub(r'[^0-9a-zA-Z. ]', '', s)
    return s
    

def tickCurrents(tick):
    url = 'http://www.nasdaq.com/symbol/{}/real-time'.format(tick)

    tickMetrics = {
            'LTP' : '',
            'C' : '',
            'CP' : '',
            'PC' : '',
            'TH' : '',
            'TL' : '',
            'YH' : '',
            'YL' : '',
            'V' : '',
            'D' : ''
        }
    #print(BeautifulSoup(urlopen(url, timeout = 10).read(), 'html5lib').encode('utf-8'))
    try:
        soup = BeautifulSoup(urlopen(url, timeout = 1).read(), 'html5lib')
        #soup = BeautifulSoup(requests.get(url, headers = headers, timeout = 5))
        _tag2met = {
            'quotes_content_left__LastSale': 'LTP', 
            'quotes_content_left__NetChange': 'C', 
            '_updownImage': 'D', 
            'quotes_content_left__PctChange': 'CP', 
            'quotes_content_left__Volume': 'V', 
            'quotes_content_left__PreviousClose': 'PC', 
            'quotes_content_left__TodaysHigh': 'TH', 
            'quotes_content_left__TodaysLow': 'TL', 
            'quotes_content_left__52WeekHigh': 'YH', 
            'quotes_content_left__52WeekLow': 'YL'
        }
        if soup:
            for content in soup.find('div', {'class' : 'genTable'}).findAll('span'):
                if content.has_attr('id'):
                    tagId = content.get('id')
                    if tagId in _tag2met:
                        if tagId == '_updownImage':
                            tickMetrics['D'] = content.get('class')[0]
                        else:
                            tickMetrics[_tag2met[tagId]] = clean(content.text.encode('ascii', 'ignore').decode())
        
    

    except (HTTPError, URLError) as error:
        logging.error('Data of %s not retrieved because %s\nURL: %s', name, error, url)

    except timeout:
        logging.error('socket timed out - URL %s', url)

        #FIX CHANGES FROM unch TO SOMETHING ELSE
    finally:
        for item in tickMetrics:
            try:
                tickMetrics[item] = float(tickMetrics[item])
            except ValueError:
                pass
        return tickMetrics if tickMetrics['LTP'] else False

         
def tickRating(self):
    rating = {'r' : None, 'c' : None}
    rate = soup.find('a', {'id' : 'quotes_content_left_OverallStockRating1_hlIconLink'}).find('img')
    ratings = soup.find('div', {'id' : 'ratingtext'}).findAll('span')
    if 'bullish' in rate.get('src'): rating['r'] = 1
    elif 'bearing' in rate.get('src'): rating['r'] = -1
    rating['c'] = ' '.join(span.text for span in ratings)
    return rating


if __name__ == '__main__':
    print(tickCurrents('nvda'))