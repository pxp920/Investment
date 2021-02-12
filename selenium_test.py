# %%
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import bs4 as bs 
import urllib.request
import regex

driver = webdriver.Chrome(ChromeDriverManager().install())

driver.get('https://www.barchart.com/')

searchticker = driver.find_element_by_name('search')

searchticker.send_keys('SNPW' + "\n")

#%%

element = driver.find_element_by_class_name("widget-content").text

print(element)
extract = element.split('\n')[0] #Extract 3 or 4 character capitalized letters
print(extract)

print(element)



# %%
