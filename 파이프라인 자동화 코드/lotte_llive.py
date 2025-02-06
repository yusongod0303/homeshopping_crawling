from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re  # 정규표현식을 위한 모듈
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

def select_date(driver, target_date):
    """
    특정 날짜를 선택하는 함수.
    :param driver: Selenium WebDriver 객체
    :param target_date: 원하는 날짜 (형식: "2024-12-18")
    """
    while True:
        date_elements = driver.find_elements(By.CSS_SELECTOR, "#date_list .swiper-slide")
        current_dates = [el.get_attribute("data-date") for el in date_elements]
        
        for date_element in date_elements:
            if date_element.get_attribute("data-date") == target_date:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", date_element)
                    driver.execute_script("arguments[0].click();", date_element)
                    print(f"{target_date} 날짜를 성공적으로 선택했습니다.")
                    return
                except Exception as e:
                    print(f"날짜 클릭 중 오류 발생: {e}")
        
        if target_date < current_dates[0]:
            try:
                prev_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".swiper-button-prev"))
                )
                prev_button.click()
                print("과거로 이동 중...")
            except Exception as e:
                print(f"이전 버튼 클릭 실패: {e}")
                break
        elif target_date > current_dates[-1]:
            try:
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".swiper-button-next"))
                )
                next_button.click()
                print("미래로 이동 중...")
            except Exception as e:
                print(f"다음 버튼 클릭 실패: {e}")
                break
        else:
            print(f"{target_date} 날짜를 찾을 수 없습니다.")
            break
        
        time.sleep(1)

# Chrome 드라이버 설정
# WebDriver 설정
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # 브라우저 창 표시 안함
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

# 지정된 URL로 이동
url = "https://www.lotteimall.com/main/viewMain.lotte#/main/tvschedule.lotte"
driver.get(url)

# "모든방송" 버튼을 클릭
try:
    all_broadcast_button = driver.find_element(By.XPATH, '//button[text()="모든방송"]')
    all_broadcast_button.click()
    print("모든방송 버튼을 클릭했습니다.")
except Exception as e:
    print(f"버튼 클릭 실패: {e}")

time.sleep(3)

# 특정 날짜 선택
year = '2025'
month = "01"
day = '04'
target_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
select_date(driver, target_date)

# "이전방송 더보기" 링크를 클릭
try:
    more_button = driver.find_element(By.XPATH, '//div[@class="schedule_previous_list"]/a[text()="이전방송 더보기"]')
    more_button.click()
    print("이전방송 더보기 버튼을 클릭했습니다.")
except Exception as e:
    print(f"버튼 클릭 실패: {e}")

time.sleep(5)

# 상품 정보를 추출
try:
    items = driver.find_elements(By.CSS_SELECTOR, ".schedule_container.schedule_mobiletv li")
    
    product_data = []
    detailed_urls = []  # 상세 페이지 URL을 저장할 리스트
    
    # 상품 정보와 상세 페이지 URL 미리 생성
    for item in items:
        try:
            # 방송 시간 추출
            broadcast_time = item.find_element(By.CSS_SELECTOR, ".schedule").text.strip()

            # 이미지 URL 추출
            image_url = item.find_element(By.CSS_SELECTOR, ".thumbnail_box img").get_attribute("src")

            # 상품명 추출
            product_name = item.find_element(By.CSS_SELECTOR, ".item_name").text.strip()

            # 상품 번호 추출
            match = re.search(r"/(\d+)_\d+\.jpg", image_url)  # 정규식을 이용해 상품 번호 추출
            product_number = match.group(1) if match else "번호 없음"

            # 상세 페이지 URL 생성
            detailed_url = f"https://www.lotteimall.com/goods/viewGoodsDetail.lotte?goods_no={product_number}"

            # 상세 페이지 URL을 리스트에 저장
            detailed_urls.append(detailed_url)

            # 상품 데이터를 미리 저장 (가격은 나중에 추가)
            product_data.append({
                "broadcast_time": broadcast_time,
                "image_url": image_url,
                "title": product_name,
                "price": "가격 정보 없음",  # 가격은 나중에 추출
                "url": detailed_url
            })

        except Exception as e:
            print(f"상품 정보 추출 실패: {e}")

    # 상세 페이지에서 가격 정보 크롤링
    for i, url in enumerate(detailed_urls):
        try:
            driver.get(url)

            # 가격 추출
            try:
                price_element = driver.find_element(By.CSS_SELECTOR, ".wrap_price .final .num")
                price = price_element.text.strip().replace(",", "")
            except Exception as e:
                print(f"가격 추출 실패: {e}")
                price = np.nan

            # 가격을 product_data에 업데이트
            product_data[i]["price"] = price

            # 이전 페이지로 돌아가기
            driver.back()
            time.sleep(1)

        except Exception as e:
            print(f"상세 페이지에서 가격 추출 실패: {e}")

    for product in product_data:
        print(product)

except Exception as e:
    print(f"상품 목록 가져오기 실패: {e}")

# pandas 데이터프레임 생성
df = pd.DataFrame(product_data)
df["datetime"] = f"{year}-{month}-{day}"

# 작업 후 브라우저 종료
driver.quit()

df['broadcast_time'] = df['broadcast_time'].str.split('~').str[0]
df['broadcast_time'] = df['broadcast_time'].replace({' ': ''}, regex=True)
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)

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
collection = db['lotte_llive']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")