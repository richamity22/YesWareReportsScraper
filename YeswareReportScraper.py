import datetime
import json
import logging
import pickle
import time

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    JavascriptException
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

EMAIL = "slava@rein.agency"
PWD = "rick_wazowski1998"


def write_to_json(data, filename):
    with open(filename + '.json', 'w') as file:
        json.dump(data, file, indent=4, )


def create_logger():
    logger = logging.getLogger('YeswareReportScraper')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s|%(levelname)s|%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


class YeswareReportScraper:

    def __init__(self):
        self.option = Options()
        self.option.add_argument('--no-sandbox')
        self.option.add_argument("--start-maximized")
        self.option.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        self.option.add_experimental_option("prefs", {"profile.password_manager_enabled": False})
        self.option.add_experimental_option("prefs", {"credentials_enable_service": False})
        self.option.add_experimental_option("excludeSwitches", ['enable-automation'])
        self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=self.option)
        self.logger = create_logger()
        self.now = datetime.datetime.now()
        self.email_life = 0
        self.f_round = 1
        self.data_to_save = []
        self.action = ActionChains(self.driver)
        self.wait = WebDriverWait(self.driver, 10)

    def log_in(self, email, password):
        self.driver.get('https://www.google.com')
        try:
            self.load_cookie("cookies.pk1")
            self.driver.refresh()
        except Exception as el:
            self.logger.debug("Error Loading Cookie "+ str(el))
        self.driver.get('https://app.yesware.com')
        try:
            self.click_when_element_can_interact("//*[text()='Sign in with Google']")
            self.send_keys_when_element_can_interact("//*[@id='identifierId']", email)
            self.click_when_element_can_interact("//button//*[text()='Next']/..")
            self.send_keys_when_element_can_interact("//*[@id='password']//input", password)
            self.click_when_element_can_interact("//button//*[text()='Next']/..")
            self.click_when_element_can_interact("//button//*[text()='Allow']/..")
            self.logger.info('Success login')
        except Exception:
            self.logger.info("Already Logged In ")
        # questionnaire
        try:
            if self.driver.find_element_by_xpath('/html/body/div[1]/div/div/section[1]'):
                # departament or field of work
                self.driver.find_element_by_xpath(
                    '//*[@id="question-1"]/ul/li[1]/input').click()  # Entrepreneur / Founder / Investor
                time.sleep(1)
                self.driver.find_element_by_xpath(
                    '//*[@id="question-2"]/ul/li[1]/input').click()  # Entrepreneur / Founder
                time.sleep(1)
                # confirm rules
                self.driver.find_element_by_xpath('//*[@id="agree-privacy-policy"]').click()
                time.sleep(1)
                # confirm form
                self.driver.find_element_by_xpath('//*[@id="field-survey"]/div[6]/a[1]').click()
                self.logger.info('Questionnaire is passed')
        except NoSuchElementException:
            self.logger.info('The questionnaire was completed earlier')

    def save_cookie(self, path):
        with open(path, 'wb') as filehandler:
            pickle.dump(self.driver.get_cookies(), filehandler)

    def load_cookie(self, path):
        with open(path, 'rb') as cookiesfile:
            cookies = pickle.load(cookiesfile)
            for cookie in cookies:
                self.driver.add_cookie(cookie)

    def scrape_page(self):
        self.click_when_element_can_interact("//*[contains(@class,'personal-tracking')]")
        xpath_next_button = "//*[@class='events']/following-sibling::*[@class='pages']//*[text()='Next']"
        there_are_more_pages = True
        while there_are_more_pages:
            self.wait_for_jquery_and_javascript_to_finish()
            all_event_web_elements_on_this_page = self.driver.find_elements_by_xpath("//*[@class='events']//li")
            for event_web_element in all_event_web_elements_on_this_page:
                result = {
                    "email": {
                        "subject": "",
                        "link": "",
                        "to": "",
                        "date": "",
                        "activity": [],
                    },
                }
                self.scroll_by_we(event_web_element)
                subject = event_web_element.find_element_by_xpath(".//*[@class='name']").text
                link = event_web_element.find_element_by_xpath(".//*[@class='name']//a").get_attribute('href')
                to = event_web_element.find_element_by_xpath(".//*[@class='to']").text
                date = event_web_element.find_element_by_xpath(".//*[@class='sent']//*[@class='localtime']").text
                result["email"]["subject"] = subject.replace('\n', ' ')
                result["email"]["link"] = link
                result["email"]["to"] = str(to).split(":")[1]
                result["email"]["date"] = date
                try:
                    view_all_button_we = event_web_element.find_element_by_xpath(".//*[@class='view_all']//*")
                    self.driver.execute_script("arguments[0].click();", view_all_button_we)
                    self.wait_for_jquery_and_javascript_to_finish()
                    message_events_we = event_web_element.find_elements_by_xpath(".//*[@class='opens']//tr")
                    for message_event_we in message_events_we:
                        event_data = {}
                        event_type = message_event_we.find_element_by_xpath(".//*[@class='message']").text
                        try:
                            event_date = message_event_we.find_element_by_xpath(".//*[@class='date']").text
                            event_data["event_date"] = str(event_date).replace('\n', ' ')
                        except NoSuchElementException:
                            self.logger.debug("No Dates")
                        event_data["event_type"] = str(event_type).replace('\n', ' ')
                        result["email"]["activity"].append(event_data)
                except NoSuchElementException:
                    self.logger.debug("No Events")
                self.data_to_save.append(result)
            there_are_more_pages = len(self.driver.find_elements_by_xpath(xpath_next_button)) != 0
            if there_are_more_pages:
                self.click_when_element_can_interact(xpath_next_button)
        write_to_json(self.data_to_save, 'data')

    def move_to_xpath_we(self, xpath_we):
        self.wait_for_jquery_and_javascript_to_finish()
        we = self.driver.find_element_by_xpath(xpath_we)
        move_retry = 0
        while move_retry < 5:
            try:
                self.logger.debug("Movimng to We")
                self.action.move_to_element(we).perform()
            except JavascriptException as ex:
                self.logger.debug(ex.stacktrace)
            except StaleElementReferenceException as se:
                self.logger.debug(se.stacktrace)
            move_retry = move_retry + 1
        self.wait_for_jquery_and_javascript_to_finish()

    def scroll_by_we(self, we):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView();", we)
        except JavascriptException as e:
            self.logger.debug(e.stacktrace)
        self.wait_for_jquery_and_javascript_to_finish()

    def wait_for_jquery_and_javascript_to_finish(self):
        try:
            self.wait.until(lambda d: d.execute_script("return jQuery.active == 0"))
            self.logger.debug("Wait for Javascript and JQuery runs to finish on page")
        except JavascriptException as jse:
            self.logger.debug(jse.stacktrace)

    def click_when_element_can_interact(self, xpath_we):
        self.wait.until(ec.visibility_of_element_located((By.XPATH, xpath_we)))
        self.wait.until(ec.presence_of_element_located((By.XPATH, xpath_we)))
        self.driver.find_element_by_xpath(xpath_we).click()

    def send_keys_when_element_can_interact(self, xpath_we, text):
        self.click_when_element_can_interact(xpath_we)
        self.driver.find_element_by_xpath(xpath_we).send_keys(text)

    def main(self):
        self.log_in(EMAIL, PWD)
        self.scrape_page()
        self.logger.info('Script complete!')


if __name__ == '__main__':
    scraper = YeswareReportScraper()
    try:
        scraper.main()
        scraper.save_cookie("cookies.pk1")
        scraper.driver.quit()
    except Exception as exception:
        scraper.logger.debug(exception)
        scraper.save_cookie("cookies.pk1")
        scraper.driver.quit()
