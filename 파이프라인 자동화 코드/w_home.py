from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import time
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# WebDriver 설정
driver = webdriver.Chrome()

year = '2024'
month = '12'
date = 30  # 예시로 15일만 수집하도록 설정

try:
    # 날짜 형식 맞추기 (예: 15 -> 15일)
    date_str = f"{date:02d}"  

    url = f"https://www.w-shopping.co.kr/broadcast/main/?fromDate={year}/{month}/{date_str}"

    # 1. 페이지로 이동
    driver.get(url)
    collected_links = []  # 수집된 링크를 저장할 리스트
    broadcast_times = []  # 방송 시간을 저장할 리스트

    while True:
        # 현재 페이지에서 상품 컨테이너 가져오기
        product_containers = driver.find_elements(By.CSS_SELECTOR, "li#onairShow")

        if not product_containers:
            print(f"No product containers found for {year}-{month}-{date_str}.")
            break

        for container in product_containers:
            try:
                # 방송 시간 추출
                time_element = container.find_element(By.CSS_SELECTOR, "div.schedule_left > p.time")
                broadcast_time = time_element.text.strip()

                # 각 컨테이너 내의 모든 상품 링크 추출
                link_elements = container.find_elements(By.CSS_SELECTOR, "a[data-target-name='broadcast']")

                for link_element in link_elements:
                    link_href = link_element.get_attribute("href")

                    if link_href not in collected_links:
                        collected_links.append(link_href)  # 링크 저장
                        broadcast_times.append(broadcast_time)  # 해당 방송 시간 저장
                        print(f"Collected link: {link_href}, Broadcast time: {broadcast_time}")

            except Exception as e:
                print(f"Error processing container for {year}-{month}-{date_str}: {e}")
                continue

        # 스크롤로 페이지 아래로 이동 (추가 상품 로드를 시도)
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)  # 스크롤 후 안정화를 위해 대기

        # 새로운 상품 로드 여부 확인
        new_containers = driver.find_elements(By.CSS_SELECTOR, "li#onairShow")
        if len(new_containers) == len(product_containers):
            print(f"No more new containers to process for {year}-{month}-{date_str}.")
            break

    # 2. 상세 페이지에서 데이터 추출
    product_data = []  # 상품 이름, 가격, URL, 방송 시간, 이미지, 별점 저장용 리스트

    for link, broadcast_time in zip(collected_links, broadcast_times):
        try:
            driver.get(link)
            time.sleep(2)  # 페이지 로드 대기

            # 상품 이름 추출
            try:
                product_name = driver.find_element(By.CSS_SELECTOR, "h2.title_detail > strong").text
            except Exception:
                product_name = "NA"

            # 가격 추출
            try:
                price_element = driver.find_element(By.CSS_SELECTOR, "span.txt_price em")
                price = price_element.text.replace(",", "").replace("원", "")
            except Exception:
                price = "NA"

            # 이미지 링크 추출
            try:
                image_element = driver.find_element(By.CSS_SELECTOR, "div.detail_main_img > img")
                image_src = image_element.get_attribute("src")
            except Exception:
                image_src = "NA"

            # 별점 추출
            try:
                # 리뷰 버튼 클릭
                review_button = driver.find_element(By.XPATH, "//a[contains(text(), '상품평')]")
                review_button.click()
                time.sleep(2)  # 리뷰 로드 대기

                # 별점 추출
                score_element = driver.find_element(By.CSS_SELECTOR, "div.score_number > strong.total_score")
                score = score_element.text.strip()
            except Exception:
                score = "NA"

            # 데이터 저장
            product_data.append({
                "title": product_name,
                "price": price,
                "url": link,
                "broadcast_time": broadcast_time,
                "image_url": image_src,
                "rating": score
            })

        except Exception as e:
            print(f"Error accessing link {link}: {e}")
            continue

    # 3. 데이터 CSV로 저장
    df = pd.DataFrame(product_data)
    df['datetime'] = f"{year}-{month}-{date_str}"
    df['broadcast_time'] = df['broadcast_time'].str.split(' ~ ').str[0]
    df['rating'] = df['rating'].fillna('0').astype(float)
    df['rating'] = df['rating'].replace(0, np.nan)
    df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
    # 'price' 열에서 'NA' 값을 NaN으로 바꿈
    df['price'] = df['price'].replace('NA', np.nan)
    
    # NaN 값을 0 또는 다른 값으로 채울 수 있음
    df['price'] = df['price'].fillna('0').astype(int)
    
    df['price'] = df['price'].replace(0, np.nan)
    

finally:
    # 드라이버 종료
    driver.quit()


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
collection = db['w_home']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")