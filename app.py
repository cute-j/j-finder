import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import openai
from datetime import datetime, timedelta

# 기본 페이지 설정
st.set_page_config(page_title="Celebrity Shopping Shorts Finder", layout="wide")

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

# 세션 상태 초기화 (즐겨찾기용)
if "favorites" not in st.session_state:
    st.session_state.favorites = []

# 2. 메인 화면 및 사이드바 설정
st.title("🛍️ 셀럽/쇼핑 떡상 쇼츠 & AI 대본 생성기")

st.sidebar.header("🔑 API 키 설정")
youtube_api_key = st.sidebar.text_input("YouTube API Key", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["🔥 조회수 폭발 쇼츠 & AI대본", "👑 황금 채널 발굴기", "⭐ 즐겨찾기 목록"])

# ==========================================
# TAB 1: 조회수 폭발 쇼츠 + AI 대본 기능
# ==========================================
with tab1:
    st.header("🔥 조회수 폭발 쇼츠 발굴 및 대본 추출")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        query = st.text_input("검색어 입력", value="연예인 착장 쇼핑", key="t1_q")
    with col2:
        max_results = st.slider("수집 영상 수", 5, 30, 10, key="t1_m")
    with col3:
        date_range = st.selectbox(
            "📅 게시 기간 선택",
            ["전체 기간", "최근 1주일", "최근 1개월", "최근 3개월", "최근 1년"],
            key="t1_d"
        )

    if st.button("쇼츠 발굴 시작!", key="btn_t1"):
        if not youtube_api_key:
            st.warning("사이드바에 YouTube API Key를 입력해주세요.")
        else:
            try:
                youtube = build("youtube", "v3", developerKey=youtube_api_key)

                # 날짜 필터 계산 (RFC 3339)
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

                search_kwargs = {
                    "q": query,
                    "part": "snippet",
                    "type": "video",
                    "videoDuration": "short",
                    "maxResults": max_results,
                    "order": "viewCount"
                }
                if published_after:
                    search_kwargs["publishedAfter"] = published_after

                search_res = youtube.search().list(**search_kwargs).execute()
                v_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]

                if not v_ids:
                    st.info("해당 조건에 만족하는 쇼츠가 없습니다.")
                else:
                    stats_res = youtube.videos().list(
                        part="snippet,statistics",
                        id=",".join(v_ids)
                    ).execute()

                    results = []
                    for item in stats_res.get("items", []):
                        v_id = item["id"]
                        title = item["snippet"]["title"]
                        channel_title = item["snippet"]["channelTitle"]
                        views = int(item["statistics"].get("viewCount", 0))
                        published_at = item["snippet"]["publishedAt"][:10]
                        url = f"https://www.youtube.com/shorts/{v_id}"

                        results.append({
                            "영상ID": v_id,
                            "제목": title,
                            "채널명": channel_title,
                            "조회수": views,
                            "게시일": published_at,
                            "링크": url
                        })

                    st.session_state.search_results = results

            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

    # 검색 결과가 세션에 있는 경우 출력
    if "search_results" in st.session_state and st.session_state.search_results:
        df = pd.DataFrame(st.session_state.search_results)
        st.subheader(f"📊 검색 결과 목록")
        st.dataframe(
            df.drop(columns=["영상ID"]),
            column_config={"링크": st.column_config.LinkColumn("쇼츠 보기")},
            hide_index=True,
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("✍️ AI 벤치마킹 대본 생성기")
        selected_title = st.selectbox("대본을 추출 및 재작성할 쇼츠를 선택하세요:", df["제목"].tolist())
        selected_item = next(item for item in st.session_state.search_results if item["제목"] == selected_title)

        col_act1, col_act2 = st.columns(2)
        
        # 버튼 1: 즐겨찾기 추가
        with col_act1:
            if st.button("⭐ 선택한 쇼츠 즐겨찾기에 추가"):
                fav_data = {k: v for k, v in selected_item.items() if k != "영상ID"}
                if fav_data not in st.session_state.favorites:
                    st.session_state.favorites.append(fav_data)
                    st.success("즐겨찾기에 추가되었습니다!")
                else:
                    st.info("이미 저장되어 있는 항목입니다.")

        # 버튼 2: AI 대본 작성
        with col_act2:
            if st.button("📝 AI 벤치마킹 대본 생성하기"):
                if not openai_api_key:
                    st.warning("사이드바에 OpenAI API Key를 입력해주세요.")
                else:
                    try:
                        # 자막 추출 시도
                        v_id = selected_item["영상ID"]
                        transcript_text = ""
                        try:
                            transcript_list = YouTubeTranscriptApi.get_transcript(v_id, languages=['ko', 'en'])
                            transcript_text = " ".join([t['text'] for t in transcript_list])
                        except:
                            transcript_text = "자막을 직접 불러올 수 없어 영상 제목을 기반으로 작성합니다."

                        # OpenAI 대본 생성 요청
                        openai.api_key = openai_api_key
                        prompt = f"""
                        당신은 쇼핑/패션 쇼츠 전문 크리에이터입니다.
                        아래 원본 쇼츠 정보를 바탕으로, 조회수가 터질 수 있는 60초 분량의 신규 벤치마킹 쇼츠 대본을 작성해주세요.

                        [원본 제목]: {selected_item['제목']}
                        [원본 자막 내용]: {transcript_text}

                        [작성 형시]:
                        1. 훅(Hook) - 초반 3초 시선 집중 대사
                        2. 본문(Body) - 핵심 내용 요약 및 추천 멘트
                        3. 결론(CTA) - 구독/댓글 유도 멘트
                        """

                        with st.spinner("AI가 대본을 작성 중입니다..."):
                            response = openai.ChatCompletion.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role": "user", "content": prompt}]
                            )
                            ai_script = response.choices[0].message.content

                        st.subheader("🤖 생성된 AI 쇼츠 대본")
                        st.write(ai_script)

                    except Exception as e:
                        st.error(f"대본 생성 중 오류가 발생했습니다: {e}")

