import time
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# WebDriver 초기화 (크롬 브라우저 사용 예시)
driver = webdriver.Chrome()

try:
    # 대상 URL로 이동
    driver.get("https://www.skstoa.com/tv_schedule")

    # 날짜 선택 함수
    def select_date(target_date):
        next_button = driver.find_element(By.CSS_SELECTOR, "span.next.js_btn_next18")
        prev_button = driver.find_element(By.CSS_SELECTOR, "span.prev.js_btn_prev18")

        # 날짜가 보이는지 확인
        def is_date_visible(date_value):
            try:
                date_element = driver.find_element(By.CSS_SELECTOR, f"li[value='{date_value}']")
                return date_element.is_displayed()  # 화면에 표시 여부 확인
            except Exception:
                return False

        # 날짜가 나타날 때까지 버튼 클릭
        max_attempts = 50
        attempts = 0
        while not is_date_visible(target_date) and attempts < max_attempts:
            attempts += 1
            visible_dates = driver.find_elements(By.CSS_SELECTOR, "li[value]")
            visible_date_values = [date.get_attribute("value") for date in visible_dates]
            print(f"Visible dates: {visible_date_values}")

            min_visible_date = min(visible_date_values)
            max_visible_date = max(visible_date_values)

            if int(target_date) < int(min_visible_date):
                print("Clicking previous button...")
                prev_button.click()
            elif int(target_date) > int(max_visible_date):
                print("Clicking next button...")
                next_button.click()
            else:
                print(f"Date {target_date} is within the visible range.")
                break

            time.sleep(1)

        # 최종적으로 날짜를 클릭
        try:
            date_element = driver.find_element(By.CSS_SELECTOR, f"li[value='{target_date}']")
            print(f"Target date element: {date_element.get_attribute('outerHTML')}")
            
            # aria-hidden 상태 확인
            if date_element.get_attribute("aria-hidden") == "true":
                print(f"Date {target_date} is hidden. Trying to click anyway.")
            
            # JavaScript로 클릭 강제 실행
            driver.execute_script("arguments[0].click();", date_element)
            print(f"Date {target_date} clicked successfully.")
            time.sleep(2)
            return True

        except Exception as e:
            print(f"Failed to click date {target_date}: {e}")
            return False

    # 원하는 날짜 선택
    year = '2024'
    month = '12'
    day = '31'
    target_date = f"{year}{month}{day}"
    if select_date(target_date):
        print(f"Date {target_date} selected successfully.")
    else:
        print(f"Failed to select date {target_date}.")

    time.sleep(2)

    # 컨테이너 요소를 모두 가져오기
    containers = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.list.ga-prd"))
    )

    # 결과 저장 리스트
    results = []

    # 이전 방송 시간을 저장할 변수
    previous_broadcast_time = None

    # 각 컨테이너에서 정보 추출
    for container in containers:
        # 방송 시간 추출 (공통 시간 적용)
        try:
            time_element = container.find_element(By.CSS_SELECTOR, "div.timebox")
            broadcast_time = time_element.text.strip()  # 공백 제거
            previous_broadcast_time = broadcast_time  # 추출 성공 시 이전 값 업데이트
        except Exception:
            broadcast_time = previous_broadcast_time  # 이전 방송 시간 사용

        # 컨테이너 내의 모든 자식 요소 가져오기
        child_elements = container.find_elements(By.XPATH, "./*")

        # 함께 보면 좋은 상품 영역인지 확인
        skip_recommendation = False
        for child in child_elements:
            # 자식 요소의 HTML 확인
            child_html = child.get_attribute("outerHTML")

            # 시작 주석 확인
            if "<!-- 함께 보면 좋은 상품 -->" in child_html:
                skip_recommendation = True

            # 종료 주석 확인
            if "<!-- //함께 보면 좋은 상품 -->" in child_html:
                skip_recommendation = False
                continue  # 종료 주석 이후는 다시 크롤링 가능

            # 추천 상품 영역이면 크롤링 건너뛰기
            if skip_recommendation:
                continue

            # 상품 정보 추출
            if child.tag_name == "input" and "ga-prd-data" in child.get_attribute("class"):
                product_id = child.get_attribute("p-id")
                product_title = child.get_attribute("p-name")

                # 결과 저장
                results.append({
                    "product_id": product_id,
                    "title": product_title,
                    "broadcast_time": broadcast_time
                })

    # 각 상품 상세 페이지 방문 및 추가 정보 추출
    for result in results:
        product_id = result["product_id"]
        product_title = result["title"]

        # 상세 페이지 URL 생성
        detail_page_url = f"https://www.skstoa.com/display/goods/{product_id}?prdListCode=TV%ED%8E%B8%EC%84%B1_%EB%B0%A9%EC%86%A1%EC%83%81%ED%92%88%3E%EC%83%81%ED%92%88"

        # 상세 페이지로 이동
        print(f"Navigating to: {detail_page_url} for Product Title: {product_title}")
        driver.get(detail_page_url)

        # 2초 대기
        time.sleep(2)

        # 상품 이미지 URL 추출
        try:
            img_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.pic img#goodsImg"))
            )
            img_url = img_element.get_attribute("src")
            print(f"Product Image URL for {product_title}: {img_url}")

            # 이미지 URL을 결과에 추가
            result["image_url"] = img_url

        except Exception:
            print(f"Failed to fetch image for Product ID: {product_id}")

        # 상품 가격 추출
        try:
            price_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.lower .l_part .price strong"))
            )
            price = price_element.text.strip()  # 공백 제거
            print(f"Product Price for {product_title}: {price}")

            # 가격을 결과에 추가
            result["price"] = price

        except Exception:
            print(f"Failed to fetch price for Product ID: {product_id}")

        # 별점 및 리뷰 수 추출
        try:
            review_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.cont_rev p.txt"))
            )
            review_text = review_element.text.strip()  # "4.8(90건)" 형태
            star_rating, review_count = review_text.split("(")  # 괄호 기준 분리
            star_rating = star_rating.strip()  # 별점
            review_count = review_count.replace("건)", "").strip()  # 리뷰 수

            print(f"Star Rating for {product_title}: {star_rating}")
            print(f"Review Count for {product_title}: {review_count}")

            # 별점과 리뷰 수를 결과에 추가
            result["rating"] = star_rating
            result["reviews"] = review_count
            result["datetime"] = f"{year}-{month}-{day}"
            result["url"] = detail_page_url


        except Exception:
            print(f"Failed to fetch review data for Product ID: {product_id}")

except Exception as e:
    print(f"에러 발생: {e}")

finally:
    # WebDriver 종료
    driver.quit()

# 결과를 DataFrame으로 변환 후 CSV 저장
df = pd.DataFrame(results)

df.drop('product_id', axis=1, inplace=True)
df['broadcast_time'] = df['broadcast_time'].str.split(' ~ ').str[0]

df['reviews'] = df['reviews'].replace({'₩': '', ',': ''}, regex=True)
df['reviews'] = df['reviews'].fillna('0').astype(int)
df['reviews'] = df['reviews'].replace(0, np.nan)

df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].fillna('0').astype(int)

df['rating'] = df['rating'].fillna('0').astype(float)
df['rating'] = df['rating'].replace(0, np.nan)
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
collection = db['sk']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")