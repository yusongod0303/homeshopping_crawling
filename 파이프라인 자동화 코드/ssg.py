import time
import re
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# 드라이버 설정
driver = webdriver.Chrome()
driver.get("https://www.shinsegaetvshopping.com/broadcast/main")

# 오늘 날짜 가져오기
today = datetime.today()
today_str = today.strftime("%Y/%m/%d")  # 형식: 2024/12/23

# 입력된 날짜 (예시: 2024년 12월 16일)
year = 2024
month = 12
day = 31
target_date = f"{year}/{month:02d}/{day:02d}"

# 편성표 버튼 클릭
tv_schedule_button = driver.find_element(By.CSS_SELECTOR, "a.link[data-index='2']")
tv_schedule_button.click()
time.sleep(2)  # 페이지 로딩 대기

# 가장 과거 날짜로 이동
def move_to_past():
    while True:
        prev_button = driver.find_element(By.CSS_SELECTOR, "button.day-tablist-prev")
        if "disabled" in prev_button.get_attribute("class"):
            print("가장 과거 날짜로 이동 완료")
            break
        else:
            prev_button.click()
            time.sleep(2)  # 페이지 로드 대기

# 날짜 버튼 클릭 (입력된 날짜로 이동)
def select_date(target_date):
    try:
        # 해당 날짜를 가진 날짜 버튼을 찾기
        date_buttons = driver.find_elements(By.CSS_SELECTOR, "a.link[data-fd]")
        for button in date_buttons:
            button_date = button.get_attribute("data-fd")
            if button_date == target_date:
                button.click()
                print(f"{target_date} 날짜 클릭")
                return True
        print(f"해당 날짜 ({target_date})를 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"날짜 클릭 중 오류 발생: {e}")
        return False

# 오늘 날짜보다 과거 날짜인 경우 과거로 이동
if target_date < today_str:
    print(f"{target_date}는 과거 날짜입니다. 과거로 이동합니다.")
    move_to_past()

# 입력된 날짜로 이동 (미래 날짜라면 과거로 이동하지 않음)
if select_date(target_date):
    # 페이지 로딩 대기 (방송 정보가 나타날 때까지)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "dl[data-onair='N'], dl[data-onair='Y']"))
    )

    # 방송 정보 크롤링
    data = []  # df는 함수 밖에서 정의된 데이터 리스트로 대체
    def crawl_broadcast_info():
        try:
            broadcasts = driver.find_elements(By.CSS_SELECTOR, "dl[data-onair='N'], dl[data-onair='Y']")
            for i, broadcast in enumerate(broadcasts):
                try:
                    # 방송 시간 추출
                    if broadcast.get_attribute("data-onair") == 'Y':
                        # 현재 방송이 진행 중인 경우, 이전 방송 끝나는 시간과 다음 방송 시작 시간 구하기
                        # 이전 방송 (종료된 방송)
                        if i > 0:  # 이전 방송이 존재하는 경우
                            prev_broadcast = broadcasts[i - 1]
                            if prev_broadcast.get_attribute("data-onair") == 'N':  # 이전 방송이 종료된 방송인 경우
                                prev_end_time = prev_broadcast.find_element(By.CSS_SELECTOR, "span._time").text.strip()
                                prev_end_time = prev_end_time[-5:]  # 종료 시간의 뒷자리 5자리 (예: 19:35)
                            else:
                                prev_end_time = "N/A"
                        else:
                            prev_end_time = "N/A"

                        # 다음 방송 (종료된 방송)
                        if i < len(broadcasts) - 1:  # 다음 방송이 존재하는 경우
                            next_broadcast = broadcasts[i + 1]
                            if next_broadcast.get_attribute("data-onair") == 'N':  # 종료된 방송이면 시작 시간 가져오기
                                next_start_time = next_broadcast.find_element(By.CSS_SELECTOR,
                                                                              "span._time").text.strip()
                                next_start_time = next_start_time[:5]  # 시작 시간의 첫자리 5자리 (예: 20:35)
                            else:
                                next_start_time = "N/A"
                        else:
                            next_start_time = "N/A"

                        # 방송 시간 포맷 (예: 19:35~20:35)
                        if prev_end_time != "N/A" and next_start_time != "N/A":
                            broadcast_time = f"{prev_end_time}~{next_start_time}"
                        else:
                            broadcast_time = "N/A"

                    else:
                        # 방송이 종료된 방송의 경우 시간 그대로 가져오기
                        broadcast_time_element = broadcast.find_element(By.CSS_SELECTOR, "span._time")
                        broadcast_time = broadcast_time_element.text.strip()

                except Exception:
                    broadcast_time = "시간 없음"

                # 각 상품 카드를 찾습니다
                product_cards = broadcast.find_elements(By.CSS_SELECTOR, "div.card")

                for card in product_cards:
                    try:
                        # 상품 정보 추출
                        supporting_text = card.find_element(By.CSS_SELECTOR, "div.area-supporting-text")
                        title = supporting_text.find_element(By.CSS_SELECTOR, "span._goodsName").text.strip()

                        # 상품 URL ID 추출
                        onclick_attr = supporting_text.find_element(By.CSS_SELECTOR, "a").get_attribute("onclick")
                        match = re.search(r"goPage\('(/display/detail/(\d+))',", onclick_attr)
                        product_url_id = match.group(2) if match else "URL 없음"
                        url = f"https://www.shinsegaetvshopping.com/display/detail/{product_url_id}"

                        try:
                            price = supporting_text.find_element(By.CSS_SELECTOR,
                                                                         "span._bestPrice").text.strip()
                        except Exception:
                            price = "NA"

                        # 이미지 URL 추출 (두 가지 구조를 모두 처리)
                        try:
                            img_element = card.find_element(By.CSS_SELECTOR, "div.area-richmedia img._image")
                            image_url = img_element.get_attribute("src")
                        except Exception:
                            image_url = "이미지 없음"

                        # 데이터 저장 및 출력
                        data.append(
                            [target_date.replace('/', '-'), broadcast_time, title, url, price, image_url])

                        print(f"상품 날짜: {target_date}")
                        print(f"방송 시간: {broadcast_time}")
                        print(f"상품 제목: {title}")
                        print(f"상품 URL: {url}")
                        print(f"상품 가격: {price}")
                        print(f"상품 이미지 URL: {image_url}")
                        print("-" * 50)

                    except Exception as e:
                        print(f"상품 데이터 수집 중 오류: {e}")
            print(f"{target_date} 날짜의 방송 정보 크롤링 완료")

        except Exception as e:
            print(f"방송 정보 크롤링 중 오류 발생: {e}")

    # 크롤링 함수 호출
    crawl_broadcast_info()

    # 크롤링된 데이터를 DataFrame으로 변환
    df = pd.DataFrame(data, columns=['datetime', 'broadcast_time', 'title', 'url', 'price', 'image_url'])

# 크롬 드라이버 종료
driver.quit()

df['broadcast_time'] = df['broadcast_time'].str.split('~').str[0]

df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
# 'price' 열에서 'NA' 값을 NaN으로 바꿈
df['price'] = df['price'].replace('NA', np.nan)

# NaN 값을 0 또는 다른 값으로 채울 수 있음
df['price'] = df['price'].fillna(0)

# 이제 int로 변환
df['price'] = df['price'].astype(int)

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
collection = db['ssg']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")