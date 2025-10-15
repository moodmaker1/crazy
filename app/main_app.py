import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from analyzer.report_generator import generate_marketing_report

# ------------------------------
# 기본 설정
# ------------------------------
st.set_page_config(page_title="지피지기 마케팅 리포트", layout="centered")
with open("app/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ------------------------------
# 세션 초기화
# ------------------------------
if "step" not in st.session_state:
    st.session_state.step = "start"
if "mct_id" not in st.session_state:
    st.session_state.mct_id = ""
if "category" not in st.session_state:
    st.session_state.category = None
if "revisit_rate" not in st.session_state:
    st.session_state.revisit_rate = None


# ------------------------------
# 전역 헤더
# ------------------------------
st.markdown("""
    <div class="header">
        <h2>👋 지피지기에 오신 것을 환영합니다!</h2>
    </div>
""", unsafe_allow_html=True)

def go(step: str):
    st.session_state.step = step


# =====================================================
# ✅ 공통 함수 1: AI 리포트 표시
# =====================================================
def display_ai_report(result: dict, title: str):
    if "error" in result:
        st.error(f"⚠️ 오류 발생: {result['error']}")
        if "traceback" in result:
            st.caption(result["traceback"])
        return

    # 기본 정보
    st.markdown(f"""
    <div class="card">
        <h4>🏪 {result.get('store_name', '알 수 없음')} ({result.get('store_code', '-')})</h4>
        <p><b>상태:</b> {result.get('status', '정보 없음')}</p>
        <p><b>요약:</b> {result.get('message', '정보 없음')}</p>
    </div>
    """, unsafe_allow_html=True)

    # RAG 결과
    rag_summary = result.get("rag_summary")
    if rag_summary:
        st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
        st.markdown(f"<div class='card'>{rag_summary}</div>", unsafe_allow_html=True)

    # 분석
    if result.get("analysis"):
        st.markdown("<h4>📊 데이터 기반 분석</h4>", unsafe_allow_html=True)
        analysis = result["analysis"]
        if isinstance(analysis, dict):
            for k, v in analysis.items():
                st.markdown(f"- **{k}**: {v}")
        else:
            st.markdown(str(analysis))

    # 전략
    if result.get("recommendations"):
        st.markdown("<h4>💡 추천 전략</h4>", unsafe_allow_html=True)
        recs = result["recommendations"]
        if isinstance(recs, list):
            for rec in recs:
                st.markdown(f"- {rec}")
        else:
            st.markdown(str(recs))

    # 참고 데이터
    refs = result.get("references", {})
    if refs:
        st.markdown("<h4>📎 참고 데이터 출처</h4>", unsafe_allow_html=True)
        if refs.get("reports"):
            codes = [str(r.get("store_code", "코드없음")) for r in refs["reports"]]
            st.markdown("📘 **분석 참고 매장:** " + ", ".join(codes))
        if refs.get("segments"):
            segs = [f"{s.get('category','-')} / {s.get('segment','-')}" for s in refs["segments"]]
            st.markdown("🧩 **세그먼트:** " + ", ".join(segs))


# =====================================================
# ✅ 공통 함수 2: AI 리포트 실행
# =====================================================
def run_ai_report(mode: str, title: str):
    with st.spinner("AI가 분석 중입니다..."):
        result = generate_marketing_report(st.session_state.mct_id, mode=mode)
    display_ai_report(result, title)


# =====================================================
# ✅ 공통 함수 3: 가맹점 코드 입력 폼
# =====================================================
def render_store_input(next_step: str):
    st.markdown("""
        <div class="card welcome-card">
            <h3>당신의 가맹점 코드를 입력해주세요.</h3>
        </div>
    """, unsafe_allow_html=True)
    st.session_state.mct_id = st.text_input("가맹점 ID", st.session_state.mct_id, placeholder="예: MCT12345")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("다음으로", use_container_width=True, on_click=lambda: go(next_step))
    with col2:
        st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))


# =====================================================
# ✅ 공통 함수 4: 매장 기본 정보 표시
# =====================================================
def render_basic_info(mct_id: str):
    with st.spinner("매장 정보를 불러오는 중입니다..."):
        info = generate_marketing_report(mct_id, mode="v0", rag=False)

    if "error" in info:
        st.error(info["error"])
        return

    st.markdown(f"""
    <div class="card" style="background:#f8fafc;padding:1.2rem;">
        <h4>🏪 {info.get('가맹점명','알 수 없음')} ({mct_id})</h4>
        <p><b>운영기간:</b> {info.get('운영개월수','-')}개월</p>
        <p><b>매출등급:</b> {info.get('최근1개월_매출액등급','-')}등급</p>
        <p><b>재방문율:</b> {info.get('재방문고객비율','-')}%</p>
        <hr>
        <p><b>📊 종합 평가:</b> {info.get('종합평가','')}</p>
    </div>
    """, unsafe_allow_html=True)


