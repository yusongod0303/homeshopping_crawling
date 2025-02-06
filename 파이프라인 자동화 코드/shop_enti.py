from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime
import pandas as pd
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# 원하는 날짜 설정 (예시: 2024년 12월 31일)
year = '2024'
month = '12'
day = '31'

# 원하는 날짜 객체 생성
target_date = datetime(year=int(year), month=int(month), day=int(day))
print(f"크롤링할 목표 날짜: {target_date.strftime('%Y-%m-%d')}")

# 1. 브라우저 설정 및 드라이버 로드
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get("https://www.shoppingntmall.com/broadcast/tvBroadcastMain")

# ul 요소 내의 모든 날짜 버튼(li) 요소 찾기
ul_element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "ul.calendar-list"))
)

# ul 안의 모든 li 요소 가져오기
li_elements = ul_element.find_elements(By.TAG_NAME, "li")

# 목표 날짜에 해당하는 버튼 찾기
target_button = None
for li in li_elements:
    try:
        button = li.find_element(By.CSS_SELECTOR, "button.day")
        # 버튼 텍스트에서 날짜 추출 (예: "12.31")
        button_date = button.text.strip().replace(".", "-")  # '12.31' -> '12-31'
        
        # 목표 날짜와 비교
        if button_date == target_date.strftime("%m-%d"):
            target_button = button
            break
    except Exception as e:
        print(f"버튼에서 오류 발생: {e}")

if target_button:
    target_button.click()  # 목표 날짜 버튼 클릭
    print(f"클릭한 날짜: {target_date.strftime('%Y-%m-%d')}")
else:
    print(f"목표 날짜 {target_date.strftime('%Y-%m-%d')}에 해당하는 버튼을 찾을 수 없습니다.")

# 페이지 갱신 대기
time.sleep(2)

# pandas DataFrame에 저장할 리스트 초기화
data = []

# 2. 동적 로딩 처리 (ul.time-list가 나타날 때까지 기다림)
try:
    ul_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.time-list"))
    )

    # 3. 모든 <li> 태그 가져오기
    li_elements = ul_element.find_elements(By.TAG_NAME, "li")

    # tit-time을 포함한 li 요소만 필터링
    filtered_li_elements = [
        li for li in li_elements if li.find_elements(By.XPATH, ".//div[@class='tit-time']")
    ]

    print(f"Filtered LI count: {len(filtered_li_elements)}")
    # 필터링된 li 요소만 처리
    for index, li in enumerate(filtered_li_elements):
        try:
            # 1. 방송 시간 가져오기
            tit_time_div = li.find_element(By.XPATH, ".//div[@class='tit-time']")
            full_text = tit_time_div.text.strip()
            broadcast_time = full_text.split("방송시간")[-1].strip()

            if "현재 방송 중" in full_text or "채널안내" in full_text:
                # 이전 방송의 종료 시간 가져오기
                if index > 0:
                    prev_time = \
                        filtered_li_elements[index - 1].find_element(By.XPATH,
                                                                     ".//div[@class='tit-time']").text.split(
                            "방송시간")[-1].strip()
                    prev_end_time = prev_time.split("~")[-1].strip()
                else:
                    prev_end_time = "00:30"  # 첫 번째 방송이라 이전 방송이 없는 경우

                # 다음 방송의 시작 시간 가져오기
                if index < len(filtered_li_elements) - 1:
                    next_time = \
                        filtered_li_elements[index + 1].find_element(By.XPATH,
                                                                     ".//div[@class='tit-time']").text.split(
                            "방송시간")[-1].strip()
                    next_start_time = next_time.split("~")[0].strip()
                else:
                    next_start_time = "00:30"  # 마지막 방송이라 다음 방송이 없는 경우

                # 방송 시간 계산
                broadcast_time = f"{prev_end_time} ~ {next_start_time}"
            else:
                # "방송시간" 텍스트 파싱
                broadcast_time = full_text.split("방송시간")[-1].strip()

            # 2. 방송 제목 가져오기
            title_a = li.find_element(By.XPATH, ".//a[@class='tit tit-h2']")
            broadcast_title = title_a.find_element(By.XPATH, ".//span[@class='name']").text.strip()

            # 3. 가격 가져오기
            price_em = li.find_element(By.XPATH, ".//em[@class='txt-2xl']")
            price = price_em.text.strip()

            # 4. 이미지 URL 가져오기
            image_tag = li.find_element(By.XPATH, ".//div[@class='prd-img']//img")
            image_url = image_tag.get_attribute("src")

            # 5. 판매 링크 가져오기
            sales_link = title_a.get_attribute("href")

            try:
                # 새 창 열기
                driver.execute_script("window.open(arguments[0]);", sales_link)

                # 창 핸들 전환
                driver.switch_to.window(driver.window_handles[-1])

                # 동적 로딩 처리
                prd_basic_info = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".prd-basic-info"))
                )

                # 별점 가져오기
                rating_span = prd_basic_info.find_element(By.CSS_SELECTOR, ".num")
                rating = rating_span.text.strip().split("\n")[-1]

                # 리뷰 수 가져오기
                review_span = prd_basic_info.find_element(By.CSS_SELECTOR, ".comment")
                review_count = review_span.text.strip().split("\n")[-1].replace("(", "").replace(")", "")

                # 창 닫기
                driver.close()

                # 원래 창으로 전환
                driver.switch_to.window(driver.window_handles[0])
            except Exception as inner_e:
                print(f"Error extracting rating or review count for LI #{index + 1}: {inner_e}")
                rating = None
                review_count = None

            # 결과를 리스트에 추가
            result = {
                "datetime": target_date.strftime("%Y-%m-%d"),
                "broadcast_time": broadcast_time,
                "title": broadcast_title,
                "price": price,
                "image_url": image_url,
                "url": sales_link,
                "rating": rating,
                "reviews": review_count
            }

            data.append(result)

            print(f"Data collected for index {index + 1}: {result}")

        except Exception as e:
            # 에러 처리
            print(f"Error processing LI #{index + 1}: {e}")

except Exception as e:
    print(f"Error: {e}")

# 브라우저 종료
driver.quit()

# 4. DataFrame으로 변환
df = pd.DataFrame(data)

df['broadcast_time'] = df['broadcast_time'].str.split('~').str[0]
df['broadcast_time'] = df['broadcast_time'].replace({' ': ''}, regex=True)
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].replace(r'[^\d]', '', regex=True)  # 숫자 외의 문자 제거
df['price'] = pd.to_numeric(df['price'], errors='coerce')
df['price'] = df['price'].fillna('0').astype(int)
df['price'] = df['price'].replace(0, np.nan)

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
collection = db['shop_enti']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")