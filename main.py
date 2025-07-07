import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from selectolax.parser import HTMLParser
from loguru import logger
import pyautogui
from playwright.sync_api import sync_playwright
import PIL




PRICE_FILEPATH = Path(__file__).parent / "Prix.json"
load_dotenv()

logger.remove()
logger.add(sys.stderr,level="DEBUG")
logger.add("logs/debug.log",level="INFO",rotation="1 MB")


def write_price_to_file(price : int):
    logger.info(f"Writing price {price} to file")
    if PRICE_FILEPATH.exists():
        with open(PRICE_FILEPATH,"r") as f:
            data = json.load(f)
    else:
        data=[]
    today = datetime.now().isoformat()

    data.append(
        {
            "price" : price,
            "timestamp" : str(datetime.today())
        }
    )

    with open(PRICE_FILEPATH,"w") as f:
        json.dump(data, f, indent=4)

def get_price_difference(current_price :int) -> int:
    logger.info(f"Getting price difference")

    if PRICE_FILEPATH.exists():
        with open(PRICE_FILEPATH,"r") as f:
            data = json.load(f)

        previous_price = data[-1]["price"]
    else:
        previous_price = current_price
    try:
        return round((previous_price-current_price) / previous_price * 100)
    except ZeroDivisionError as e:
        logger.error("La variable previous_price contient la valeur 0 : division par zéro")
        raise e

def send_alert(message):
    logger.info(f"Sending alert with message {message}")
    try:
        response = requests.post("https://api.pushover.net/1/messages.json",
                      data={"token" : os.environ["PUSHOVER_TOKEN"],
                            "user" : os.environ["PUSHOVER_USER"],
                            "message" : message}
                      )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Couldn't send alert due to {str(e)}")
        raise e




def get_current_price(pw, headless:bool, asin:str):
    user_agent= {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0"
    }
    url = f"https://www.amazon.fr/dp/{asin}"


    try:

        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context()
        context.set_default_timeout(30000)
        page = context.new_page()
        page.goto(url)
        page.wait_for_timeout(1000)
        if page.get_by_text("Essayez une autre image"):
            #image = page.locator("form").get_by_role("img")
            #image = image.get_attribute("src")
            #print(image)
            page2 = context.new_page()
            page2.goto(url)
            page2.wait_for_timeout(500)
            #pyautogui.mouseInfo()
            #pyautogui.screenshot()
            page2.get_by_label("Accepter").click()
            page2.wait_for_timeout(500)
            html_content = page2.content()
        #response = requests.get(url, headers=user_agent, verify=False)
        #response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Couldn't fetch content from {url} due to {str(e)}")
        raise e

    #html_content = response.text

    tree = HTMLParser(html_content)
    price_node = tree.css_first("span.a-price-whole")
    if price_node:
        price = re.sub(r"\D", "", price_node.text())
        return int(price)
    #print(response.text)
    error_msg = f"Couldn't find price in {url}"
    logger.error(error_msg)
    raise ValueError(error_msg)

def main(pw, asin : str, headless):
    current_price = get_current_price(pw=pw,asin=asin,headless=headless)
    price_difference = get_price_difference(current_price=current_price)
    write_price_to_file(price=current_price)

    if price_difference > 0:
        send_alert(f"Price has decreased by {price_difference}%")

if __name__=="__main__":
    asin= "B0CLTBHXWQ" # PS4
    #asin = "B0DHSV68YZ"
    #asin="B0BCGT219J "
    with sync_playwright() as pw:
        main(pw=pw,asin=asin,headless=True)
