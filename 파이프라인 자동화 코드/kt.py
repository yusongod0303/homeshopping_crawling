from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import numpy as np
from openai import OpenAI
import json
import os
from pymongo import MongoClient

# 드라이버 설정 (ChromeDriver를 사용할 경우)
driver = webdriver.Chrome()  # chromedriver 경로 입력

# URL 열기
driver.get("https://www.kshop.co.kr/display/ec/broadcast/broadcast?ctgrCdId=555")

# 페이지 로딩을 기다리기 위한 시간 지연
time.sleep(3)

# 월/일 설정
year = '2024'
month = '12'
day = '31'
date = f"{month}/{day}"  # '12/19' 형식의 날짜 생성




# 날짜 선택하기
try:
    # 날짜 리스트에서 원하는 날짜를 찾아 클릭
    date_elements = driver.find_elements(By.CSS_SELECTOR, "ul#ulDateList li a._tabs")
    
    for date_element in date_elements:
        date_value = date_element.get_attribute("data-value")
        
        if date_value == f"{year}{month}{day}":  # "20241219" 형식의 날짜
            # 원하는 날짜 클릭
            date_element.click()
            print(f"날짜 {date}가 선택되었습니다.")
            break
    else:
        print(f"날짜 {date}를 찾을 수 없습니다.")
except:
    driver.quit()


# "이전방송보기" 버튼이 있으면 클릭하는 코드
try:
    preview_button = driver.find_element(By.ID, "showPreviewBroadcast")
    if preview_button.is_displayed():  # 버튼이 보이는지 확인
        preview_button.click()
        print("이전방송보기 버튼을 클릭했습니다.")
        time.sleep(2)  # 버튼 클릭 후 대기
except Exception as e:
    print("이전방송보기 버튼이 없습니다.")

# 클릭된 상품 제목을 추적할 리스트
clicked_titles = []
product_data = []  # 수집한 데이터를 저장할 리스트
broadcast_data = []  # 방송 시간 데이터를 저장할 리스트

# 방송 시간 리스트를 새로 가져오기
broadcast_containers = driver.find_elements(By.CSS_SELECTOR, 'div.appearance_table')

for container in broadcast_containers:
    # 방송 시간 추출
    try:
        air_time = container.find_element(By.CSS_SELECTOR, 'span.air_time').text.strip()
    except Exception:
        air_time = "N/A"

    # 방송 시간에 포함된 상품 리스트 추출
    product_elements = container.find_elements(By.CSS_SELECTOR, 'ul.prodUnitW.unitLI li.list')

    for product_element in product_elements:
        # 상품 제목 추출
        try:
            product_name = product_element.find_element(By.CSS_SELECTOR, 'div.prodTlt').text.strip()
        except Exception:
            product_name = "N/A"
        
        # 방송 시간과 상품명을 매핑하여 broadcast_data에 저장
        broadcast_data.append({
            "product_name": product_name,
            "air_time": air_time
        })

