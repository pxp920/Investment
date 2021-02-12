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

new_penny = subreddit.new(limit=500)

Ticker = {}

Exclusionlist = ['FOMO','HOLD','THE','MOON','LINE','FUCK','ASS','DICK','OTC','DATE','LMAO','TSLA','IPO','ICO'
                'LINK','URL','YOUR','GOOD','HUGE','CEO','COOL','CASH','PUMP','SEC','RIP','YOLO','THIS','VERY','YES','TOO'
                ,'LATE','CBD','IMO']

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
                if extract[i] not in Ticker.keys():
                    Ticker[extract[i]] = 0
                else:
                    Ticker[extract[i]]+=1
        
            for comment in submission.comments.list():

                commentdt = datetime.fromtimestamp(comment.created_utc)

                if commentdt.date()==date.today():

                    extract = re.findall(r'\b[A-Z]{3,4}\b',comment.body) #Extract 3 or 4 character capitalized letters

                    for i in range(len(extract)):
                        if extract[i] not in Ticker.keys():
                            Ticker[extract[i]] = 0
                        else:
                            Ticker[extract[i]]+=1
                else:
                    print('Covered today''s submissions')
                    break
        else:
            print('Covered today''s submissions')
            break

print(Ticker)

# Increment values by 1 since it was 0 indexed
for key, value in Ticker.items():
    Ticker[key]+=1

# Prep Today's data by excluding blacklisted words
todays_dataframe = pd.DataFrame(Ticker.items(), columns=['Ticker',date.today().strftime("%m/%d/%Y")])
todays_dataframe = todays_dataframe[~todays_dataframe.Ticker.isin(Exclusionlist)] #exclusion list
ordered = todays_dataframe.sort_values(by=date.today().strftime("%m/%d/%Y"),ascending=False)

ordered["Indicator"]=np.nan

# Let's do some DD from barchart.com
tickerlist = ordered['Ticker'].tolist()

#boot up selenium
options = webdriver.ChromeOptions()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')
driver = webdriver.Chrome(executable_path='C:\webdrivers\chromedriver.exe',chrome_options=options)
# driver = webdriver.Chrome(ChromeDriverManager().install())

for i in tickerlist:
    sleep(2)

    driver.get('https://www.barchart.com/')
    searchticker = driver.find_element_by_name('search')
    try:
        searchticker.send_keys(i + "\n")
        sleep(5)
        
        element = driver.find_element_by_class_name("widget-content").text
        extract = element.split('\n')[0] #Extract indicator
        if(len(extract))>13:
            extract = np.nan
        else:
            extract

        print(extract)
        ordered.loc[ordered['Ticker'] == i, 'Indicator'] = extract
    except:
        print("Some kind of problem with barchart ping")

driver.close()

#joineddf = pd.merge(existingdf,todays_dataframe,on='Ticker',how='inner')

# Push results to gsheet
set_with_dataframe(ws, ordered)


