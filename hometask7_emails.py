"""Написать программу, которая собирает входящие письма из своего или тестового почтового ящика, и сложить информацию
о письмах в базу данных (от кого, дата отправки, тема письма, текст письма)."""
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
import os
from dotenv import load_dotenv
from pathlib import Path
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

import time
import json

class EmailsParse:
    domain = 'https://mail.ru'
    start_url = 'https://e.mail.ru/inbox'
    login_url = 'https://mail.ru'

    __xpath_query = {
        'submit': '//button[@id = "mailbox:submit-button"]',
        'login_field': '//input[@id = "mailbox:login-input"]',
        'password_field': '//input[@id = "mailbox:password-input"]',
        'author': '//div[@class = "letter__author"]//span[@class="letter-contact"]',
        'date': '//div[@class="letter__date"]',
        'body': '//div[@class = "thread__subject-line"]//h2',
        'body_text': '//div[@class = "letter-blockquote__body"]//tbody//child::*[text()]',
        'scroll_cont': '//div[@class = "scrollable g-scrollable scrollable_bright scrollable_footer scrollable_ponymode"]',
        'emails': '//a[@class="llc js-tooltip-direction_letter-bottom js-letter-list-item llc_pony-mode llc_normal"]'
    }

    def __init__(self):
        self.visited_urls = set()
        self.emails_data = []
        self.client = MongoClient()
        self.db = self.client['parse_emails']
        self.collection_emails = self.db['emails']
        self.collection_user = self.db['user']
        self.__login = os.getenv('LOGIN_E')
        self.__password = os.getenv('PASSWORD_E')
        self.driver = webdriver.Firefox()
        self.wait = WebDriverWait(self.driver, 20)
        self.original_window = self.driver.current_window_handle
        self.userConfig = json

    def parse(self):
        self.login(self.driver)
        self.get_user_data(self.driver)
        self.get_emails_from_main_page(self.driver)
        self.save_to_mongo()
        self.driver.quit()

    def wait_for(self, X_path_name):
        self.wait.until(EC.visibility_of_element_located ((By.XPATH, self.__xpath_query[f'{X_path_name}'])))

    def login(self, driver):
        driver.get(self.login_url)

        self.wait_for('submit')
        submit = driver.find_element_by_xpath(self.__xpath_query['submit'])

        self.wait_for('login_field')
        email_log = driver.find_element_by_xpath(self.__xpath_query['login_field'])
        email_log.send_keys(self.__login[:self.__login.index('@')])

        submit.click()

        self.wait_for('password_field')
        pass_log = driver.find_element_by_xpath(self.__xpath_query['password_field'])
        pass_log.send_keys(self.__password)

        submit.click()


    def get_user_data(self, driver):
        for i in range(5):
            try:
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'lxml')
                data = soup.find('script', id = 'sota.config')
                data = data.contents
                data = data[0].strip('\n\t')
                js_data = json.loads(data)
                self.get_userConfig(js_data)

            except Exception:
                print(Exception)

    def get_userConfig(self, js_data):
        self.userConfig = js_data['userConfig']['api'][0]['data']['body']
        return self.userConfig

    def get_emails_from_main_page(self, driver):
        while True:
            try:
                self.wait_for('emails')
                emails = driver.find_elements_by_xpath(self.__xpath_query['emails'])
                self.go_to_email(emails, driver)
                driver.execute_script("arguments[0].scrollIntoView();", emails[-10])
            except TimeoutException:
                break

    def go_to_email(self, emails, driver):
        for email in emails:
            if email.get_attribute('href') in self.visited_urls:
                continue
            try:
                assert len(driver.window_handles) == 1
                action = ActionChains(driver)
                action.key_down(Keys.CONTROL).key_down(Keys.SHIFT).click(email).perform()
                self.wait.until(EC.number_of_windows_to_be(2))
                driver.switch_to.window(driver.window_handles[1])
                self.collect_email_info(driver)
                self.visited_urls.add(driver.current_url)
                driver.close()
                driver.switch_to.window(self.original_window)
            except Exception:
                driver.execute_script( "arguments[0].scrollIntoView();", emails[-10])
        print(f'collected {len(self.visited_urls)} emails')


    def collect_email_info(self, driver):

        email_data = {}

        self.wait_for('author')
        email_data['from'] = driver.find_element_by_xpath(self.__xpath_query['author']).get_attribute('title')
        self.wait_for('date')
        email_data['date'] = driver.find_element_by_xpath(self.__xpath_query['date']).text
        self.wait_for('body')
        email_data['title'] = driver.find_element_by_xpath(self.__xpath_query['body']).text
        email_data['body_text'] = ''
        for text in driver.find_elements_by_xpath(self.__xpath_query['body_text']):
            email_data['body_text']+= text.text

        self.emails_data.append(email_data)


    def save_to_mongo(self):

       self.collection_emails.insert_many(self.emails_data)
       self.collection_user.insert_one(self.userConfig)

if __name__ == '__main__':
    load_dotenv(dotenv_path=Path( '.env' ).absolute())
    parser = EmailsParse()
    parser.parse()

