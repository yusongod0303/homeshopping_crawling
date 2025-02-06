from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import pandas as pd
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# Selenium WebDriver 설정
chrome_options = Options()
chrome_options.add_argument("--headless")  # 브라우저 GUI 없이 실행
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

driver = webdriver.Chrome(options=chrome_options)

# 공영쇼핑 TV 쇼핑 스케줄 페이지 접속
driver.get("https://www.gongyoungshop.kr/tvshopping/tvSchedule.do#")
driver.implicitly_wait(10)  # 페이지 로딩 대기

# 날짜 선택 함수
def select_date(year, month, day):
    date_str = f"{year}{month:02}{day:02}"
    try:
        date_element = driver.find_element(By.CSS_SELECTOR, f"a[data-date='{date_str}']")
        date_element.click()
        print(f"Selected date: {date_str}")
    except Exception as e:
        print(f"Error selecting date {date_str}: {e}")
        driver.quit()

def crawl_data(year, month, day):
    date_str = f"{year}{month:02}{day:02}"  # 날짜 포맷: YYYYMMDD
    time.sleep(3)  # 페이지 갱신 대기
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    
    # 선택한 날짜에 해당하는 상위 div 선택
    target_div = soup.find("div", id=f"devPrdArea_{date_str}")
    if not target_div:
        print(f"No data found for {date_str}")
        return []  # 데이터가 없으면 빈 리스트 반환
    
    # 선택한 날짜의 time-box들 크롤링
    containers = target_div.find_all("div", class_="time-box")
    data = []

    for container in containers:
        try:
            time_text = container.find("div", class_="time").text.strip()
            title = container.find("h3", class_="tit").text.strip()
            price_section = container.find("div", class_="price")
            if price_section.find("span", class_="dc"):
                price = price_section.find_all("span")[1].text.strip()
            else:
                price = price_section.find("span").text.strip()
            rating = container.find("i", class_="i-star-full").find_next("span").text.strip()
            reviews = container.find("span", class_="t-gray").text.strip().strip("()")
            purchases = container.find("span", class_="ml-4").text.strip()
            image_url = container.find("div", class_="img").img["src"]
            class_attribute = container.get("class", [])
            product_id = [cls for cls in class_attribute if "dv-goodsUnit_" in cls][0].split("dv-goodsUnit_")[1]
            detail_url = f"https://www.gongyoungshop.kr/goods/selectGoodsDetail.do?prdId={product_id}"

            # 데이터 저장
            data.append({
                "broadcast_time": time_text,
                "title": title,
                "price": price,
                "rating": rating,
                "reviews": reviews,
                "purchases": purchases,
                "image_url": image_url,
                "url": detail_url,
                "datetime": f"{year}-{month:02}-{day:02}"
            })
        except AttributeError:
            continue  # 일부 데이터 누락된 경우 스킵

    return data


# 연, 월, 일 지정
year = 2025
month = 1
day = 9

# 날짜 선택 및 데이터 크롤링 실행
select_date(year, month, day)
data = crawl_data(year, month, day)

# 브라우저 종료
driver.quit()

# 결과 저장 및 출력
df = pd.DataFrame(data)
df['broadcast_time'] = df['broadcast_time'].str.split('~').str[0]
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)

df['rating'] = df['rating'].fillna('0').astype(float)
df['rating'] = df['rating'].replace(0, np.nan)

df['reviews'] = df['reviews'].replace({'₩': '', ',': ''}, regex=True)
df['reviews'] = df['reviews'].fillna('0').astype(int)
df['reviews'] = df['reviews'].replace(0, np.nan)

df['purchases'] = df['purchases'].replace([r'\+', r','], '', regex=True)
df['purchases'] = df['purchases'].fillna('0').astype(int)
df['purchases'] = df['purchases'].replace(0, np.nan)

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
collection = db['gongyoung']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")
