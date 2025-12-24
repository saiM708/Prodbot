from flask import Flask, render_template, request, jsonify
from prodbot.data_ingestion import data_ingestion
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv
import os
import threading
import time
import bs4
import urllib.request
import smtplib
import requests

# Price tracking functions from amazontrack.py
prices_list = []

def check_price(url):
    """Fetches the current price of the product from the given URL."""
    try:
        # Enhanced headers to better mimic a real browser and avoid bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.amazon.in/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        final_url = response.url
        soup = bs4.BeautifulSoup(response.content, "html.parser")
        print(f"Final URL: {final_url}")
        print(f"HTML snippet: {soup.find('title').get_text(strip=True) if soup.find('title') else 'No title'}")

        # Attempt to find the price using various selectors (consolidated and expanded)
        price_selectors = [
            {'id': 'priceblock_ourprice'},
            {'id': 'priceblock_dealprice'},
            {'id': 'priceblock_saleprice'},
            {'class': 'a-price-whole'},
            {'class': 'a-color-price'},
            {'class': 'a-offscreen'},
            {'id': 'corePrice_desktop'},
            {'id': 'corePriceDisplay_desktop_feature_div'},
            {'class': 'a-price'},
        ]

        price_tag = None
        for selector in price_selectors:
            if 'id' in selector:
                price_tag = soup.find(id=selector['id'])
            elif 'class' in selector:
                price_tag = soup.find(attrs={'class': selector['class']})
            if price_tag:
                break

        # If still not found, try regex on all text
        if not price_tag:
            all_text = soup.get_text()
            import re
            price_match = re.search(r'₹\s*[\d,]+(?:\.\d{2})?', all_text)
            if price_match:
                prices_text = price_match.group()
                prices = float(prices_text.replace(",", "").replace("₹", "").replace("£", "").replace("$", ""))
                prices_list.append(prices)
                return prices

        if not price_tag:
            print("Could not find the price element. Check the HTML ID.")
            # Debug: print some HTML content for troubleshooting
            print("Debug: First 500 chars of HTML:", str(soup)[:500])
            return None

        # Extract and clean the price text
        prices_text = price_tag.get_text(strip=True)
        print(f"Raw price text: '{prices_text}'")  # Debug logging
        # Remove currency symbols and commas, then convert to float
        prices = float(prices_text.replace(",", "").replace("₹", "").replace("£", "").replace("$", ""))
        prices_list.append(prices)
        return prices
    except requests.exceptions.RequestException as e:
        print(f"Request error while fetching the price: {e}")
        return None
    except Exception as e:
        print(f"An error occurred while fetching the price: {e}")
        return None

def get_product_title(url):
    """Fetches the product title from the given URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.amazon.in/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.content, "html.parser")
        title_tag = soup.find('span', id="productTitle")
        if title_tag:
            return title_tag.get_text(strip=True)
        # Fallback: try title tag
        title = soup.find('title')
        if title:
            return title.get_text(strip=True).split(':')[0].strip()  # Remove ": Amazon.in: Electronics"
        return "The specified product"
    except Exception as e:
        print(f"Error fetching product title: {e}")
        return "The specified product"

def get_product_image(url):
    """Fetches the product image from the given URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.amazon.in/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.content, "html.parser")

        # Try multiple selectors for the main product image
        image_selectors = [
            '#ivLargeImage img',
            '#landingImage',
            '#imgBlkFront',
            'img[data-image-index="0"]',
            '.a-dynamic-image',
            'img[alt*="product"]',
            '#ebooksImgBlkFront',  # For ebooks
            '#img-canvas img',     # Alternative
        ]

        for selector in image_selectors:
            img_tag = soup.select_one(selector)
            if img_tag and img_tag.get('src'):
                image_url = img_tag['src']
                print(f"Found image with selector '{selector}': {image_url}")  # Debug
                # Ensure it's a full URL
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = 'https://www.amazon.in' + image_url
                # Check if it's a valid image URL (not a placeholder)
                if 'amazon' in image_url.lower() and ('jpg' in image_url.lower() or 'png' in image_url.lower() or 'jpeg' in image_url.lower()):
                    return image_url

        # Fallback: look for any img tag with data-image-index
        img_tags = soup.find_all('img', {'data-image-index': True})
        if img_tags:
            image_url = img_tags[0]['src']
            print(f"Found image with data-image-index: {image_url}")  # Debug
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://www.amazon.in' + image_url
            if 'amazon' in image_url.lower() and ('jpg' in image_url.lower() or 'png' in image_url.lower() or 'jpeg' in image_url.lower()):
                return image_url

        # Last resort: look for any image in the main content area
        main_img = soup.select_one('#ppd img, #dp-container img, #imageBlock img')
        if main_img and main_img.get('src'):
            image_url = main_img['src']
            print(f"Found image in main content: {image_url}")  # Debug
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = 'https://www.amazon.in' + image_url
            if 'amazon' in image_url.lower() and ('jpg' in image_url.lower() or 'png' in image_url.lower() or 'jpeg' in image_url.lower()):
                return image_url

        print("No suitable product image found")  # Debug
        return None
    except Exception as e:
        print(f"Error fetching product image: {e}")
        return None

