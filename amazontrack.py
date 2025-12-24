import bs4
import urllib.request
import smtplib
import time

from bs4 import BeautifulSoup

price_list = []
url = 'https://amzn.in/d/cgmsbIv'

def check_price():
    
    sauce = urllib.request.urlopen(url).read()
    soup = bs4.BeautifulSoup(sauce, "html.parser")

    price = soup.find('span', class_='a-price-whole').text
    price = float(price.replace(",", ""))

    price_list.append(price)

    return price

def find_product_image():
    # Select the image tag inside the ID
    image_tag = bs4.soup.select_one('#ivLargeImage img')

# Get the source link
    if image_tag:
        image_url = image_tag['src']
    return image_url

def send_email(message):
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login("prodbot8@gmail.com", "yjymwbjzfaszdmzj")
    s.sendmail("prodbot8@gmail.com", "mansinghsai8@gmail.com", message)
    s.quit()


def price_decrease_check(price_list):
    if price_list[-1] < price_list[-2]:
        return True
    else:
        return False
    
while True:
    count = 1
    current_price = check_price()
    if count > 1:
        flag = price_decrease_check(price_list)
        if flag:
            decrease = price_list[-2] - price_list[-1]
            message = f"The price has decreased please check the item: {url}. \nThe price decreased by {decrease} rupees."
            send_email(message)
    time.sleep(43000)
    count += 1

