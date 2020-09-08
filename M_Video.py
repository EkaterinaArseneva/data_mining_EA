import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import json

class MVideoParser:
    domain = 'www.mvideo.ru'
    start_url = 'https://www.mvideo.ru'
    driver = webdriver.Firefox()
    __xpath_query = {
        'bestsellers_block': '//div[@class = "gallery-layout sel-hits-block "]',
        'next_for_bestsellers': './/a[@class = "next-btn sel-hits-button-next"]',
        'products': './/div[@class = "product-tile sel-product-tile"]',
        'product_info': './/a[@class = "product-tile-picture-link"]',
        'open_extra_categories': '//li[@class = "header-nav-item last"]',
        'extra_categories': '//a[@class = "header-nav-extra-item-link"]'
    }

    def __init__(self):
        self.categories_links = []
        self.bestsellers_info = []
        self.client = MongoClient()
        self.db = self.client['parse_Mvideo']
        self.collection = self.db['best_sellers']
        self.wait = WebDriverWait(self.driver, 10)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36"}


    def parse(self, url = start_url):
        response = requests.get(url, headers=self.headers )
        time.sleep( 0.01 )
        soup = BeautifulSoup( response.text, 'lxml' )
        self.get_categories_links(soup)
        self.open_categories_links_selenium(self.categories_links)
        self.driver.quit()


    def get_categories_links(self, soup):

        lis = soup.find_all('li', attrs={'class': 'header-nav-item has-dropdown'})
        for li in lis:
            a = li.find('a', attrs={'class': 'header-nav-item-link'} )
            category_page_link = f'{self.start_url}{a.get( "href" )}' if a and a.get( "href" ) else None
            self.categories_links.append(category_page_link)
        self.get_extra_categories()


    def get_extra_categories(self, driver = driver):

        driver.get(self.start_url)
        driver.find_element_by_xpath(self.__xpath_query['open_extra_categories']).click()
        extra_items = driver.find_elements_by_xpath(self.__xpath_query['extra_categories'])
        for a in extra_items:
            category_page_link = a.get_attribute("href") if a and a.get_attribute("href") else None
            self.categories_links.append(category_page_link)


    def open_categories_links_selenium(self, categories_links, driver = driver):
        for link in categories_links:
            driver.get(link)
            while True:
                previous_len = len(self.bestsellers_info)
                try:
                    self.wait_for('bestsellers_block')
                    best_sellers_block = driver.find_element_by_xpath(self.__xpath_query['bestsellers_block'])
                except NoSuchElementException:
                    break
                self.get_product_info(best_sellers_block)
                if previous_len == len(self.bestsellers_info):
                    break
                self.wait_for('next_for_bestsellers')
                next = best_sellers_block.find_element_by_xpath(self.__xpath_query['next_for_bestsellers'])
                if EC.element_to_be_clickable(next):
                    next.click()


    def get_product_info(self, best_sellers_block):
        self.wait_for('products')
        products = best_sellers_block.find_elements_by_xpath(self.__xpath_query['products'])
        for product in products:
            for n in range(5):
                try:
                    self.wait_for('product_info')
                    product_info = product.find_element_by_xpath(self.__xpath_query['product_info']).\
                        get_attribute("data-product-info")
                    self.save_product_info_info(product_info)
                except StaleElementReferenceException:
                    continue


    def save_product_info_info(self, product_info):
        product_info_json = json.loads( product_info )
        if not product_info_json in self.bestsellers_info:
            self.bestsellers_info.append(dict.copy(product_info_json))
            self.collection.insert_one(product_info_json)



    def wait_for(self, X_path_name):
        self.wait.until(EC.presence_of_element_located((By.XPATH, self.__xpath_query[f'{X_path_name}'])))

if __name__ == '__main__':
    parser = MVideoParser()
    parser.parse()
    print(parser.bestsellers_info)