# 새로운 상품이 없을 때까지 반복
while True:
    new_product_found = False  # 새 상품 발견 여부 플래그
    
    # 제품 제목 리스트를 새로 가져오기
    product_elements = driver.find_elements(By.XPATH, '//div[@class="prodTlt"]')

    for product_element in product_elements:
        # 상품 이름 추출
        product_name = product_element.text.strip()
        
        # 이미 클릭된 상품인지 확인
        if product_name not in clicked_titles:
            clicked_titles.append(product_name)  # 리스트에 추가
            new_product_found = True  # 새 상품 발견 플래그 설정
            
            # 스크롤 이동 후 JavaScript로 클릭
            driver.execute_script("arguments[0].scrollIntoView(true);", product_element)
            time.sleep(1)  # 스크롤 후 대기
            driver.execute_script("arguments[0].click();", product_element)
            
            # 상세 페이지 로딩 대기
            WebDriverWait(driver, 15).until(lambda d: d.current_url != "https://www.kshop.co.kr/display/ec/broadcast/broadcast?ctgrCdId=555")
            current_url = driver.current_url
            
            # 상품 이름, 가격, 이미지 URL 가져오기
            try:
                title_element = driver.find_element(By.CSS_SELECTOR, "h2.title")
                title = title_element.text.strip().replace("[방송]", "").strip()
            except Exception:
                title = "N/A"
            
            try:
                price_element = driver.find_element(By.CSS_SELECTOR, "span.p_price span.f-bold.point")
                price = price_element.text.strip().replace(",", "").replace("원", "")
            except Exception:
                price = "N/A"
            
            try:
                video_element = driver.find_element(By.ID, "vodPlayer1_html5_api")
                image_url = video_element.get_attribute("poster")
            except Exception:
                image_url = "NA"  # 이미지 URL이 없을 경우
            
            # 별점 및 리뷰 수 가져오기
            try:
                # "상품평" 탭 클릭
                review_tab = driver.find_element(By.CSS_SELECTOR, 'li#dt3 a[data-name="totalReviewCount"]')
                driver.execute_script("arguments[0].click();", review_tab)
                
                # 탭 로딩 대기
                time.sleep(2)
                
                # 별점 추출
                star_score_element = driver.find_element(By.CSS_SELECTOR, "span.num b.point.f-red")
                star_score = star_score_element.text.strip()
                
                # 리뷰 수 추출
                review_count_element = driver.find_element(By.CSS_SELECTOR, "p.f-light-gray[data-avgcount]")
                review_count = review_count_element.get_attribute("data-avgcount")
            except Exception:
                star_score = "0"
                review_count = "0"
            
            # 방송 시간 추가
            air_time = next((item['air_time'] for item in broadcast_data if item['product_name'] == product_name), "N/A")
            
            # 데이터 저장
            product_data.append({
                "title": title,
                "price": price,
                "image_url": image_url,
                "url": current_url,
                "rating": star_score,
                "reviews": review_count,
                "broadcast_time": air_time
            })
            print(f"크롤링 성공: {current_url},{title}, {price}, {image_url}, 별점 {star_score}, 리뷰 수 {review_count}, 방송 시간 {air_time}")
            
            # 원래 페이지로 돌아가기
            driver.back()
            
            # 날짜를 다시 선택
            # 날짜 선택하기
            try:
                # 날짜 리스트에서 원하는 날짜를 찾아 클릭
                date_elements = driver.find_elements(By.CSS_SELECTOR, "ul#ulDateList li a._tabs")
                
                for date_element in date_elements:
                    date_value = date_element.get_attribute("data-value")
                    
                    if date_value == f"{year}{month}{day}":  # "20241219" 형식의 날짜
                        # 원하는 날짜 클릭
                        date_element.click()
                        print(f"날짜 {date}가 선택되었습니다.")
                        break
                else:
                    print(f"날짜 {date}를 찾을 수 없습니다.")
            except:
                driver.quit()
            # "이전방송보기" 버튼이 있으면 클릭하는 코드
            try:
                preview_button = driver.find_element(By.ID, "showPreviewBroadcast")
                if preview_button.is_displayed():  # 버튼이 보이는지 확인
                    preview_button.click()
                    print("이전방송보기 버튼을 클릭했습니다.")
                    time.sleep(2)  # 버튼 클릭 후 대기
            except Exception as e:
                print("이전방송보기 버튼이 없습니다.")
            
            # 뒤로 가기 후 대기
            time.sleep(2)
            break  # **내부 루프 종료**
    else:
        # 모든 상품이 이미 클릭된 경우 메시지 출력
        if not new_product_found:
            print("페이지에 더 이상 새로운 상품이 없습니다.")
            break  # 전체 반복 종료

# 드라이버 종료
driver.quit()


df = pd.DataFrame(product_data)
df['datetime'] = f"{year}-{month}-{day}"
df['broadcast_time'] = df['broadcast_time'].str.split('~').str[0]
df['rating'] = df['rating'].fillna('0').astype(float)
df['rating'] = df['rating'].replace(0, np.nan)
df['rating'] = (df['rating'] / 20).round(1)
df['reviews'] = df['reviews'].replace({'₩': '', ',': ''}, regex=True)
df['reviews'] = df['reviews'].fillna('0').astype(int)
df['reviews'] = df['reviews'].replace(0, np.nan)
df['image_url'] = df['image_url'].replace('NA', np.nan)
df['price'] = df['price'].replace({'원': '', ',': '', '~' : '', '상담상품': '0', '상담후결정': '0', '가격 없음': '0', '상담접수 상품': '0'}, regex=True)
df['price'] = df['price'].replace('NA', np.nan)
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
collection = db['kt']  # 사용할 컬렉션 이름

# DataFrame을 MongoDB에 삽입하기 위한 형식으로 변환
data = df.to_dict(orient='records')  # DataFrame을 딕셔너리 리스트로 변환

# MongoDB에 데이터 삽입
collection.insert_many(data)
print(f"데이터 {len(data)}건이 MongoDB에 삽입되었습니다.")