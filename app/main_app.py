import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from analyzer.report_generator import generate_marketing_report

st.set_page_config(page_title="지피지기 마케팅 리포트", layout="centered")

# CSS 적용
with open("app/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 세션 상태 초기화
if "step" not in st.session_state:
    st.session_state.step = "start"
if "mct_id" not in st.session_state:
    st.session_state.mct_id = ""
if "category" not in st.session_state:
    st.session_state.category = None
if "revisit_rate" not in st.session_state:
    st.session_state.revisit_rate = None

# --- 전역 헤더 ---
# 기존의 전역 헤더 마크다운을 복원합니다.
st.markdown("""
    <div class="header">
        <h2>👋 지피지기에 오신 것을 환영합니다!</h2>
    </div>
""", unsafe_allow_html=True)


def go(step: str):
    st.session_state.step = step


# ========== 1. 초기 온보딩 ==========
if st.session_state.step == "start":
    # 온보딩 질문 카드 (크기 조정을 위해 welcome-card 클래스 사용)
    # 카드가 사라진 문제를 해결하기 위해 이 부분을 반드시 복원합니다.
    st.markdown("""
        <div class="card welcome-card">
            <h3>당신은 어떤 가게의 사장입니까?</h3>
        </div>
    """, unsafe_allow_html=True)

    # 버튼 정렬을 위해 st.columns를 사용합니다.
    # col1, col2를 감싸는 별도의 컨테이너를 추가하지 않고,
    # st.columns 자체가 가운데 정렬되도록 CSS를 수정합니다.
    col1, col2 = st.columns(2)
    with col1:
        st.button("☕ 카페", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="카페"), go("A_1")])
    with col2:
        st.button("🍽️ 요식업", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="요식업"), go("B_1")])



# ========== 2. [흐름 A] 카페 ==========
elif st.session_state.step == "A_1":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("당신의 가맹점 코드를 입력해주세요.")
    st.session_state.mct_id = st.text_input("가맹점 ID", st.session_state.mct_id, placeholder="예: MCT12345")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("다음으로", use_container_width=True, on_click=lambda: go("A_2"))
    with col2:
        st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == "A_2":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>어떤 전략을 추천받고 싶으세요?</h3>", unsafe_allow_html=True)
    st.button("🎯 고객 분석 및 마케팅 채널을 추천받고 싶어요!", use_container_width=True, on_click=lambda: go("A_3"))
    st.button("🔁 재방문율을 높이고 싶어요!", use_container_width=True, on_click=lambda: go("A_4"))
    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("A_1"))
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == "A_3":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>📢 고객 분석 및 마케팅 채널 추천</h3>", unsafe_allow_html=True)
    st.write("AI가 고객 데이터를 기반으로 적합한 마케팅 채널과 문구를 제안합니다.")

    if st.button("마케팅 채널과 문구 생성", use_container_width=True):
        with st.spinner("AI가 고객 분석 중입니다..."):
            result = generate_marketing_report(st.session_state.mct_id, mode="v1")

        # ----------------------
        # 결과 분기 처리
        # ----------------------
        if "error" in result:
            st.error(result["error"])

        else:
            st.success("✅ 분석 완료!")

            # 기본 매장 정보
            st.markdown(f"""
            <div class="card">
                <h4>🏪 {result.get('store_name', '알 수 없음')} ({result.get('store_code', '-')})</h4>
                <p><b>상태:</b> {result.get('status', '정보 없음')}</p>
                <p><b>세부 설명:</b> {result.get('status_detail', '설명 없음')}</p>
            </div>
            """, unsafe_allow_html=True)

            # 분석 요약 섹션
            if result.get("analysis"):
                st.markdown("<h4>📊 분석 결과</h4>", unsafe_allow_html=True)
                analysis = result["analysis"]

                # dict일 경우 key-value 쌍 출력
                if isinstance(analysis, dict):
                    for key, val in analysis.items():
                        st.markdown(f"- **{key}**: {val}")
                # 문자열일 경우 그대로 출력
                else:
                    st.markdown(f"{analysis}")

            # 추천 전략
            if result.get("recommendations"):
                st.markdown("<h4>💡 추천 마케팅 전략</h4>", unsafe_allow_html=True)
                recs = result["recommendations"]

                if isinstance(recs, list):
                    for rec in recs:
                        st.markdown(f"- {rec}")
                else:
                    st.markdown(f"{recs}")

            # 부가 정보
            if result.get("metadata"):
                meta = result["metadata"]
                st.markdown("<h4>📎 참고 정보</h4>", unsafe_allow_html=True)
                for k, v in meta.items():
                    st.caption(f"{k}: {v}")

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)


