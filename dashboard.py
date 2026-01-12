import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. 보안 설정 및 API 키 로드
def load_api_keys():
    # 1단계: .env 파일 로드 시도
    if os.path.exists(".env"):
        load_dotenv(override=True)
    
    # 2단계: 환경 변수에서 먼저 확인 (OS 환경변수 + .env)
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    # 3단계: 환경 변수가 없으면 Streamlit Secrets에서 확인
    if not client_id or not client_secret:
        try:
            # Streamlit Cloud의 경우 하이픈(-)을 쓰는 경우도 있어 둘 다 확인
            client_id = st.secrets.get("NAVER_CLIENT_ID") or st.secrets.get("X-Naver-Client-Id")
            client_secret = st.secrets.get("NAVER_CLIENT_SECRET") or st.secrets.get("X-Naver-Client-Secret")
        except:
            pass
            
    return client_id, client_secret

# 2. 네이버 쇼핑 인사이트 API 호출 함수 (키워드 상세 트렌드)
def get_shopping_insight(client_id, client_secret, keywords, start_date, end_date, category_id="50000000"):
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json"
    }
    
    # 키워드 그룹 생성 (최대 5개)
    keyword_groups = [{"groupName": kw.strip(), "name": [kw.strip()]} for kw in keywords.split(",")]
    
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "category": [category_id],  # 쇼핑인사이트 키워드 API에서는 리스트로 전달
        "device": "",
        "gender": "",
        "ages": [],
        "keywordGroups": keyword_groups
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"API 호출 실패: {response.status_code} - {response.text}")
        return None

# 3. 데이터 전처리 함수
def process_data(api_data):
    if not api_data or 'results' not in api_data:
        return None
    
    df_list = []
    for result in api_data['results']:
        title = result['title']
        temp_df = pd.DataFrame(result['data'])
        temp_df['period'] = pd.to_datetime(temp_df['period'])
        temp_df = temp_df.rename(columns={'ratio': title})
        temp_df = temp_df.set_index('period')
        df_list.append(temp_df)
    
    final_df = pd.concat(df_list, axis=1).fillna(0)
    return final_df

# --- 페이지 설정 ---
st.set_page_config(page_title="Naver Shopping Trend Dashboard", layout="wide")
st.title("📊 네이버 쇼핑 인사이트 트렌드 대시보드")

client_id, client_secret = load_api_keys()

# --- 사이드바 ---
with st.sidebar:
    st.header("🔍 검색 설정")
    input_keywords = st.text_input("키워드 (쉼표로 구분)", value="원피스, 니트, 자켓")
    
    today = datetime.now()
    default_start = today - timedelta(days=90)
    date_range = st.date_input("조희 기간", value=(default_start, today))
    
    with st.expander("🛠️ 디버그 정보 (Key 확인용)"):
        if client_id:
            st.success(f"ID 감지됨 (길이: {len(client_id)})")
        else:
            st.error("ID 미감지")
            
        if client_secret:
            st.success(f"Secret 감지됨 (길이: {len(client_secret)})")
        else:
            st.error("Secret 미감지")
            
        if os.path.exists(".env"):
            st.write(".env 파일 존재 여부: ✅ 있음")
        else:
            st.write(".env 파일 존재 여부: ❌ 없음")
    
    search_button = st.button("분석 시작", type="primary")

# --- 메인 로직 ---
if search_button:
    if not client_id or not client_secret:
        st.warning("API 키가 설정되지 않았습니다.")
    else:
        with st.spinner("데이터를 불러오는 중..."):
            start_date, end_date = date_range
            data = get_shopping_insight(client_id, client_secret, input_keywords, start_date, end_date)
            
            if data:
                df = process_data(data)
                
                # --- 탭 구성 ---
                tab1, tab2, tab3 = st.tabs(["📈 트렌드 분석", "🔬 기초 EDA", "💾 RAW 데이터"])
                
                # Tab 1: 트렌드 분석
                with tab1:
                    st.subheader("키워드별 검색 트렌드 (Plotly Line Chart)")
                    fig_line = px.line(df, x=df.index, y=df.columns, labels={'value': '상대적 지수', 'period': '날짜'})
                    st.plotly_chart(fig_line, use_container_width=True)
                    
                    st.divider()
                    st.subheader("키워드 기반 점유율 (Plotly Pie Chart)")
                    total_counts = df.sum()
                    fig_pie = px.pie(values=total_counts.values, names=total_counts.index)
                    st.plotly_chart(fig_pie, use_container_width=True)

                # Tab 2: 기초 EDA (표 5개, 그래프 5개 이상 보강)
                with tab2:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 1. 기술 통계량 (표 1)")
                        st.table(df.describe())
                        
                        st.markdown("#### 2. 키워드별 분포 (그래프 1: Histogram)")
                        fig_hist = px.histogram(df, barmode='overlay')
                        st.plotly_chart(fig_hist, use_container_width=True)
                        
                        st.markdown("#### 3. 변동성 분석 (그래/표 2: Box Plot)")
                        fig_box = px.box(df)
                        st.plotly_chart(fig_box, use_container_width=True)

                    with col2:
                        st.markdown("#### 4. 키워드간 상관관계 (그래프 3: Heatmap)")
                        corr = df.corr()
                        fig_heat = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r')
                        st.plotly_chart(fig_heat, use_container_width=True)
                        
                        st.markdown("#### 5. 일일 변동률 (표 2)")
                        growth_df = df.pct_change().multiply(100).round(2)
                        st.dataframe(growth_df.tail(10))
                    
                    st.divider()
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        st.markdown("#### 6. 기간 내 최고 지수 기록일 (표 3)")
                        max_dates = df.idxmax().to_frame(name="최고지수일")
                        max_values = df.max().to_frame(name="최고지수")
                        st.table(pd.concat([max_dates, max_values], axis=1))
                        
                        st.markdown("#### 7. 누적 트렌드 합계 (그래프 4: Bar)")
                        fig_bar = px.bar(total_counts, labels={'index': '키워드', 'value': '누적 지수'})
                        st.plotly_chart(fig_bar, use_container_width=True)

                    with col4:
                        st.markdown("#### 8. 주간 평균 트렌드 (표 4)")
                        weekly_df = df.resample('W').mean().round(2)
                        st.dataframe(weekly_df.tail(5))
                        
                        st.markdown("#### 9. 검색량 추이 (그래프 5: Area)")
                        fig_area = px.area(df)
                        st.plotly_chart(fig_area, use_container_width=True)
                        
                        st.markdown("#### 10. 상위 5개 날짜 (표 5)")
                        # 각 키워드별 상위 5일 날짜 요약
                        top5_summary = {}
                        for col in df.columns:
                            top5_summary[col] = df[col].nlargest(5).index.strftime('%Y-%m-%d').tolist()
                        st.write(pd.DataFrame(top5_summary))

                # Tab 3: RAW 데이터
                with tab3:
                    st.subheader("전체 데이터 테이블")
                    st.dataframe(df)
                    
                    csv = df.to_csv().encode('utf-8-sig')
                    st.download_button(
                        label="CSV로 다운로드",
                        data=csv,
                        file_name=f"naver_trend_{datetime.now().strftime('%Y%md')}.csv",
                        mime='text/csv'
                    )
else:
    st.info("사이드바에서 키워드를 입력하고 '분석 시작' 버튼을 눌러주세요.")