def extract_product_info(url):
    """Extracts comprehensive product information from an Amazon URL using BeautifulSoup."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.amazon.in/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.content, "html.parser")

        info = {
            'title': None,
            'price': None,
            'image': None,
            'description': None,
            'rating': None,
            'reviews': None,
            'url': url
        }

        # Extract title
        title_tag = soup.find('span', id="productTitle")
        if title_tag:
            info['title'] = title_tag.get_text(strip=True)
        else:
            title = soup.find('title')
            if title:
                info['title'] = title.get_text(strip=True).split(':')[0].strip()

        # Extract price
        price_selectors = [
            {'id': 'priceblock_ourprice'},
            {'id': 'priceblock_dealprice'},
            {'id': 'priceblock_saleprice'},
            {'class': 'a-price-whole'},
            {'class': 'a-color-price'},
            {'class': 'a-offscreen'},
            {'id': 'corePrice_desktop'},
            {'id': 'corePriceDisplay_desktop_feature_div'},
            {'class': 'a-price'},
        ]

        price_tag = None
        for selector in price_selectors:
            if 'id' in selector:
                price_tag = soup.find(id=selector['id'])
            elif 'class' in selector:
                price_tag = soup.find(attrs={'class': selector['class']})
            if price_tag:
                break

        if price_tag:
            prices_text = price_tag.get_text(strip=True)
            info['price'] = prices_text.replace(",", "").replace("₹", "").replace("£", "").replace("$", "")
        else:
            # Try regex on all text
            all_text = soup.get_text()
            import re
            price_match = re.search(r'₹\s*[\d,]+(?:\.\d{2})?', all_text)
            if price_match:
                prices_text = price_match.group()
                info['price'] = prices_text.replace(",", "").replace("₹", "").replace("£", "").replace("$", "")

        # Extract image
        info['image'] = get_product_image(url)

        # Extract description
        desc_selectors = [
            '#productDescription p',
            '#feature-bullets ul',
            '.a-list-item',
            '#productDescription'
        ]
        for selector in desc_selectors:
            desc_tag = soup.select_one(selector)
            if desc_tag:
                info['description'] = desc_tag.get_text(strip=True)[:500]  # Limit to 500 chars
                break

        # Extract rating
        rating_tag = soup.select_one('.a-icon-star .a-icon-alt')
        if rating_tag:
            info['rating'] = rating_tag.get_text(strip=True)

        # Extract number of reviews
        reviews_tag = soup.select_one('#acrCustomerReviewText')
        if reviews_tag:
            info['reviews'] = reviews_tag.get_text(strip=True)

        return info
    except Exception as e:
        print(f"Error extracting product info: {e}")
        return None

def send_email(subject, body, receiver_email):
    """Sends an email with the specified subject and body."""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    sender_email = "prodbot8@gmail.com"
    sender_password = os.getenv("EMAIL_PASSWORD")
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        # Attach body
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Send email
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()  # Encrypts the connection
        s.login(sender_email, sender_password)
        text = msg.as_string()
        s.sendmail(sender_email, receiver_email, text)
        s.quit()
        print(f"Email sent successfully to {receiver_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def price_decrease_check():
    """Checks if the latest price is less than the previous price."""
    # Ensure there are at least two prices to compare
    if len(prices_list) >= 2 and prices_list[-1] < prices_list[-2]:
        return True
    else:
        return False

def track_price(url, user_email):
    global prices_list
    prices_list = []  # Reset for new tracking
    product_title = get_product_title(url)
    count = 1
    while True:
        print(f"\n--- Price Check #{count} ---")

        if count > 1:
            time.sleep(43000)

        current_price = check_price(url)
        if current_price is None:
            count += 1
            continue

        print(f"Current Price: ₹{current_price:.2f}")

        if count == 1:
            # Send initial confirmation email
            initial_subject = f"✅ Price Tracking Started for: {product_title}"
            initial_body = (
                f"Hi there,\n\n"
                f"We have started tracking the price for '{product_title}'.\n"
                f"The current price is: ₹{current_price:.2f}\n\n"
                f"We will notify you immediately if the price drops!"
            )
            send_email(initial_subject, initial_body, user_email)

        if count > 1:
            flag = price_decrease_check()
            if flag:
                # Calculate the decrease
                decrease = prices_list[-2] - prices_list[-1]

                # Email the user about the price drop
                drop_subject = f"🚨 PRICE DROP ALERT for {product_title}"
                drop_body = (
                    f"Great news! The price for '{product_title}' has dropped!\n\n"
                    f"Previous Price: ₹{prices_list[-2]:.2f}\n"
                    f"Current Price: ₹{prices_list[-1]:.2f}\n"
                    f"The price decreased by ₹{decrease:.2f}.\n\n"
                    f"Check the item now: {url}"
                )
                send_email(drop_subject, drop_body, user_email)
            else:
                print("Price did not decrease. Continuing to track.")

        count += 1

load_dotenv()

app = Flask(__name__)

# Load environment variables
GROQ_API = os.getenv("GROQ_API_KEY")

# Initialize vector store
vstore = data_ingestion("loaded")

# Create retriever
retriever = vstore.as_retriever()

# Create Groq LLM model
llm = ChatGroq(
    temperature=0,
    groq_api_key=GROQ_API,
    model_name="llama-3.3-70b-versatile"
)

system_instruction = """
You are a specialized Tech Product Analyst. Your goal is to provide recommendations and answers based on **aggregated user reviews** and real-world usage feedback.