elif st.session_state.step == "A_4":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>🔁 재방문율 향상 전략</h3>", unsafe_allow_html=True)
    st.write("이에 대한 마케팅이 필요하신가요?")

    if st.button("마케팅 전략 리포트 생성", use_container_width=True):
        # ✅ 게이트웨이를 통해 호출 (경로 고정)
        from analyzer.report_generator import generate_marketing_report

        with st.spinner("AI가 리포트를 생성 중입니다..."):
            result = generate_marketing_report(st.session_state.mct_id, mode="v2")

        st.success("✅ 리포트 생성 완료!")

        # ----------------------
        # 리턴 타입에 따른 분기 처리
        # ----------------------
        if "error" in result:
            st.error(result["error"])

        elif result.get("status") == "양호":
            st.markdown(f"""
            <div class="card">
                <h4>🎉 {result['store_name']} ({result['store_code']})</h4>
                <p>{result['message']}</p>
            </div>
            """, unsafe_allow_html=True)

        elif result.get("status") == "개선 필요":
            st.markdown(f"""
            <div class="card">
                <h4>🏪 {result['store_name']} ({result['store_code']})</h4>
                <p><b>상권 유형:</b> {result['analysis']['type']}</p>
                <p><b>재방문율:</b> {result['analysis']['revisit_rate']}</p>
                <p><b>벤치마크 기준:</b> {result['analysis']['benchmark_type']}</p>
                <hr>
                <h4>📊 주요 진단 요인</h4>
            </div>
            """, unsafe_allow_html=True)

            for d in result["analysis"]["diagnosis"]:
                st.markdown(f"""
                <div class="card">
                    <p><b>{d['factor']}</b></p>
                    <p>내 매장: {d['store_value']} | 업종 평균: {d['benchmark_value']} | 격차: {d['gap']}</p>
                </div>
                """, unsafe_allow_html=True)

            if result.get("recommendations"):
                st.markdown("<h4>💡 추천 전략</h4>", unsafe_allow_html=True)
                for rec in result["recommendations"]:
                    st.markdown(f"- {rec}")

        else:
            st.warning("⚠️ 분석 결과를 표시할 수 없습니다. 데이터 구조를 확인하세요.")

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)



