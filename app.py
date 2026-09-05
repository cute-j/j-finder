import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from youtube_transcript_api import YouTubeTranscriptApi
import re
from openai import OpenAI
import pandas as pd
import os

# ---------------------------------------------------------
# [1] 웹 페이지 기본 설정 & 비밀번호 잠금 기능
# ---------------------------------------------------------
st.set_page_config(page_title="연예인 쇼핑 쇼츠 발굴기", layout="wide")

MY_PASSWORD = "sunsun360535!"  # <-- 원하는 비밀번호로 변경하세요!

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 나만의 쇼츠 발굴기 로그인")
        user_input = st.text_input("비밀번호를 입력하세요", type="password")
        if st.button("로그인"):
            if user_input == MY_PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다.")
        return False
    return True

if not check_password():
    st.stop()

# ---------------------------------------------------------
# [2] 즐겨찾기 저장/불러오기 로직 (CSV 파일 활용)
# ---------------------------------------------------------
FAV_FILE = "favorites.csv"

def load_favorites():
    if os.path.exists(FAV_FILE):
        return pd.read_csv(FAV_FILE)
    return pd.DataFrame(columns=["video_id", "title", "channel_title", "views", "subscribers", "viral_score"])

def save_to_favorites(item):
    df = load_favorites()
    if item['video_id'] in df['video_id'].values:
        st.warning("이미 즐겨찾기에 등록된 영상입니다.")
    else:
        new_row = pd.DataFrame([{
            "video_id": item['video_id'],
            "title": item['title'],
            "channel_title": item['channel_title'],
            "views": item['views'],
            "subscribers": item['subscribers'],
            "viral_score": item['viral_score']
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(FAV_FILE, index=False)
        st.success("⭐ 즐겨찾기에 추가되었습니다!")

# ---------------------------------------------------------
# [3] 사이드바 설정
# ---------------------------------------------------------
st.title("🔥 연예인 쇼핑 쇼츠 발굴기")

if st.sidebar.button("🔒 로그아웃"):
    st.session_state["password_correct"] = False
    st.rerun()

st.sidebar.header("⚙️ 검색 및 API 설정")
youtube_api_key = st.sidebar.text_input("YouTube API Key", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key (AI대본용)", type="password")

st.sidebar.divider()
keyword = st.sidebar.text_input("검색 키워드", value="연예인 추천템")

col_sub, col_views = st.sidebar.columns(2)
max_subscribers = col_sub.number_input("최대 구독자 수", value=100000, step=10000)
min_views = col_views.number_input("최소 조회수", value=50000, step=10000)

search_btn = st.sidebar.button("떡상 쇼츠 검색하기")

# [기능] 쇼핑 링크 감지
def detect_shopping_links(text):
    shopping_domains = ['coupang.com', 'smartstore.naver.com', 'musinsa.com', '29cm.co.kr', 'a-bly.com', 'zigzag.kr', 'brandi.co.kr']
    found_links = []
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%09[0-9a-fA-F][0-9a-fA-F]))+', text)
    for url in urls:
        if any(domain in url for domain in shopping_domains):
            found_links.append(url)
    return found_links

# [기능] OpenAI 대본 생성
def generate_ai_script(openai_key, original_script, video_title):
    try:
        client = OpenAI(api_key=openai_key)
        prompt = f"""
        당신은 연예인 쇼핑 쇼츠 전문 크리에이터입니다.
        아래 원본 영상 자막을 바탕으로 30초 쇼츠용 [녹음용 나레이션 대본]과 [화면 삽입용 핵심 자막]을 구분하여 작성해 주세요.

        [영상 제목]: {video_title}
        [원본 자막]: {original_script}

        [작성 형식]:
        ---
        🎤 **30초 나레이션 대본:**
        (녹음할 내용을 구어체로 작성)

        🎬 **화면 자막용 핵심 문구:**
        (영상 화면에 크게 띄울 핵심 단어/문장 5~7개)
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 대본 생성 실패: {str(e)}"

# 유튜브 데이터 수집
def get_shorts_data(api_key, keyword, max_sub, min_v):
    youtube = build("youtube", "v3", developerKey=api_key)
    published_after = (datetime.utcnow() - timedelta(days=60)).isoformat() + "Z"
    search_response = youtube.search().list(
        q=keyword, part="snippet", maxResults=20, type="video",
        videoDuration="short", publishedAfter=published_after, order="viewCount"
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    if not video_ids: return []

    videos_response = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()

    results = []
    for video in videos_response.get('items', []):
        views = int(video['statistics'].get('viewCount', 0))
        if views < min_v: continue
            
        channel_id = video['snippet']['channelId']
        description = video['snippet'].get('description', '')
        detected_links = detect_shopping_links(description)
        
        channel_response = youtube.channels().list(part="statistics", id=channel_id).execute()
        subscribers = int(channel_response['items'][0]['statistics'].get('subscriberCount', 0))
        
        if subscribers <= max_sub:
            viral_score = round(views / max(subscribers, 1), 1)
            results.append({
                "video_id": video['id'],
                "title": video['snippet']['title'],
                "channel_title": video['snippet']['channelTitle'],
                "views": views,
                "subscribers": subscribers,
                "viral_score": viral_score,
                "thumbnail": video['snippet']['thumbnails']['high']['url'],
                "shopping_links": detected_links
            })
    return results

# ---------------------------------------------------------
# [4] 상단 메뉴 탭 구성 (골든파인더 화면 방식)
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🚀 조회수 폭발 쇼츠", "🏆 황금채널 발굴기", "⭐ 즐겨찾기 목록"])

# 세션 상태에 수집 데이터 저장
if "collected_data" not in st.session_state:
    st.session_state["collected_data"] = []

if search_btn:
    if not youtube_api_key:
        st.warning("사이드바에 YouTube API Key를 입력해주세요.")
    else:
        with st.spinner("떡상 쇼츠 및 쇼핑 데이터 수집 중..."):
            st.session_state["collected_data"] = get_shorts_data(youtube_api_key, keyword, max_subscribers, min_views)

# --- [TAB 1] 조회수 폭발 쇼츠 ---
with tab1:
    data = st.session_state["collected_data"]
    if not data:
        st.info("사이드바에서 조건을 입력하고 [떡상 쇼츠 검색하기] 버튼을 눌러주세요.")
    else:
        st.success(f"총 {len(data)}개의 떡상 쇼츠를 발굴했습니다!")
        cols = st.columns(3)
        for idx, item in enumerate(data):
            with cols[idx % 3]:
                st.image(item['thumbnail'], use_container_width=True)
                st.markdown(f"**[{item['title']}](https://youtube.com/shorts/{item['video_id']})**")
                st.caption(f"📺 채널명: {item['channel_title']}")
                st.write(f"👥 구독자: **{item['subscribers']:,}명** | 👁️ 조회수: **{item['views']:,}회**")
                st.write(f"🚀 떡상지수: **{item['viral_score']}배**")
                
                # 즐겨찾기 버튼
                if st.button("⭐ 즐겨찾기 저장", key=f"fav_{item['video_id']}"):
                    save_to_favorites(item)

                if item['shopping_links']:
                    st.success(f"🛒 쇼핑 링크 감지됨 ({len(item['shopping_links'])}개)")
                    with st.expander("감지된 링크 보기"):
                        for link in item['shopping_links']:
                            st.write(link)
                else:
                    st.caption("🛒 감지된 쇼핑 링크 없음")
                
                if st.button(f"✨ AI 대본 생성하기", key=f"ai_{item['video_id']}"):
                    try:
                        transcript = YouTubeTranscriptApi.get_transcript(item['video_id'], languages=['ko'])
                        script_text = " ".join([t['text'] for t in transcript])
                        if not openai_api_key:
                            st.warning("사이드바에 OpenAI API Key를 입력해 주세요.")
                            st.text_area("원본 자막", script_text, height=150)
                        else:
                            with st.spinner("ChatGPT가 대본 및 자막을 작성 중입니다..."):
                                ai_script = generate_ai_script(openai_api_key, script_text, item['title'])
                                st.markdown(ai_script)
                    except Exception:
                        st.error("자막 데이터를 추출할 수 없습니다.")
                st.divider()

# --- [TAB 2] 황금채널 발굴기 ---
with tab2:
    st.subheader("🏆 발견된 황금 채널 순위")
    data = st.session_state["collected_data"]
    if not data:
        st.info("먼저 쇼츠 검색을 실행해 주세요.")
    else:
        df_data = pd.DataFrame(data)
        # 채널별 그룹화 (평균 떡상지수 및 평균 조회수 계산)
        channel_summary = df_data.groupby('channel_title').agg(
            구독자수=('subscribers', 'first'),
            발굴된쇼츠수=('video_id', 'count'),
            최대조회수=('views', 'max'),
            평균떡상지수=('viral_score', 'mean')
        ).reset_index().sort_values(by='평균떡상지수', ascending=False)
        
        st.dataframe(channel_summary, use_container_width=True)

# --- [TAB 3] 즐겨찾기 목록 ---
with tab3:
    st.subheader("⭐ 저장된 즐겨찾기 영상")
    fav_df = load_favorites()
    if fav_df.empty:
        st.info("저장된 즐겨찾기가 없습니다. 쇼츠 카드에서 [⭐ 즐겨찾기 저장]을 눌러보세요!")
    else:
        st.dataframe(fav_df, use_container_width=True)
        if st.button("🗑️ 즐겨찾기 전체 삭제"):
            if os.path.exists(FAV_FILE):
                os.remove(FAV_FILE)
                st.rerun()