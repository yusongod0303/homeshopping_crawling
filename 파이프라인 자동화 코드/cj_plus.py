import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# WebDriver 설정
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # 브라우저 창 표시 안함
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 날짜 선택 함수
def select_date(driver, year, month, day):
    target_date = f"{year}{month.zfill(2)}{day.zfill(2)}"
    try:
        # 날짜 선택
        date_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"li[data-bd-dt='{target_date}'] a"))
        )
        date_element.click()  # 선택한 날짜 클릭
        print(f"날짜 {target_date}를 성공적으로 선택했습니다.")
        # 페이지 로딩 대기
        time.sleep(3)
    except Exception as e:
        print(f"날짜 {target_date}를 선택하는 데 실패했습니다: {e}")

# 방송 시간 크롤링 함수 (기존 코드 유지)
def get_broadcast_times(soup):
    times = []

    # 첫 번째 방송 시간 가져오기
    first_broadcast = soup.find('h4', class_='state_bar past')
    if first_broadcast:
        first_time = first_broadcast.find('span', id='time_area')
        if first_time:
            times.append(first_time.text.strip())

    # 이후 방송 시간 가져오기
    other_broadcasts = soup.find_all('h4', class_='state_bar')
    for broadcast in other_broadcasts:
        time_span = broadcast.find('span', class_='pgmDtm')
        if time_span:
            times.append(time_span.text.strip())

    return times

# 방송 상품 크롤링 함수 (수정)
def get_broadcast_products_with_times(driver, broadcast_times):
    """방송 시간(broadcast_times)과 상품 데이터를 매핑"""
    product_list = []
    try:
        # state_bar와 연결된 상품 컨테이너 추출
        state_bars = driver.find_elements(By.CSS_SELECTOR, "h4.state_bar")

        for idx, state_bar in enumerate(state_bars):
            # 현재 방송 시간 매핑
            broadcast_time = broadcast_times[idx] if idx < len(broadcast_times) else "시간 없음"

            try:
                # 다음 형제 요소로 이동하여 상품 컨테이너 확인
                product_container = state_bar.find_element(By.XPATH, "following-sibling::ul[@class='list_schedule_prod']")
                
                # 상품 추출
                product_elements = product_container.find_elements(By.CSS_SELECTOR, "li")
                for product in product_elements:
                    try:
                        link = product.find_element(By.CSS_SELECTOR, "a.link_thumb").get_attribute("href")
                        title = product.find_element(By.CSS_SELECTOR, "strong.tit_prod a").text.strip()
                        try:
                            price = product.find_element(By.CSS_SELECTOR, "span.num_cost em.num").text.strip()
                        except:
                            price = "가격 없음"
                        image_url = product.find_element(By.CSS_SELECTOR, "span.flex_cont img").get_attribute("src")
                        
                        # 상품 정보와 방송 시간 추가
                        product_list.append({
                            "broadcast_time": broadcast_time,
                            "url": link,
                            "title": title,
                            "price": price,
                            "image_url": image_url
                        })
                    except Exception as e:
                        print(f"상품 정보 추출 중 오류: {e}")
            except Exception as e:
                print(f"상품 컨테이너를 찾는 중 오류: {e}")
    except Exception as e:
        print(f"상품 크롤링 오류: {e}")

    return product_list

# 사이트 URL
# url = "https://display.cjonstyle.com/p/homeTab/main?hmtabMenuId=002409&rPIC=schedulePC" # 라이브
url = "https://display.cjonstyle.com/p/homeTab/main?hmtabMenuId=002409&broadType=plus" # 플러스
driver.get(url)

# 페이지 로딩 대기
time.sleep(3)

# 날짜 선택 (사용자가 원하는 날짜 입력)
year_t = '2025'
month_t = "1"
day_t = '8'
select_date(driver, year_t, month_t, day_t)

# 방송 시간 및 상품 크롤링
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')
broadcast_times = get_broadcast_times(soup)  # 기존 함수 호출
broadcast_products_with_times = get_broadcast_products_with_times(driver, broadcast_times)

# WebDriver 종료
driver.quit()

# 확인 출력
print("방송 상품 및 시간 매핑 완료:")
for product in broadcast_products_with_times:
    print(product)

# pandas 데이터프레임 생성
df = pd.DataFrame(broadcast_products_with_times)
df["datetime"]=f"{year_t}-{month_t.zfill(2)}-{day_t.zfill(2)}"
df['broadcast_time'] = df['broadcast_time'].str.split(' ~ ').str[0]
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)


client = OpenAI(
    api_key="#api키"
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
collection = db['cj_plus']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")