# ========== 3. [흐름 B] 요식업 ==========
elif st.session_state.step == "B_1":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("당신의 가맹점 코드를 입력해주세요.")
    st.session_state.mct_id = st.text_input("가맹점 ID", st.session_state.mct_id, placeholder="예: MCT98765")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.button("다음으로", use_container_width=True, on_click=lambda: go("B_2"))
    with col2:
        st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == "B_2":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>어떤 전략을 추천받고 싶으세요?</h3>", unsafe_allow_html=True)
    mct_id = st.session_state.mct_id.strip()
    if not mct_id:
        st.warning("가맹점 ID를 입력해주세요.")
    else:
        with st.spinner("재방문율 분석 중..."):
            result = generate_marketing_report(mct_id)
        st.session_state.revisit_rate = result.get("report", {}).get("revisit_rate", 25)
    st.button("🔁 재방문율을 높이고 싶어요!", use_container_width=True,
              on_click=lambda: go("B_high" if st.session_state.revisit_rate >= 30 else "B_low"))
    st.button("🧩 나의 매장의 문제를 파악하고 개선하고 싶어요!", use_container_width=True, on_click=lambda: go("B_problem"))
    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("B_1"))
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == "B_high":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>🎉 축하드립니다!</h3>", unsafe_allow_html=True)
    st.write("재방문율이 **30% 이상**입니다! 이미 훌륭한 점포 운영 중이에요 👏")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == "B_low":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>📉 재방문율이 30% 미만입니다</h3>", unsafe_allow_html=True)
    st.write("이에 대한 마케팅이 필요하신가요?")
    if st.button("마케팅 전략 아이디어 보기", use_container_width=True):
        with st.spinner("AI가 전략을 분석 중입니다..."):
            result = generate_marketing_report(st.session_state.mct_id,"v1")
        
        # ----------------------
        # 결과 분기 처리
        # ----------------------
        if "error" in result:
            st.error(result["error"])

        else:
            st.success("✅ 전략 생성 완료!")

            # 기본 매장 정보
            st.markdown(f"""
            <div class="card">
                <h4>🏪 {result.get('store_name', '알 수 없음')} ({result.get('store_code', '-')})</h4>
                <p><b>상태:</b> {result.get('status', '정보 없음')}</p>
                <p><b>세부 설명:</b> {result.get('status_detail', '설명 없음')}</p>
            </div>
            """, unsafe_allow_html=True)

            # 분석 결과
            if result.get("analysis"):
                st.markdown("<h4>📊 분석 결과</h4>", unsafe_allow_html=True)
                analysis = result["analysis"]

                if isinstance(analysis, dict):
                    for key, val in analysis.items():
                        st.markdown(f"- **{key}**: {val}")
                else:
                    st.markdown(f"{analysis}")

            # 추천 전략
            if result.get("recommendations"):
                st.markdown("<h4>💡 추천 마케팅 전략</h4>", unsafe_allow_html=True)
                recs = result["recommendations"]

                if isinstance(recs, list):
                    for rec in recs:
                        st.markdown(f"- {rec}")
                else:
                    st.markdown(f"{recs}")

            # 부가 정보
            if result.get("metadata"):
                meta = result["metadata"]
                st.markdown("<h4>📎 참고 정보</h4>", unsafe_allow_html=True)
                for k, v in meta.items():
                    st.caption(f"{k}: {v}")

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.step == "B_problem":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>🧩 매장의 문제를 파악하고 개선하고 싶으세요?</h3>", unsafe_allow_html=True)
    st.write("AI가 매장의 약점을 분석하고, 맞춤 전략을 제시합니다.")

    if st.button("문제 파악 및 전략 생성", use_container_width=True):
        from analyzer.report_generator import generate_marketing_report

        with st.spinner("AI가 약점 진단 리포트를 생성 중입니다..."):
            result = generate_marketing_report(st.session_state.mct_id, mode="v3")

        # -----------------------------
        # 결과 표시 로직
        # -----------------------------
        if "error" in result:
            st.error(f"❌ 오류 발생: {result['error']}")
            if "traceback" in result:
                st.caption(result["traceback"])

        elif result.get("status") == "진단 완료":
            st.success("✅ 진단이 완료되었습니다!")

            # 매장 정보 카드
            st.markdown(f"""
            <div class="card">
                <h4>🏪 {result['store_name']} ({result['store_code']})</h4>
                <p><b>분석 유형:</b> {result['analysis']['type']}</p>
                <p><b>상권 맥락:</b> {result['analysis']['market_type_context']}</p>
            </div>
            """, unsafe_allow_html=True)

            # 약점 TOP 3
            st.markdown("<h4>📊 약점 TOP 3</h4>", unsafe_allow_html=True)
            for item in result['analysis']['diagnosis_top3']:
                # 심각도에 따라 색상 지정
                color = (
                    "#ef4444" if item['심각도'] >= 80 else
                    "#f59e0b" if item['심각도'] >= 60 else
                    "#10b981"
                )
                st.markdown(f"""
                <div class="card" style="border-left: 6px solid {color};">
                    <p><b>{item['약점']}</b></p>
                    <p>심각도: <span style="color:{color}; font-weight:600;">{item['심각도']}%</span></p>
                </div>
                """, unsafe_allow_html=True)

            # 개선 전략 제안
            if result.get('recommendations'):
                st.markdown("<h4>💡 개선 전략 제안</h4>", unsafe_allow_html=True)
                for rec in result['recommendations']:
                    st.markdown(f"- {rec}")

        else:
            st.warning("⚠️ 결과를 표시할 수 없습니다. 모델 출력 구조를 확인하세요.")

    # 하단 버튼
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
    st.markdown("</div>", unsafe_allow_html=True)

