from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
from bs4 import BeautifulSoup

# 자동으로 chromedriver 관리
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install())) 

# 네이버 데이터랩 접속
url = "https://datalab.naver.com/"
driver.get(url)

# 페이지 로드 대기
time.sleep(2)

# 카테고리 버튼을 찾아 클릭하여 카테고리 리스트 열기
category_button = driver.find_element(By.CSS_SELECTOR, "div.select.depth._dropdown a.select_btn")
category_button.click()

# 페이지 로드 대기
time.sleep(2)

# 카테고리 목록 찾기
categories = driver.find_elements(By.CSS_SELECTOR, "div.select.depth._dropdown ul.select_list a.option")

# 기간 옵션 (일간, 주간, 월간) 클릭 요소들
period_button = driver.find_element(By.CSS_SELECTOR, "div.select.period._dropdown a.select_btn")
period_list = driver.find_elements(By.CSS_SELECTOR, "div.select.period._dropdown ul.select_list a.option")

# 데이터를 저장할 리스트 초기화
data = []

# 기간별 반복 (일간, 주간, 월간)
for period in period_list:
    # 클릭할 기간 버튼에서 'period_name'을 추출
    period_name = period.text.strip()
    
    # 기간 버튼 클릭
    period_button.click()
    
    # 페이지 로드 대기
    time.sleep(1)  # 클릭 후 요소들이 로드될 수 있도록 대기
    
    # 선택할 기간 클릭
    try:
        period.click()  # "일간", "주간", "월간" 중 하나 클릭
    except Exception as e:
        print(f"Error clicking period button: {e}")
        continue
    
    # 페이지 로드 대기 (2초에서 더 긴 시간 대기 필요할 수 있음)
    time.sleep(2)  # 클릭 후 페이지 완전 로드를 위한 대기

    # 실제로 클릭된 "일간", "주간", "월간"의 텍스트를 새로 업데이트
    updated_period_name = driver.find_element(By.CSS_SELECTOR, "div.select.period._dropdown a.select_btn").text.strip()

    # 카테고리 클릭을 10번만 반복하도록 제한
    for idx, category in enumerate(categories[:10]):  # 첫 10개의 카테고리만 선택
        category_name = category.text.strip()  # 카테고리명 추출
        driver.execute_script("arguments[0].scrollIntoView();", category)
        category.click()  # 카테고리 클릭

        # 페이지 로드 대기
        time.sleep(2)

        # 페이지 소스 가져오기
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # 분야별 인기 키워드 데이터 찾기
        sections = soup.select('.keyword_rank')
        for section in sections:
            # 날짜 추출
            datetime_element = section.select_one('.title_cell')
            if datetime_element:
                datetime = datetime_element.text.strip()
            else:
                datetime = "알 수 없음"

            # 키워드 리스트 추출
            keywords = [item.text.strip() for item in section.select('.list span')]

            # 순위 리스트 추출
            rank = [item.text.strip() for item in section.select('.list em.num')]

            # 데이터 리스트에 카테고리와 키워드 저장
            for k, keyword in enumerate(keywords):
                data.append([datetime, category_name, keyword, rank[k], updated_period_name])

        # 카테고리 버튼을 다시 클릭하여 카테고리 목록으로 돌아가기
        category_button.click()

        # 페이지 로드 대기
        time.sleep(2)

# pandas DataFrame으로 변환
df = pd.DataFrame(data, columns=['datetime', 'categories', 'Keyword', 'rank', 'period'])

print(df)

# MongoDB 클라이언트 연결
client = MongoClient('mongodb://localhost:27017/')  # MongoDB 연결 (기본 로컬 호스트)

# 사용할 데이터베이스 선택 (없으면 자동 생성)
db = client['naver_data']  # 데이터베이스 이름: naver_data

# 컬렉션 선택 (없으면 자동 생성)
collection = db['trends']  # 컬렉션 이름: trends

# 데이터프레임을 딕셔너리 리스트로 변환
data_dict = df.to_dict(orient='records')

# 데이터 삽입 전에 중복 확인 및 삽입
for record in data_dict:
    if not collection.find_one({'datetime': record['datetime'], 'categories': record['categories'], 'Keyword': record['Keyword'], 'rank': record['rank'], 'period': record['period']}):
        collection.insert_one(record)
    else:
        print(f"중복된 데이터: {record['datetime']} - {record['categories']} - {record['Keyword']} - {record['rank']} - {record['period']}")

print("데이터가 MongoDB에 저장되었습니다.")

# 브라우저 종료
driver.quit()