# ==========================================
# TAB 2: 황금 채널 발굴기
# ==========================================
with tab2:
    st.header("👑 황금 채널 발굴기 (구독자 대비 조회수 폭발 채널)")
    col1_c, col2_c = st.columns(2)
    with col1_c:
        channel_query = st.text_input("채널 검색 키워드", value="연예인 패션", key="t2_q")
    with col2_c:
        max_channels = st.slider("검색할 채널 수", 3, 15, 5, key="t2_m")

    if st.button("황금 채널 찾기", key="btn_t2"):
        if not youtube_api_key:
            st.warning("사이드바에 YouTube API Key를 입력해주세요.")
        else:
            try:
                youtube = build("youtube", "v3", developerKey=youtube_api_key)
                
                ch_search = youtube.search().list(
                    q=channel_query,
                    part="snippet",
                    type="channel",
                    maxResults=max_channels
                ).execute()

                ch_ids = [item["id"]["channelId"] for item in ch_search.get("items", [])]

                if not ch_ids:
                    st.info("검색된 채널이 없습니다.")
                else:
                    ch_stats = youtube.channels().list(
                        part="snippet,statistics",
                        id=",".join(ch_ids)
                    ).execute()

                    ch_results = []
                    for item in ch_stats.get("items", []):
                        title = item["snippet"]["title"]
                        subs = int(item["statistics"].get("subscriberCount", 0))
                        views = int(item["statistics"].get("viewCount", 0))
                        v_count = int(item["statistics"].get("videoCount", 1))
                        ch_url = f"https://www.youtube.com/channel/{item['id']}"
                        
                        avg_views = int(views / v_count) if v_count > 0 else 0

                        ch_results.append({
                            "채널명": title,
                            "구독자 수": subs,
                            "총 영상 수": v_count,
                            "영상당 평균 조회수": avg_views,
                            "채널 링크": ch_url
                        })

                    ch_df = pd.DataFrame(ch_results)
                    st.subheader("🏆 발견된 채널 목록")
                    st.dataframe(
                        ch_df,
                        column_config={"채널 링크": st.column_config.LinkColumn("채널 방문")},
                        hide_index=True,
                        use_container_width=True
                    )

            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# ==========================================
# TAB 3: 즐겨찾기 목록
# ==========================================
with tab3:
    st.header("⭐ 내가 저장한 즐겨찾기 목록")
    if not st.session_state.favorites:
        st.info("아직 저장된 즐겨찾기가 없습니다. 첫 번째 탭에서 쇼츠를 보관해 보세요!")
    else:
        fav_df = pd.DataFrame(st.session_state.favorites)
        st.dataframe(
            fav_df,
            column_config={"링크": st.column_config.LinkColumn("쇼츠 바로가기")},
            hide_index=True,
            use_container_width=True
        )
        if st.button("즐겨찾기 전체 비우기"):
            st.session_state.favorites = []
            st.rerun()
