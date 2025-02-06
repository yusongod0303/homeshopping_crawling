from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
import pandas as pd
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# ChromeDriver 경로 지정
driver = webdriver.Chrome()

#날짜 설정
year="2025"
month="01"
day="09"

# 웹 페이지 열기
url =f"https://www.gsshop.com/shop/tv/tvScheduleMain.gs?lseq=415680-1&gsid=gnb-AU415680-AU415680-1#{year}{month}{day}_LIVE"
# url =f"https://www.gsshop.com/shop/tv/tvScheduleMain.gs?lseq=415680-1&gsid=gnb-AU415680-AU415680-1#{year}{month}{day}_DATA"
driver.get(url)

# 3초 대기
time.sleep(3)

# 모든 <article class="items"> 컨테이너 찾기
articles = driver.find_elements(By.CSS_SELECTOR, "article.items")

# 각 article에서 방송 시간과 상품 URL 추출
urls = []  # 상품 URL을 저장할 리스트

for article in articles:
    # 방송 시간 추출
    broadcast_time = article.find_element(By.CSS_SELECTOR, "aside span.times").text
    
    # 상품의 상세 URL을 추출할 모든 <a> 태그 찾기
    product_links = article.find_elements(By.CSS_SELECTOR, "dt.prd-name a")
    
    # URL 추출
    for link in product_links:
        url = link.get_attribute('href')
        urls.append((url, broadcast_time))  # URL과 방송 시간을 튜플로 저장

# 데이터를 저장할 리스트 초기화
data = []

# 각 URL을 순차적으로 열고, 작업 후 닫기
for url, broadcast_time in urls:
    # 새로운 페이지 열기
    driver.get(url)
    
    # 페이지 로딩 대기
    time.sleep(3)  # 필요에 따라 시간을 조절하세요
    
    # 판매량 크롤링
    try:
        sales_count = driver.find_element(By.CSS_SELECTOR, "div.product-feature-bar .product-feature-bar_sellcount strong#ordQtyText").text
    except Exception as e:
        sales_count = "판매량 정보 없음"
    
    # 상품 제목 크롤링
    try:
        product_title = driver.find_element(By.CSS_SELECTOR, "p.product-title span.title-attribute-tv_shop").text
        product_title += driver.find_element(By.CSS_SELECTOR, "p.product-title").text.split(product_title)[-1]
    except Exception as e:
        product_title = "상품 제목 정보 없음"
    
    # 별점과 리뷰 수 크롤링
    try:
        rating = driver.find_element(By.CSS_SELECTOR, "p.customer-reviews span.customer-reviews-score em").text
        review_count = driver.find_element(By.CSS_SELECTOR, "p.customer-reviews span.customer-reviews-link em").text
    except Exception as e:
        rating = "별점 정보 없음"
        review_count = "리뷰 수 정보 없음"
    
    # 가격 크롤링
    try:
        price = driver.find_element(By.CSS_SELECTOR, "span.price-definition-ins ins strong").text
    except Exception as e:
        price = "가격 정보 없음"
    
    # 이미지 URL 크롤링
    try:
        image_url = driver.find_element(By.CSS_SELECTOR, "a.btn_img img").get_attribute("src")
    except Exception as e:
        image_url = "이미지 정보 없음"
    
    # 데이터를 리스트에 추가
    data.append([url, broadcast_time, sales_count, product_title, rating, review_count, price, image_url])

    print(f"url: {url}, broadcast_time: {broadcast_time}")
    print(f"purchases: {sales_count}")
    print(f"title: {product_title}")
    print(f"rating: {rating}, reviews: {review_count}")
    print(f"price: {price}")
    print(f"image url: {image_url}")
    print("-" * 50)
    
    # 페이지 닫기
    driver.close()
    
    # 새 페이지를 열기 위해서는 새로운 드라이버 객체를 생성해야 할 수 있습니다.
    driver = webdriver.Chrome()  # 새로 드라이버 생성

