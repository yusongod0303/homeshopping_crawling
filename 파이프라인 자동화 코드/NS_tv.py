from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import pandas as pd
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

#필터
type='tv' # shop-plus, tv 두 종류 있음 
year ='2025'
month ='01'
day ='06'

# 드라이버 설정
driver = webdriver.Chrome()

# URL 열기 (메인 페이지)
url = f"https://m.nsmall.com/store/fixed/schedule/tv/{year}{month}{day}"
# url = f"https://m.nsmall.com/store/fixed/schedule/shop-plus/{year}{month}{day}"
driver.get(url)

# 페이지 로딩 대기
time.sleep(3)

# 방송 시간과 링크 추출
products = []

# 모든 컨테이너 탐색
containers = driver.find_elements(By.CSS_SELECTOR, "li.schedule-a-item")

for container in containers:
    try:
        # 방송 시간 추출
        broadcast_time = container.find_element(By.CSS_SELECTOR, ".onair-time .time").text.strip()

        # 상품 링크 추출
        product_elements = container.find_elements(By.CSS_SELECTOR, "a.img-wrap")
        for product in product_elements:
            link = product.get_attribute("href")

            # 방송 시간과 링크 저장
            products.append({
                "broadcast_time": broadcast_time,
                "link": link
            })
    except Exception as e:
        print(f"[ERROR] Error processing container: {e}")

# 드라이버 종료
driver.quit()

# products 리스트를 데이터프레임으로 변환
df = pd.DataFrame(products)

# 드라이버 설정
driver = webdriver.Chrome()

# 각 링크에 대해서 추가적인 정보를 크롤링하여 데이터프레임에 새로운 컬럼 추가
for index, row in df.iterrows():
    link = row['link']
    
    try:
        # 링크로 이동
        driver.get(link)
        time.sleep(3)  # 페이지 로딩 대기
        
        # 상품 이름 추출
        product_name = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".goods-name"))
        ).text.strip()
        
        # 가격 추출
        price_element = driver.find_elements(By.CSS_SELECTOR, ".current-price")
        price = price_element[0].text.strip() if price_element else "0 원"
        
        # 판매 수 추출
        buy_num_element = driver.find_elements(By.CSS_SELECTOR, ".buy-num")
        buy_num = buy_num_element[0].text.strip() if buy_num_element else "0"
        
        # 별점 추출
        try:
            rating_element = driver.find_element(By.CSS_SELECTOR, ".review-info .rating em")
            rating = rating_element.text.strip()
        except Exception:
            rating = "0"
        
        # 리뷰 수 추출
        try:
            review_count_element = driver.find_element(By.CSS_SELECTOR, ".review-info .number")
            review_count = review_count_element.text.strip().strip("()")
        except Exception:
            review_count = "0"
        
       # 이미지를 로드하기 위해 해당 이미지를 화면에 보이도록 스크롤
        try:
            # 이미지 요소를 찾아서 화면에 보이게 스크롤
            image_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "picture.lazy-image img"))
            )
            
            # 이미지를 화면에 보이도록 스크롤
            driver.execute_script("arguments[0].scrollIntoView(true);", image_element)
            time.sleep(2)  # 이미지가 로드될 시간 기다리기

            # 이미지 URL 추출
            image_url = image_element.get_attribute("src")
            if not image_url:
                print("src 속성에서 이미지 URL을 찾을 수 없습니다.")
            else:
                print(f"이미지 URL: {image_url}")

        except Exception as e:
            print(f"[ERROR] 이미지 URL 추출 실패: {e}")
        
        # 데이터프레임에 새로운 정보 추가
        df.at[index, 'title'] = product_name
        df.at[index, 'price'] = price
        df.at[index, 'purchases'] = buy_num
        df.at[index, 'rating'] = rating
        df.at[index, 'reviews'] = review_count
        df.at[index, 'image_url'] = image_url
        df.at[index, 'datetime'] = f"{year}-{month}-{day}"

    except Exception as e:
        print(f"[ERROR] Error extracting details for product link {link}: {e}")

# 드라이버 종료
driver.quit()

df = df.rename(columns={'link': 'url'})
df['broadcast_time'] = df['broadcast_time'].str.split(' ~ ').str[0]
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)
df['purchases'] = df['purchases'].replace({'구매': '', ',': '', ' ' : ''}, regex=True)
df['purchases'] = df['purchases'].fillna('0').astype(int)
df['rating'] = df['rating'].fillna('0').astype(float)
df['rating'] = df['rating'].replace(0, np.nan)
df['reviews'] = df['reviews'].replace({'₩': '', ',': ''}, regex=True)
df['reviews'] = df['reviews'].fillna('0').astype(int)
df['reviews'] = df['reviews'].replace(0, np.nan)


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
collection = db['NS_tv']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.reset_index(drop=True).to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")