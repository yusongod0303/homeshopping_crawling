import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# Selenium 설정
chrome_options = Options()
driver = webdriver.Chrome(options=chrome_options)

# URL로 이동
url = "https://www.hnsmall.com/display/tvschedule"
driver.get(url)

# 원하는 날짜
year = "2025"
month = "01"
day = "9"  # 원하는 날짜
prev_button_selector = ".btn.prev.swiper-prev"  # 이전 버튼

def select_date():
    """특정 날짜를 찾아 클릭하거나 이전 버튼 클릭 후 다시 시도"""
    def find_and_click_day():
        try:
            # 날짜 선택
            target_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, f"//span[text()='{day}']"))
            )
            driver.execute_script("arguments[0].click();", target_element)
            print(f"날짜 {day}를 클릭했습니다.")
            return True
        except Exception:
            return False

    # 1차 시도
    if not find_and_click_day():
        print(f"날짜 {day}를 찾을 수 없어 이전 버튼을 클릭합니다.")
        try:
            prev_button = driver.find_element(By.CSS_SELECTOR, prev_button_selector)
            driver.execute_script("arguments[0].click();", prev_button)
            time.sleep(1)
            if not find_and_click_day():
                raise Exception(f"날짜 {day}를 찾을 수 없습니다.")
        except Exception as e:
            print(f"이전 버튼 클릭 중 문제가 발생했습니다: {e}")
            raise

try:
    # 날짜 선택
    select_date()

    # 페이지 로딩 대기
    time.sleep(3)

    # 'item' 컨테이너 찾기
    items = driver.find_elements(By.CLASS_NAME, "item")

    # 상품 정보 리스트 초기화
    products = []

    # 상품 제목, 상품 ID, 방송 시간 추출
    for item in items:
        try:
            # 방송 시간 추출
            time_element = item.find_element(By.CSS_SELECTOR, ".live-time .time span")
            broadcast_time = time_element.text.strip()

            # 'goods-list' 컨테이너 찾기 (상품 리스트)
            goods = item.find_elements(By.CLASS_NAME, "goods-list")

            for good in goods:
                try:
                    # 상품 제목 추출
                    title_element = good.find_element(By.CSS_SELECTOR, ".tit")
                    title = title_element.text.strip()

                    # title이 비어 있으면 건너뛰기
                    if not title:
                        continue

                    # 상품 ID 추출 (1단계: onclick 속성에서 추출)
                    onclick_value = good.get_attribute("onclick")
                    product_id = None

                    if onclick_value and "goGoods" in onclick_value:
                        product_id = onclick_value.split("'")[1]
                    else:
                        try:
                            a_tag = good.find_element(By.CSS_SELECTOR, "a.goods-info")
                            onclick_value_a = a_tag.get_attribute("onclick")
                            if onclick_value_a and "goGoods" in onclick_value_a:
                                product_id = onclick_value_a.split("'")[1]
                        except:
                            product_id = None

                    # 상품 정보를 리스트에 추가
                    products.append({
                        "broadcast_time": broadcast_time,
                        "title": title,
                        "product_id": product_id,
                    })
                except Exception as e:
                    continue
        except Exception as e:
            continue

    # 상품 상세 페이지 방문 및 정보 추출
    base_url = "http://www.hnsmall.com/display/goods.do?goods_code={}&trackingarea=60000059^8005369^1304363"

    for product in products:
        product_id = product["product_id"]
        if product_id:
            detail_url = base_url.format(product_id)
            print(f"Visiting: {detail_url}")
            
            # 상세 페이지로 이동
            driver.get(detail_url)
            time.sleep(2)
            
            try:
                # 이미지 URL 추출
                image_element = driver.find_element(By.CSS_SELECTOR, "div.imgBig img")
                image_url = image_element.get_attribute("src")
                if image_url.startswith("//"):
                    image_url = "http:" + image_url

                # 가격 추출
                price_element = driver.find_element(By.CSS_SELECTOR, "div.priceTotal strong")
                price = price_element.text.strip()

                # 평점 추출
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.reviewWrap em"))
                    )
                    rating_element = driver.find_element(By.CSS_SELECTOR, "div.reviewWrap em")
                    rating = rating_element.text.strip()
                except Exception as e:
                    print(f"평점 요소를 찾을 수 없습니다: {e}")
                    rating = None

                # 리뷰 수 추출
                try:
                    review_element = driver.find_element(By.CSS_SELECTOR, "div.reviewWrap span.num")
                    reviews = review_element.text.strip("()")
                except Exception as e:
                    reviews = None

                # 상품 정보를 업데이트
                product["url"] = detail_url
                product["image_url"] = image_url
                product["price"] = price
                product["rating"] = rating
                product["reviews"] = reviews
                product["date"] = f"{year}-{month}-{day}"
            except Exception as e:
                print(f"상세 페이지에서 데이터를 추출하는 중 오류 발생: {e}")
                product["url"] = detail_url
                product["image_url"] = None
                product["price"] = None
                product["rating"] = None
                product["reviews"] = None

    # DataFrame으로 변환
    df = pd.DataFrame(products)
finally:
    # 브라우저 종료
    driver.quit()

# DataFrame 수정 예시: 가격을 정수형으로 변경
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)

# 추가적으로 DataFrame 수정 예시: 평점이 없는 항목은 0으로 설정
df['rating'] = df['rating'].fillna('0').astype(float)
df['rating'] = df['rating'].replace(0, np.nan)
df['rating'] = (df['rating'] / 20).round(1)
df['reviews'] = df['reviews'].replace({'₩': '', ',': ''}, regex=True)
df['reviews'] = df['reviews'].fillna('0').astype(int)
df['reviews'] = df['reviews'].replace(0, np.nan)

df['broadcast_time'] = df['broadcast_time'].str.split(' ~ ').str[0]
df = df.drop('product_id', axis=1)

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
collection = db['home_and_shop']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")