# 브라우저 완전히 닫기
driver.quit()

# 데이터를 pandas DataFrame으로 변환
df = pd.DataFrame(data, columns=['url', 'broadcast_time', 'purchases', 'title', 'rating', 'reviews', 'price', 'image_url'])
df['datetime'] = f"{year}-{month}-{day}"
df['rating'] = df['rating'].replace({'별점 정보 없음': '0'}, regex=True)
df['rating'] = df['rating'].fillna('0').astype(float)
df['rating'] = df['rating'].replace(0, np.nan)
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0', '가격 정보 없음': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)
df['purchases'] = df['purchases'].replace({'판매량 정보 없음': '0', '구매': '', ',': '', ' ' : ''}, regex=True)
df['purchases'] = df['purchases'].replace('', np.nan)
df['purchases'] = df['purchases'].fillna(0).astype(int)
df['purchases'] = df['purchases'].replace(0, np.nan)
df['reviews'] = df['reviews'].str.replace(r'[()]', '', regex=True)
df['reviews'] = df['reviews'].replace({'₩': '', ',': '', '리뷰 수 정보 없음': ''}, regex=True)
df['reviews'] = df['reviews'].replace('', np.nan)
df['reviews'] = df['reviews'].fillna('0').astype(int)

client = OpenAI(
    api_key=""
    #api키 삽입
)

# 사전 정의된 카테고리
categories = ["패션의류", "패션잡화", "화장품/미용", "디지털/가전", "가구/인테리어", "출산/육아", "식품", "스포츠/레저", "생활/건강", "여가/생활편의"]


# OpenAI 호출 함수
def chat_with_gpt4omini(prompt, max_tokens=100):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"An error occurred: {str(e)}"

    # 카테고리와 키워드 추출 함수


def extract_category_and_keywords(product_name):
    category_list = ", ".join(categories)
    prompt = (
        f"{product_name}.\n"
        f"위 제목에서 카테고리를 선택하고, 제목 및 카테고리와 연관된 키워드 3개를 JSON 형식으로만 반환하세요.\n"
        f"category: {', '.join(categories)}.\n"
    )

    response = chat_with_gpt4omini(prompt)

    try:
        # Markdown 제거 및 JSON 파싱
        cleaned_response = response.replace("```json", "").replace("```", "").strip()
        result = json.loads(cleaned_response)

        # JSON 키값 고정
        category = result.get("category") or result.get("카테고리") or "Unknown"
        keywords = result.get("keywords") or result.get("키워드") or result.get("related_keywords") or ["Error", "parsing",
                                                                                                        "response"]

        # 고정된 키값으로 재구성
        normalized_result = {
            "category": category,
            "keywords": keywords
        }

        print(normalized_result["category"], normalized_result["keywords"])

        return normalized_result["category"], normalized_result["keywords"]

    except json.JSONDecodeError:
        print(f"JSON Parsing Error: {cleaned_response}")
        return "Unknown", ["Error", "parsing", "response"]
    except Exception as e:
        print(f"API Error: {str(e)}")
        return "Unknown", ["Error", "parsing", "response"]

    # JSON 결과를 데이터프레임에 추가

# 'title'을 기준으로 카테고리 및 키워드 추출하여 바로 저장
categories_and_keywords = df['title'].apply(extract_category_and_keywords)

# 'Category'와 'Keyword1', 'Keyword2', 'Keyword3' 컬럼 추가
df['Category'] = categories_and_keywords.apply(lambda x: x[0])
df[['Keyword1', 'Keyword2', 'Keyword3']] = pd.DataFrame(
    categories_and_keywords.apply(lambda x: x[1]).tolist(), index=df.index)


# MongoDB 연결 설정
client = MongoClient("mongodb+srv://yusongod:gogogo1234@lglastproject.7etr9.mongodb.net/")  # MongoDB 서버에 연결
db = client['homeshop']  # 사용할 데이터베이스 이름
collection = db['GS_shop_live']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.reset_index(drop=True).to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")