# =====================================================
# 🏁 START
# =====================================================
if st.session_state.step == "start":
    st.markdown("""
        <div class="card welcome-card">
            <h3>당신은 어떤 가게의 사장입니까?</h3>
        </div>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.button("☕ 카페", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="카페"), go("A_1")])
    with col2:
        st.button("🍽️ 요식업", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="요식업"), go("B_1")])


# =====================================================
# ☕ 카페 플로우
# =====================================================
elif st.session_state.step == "A_1":
    render_store_input("A_2")

elif st.session_state.step == "A_2":
    mct_id = st.session_state.mct_id.strip()
    if mct_id:
        render_basic_info(mct_id)
    else:
        st.warning("가맹점 ID를 입력해주세요.")

    st.markdown("<h3 style='text-align:center;'>어떤 전략을 추천받고 싶으세요?</h3>", unsafe_allow_html=True)
    st.button("🎯 마케팅 채널 추천", use_container_width=True, on_click=lambda: go("A_3"))
    st.button("🔁 재방문율 향상 전략", use_container_width=True, on_click=lambda: go("A_4"))
    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("A_1"))

elif st.session_state.step == "A_3":
    st.markdown("<div class='card welcome-card'><h3 style='text-align:center;'>📢 고객 분석 및 마케팅 채널 추천</h3></div>", unsafe_allow_html=True)
    if st.button("AI 리포트 생성", use_container_width=True):
        run_ai_report("v1", "🧠 AI 통합 마케팅 리포트")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

elif st.session_state.step == "A_4":
    st.markdown("<div class='card welcome-card'><h3 style='text-align:center;'>🔁 재방문율 향상 전략 제안</h3></div>", unsafe_allow_html=True)
    if st.button("AI 리포트 생성", use_container_width=True):
        run_ai_report("v2", "🧠 AI 재방문율 향상 리포트")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))


# =====================================================
# 🍽️ 요식업 플로우
# =====================================================
elif st.session_state.step == "B_1":
    render_store_input("B_2")

elif st.session_state.step == "B_2":
    mct_id = st.session_state.mct_id.strip()

    if not mct_id:
        st.warning("가맹점 ID를 입력해주세요.")
    else:
        with st.spinner("내부 분석 모델 실행 중..."):
            result = generate_marketing_report(mct_id, mode="v2", rag=False)  # ✅ RAG 비활성화

        if "error" in result:
            st.error(result["error"])
        else:
            store_name = result.get("store_name", "알 수 없음")
            rate = result.get("revisit_rate", 0)
            st.session_state.revisit_rate = rate

            st.markdown(f"""
            <div class="card" style="background:#f8fafc;padding:1.2rem;margin-bottom:1rem;">
                <h4>🏪 {store_name} ({mct_id})</h4>
                <p><b>상태:</b> {result.get('status', '-')}</p>
                <p><b>재방문율:</b> {rate:.1f}%</p>
                <p><b>상권 유형:</b> {result.get('market_type', '-')}</p>
            </div>
            """, unsafe_allow_html=True)

            st.button("🔁 재방문율 향상 전략 보기", use_container_width=True,
                      on_click=lambda: go("B_high" if rate >= 30 else "B_low"))
            st.button("🧩 매장 문제 진단", use_container_width=True, on_click=lambda: go("B_problem"))

    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("B_1"))


elif st.session_state.step == "B_high":
    st.markdown("<h3 style='text-align:center;'>🎉 축하드립니다!</h3>", unsafe_allow_html=True)
    st.write("재방문율이 **30% 이상**입니다! 이미 훌륭한 점포 운영 중이에요 👏")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

elif st.session_state.step == "B_low":
    st.markdown("<h3 style='text-align:center;'>📉 재방문율이 30% 미만입니다</h3>", unsafe_allow_html=True)
    if st.button("마케팅 전략 아이디어 보기", use_container_width=True):
        run_ai_report("v2", "🧠 AI 재방문율 향상 전략 리포트")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

elif st.session_state.step == "B_problem":
    st.markdown("<div class='card welcome-card'><h3 style='text-align:center;'>🧩 매장 약점 및 개선 전략</h3></div>", unsafe_allow_html=True)
    if st.button("AI 진단 리포트 생성", use_container_width=True):
        run_ai_report("v3", "🧠 AI 약점 진단 및 개선 전략 리포트")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