**YOUR GUIDELINES:**
1. **Domain Restriction:** You must ONLY answer questions related to electronic gadgets (Smartphones, Laptops, PC components, Displays, Graphics Cards, Earbuds, Cameras, Smartwatches, etc.).
2. **Refusal Policy:** If the user asks about ANY other topic (e.g., clothes, food, politics, general coding, history), politely refuse. Say: "I can only assist with electronic gadgets and tech reviews."
3. **Review-Based Analysis:** When answering, frame your response around user experiences. Use phrases like "Users generally report...", "Common complaints include...", or "Reviewers praise the...". Focus on pros and cons.
4. **URL Processing:** When users provide Amazon product URLs, use BeautifulSoup to extract product information including title, price, description, rating, and reviews. Provide a summary of the product details.
5. **Product Suggestions:** When users ask for product recommendations or alternatives, provide 2-3 relevant product suggestions with brief descriptions. Format the response as follows:
Context: {context}
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_instruction),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# Memory setup
memory = ConversationBufferMemory(memory_key="history", return_messages=True)

# Create a chain with retrieval and memory
chain = (
    RunnablePassthrough.assign(
        context=lambda x: "\n".join([doc.page_content for doc in retriever.invoke(x["input"])]),
        history=lambda _: memory.load_memory_variables({})["history"]
    )
    | prompt
    | llm
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get', methods=['POST'])
def get_response():
    msg = request.form['msg']

    # Check if the message contains an Amazon URL
    import re
    url_pattern = r'https?://(?:www\.)?amazon\.in/[^/\s]+(?:/[^/\s]+)*'
    urls = re.findall(url_pattern, msg)

    if urls:
        # Extract product info from the first URL found
        product_info = extract_product_info(urls[0])
        if product_info:
            # Create a summary response with product details
            summary = f"Product Information:\n"
            summary += f"Title: {product_info['title'] or 'N/A'}\n"
            summary += f"Price: ₹{product_info['price'] or 'N/A'}\n"
            summary += f"Rating: {product_info['rating'] or 'N/A'}\n"
            summary += f"Reviews: {product_info['reviews'] or 'N/A'}\n"
            summary += f"Description: {product_info['description'] or 'N/A'}\n"
            summary += f"URL: {product_info['url']}\n"

            # Add to memory and return summary
            memory.save_context({"input": msg}, {"output": summary})
            return summary

    # For regular queries, use the chain
    result = chain.invoke({"input": msg})
    memory.save_context({"input": msg}, {"output": result.content})
    return result.content

@app.route('/track', methods=['POST'])
def start_tracking():
    url = request.form.get('url')
    email = request.form.get('email')
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    try:
        current_price = check_price(url)
        product_title = get_product_title(url)
        product_image = get_product_image(url)
        message = f"Price tracking started for '{product_title}'. Current price: ₹{current_price}."
        if email and os.getenv("EMAIL_PASSWORD"):
            # Start tracking in a new thread (initial email sent inside track_price)
            threading.Thread(target=track_price, args=(url, email)).start()
            message += " You will be notified on price drops."
        else:
            message += " Email notifications not configured."
        return jsonify({"message": message, "price": current_price, "image": product_image, "title": product_title})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
