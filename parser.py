# %%
import  praw
import  pandas as pd
import  regex as re
import  gspread
import  selenium
import  requests
import  pytz
import  numpy as np
from    pytz import timezone
from    gspread_pandas import Spread
from    gspread_dataframe import get_as_dataframe, set_with_dataframe
from    oauth2client.service_account import ServiceAccountCredentials
from    configparser import ConfigParser
from    datetime import datetime, date
from    selenium import webdriver
from    time import sleep
from    collections import defaultdict, OrderedDict
from    operator import itemgetter
from    functools import reduce

# Gsgeets authentication
scope = ["https://spreadsheets.google.com/feeds"
        ,'https://www.googleapis.com/auth/spreadsheets'
        ,"https://www.googleapis.com/auth/drive.file"
        ,"https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("InvestmentCrawl.json", scope)
gc = gspread.authorize(creds)

# Open my sheet
sh = gc.open('Investments')
ws = sh.worksheet('Pennys')
existingdf = pd.DataFrame(ws.get_all_records())

# Read my config file
config = ConfigParser()
config.read('config.ini')

# Connect to the reddit API
reddit = praw.Reddit(client_id='pqkIk5-LFDs3iw', \
                     client_secret='hzPWlsL7OD35SRYeI1efZ5l2Z7SwFA', \
                     user_agent='panos_fin', \
                     username=config['reddit']['user'], \
                     password=config['reddit']['password'])

subreddit = reddit.subreddit('pennystocks') #sub in question

new_penny = subreddit.new(limit=5)

Ticker_count = {}
Award_count = {}
Score_sum = {}

Exclusionlist = ['FOMO','HOLD','THE','MOON','LINE','FUCK','ASS','DICK','OTC','DATE','LMAO','TSLA','IPO','ICO'
                'LINK','URL','YOUR','GOOD','HUGE','CEO','COOL','CASH','PUMP','SEC','RIP','YOLO','THIS','VERY','YES','TOO'
                ,'LATE','CBD','IMO','FREE','BTC','UTC','CFO','BUY','SELL','ETF','NEWS','BIG','FOR','ROFL','LOL','RIOT']

# Timezone switch criteria
est = timezone('US/Eastern')
mst = pytz.timezone('Europe/Moscow')
count = 0

# Iterate through today's posts and today's comments and pick up mention counts
for submission in new_penny:

    submissiontime = mst.localize(datetime.fromtimestamp(submission.created))
    submissiontime_est = submissiontime.astimezone(est)
    
    if not submission.stickied:
        submission.comments.replace_more(limit=None)
        submission.comments.replace_more(limit=None)
        submission.comments.replace_more(limit=None)    
        
        #check progress
        count+=1    
        print(count)
        sleep(0.5)

        if submissiontime_est.date()==date.today():
            # print(submission.title)
            # print(submissiontime_est.date())

            extract = re.findall(r'\b[A-Z]{3,5}\b',submission.title) #Extract 3 or 4 character capitalized letters

            for i in range(len(extract)):
                if extract[i] not in Ticker_count.keys():
                    Ticker_count[extract[i]]=0
                    Award_count[extract[i]]=submission.total_awards_received #edit
                    Score_sum[extract[i]]=submission.score #edit


                else:
                    Ticker_count[extract[i]]+=1
                    Award_count[extract[i]]=submission.total_awards_received+Award_count[extract[i]]  #edit
                    Score_sum[extract[i]]=submission.score+Score_sum[extract[i]]
            
            for comment in submission.comments.list():

                commentdt = datetime.fromtimestamp(comment.created_utc)

                if commentdt.date()==date.today():

                    extract = re.findall(r'\b[A-Z]{3,4}\b',comment.body) #Extract 3 or 4 character capitalized letters

                    for i in range(len(extract)):
                        if extract[i] not in Ticker_count.keys():
                            Ticker_count[extract[i]] = 0
                            Award_count[extract[i]]=comment.total_awards_received #edit
                            Score_sum[extract[i]]=comment.score #edit

                        else:
                            Ticker_count[extract[i]]+=1
                            Award_count[extract[i]]=+comment.total_awards_received+Award_count[extract[i]]  #edit
                            Score_sum[extract[i]]=comment.score+Score_sum[extract[i]]

                else:
                    print('Covered today''s submissions')
                    break
        else:
            print('Covered today''s submissions')
            break

# Increment values by 1 since it was 0 indexed
for key, value in Ticker_count.items():
    Ticker_count[key]+=1

# Prep Today's data by excluding blacklisted words
Ticker_dataframe = pd.DataFrame(list(Ticker_count.items()),columns = ['Ticker','Mentions']) 
Award_dataframe = pd.DataFrame(list(Award_count.items()),columns = ['Ticker','Awards']) 
Score_dataframe = pd.DataFrame(list(Score_sum.items()),columns = ['Ticker','Score']) 

# Drop blacklisted words
Ticker_dataframe = Ticker_dataframe[~Ticker_dataframe.Ticker.isin(Exclusionlist)] #exclusion list
Award_dataframe = Award_dataframe[~Award_dataframe.Ticker.isin(Exclusionlist)] #exclusion list
Score_dataframe = Score_dataframe[~Score_dataframe.Ticker.isin(Exclusionlist)] #exclusion list

# Join the three metrics & create empty indicator columns
dfs = [Ticker_dataframe,Award_dataframe,Score_dataframe]
joineddf = reduce(lambda left,right: pd.merge(left,right,on='Ticker'), dfs)
joineddf["Derived_Total_Score"] = joineddf['Mentions']*0.5 + joineddf['Awards']*0.25 + joineddf['Score']*0.25

# Financials
joineddf["Previous_Close"]=np.nan
joineddf["Volume"]=np.nan
joineddf["Avg_Volume"]=np.nan
joineddf["Stochastic_K"]=np.nan
joineddf["Weighted_A"]=np.nan
joineddf["5_Day_Change"]=np.nan
joineddf["52_Week_Range"]=np.nan

# Fundamentals
joineddf["Market_Cap"]=np.nan
joineddf["Shares_Outstanding"]=np.nan
joineddf["Annual_Sales"]=np.nan
joineddf["Annual_Income"]=np.nan
joineddf["Beta_60m"]=np.nan
joineddf["Price_to_Sales"]=np.nan
joineddf["Price_to_CF"]=np.nan
joineddf["Price_Book"]=np.nan
joineddf["Price_Earnings_TTM"]=np.nan
joineddf["EPS"]=np.nan
joineddf["Recent_Earnings"]=np.nan
joineddf["Next_Earnings_Dt"]=np.nan
joineddf["Annual_Div_Yield"]=np.nan
joineddf["Rec_Div"]=np.nan

ordered = joineddf.sort_values(by='Derived_Total_Score',ascending=False)

print(ordered)

# %%

# Let's do some DD from barchart.com
tickerlist = ordered['Ticker'].tolist()

#boot up selenium
options = webdriver.ChromeOptions()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')
driver = webdriver.Chrome(executable_path='C:/webdrivers/chromedriver.exe',options=options)

for i in tickerlist:
    sleep(2)

    driver.get('https://www.barchart.com/')
    searchticker = driver.find_element_by_name('search')
    try:
        searchticker.send_keys(i + "\n")
        sleep(5)

        element1 = driver.find_element_by_class_name("widget-content").text
        indicator = element1.split('\n')[0] #Extract indicator
        print(indicator)

        element2 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[1]").text
        previousclose = element2.split('\n')[1] 

        element3 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[2]").text
        volume = element3.split('\n')[1] 

        element4 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[3]").text
        avg_volume = element4.split('\n')[1] 

        element5 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[4]").text
        stochastik_k = element5.split('\n')[1] 

        element6 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[5]").text
        weighted_alpha = element6.split('\n')[1] 

        element7 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[6]").text
        change_5day = element7.split('\n')[1] 

        element8 = driver.find_element_by_xpath("(//div[@class='financial-data-row'])[7]").text
        change_52_week = element8.split('\n')[1] 

        element9 = driver.find_element_by_xpath("(//div[@class='row symbol-data'])").text
        # print(element8)
        market_cap = element9.split('\n')[1] 
        shares_outstanding = element9.split('\n')[3] 
        annual_sales = element9.split('\n')[5] 
        annual_income = element9.split('\n')[7] 
        beta_60month = element9.split('\n')[9] 
        price_to_sales = element9.split('\n')[11] 
        price_to_cf = element9.split('\n')[13] 
        price_book = element9.split('\n')[15] 
        price_earnings_ttm = element9.split('\n')[18] 
        EPS = element9.split('\n')[20] 
        recent_earnings_date = element9.split('\n')[22] 
        next_earnings_dt = element9.split('\n')[24] 
        annual_div_yield = element9.split('\n')[26] 
        rec_div = element9.split('\n')[28] 
            
        if(len(indicator))>13:
            extraindicatorct = np.nan
        else:
            indicator

        ordered.loc[ordered['Ticker'] == i, 'Previous_Close'] = previousclose
        ordered.loc[ordered['Ticker'] == i, 'Volume'] = volume
        ordered.loc[ordered['Ticker'] == i, 'Avg_Volume'] = avg_volume
        ordered.loc[ordered['Ticker'] == i, 'Stochastic_K'] = stochastik_k
        ordered.loc[ordered['Ticker'] == i, 'Weighted_A'] = weighted_alpha
        ordered.loc[ordered['Ticker'] == i, '5_Day_Change'] = change_5day
        ordered.loc[ordered['Ticker'] == i, '52_Week_Range'] = change_52_week
        ordered.loc[ordered['Ticker'] == i, 'Market_Cap'] = market_cap
        ordered.loc[ordered['Ticker'] == i, 'Shares_Outstanding'] = shares_outstanding
        ordered.loc[ordered['Ticker'] == i, 'Annual_Sales'] = annual_sales
        ordered.loc[ordered['Ticker'] == i, 'Annual_Income'] = annual_income
        ordered.loc[ordered['Ticker'] == i, 'Beta_60m'] = beta_60month
        ordered.loc[ordered['Ticker'] == i, 'Price_to_Sales'] = price_to_sales
        ordered.loc[ordered['Ticker'] == i, 'Price_to_CF'] = price_to_cf
        ordered.loc[ordered['Ticker'] == i, 'Price_Book'] = price_book
        ordered.loc[ordered['Ticker'] == i, 'Price_Earnings_TTM'] = price_earnings_ttm
        ordered.loc[ordered['Ticker'] == i, 'EPS'] = EPS
        ordered.loc[ordered['Ticker'] == i, 'Recent_Earnings'] = recent_earnings_date
        ordered.loc[ordered['Ticker'] == i, 'Next_Earnings_Dt'] = next_earnings_dt
        ordered.loc[ordered['Ticker'] == i, 'Annual_Div_Yield'] = annual_div_yield
        ordered.loc[ordered['Ticker'] == i, 'Rec_Div'] = rec_div

    except:
        print("Some kind of problem with data extraction")

driver.close()


#joineddf = pd.merge(existingdf,todays_dataframe,on='Ticker',how='inner')

# Push results to gsheet
set_with_dataframe(ws, ordered)



# %%
