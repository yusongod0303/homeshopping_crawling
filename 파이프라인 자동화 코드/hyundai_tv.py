import time
import pandas as pd
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient


# 동적 클릭 함수 정의
def click_date_button(driver, day):
    wait = WebDriverWait(driver, 10)

    # "이전" 버튼 가져오기
    prev_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.ui-item-control.prev-tab')))

    while True:
        # 모든 날짜 항목 가져오기
        date_elements = driver.find_elements(By.CSS_SELECTOR, 'ul.scroll-items li.ui-nav')

        for element in date_elements:
            try:
                # 날짜 텍스트 확인
                date_span = element.find_element(By.CLASS_NAME, 'date')
                if date_span.text == f"{day:02d}":  # 날짜와 일치하는 버튼 클릭
                    element.click()
                    print(f"Clicked on date: {day}")
                    return
            except Exception as e:
                continue

        # "이전" 버튼 클릭 (날짜 스크롤)
        try:
            print("Clicking 'Previous' button to load earlier dates...")
            prev_button.click()
            time.sleep(1)  # 버튼 클릭 후 1초 대기
        except Exception as e:
            print(f"Failed to click 'Previous' button: {e}")
            break


# 상품 데이터 추출 함수 (DataFrame 반환)
def extract_product_info(driver, date):
    # 빈 리스트로 초기화
    product_data = []

    time_text = None  # 기본적으로 시간 정보를 None으로 설정

    # 페이지 끝까지 스크롤 다운 (상품 모두 로드)
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # 각 타임별 상품 데이터 추출
    time_blocks = driver.find_elements(By.CSS_SELECTOR, "ul.time-product-list > li.ui-conts-break-wrap")
    for block in time_blocks:
        try:
            # 시간 정보 추출
            try:
                time_element = block.find_element(By.CSS_SELECTOR, ".time-bar .time")
                time_text = time_element.text
            except Exception as time_error:
                print("시간 정보 추출 실패, 기존 시간을 사용합니다.")

            # 해당 시간 블록 내 상품 리스트 추출
            products_in_time = block.find_elements(By.CSS_SELECTOR, ".pdlist-wrap ul > li.pdthumb")

            for product in products_in_time:
                try:
                    # 상품 정보 추출
                    title_element = product.find_element(By.CSS_SELECTOR, ".pdname")
                    title = title_element.text

                    img_element = product.find_element(By.CSS_SELECTOR, "div#fullImg img")
                    img_url = img_element.get_attribute("src")

                    # 가격 가져오기
                    try:
                        price_element = product.find_element(By.CSS_SELECTOR, ".pdprice .discount em")
                        price = price_element.text.strip()
                    except Exception:
                        # "상담후결정" 등 다른 구조 처리
                        try:
                            price_element = product.find_element(By.CSS_SELECTOR, ".pdprice em.rental")
                            price = price_element.text.strip()
                        except Exception:
                            price = "가격 없음"

                    # 상품 URL 추출
                    try:
                        detail_link_element = product.find_element(By.CSS_SELECTOR, "a.hoverview")
                        relative_url = detail_link_element.get_attribute("href")
                        base_url = "https://www.hmall.com"
                        detail_url = base_url + relative_url if relative_url.startswith("/") else relative_url
                    except Exception:
                        detail_url = "URL 없음"

                    # 데이터 저장 (DataFrame에 추가할 형태로 변환)
                    product_data.append({
                        "datetime": date,
                        "broadcast_time": time_text,  # 시간 정보가 없으면 None을 사용
                        "title": title,
                        "price": price,
                        "image_url": img_url,
                        "url": detail_url,
                    })

                    # 결과 출력
                    print(
                        f"datetime : {date}, broadcast_time: {time_text}, title: {title}, price: {price}, image: {img_url}, item_url : {detail_url}")
                except Exception as e:
                    print(f"상품 데이터 추출 실패: {e}")
                    continue

        except Exception as e:
            print(f"시간 블록 데이터 추출 실패: {e}")
            continue

    # DataFrame으로 변환하여 반환
    return pd.DataFrame(product_data)


# 드라이버 실행 및 종료를 포함하는 함수
def run_crawling_for_day(day):
    # ChromeDriver 설정
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get("https://www.hmall.com/pd/dpl/brodPordPbdv?mainDispSeq=2&brodType=dtv")  # 현대홈쇼핑의 플러스 URL

    # 날짜 선택
    year = 2025
    month = 1
    date = f"{year}-{month:02d}-{day:02d}"

    # 모든 날짜 항목 로드 대기
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'ul.scroll-items li.ui-nav'))
    )

    # 날짜 선택
    click_date_button(driver, day)

    # 데이터 추출
    time.sleep(2)
    product_data_df = extract_product_info(driver, date)

    # DataFrame 저장 (필요시 csv 등으로 저장 가능)
    # 예: product_data_df.to_csv(f"products_{date}.csv", index=False, encoding='utf-8-sig')
    print(f"Data for {date} extracted successfully.")

    # 드라이버 종료
    driver.quit()
    print(f"크롤링 완료 for {date}")

    return product_data_df


# 메인 실행
if __name__ == "__main__":
    day = 6
    df = run_crawling_for_day(day)

    df['broadcast_time'] = df['broadcast_time'].str.split(' ~ ').str[0]
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
    collection = db['hyundai_tv']  # 사용할 컬렉션 이름

    # DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
    data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

    # MongoDB에 데이터 삽입
    collection.insert_many(data)
    print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")