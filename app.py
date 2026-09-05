import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import openai
from datetime import datetime, timedelta

# 기본 페이지 설정
st.set_page_config(page_title="Celebrity Shopping Shorts", layout="wide")

# 1. 로그인 인증
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 나만의 쇼츠 발굴기 로그인")
    pwd = st.text_input("비밀번호를 입력하세요:", type="password")
    if st.button("로그인"):
        if pwd == "sunsun360535!":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# 2. 메인 화면
st.title("🛍️ 쇼핑/셀럽 떡상 쇼츠 발굴기")

# 사이드바 설정
st.sidebar.header("🔑 API 키 설정")
youtube_api_key = st.sidebar.text_input("YouTube API Key", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

st.sidebar.header("🔍 검색 및 필터 옵션")
query = st.sidebar.text_input("검색어 입력", value="연예인 착장 쇼핑")
max_results = st.sidebar.slider("수집할 영상 수", min_value=5, max_value=30, value=10)

# 📅 날짜 필터 옵션 추가
date_range = st.sidebar.selectbox(
    "📅 게시 기간 선택",
    ["전체 기간", "최근 1주일", "최근 1개월", "최근 3개월", "최근 1년"]
)

# 검색 버튼
if st.button("쇼츠 발굴 시작!"):
    if not youtube_api_key:
        st.warning("YouTube API Key를 입력해주세요.")
        st.stop()

    try:
        youtube = build("youtube", "v3", developerKey=youtube_api_key)

        # 날짜 필터 계산 (RFC 3339 형식: YYYY-MM-DDTHH:MM:SSZ)
        published_after = None
        now = datetime.utcnow()
        if date_range == "최근 1주일":
            published_after = (now - timedelta(days=7)).isoformat() + "Z"
        elif date_range == "최근 1개월":
            published_after = (now - timedelta(days=30)).isoformat() + "Z"
        elif date_range == "최근 3개월":
            published_after = (now - timedelta(days=90)).isoformat() + "Z"
        elif date_range == "최근 1년":
            published_after = (now - timedelta(days=365)).isoformat() + "Z"

        # 검색 매개변수 설정
        search_kwargs = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "videoDuration": "short",  # 60초 미만 쇼츠 기준
            "maxResults": max_results,
            "order": "viewCount"       # 조회수 순 정렬
        }
        
        # 날짜 필터가 지정된 경우 조건 추가
        if published_after:
            search_kwargs["publishedAfter"] = published_after

        # YouTube API 검색 실행
        search_response = youtube.search().list(**search_kwargs).execute()

        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

        if not video_ids:
            st.info("조건에 맞는 쇼츠 영상이 없습니다. 검색어나 기간을 변경해보세요.")
            st.stop()

        # 영상 상세 정보 가져오기 (조회수, 좋아요 등)
        stats_response = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids)
        ).execute()

        results = []
        for item in stats_response.get("items", []):
            title = item["snippet"]["title"]
            v_id = item["id"]
            view_count = int(item["statistics"].get("viewCount", 0))
            published_at = item["snippet"]["publishedAt"][:10]
            url = f"https://www.youtube.com/shorts/{v_id}"

            results.append({
                "제목": title,
                "조회수": view_count,
                "게시일": published_at,
                "링크": url
            })

        # DataFrame 변환 및 표시
        df = pd.DataFrame(results)
        st.subheader(f"📊 [{date_range}] 조회수 높은 쇼츠 결과")
        st.dataframe(
            df,
            column_config={
                "링크": st.column_config.LinkColumn("쇼츠 바로가기")
            },
            hide_index=True,
            use_container_width=True
        )

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
