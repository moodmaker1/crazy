import sys, os, re, html, base64
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from analyzer.report_generator import generate_marketing_report

# ------------------------------
# 기본 설정
# ------------------------------
st.set_page_config(page_title="지피지기 마케팅 리포트", layout="centered")
with open("app/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def set_global_background(image_path: str):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
    except Exception:
        return

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image:
                linear-gradient(rgba(241,246,255,0.88), rgba(250,252,255,0.9)),
                url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-color: #f1f6ff;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


set_global_background("app/back_3.png")


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
# 로고 표시
logo_path = "app/logo.png"
if os.path.exists(logo_path):
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.image(logo_path, use_column_width=True)



def go(step: str):
    st.session_state.step = step


# =====================================================
# ✅ RAG 하이라이트 파싱 & 포매팅
# =====================================================
HIGHLIGHT_LABELS = {
    "channel": "📍 추천 채널",
    "message": "💬 홍보 문구 예시",
    "execution": "✅ 실행 방법",
    "evidence": "📊 근거",
}


def _format_rag_text_block(value: str) -> str:
    if not value:
        return ""
    lines = [line.strip() for line in value.splitlines()]
    filtered = [line for line in lines if line]
    if not filtered:
        return ""

    as_list = any(line.lstrip().startswith(("-", "•")) for line in filtered)
    if as_list:
        items = "".join(
            f"<li>{html.escape(line.lstrip('-•').strip())}</li>"
            for line in filtered
        )
        return f"<ul>{items}</ul>"
    return "<br>".join(html.escape(line) for line in filtered)


def extract_highlight_sections(summary: str):
    if not summary:
        return {}, summary

    cleaned_text = summary
    extracted = {}
    for key, label in HIGHLIGHT_LABELS.items():
        pattern = re.compile(
            rf"(^|\n)[ \t]*{re.escape(label)}\s*[:：-]*\s*(.*?)(?=(\n[ \t]*[📍💬✅📊])|\n*$)",
            re.S,
        )

        match = pattern.search(cleaned_text)
        if not match:
            continue

        content = match.group(2).strip()
        if content:
            extracted[key] = content

        def _replacement(m):
            return "\n" if m.group(1) == "\n" else ""

        cleaned_text = pattern.sub(_replacement, cleaned_text, count=1)

    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
    return extracted, cleaned_text


def clean_remaining_text(text: str) -> str:
    if not text:
        return ""

    filtered_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(tuple(HIGHLIGHT_LABELS.values())):
            continue
        if re.match(r"\[[A-Z]\]", stripped):
            continue
        if re.match(r"\d+\.", stripped):
            continue
        filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()


def extract_action_cards(summary: str):
    if not summary:
        return [], summary

    lines = summary.splitlines()
    used = [False] * len(lines)

    cards = []
    heading = None
    current_item = None
    current_field = None

    def mark_used(index: int):
        if 0 <= index < len(used):
            used[index] = True

    def append_text(target: str, value: str):
        return f"{target}\n{value}" if target else value

    def flush_item():
        nonlocal current_item, current_field
        if current_item and (current_item.get("channel") or current_item.get("message")):
            cards.append(
                {
                    "heading": heading or "",
                    "title": current_item.get("title", ""),
                    "channel": (current_item.get("channel") or "").strip(),
                    "message": (current_item.get("message") or "").strip(),
                    "execution": "\n".join(current_item.get("execution", [])).strip(),
                    "evidence": "\n".join(current_item.get("evidence", [])).strip(),
                }
            )
        current_item = None
        current_field = None

    i = 0
    while i < len(lines):
        original = lines[i]
        stripped = original.strip()

        if not stripped:
            if current_item and current_field in {"channel", "message"}:
                current_item[current_field] = append_text(current_item[current_field], "")
                mark_used(i)
            elif current_item and current_field in {"execution", "evidence"}:
                current_item.setdefault(current_field, []).append("")
                mark_used(i)
            i += 1
            continue

        if stripped.startswith("[") and "]" in stripped[:6]:
            flush_item()
            heading = stripped
            mark_used(i)
            i += 1
            continue

        if re.match(r"\d+\.", stripped):
            flush_item()
            current_item = {
                "title": stripped,
                "channel": "",
                "message": "",
                "execution": [],
                "evidence": [],
            }
            current_field = None
            mark_used(i)
            i += 1
            continue

        matched_label = False
        for key, label in HIGHLIGHT_LABELS.items():
            if stripped.startswith(label):
                value = stripped[len(label):].strip(" :：-")
                mark_used(i)
                matched_label = True
                current_field = key
                if key in {"channel", "message"}:
                    current_item[key] = append_text(current_item.get(key, ""), value)
                else:
                    bucket = current_item.setdefault(key, [])
                    if value:
                        bucket.append(value)
                break

        if matched_label:
            i += 1
            continue

        if current_item and current_field:
            mark_used(i)
            if current_field in {"channel", "message"}:
                current_item[current_field] = append_text(current_item[current_field], stripped)
            else:
                current_item.setdefault(current_field, []).append(stripped)
            i += 1
            continue

        i += 1

    flush_item()

    remaining_lines = [lines[idx] for idx, flag in enumerate(used) if not flag]
    remaining_summary = "\n".join(remaining_lines).strip()

    return cards, remaining_summary


# =====================================================
# ✅ 공통 함수 1: AI 리포트 표시
# =====================================================
def display_ai_report(result: dict, title: str):
    if "error" in result:
        st.error(f"⚠️ 오류 발생: {result['error']}")
        if "traceback" in result:
            st.caption(result["traceback"])
        return

    # 기본 정보 섹션은 현재 비어 있어 제거

    # ✅ 키워드 트렌드 섹션 (RAG 이전에 표시)
    keyword_trend = result.get("keyword_trend", [])
    industry = result.get("industry", "알 수 없음")
    if keyword_trend:
        st.markdown(f"<h4>📈 업종 트렌드 TOP10 ({industry}) - 검색량</h4>", unsafe_allow_html=True)
        trend_html = "<ul style='line-height:1.8;'>"
        for item in keyword_trend:
            kw = item.get("keyword") or item.get("키워드") or "-"
            val = item.get("value") or item.get("평균검색비율") or "-"
            trend_html += f"<li>🔹 <b>{kw}</b> — {val}</li>"
        trend_html += "</ul>"
        st.markdown(f"<div class='card'>{trend_html}</div>", unsafe_allow_html=True)

    # RAG 결과
    rag_summary = result.get("rag_summary")
    if rag_summary:
        st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
        action_cards, remaining_for_highlights = extract_action_cards(rag_summary)
        highlight_sections, remaining_summary = extract_highlight_sections(remaining_for_highlights)

        if action_cards:
            for card in action_cards:
                heading_html = html.escape(card.get("heading", ""))
                title_html = html.escape(card.get("title", ""))

                channel_block = _format_rag_text_block(card.get("channel", ""))
                message_block = _format_rag_text_block(card.get("message", ""))

                summary_html = ""
                if channel_block or message_block:
                    chip_blocks = []
                    if channel_block:
                        chip_blocks.append(
                            f"""
                            <div class="highlight-card__item">
                                <span class="highlight-card__label">📍 추천 채널</span>
                                <div class="highlight-card__value">{channel_block}</div>
                            </div>
                            """
                        )
                    if message_block:
                        chip_blocks.append(
                            f"""
                            <div class="highlight-card__item">
                                <span class="highlight-card__label">💬 홍보 문구 예시</span>
                                <div class="highlight-card__value">{message_block}</div>
                            </div>
                            """
                        )
                    summary_html = "".join(chip_blocks)

                card_surface = f"""
                <div class="highlight-card-surface">
                    <div class="highlight-card__heading">{heading_html}</div>
                    <div class="highlight-card__summary-text">{title_html}</div>
                    <div class="highlight-card__summary">
                        {summary_html}
                    </div>
                </div>
                """
                st.markdown(card_surface, unsafe_allow_html=True)

                exec_block = _format_rag_text_block(card.get("execution", ""))
                evidence_block = _format_rag_text_block(card.get("evidence", ""))

                if exec_block or evidence_block:
                    with st.expander("자세히 보기", expanded=False):
                        if exec_block:
                            st.markdown("<h5>✅ 실행 방법</h5>", unsafe_allow_html=True)
                            st.markdown(exec_block, unsafe_allow_html=True)
                        if evidence_block:
                            st.markdown("<h5>📊 근거</h5>", unsafe_allow_html=True)
                            st.markdown(evidence_block, unsafe_allow_html=True)

        elif highlight_sections.get("channel") or highlight_sections.get("message"):
            channel_block = _format_rag_text_block(highlight_sections.get("channel", ""))
            message_block = _format_rag_text_block(highlight_sections.get("message", ""))

            summary_html = ""
            if channel_block or message_block:
                chip_blocks = []
                if channel_block:
                    chip_blocks.append(
                        f"""
                        <div class="highlight-card__item">
                            <span class="highlight-card__label">📍 추천 채널</span>
                            <div class="highlight-card__value">{channel_block}</div>
                        </div>
                        """
                    )
                if message_block:
                    chip_blocks.append(
                        f"""
                        <div class="highlight-card__item">
                            <span class="highlight-card__label">💬 홍보 문구 예시</span>
                            <div class="highlight-card__value">{message_block}</div>
                        </div>
                        """
                    )
                summary_html = "".join(chip_blocks)

            card_surface = f"""
            <div class="highlight-card-surface">
                <div class="highlight-card__summary">
                    {summary_html}
                </div>
            </div>
            """
            st.markdown(card_surface, unsafe_allow_html=True)

            exec_block = _format_rag_text_block(highlight_sections.get("execution", ""))
            evidence_block = _format_rag_text_block(highlight_sections.get("evidence", ""))

            if exec_block or evidence_block:
                with st.expander("자세히 보기", expanded=False):
                    if exec_block:
                        st.markdown("<h5>✅ 실행 방법</h5>", unsafe_allow_html=True)
                        st.markdown(exec_block, unsafe_allow_html=True)
                    if evidence_block:
                        st.markdown("<h5>📊 근거</h5>", unsafe_allow_html=True)
                        st.markdown(evidence_block, unsafe_allow_html=True)

        if remaining_summary:
            cleaned_remaining = clean_remaining_text(remaining_summary)
            if cleaned_remaining:
                st.markdown("<div class='card rag-summary'>", unsafe_allow_html=True)
                st.markdown(cleaned_remaining)
                st.markdown("</div>", unsafe_allow_html=True)

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
    category = st.session_state.get("category")

    if category == "카페":
        intro_cols = st.columns([1, 2])
        with intro_cols[0]:
            if os.path.exists("app/1.png"):
                st.image("app/1.png", use_column_width=True)
        with intro_cols[1]:
            st.markdown(
                """
                <div style="
                    background: linear-gradient(135deg, #f3f4ff 0%, #ffffff 100%);
                    border-radius: 12px;
                    padding: 1.2rem 1.4rem;
                    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
                    border-left: 6px solid #6366f1;
                ">
                    <h3 style="margin:0 0 0.6rem 0;">안녕하세요! 카페 사장님 ☕</h3>
                    <p style="margin:0; line-height:1.6; color:#374151;">
                        사장님의 가게를 신속하고 정확하게 분석해<br>
                        <strong>최고의 마케팅 전략</strong>을 제시해드릴게요.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="card welcome-card">
            <h3>당신의 가맹점 코드를 입력해주세요.</h3>
        </div>
    """,
        unsafe_allow_html=True,
    )
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

    # 카드 헤더
    st.markdown(f"""
    <div class="card" style="background:#f8fafc;padding:1.2rem;">
        <h4>🏪 {info.get('가맹점명','알 수 없음')} ({mct_id})</h4>
    </div>
    """, unsafe_allow_html=True)

    # 기본 정보
    st.markdown(f"""
    <div class="info-section">
        <h4>📍 기본 정보</h4>
        <ul>
            <li><strong>업종:</strong> {info.get('업종분류', '-')}</li>
            <li><strong>주소:</strong> {info.get('주소', '-')}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # 매출등급 (등급에 따라 색상 변경)
    grade = info.get('최근1개월_매출액등급', 6)
    grade_class = 'grade-high' if grade <= 2 else 'grade-medium' if grade <= 4 else 'grade-low'

    st.markdown(f"""
    <div class="info-section {grade_class}">
        <h4>💰 매출등급</h4>
        <ul>
            <li><strong>매출등급:</strong> {grade}등급</li>
            <li class="insight">💬 {info.get('매출등급_해석', '')}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # 고객 지표 (주석처리)
    # st.markdown(f"""
    # <div class="info-section">
    #     <h4>👥 고객 지표</h4>
    #     <ul>
    #         <li><strong>재방문율:</strong> {info.get('재방문고객비율', '-')}%</li>
    #         <li class="insight">💬 {info.get('재방문율_해석', '')}</li>
    #         <li><strong>신규고객:</strong> {info.get('신규고객비율', '-')}%</li>
    #         <li class="insight">💬 {info.get('신규고객_해석', '')}</li>
    #         <li><strong>객단가비율:</strong> {info.get('객단가비율', '-')}</li>
    #         <li class="insight">💬 {info.get('객단가_해석', '')}</li>
    #     </ul>
    # </div>
    # """, unsafe_allow_html=True)

    # 성장성
    st.markdown(f"""
    <div class="info-section">
        <h4>📈 성장성</h4>
        <ul>
            <li><strong>업종 매출증감률:</strong> {info.get('업종매출증감률', 0):+.1f}%</li>
            <li><strong>상권 매출증감률:</strong> {info.get('상권매출증감률', 0):+.1f}%</li>
            <li class="insight">💬 {info.get('성장성_해석', '')}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # 고객 거주지 분포 (주석처리)
    # st.markdown(f"""
    # <div class="info-section">
    #     <h4>🗺️ 고객 거주지 분포</h4>
    #     <ul>
    #         <li><strong>거주:</strong> {info.get('거주고객비율', 0):.0f}% | <strong>직장:</strong> {info.get('직장고객비율', 0):.0f}% | <strong>유동:</strong> {info.get('유동고객비율', 0):.0f}%</li>
    #         <li class="insight">💬 {info.get('고객분포_해석', '')}</li>
    #     </ul>
    # </div>
    # """, unsafe_allow_html=True)


# =====================================================
# 🏁 START
# =====================================================
if st.session_state.step == "start":

    st.markdown("""
        <div class="hero">
            <h1>내 가게를 부탁해</h1>
            <p class="subtitle">신한카드 AI 마케팅 프로젝트</p>
        </div>
        <div class="hero-description">
            <p>
                점포 분석 & 마케팅 전략에 특화된 AI가<br>
                여러분의 가게를 신속, 정확히 분석해 최고의 마케팅 전략을 제안합니다.
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="category-selection-wrapper">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if os.path.exists("app/1.png"):
            st.image("app/1.png")
        st.button("카페 셰프", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="카페"), go("A_1")])
    with col2:
        if os.path.exists("app/2.png"):
            st.image("app/2.png")
        st.button("요식업 셰프", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="요식업"), go("B_1")])
    with col3:
        if os.path.exists("app/3.png"):
            st.image("app/3.png")
        st.button("배달 진단 셰프", use_container_width=True,
                  on_click=lambda: [st.session_state.update(category="배달"), go("C_1")])
    st.markdown('</div>', unsafe_allow_html=True)


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

    mct_id = st.session_state.mct_id.strip()

    # v1 모델 요약 결과 먼저 표시
    with st.spinner("AI가 고객 데이터를 분석 중입니다..."):
        from experiments._1_final.report_generator import generate_marketing_report1
        result = generate_marketing_report1(mct_id)

    if "error" not in result:
        # 1. 매장 헤더 카드 (상태에 따라 색상 변경)
        status = result.get('status', '')
        status_detail = result.get('status_detail', '')
        store_name = result.get('store_name', '알 수 없음')

        # 상태에 따른 색상 및 이모지
        if "매우 탄탄" in status:
            color = "#22c55e"
            emoji = "🎉"
        elif "안정적" in status:
            color = "#3b82f6"
            emoji = "✅"
        elif "보완" in status or "필요" in status:
            color = "#f59e0b"
            emoji = "⚠️"
        else:
            color = "#ef4444"
            emoji = "🚨"

        st.markdown(f"""
        <div style="background:{color}15;padding:1.5rem;border-left:6px solid {color};
                    border-radius:12px;margin-bottom:1.5rem;">
            <h3>{emoji} {store_name}</h3>
            <p style="font-size:1.1rem;font-weight:600;margin-top:0.8rem;">{status}</p>
            <p style="margin-top:0.5rem;color:#4b5563;">{status_detail}</p>
        </div>
        """, unsafe_allow_html=True)

        # 2. 핵심 고객 요약 카드
        analysis = result.get('analysis', {})
        summary = analysis.get('summary', '')
        cluster = analysis.get('cluster', '-')

        st.markdown(f"""
        <div style="background:#f0f9ff;padding:1.3rem;border-left:5px solid #3b82f6;
                    border-radius:10px;margin-bottom:1.5rem;">
            <h4>👥 핵심 고객 요약</h4>
            <p style="margin-top:0.8rem;line-height:1.6;">{summary}</p>
            <p style="margin-top:0.8rem;font-size:0.9rem;color:#6b7280;">
                🗺️ 상권 클러스터: <b>{cluster}</b>
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 3. 주요 인사이트 카드
        insights = analysis.get('insights', [])[:2]
        if insights:
            insights_html = "".join([f"<li style='margin-bottom:0.5rem;'>{insight}</li>" for insight in insights])
            st.markdown(f"""
            <div style="background:#fef9c3;padding:1.3rem;border-left:5px solid #f59e0b;
                        border-radius:10px;margin-bottom:1.5rem;">
                <h4>💡 주요 인사이트</h4>
                <ul style="margin-top:0.8rem;padding-left:1.5rem;">
                    {insights_html}
                </ul>
            </div>
            """, unsafe_allow_html=True)

        # RAG 버튼 안내
        st.markdown("""
        <div style="background:#ecfdf5;padding:1.2rem;border-radius:10px;text-align:center;margin-top:1rem;">
            <h4>💡 AI가 추천하는 상세 전략을 확인해보세요</h4>
            <p><b>외식행태 경영실태 통계 보고서</b>를 참고한 <b>맞춤형 마케팅 전략</b>이 자동 생성됩니다.</p>
        </div>
        """, unsafe_allow_html=True)

        # RAG 버튼
        if st.button("🧠 마케팅 채널 & 홍보 문구 제안 (RAG)", use_container_width=True):
            run_ai_report("v1", "🧠 AI 마케팅 채널 & 홍보 전략 리포트")
    else:
        st.error(f"⚠️ {result.get('error', '오류가 발생했습니다.')}")

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
        # 매장 기본 정보 표시 (카페 플로우와 동일)
        render_basic_info(mct_id)

        # 재방문율 가져오기 (버튼 분기용)
        info = generate_marketing_report(mct_id, mode="v0", rag=False)
        if "error" not in info:
            rate = info.get('재방문고객비율', 0)
            st.session_state.revisit_rate = rate

            st.markdown("<h3 style='text-align:center;'>어떤 분석을 원하시나요?</h3>", unsafe_allow_html=True)
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

    # v2 모델링 결과 먼저 표시 (RAG 없이)
    with st.spinner("재방문율 분석 결과를 불러오는 중..."):
        result = generate_marketing_report(st.session_state.mct_id, mode="v2", rag=False)

    if "error" not in result:
        # ✅ 진단 요약 카드
        revisit = result.get("revisit_rate", 0)
        benchmark_rate = result.get("benchmark", {}).get("재방문율", 0)
        status_text = result.get("status", "정보 없음")
        market_type = result.get("market_type", "-")
        message = result.get("message", "")
        color = "#ef4444" if revisit < 30 else "#eab308" if revisit < 40 else "#22c55e"

        # 벤치마크가 없으면 표시하지 않음
        benchmark_text = f"(유사 매장 평균 {benchmark_rate:.1f}% 대비)" if benchmark_rate > 0 else ""

        st.markdown(f"""
        <div style="background:{color}15;padding:1.4rem;border-left:6px solid {color};
                    border-radius:10px;margin-bottom:1rem;">
            <h3>🏪 {result.get('store_name', '알 수 없음')} ({result.get('store_code', '-')}) — {status_text}</h3>
            <p><b>현재 재방문율:</b> {revisit:.1f}% {benchmark_text}</p>
            <p>📍 상권 유형: {market_type}</p>
            <p>💬 {message}</p>
        </div>
        """, unsafe_allow_html=True)

        # ✅ 혼합형, 유동형 또는 재방문율 양호 시 별도 안내
        show_strategy_button = True  # 기본적으로 전략 버튼 표시

        if market_type == "혼합형":
            st.markdown("""
            <div style="background:#f0f9ff;padding:1.2rem;border-left:5px solid #3b82f6;
                        border-radius:10px;margin-bottom:1rem;">
                <h4>ℹ️ 혼합형 상권 특성</h4>
                <p>혼합형 상권은 <b>거주, 직장, 유동 고객이 골고루 분포</b>된 지역입니다.</p>
                <p>다양한 고객층을 대상으로 하기 때문에, 특정 고객군에 집중하기보다는
                   <b>시간대별 맞춤 전략</b>이 필요합니다.</p>
                <ul>
                    <li>🌅 점심: 직장인 대상 빠른 서비스</li>
                    <li>🌆 저녁/주말: 거주민 대상 편안한 분위기</li>
                    <li>☀️ 평일 낮: 유동 고객 대상 테이크아웃 강화</li>
                </ul>
                <p style="margin-top:1rem;">💡 혼합형 매장은 <b>매장 약점 진단</b>을 통해 개선점을 찾는 것이 더 효과적입니다.</p>
            </div>
            """, unsafe_allow_html=True)
            show_strategy_button = False  # 혼합형은 재방문율 전략 버튼 숨김

        elif market_type == "유동형":
            st.markdown("""
            <div style="background:#fef3c7;padding:1.2rem;border-left:5px solid #f59e0b;
                        border-radius:10px;margin-bottom:1rem;">
                <h4>⚡ 유동형 상권 특성</h4>
                <p>유동형 상권은 <b>재방문율보다 매출액과 회전율</b>이 더 중요한 지표입니다.</p>
                <p><b>신규 고객 유입</b>이 핵심이며, 빠른 서비스와 높은 가시성이 성공 요소입니다.</p>
                <ul>
                    <li>💰 <b>객단가 향상</b>: 세트 메뉴, 업셀링 전략</li>
                    <li>🚚 <b>배달 서비스</b>: 온라인 채널 확장</li>
                    <li>📣 <b>가시성 강화</b>: 간판, SNS 마케팅</li>
                    <li>⚡ <b>회전율 개선</b>: 빠른 서비스, 메뉴 단순화</li>
                </ul>
                <p style="margin-top:1rem;">💡 유동형 매장은 <b>매장 약점 진단</b>을 통해 매출 증대 전략을 찾는 것이 더 효과적입니다.</p>
            </div>
            """, unsafe_allow_html=True)
            show_strategy_button = False  # 유동형은 재방문율 전략 버튼 숨김

        elif status_text == "양호":
            st.markdown("""
            <div style="background:#f0fdf4;padding:1.2rem;border-left:5px solid #22c55e;
                        border-radius:10px;margin-bottom:1rem;">
                <h4>✅ 재방문율이 양호합니다</h4>
                <p>현재 운영 방식을 유지하면서, <b>추가 성장</b>을 위한 전략이 필요합니다:</p>
                <ul>
                    <li>✨ <b>신규 고객 유입 확대</b> (SNS, 배달 플랫폼)</li>
                    <li>💰 <b>객단가 향상</b> (세트 메뉴, 업셀링)</li>
                    <li>🎁 <b>단골 고객 우대 프로그램 강화</b></li>
                </ul>
                <p style="margin-top:1rem;">💡 더 나은 성과를 위해 <b>매장 약점 진단</b>을 받아보세요.</p>
            </div>
            """, unsafe_allow_html=True)
            show_strategy_button = False  # 양호한 경우 재방문율 전략 버튼 숨김

        # ✅ 클러스터 정보 요약 (거주형/직장형만)
        if result.get("cluster_info"):
            ci = result["cluster_info"]
            st.markdown(f"""
            <div style="background:#eef2ff;padding:1.2rem;border-left:5px solid #6366f1;
                        border-radius:10px;margin-bottom:1rem;">
                <h4>🏷️ AI 분류 결과</h4>
                <p>당신의 매장은 <b>‘{ci.get('cluster_name', '-')}’</b> 유형으로 분석되었습니다.</p>
                <p>{ci.get('cluster_description', '비슷한 운영 특성을 가진 매장과 비교해 분석되었습니다.')}</p>
                <p>이 그룹은 총 <b>{ci.get('cluster_size', 0)}개 매장</b>으로 구성되어 있으며, 
                   그중 <b>{ci.get('success_count', 0)}개({ci.get('success_rate', '-')})</b>가 개선에 성공했습니다.</p>
            </div>
            """, unsafe_allow_html=True)

        # ✅ 데이터 차이 요약
        if result.get("gaps"):
            g = result["gaps"]
            st.markdown(f"""
            <div style="background:#fef9c3;padding:1.2rem;border-left:5px solid #f59e0b;
                        border-radius:10px;margin-bottom:1rem;">
                <h4>📉 데이터 차이 요약</h4>
                <ul>
                    <li>💰 객단가: 평균 대비 <b>{g.get('객단가', {}).get('gap', 0):+.2f}</b> 낮음</li>
                    <li>💬 충성도: 벤치마크보다 <b>{g.get('충성도', {}).get('gap', 0):+.2f}</b> 낮음 → 단골 확보 필요</li>
                    <li>🚚 배달비율: <b>{g.get('배달비율', {}).get('gap', 0):+.2f}</b> 부족 → 온라인 채널 확장 여지 있음</li>
                </ul>
                <p>➡️ 위 3가지 요인이 <b>재방문율 저하</b>에 가장 큰 영향을 주는 것으로 분석됩니다.</p>
            </div>
            """, unsafe_allow_html=True)

        # ✅ 다음 단계 안내 카드 및 버튼 (조건부 표시)
        if show_strategy_button:
            st.markdown("""
            <div style="background:#ecfdf5;padding:1.2rem;border-radius:10px;text-align:center;margin-top:1rem;">
                <h4>💡 AI가 제시하는 맞춤 전략을 확인해보세요</h4>
                <p>고객 재방문을 늘릴 수 있는 <b>단기·중기·장기 전략</b>이 자동 생성됩니다.</p>
            </div>
            """, unsafe_allow_html=True)

            # ✅ 버튼
            if st.button("🚀 AI 재방문율 향상 전략 보기", use_container_width=True):
                run_ai_report("v2", "🧠 AI 재방문율 향상 전략 리포트")
        else:
            # 혼합형/양호 매장은 매장 약점 진단 추천
            st.markdown("""
            <div style="background:#f0f9ff;padding:1.2rem;border-radius:10px;text-align:center;margin-top:1rem;">
                <h4>💡 더 나은 성과를 위한 전략이 필요하신가요?</h4>
                <p><b>매장 약점 진단</b>을 통해 개선점을 찾아보세요.</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔍 매장 약점 진단 받기", use_container_width=True, on_click=lambda: go("B_problem")):
                pass

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

elif st.session_state.step == "B_problem":
    st.markdown("<div class='card welcome-card'><h3 style='text-align:center;'>🧩 매장 약점 및 개선 전략</h3></div>", unsafe_allow_html=True)

    # v3 모델링 결과 먼저 표시 (RAG 없이)
    with st.spinner("매장 약점을 진단하는 중..."):
        result = generate_marketing_report(st.session_state.mct_id, mode="v3", rag=False)

    if "error" not in result:
        # 기본 정보 카드
       
        # 분석 정보 표시
        if result.get("analysis"):
            analysis = result["analysis"]

    
            # Top 3 약점 표시
            if analysis.get("diagnosis_top3"):
                st.markdown("<h4 style='text-align:center;margin-top:1.5rem;'>⚠️ 주요 약점 Top 3</h4>", unsafe_allow_html=True)

                for i, weakness in enumerate(analysis["diagnosis_top3"], 1):
                    severity = weakness.get('심각도', 0)
                    # 심각도에 따른 색상
                    if severity >= 70:
                        color = "#ef4444"  # 빨강
                        severity_text = "높음"
                    elif severity >= 40:
                        color = "#f59e0b"  # 주황
                        severity_text = "보통"
                    else:
                        color = "#4b9ce2"  # 파랑
                        severity_text = "낮음"

                    st.markdown(f"""
                    <div class="card" style="background:#ffffff;padding:1.2rem;border-left:4px solid {color};">
                        <h4>{i}. {weakness.get('약점', '-')}</h4>
                        <p><b>심각도:</b> {severity}점 / 100점 ({severity_text})</p>
                        <div style="background:#f3f4f6;border-radius:8px;height:20px;overflow:hidden;">
                            <div style="background:{color};height:100%;width:{severity}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # 추천 전략 표시
        if result.get("recommendations"):
            st.markdown("<h4 style='text-align:center;margin-top:1.5rem;'>💡 개선 전략</h4>", unsafe_allow_html=True)
            for i, rec in enumerate(result["recommendations"], 1):
                st.markdown(f"""
                <div class="card" style="background:#f0fdf4;padding:1.2rem;border-left:4px solid #22c55e;">
                    <p><b>{i}. {rec}</b></p>
                </div>
                """, unsafe_allow_html=True)

        # RAG 버튼
        st.markdown("<hr style='margin:2rem 0;'>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#ecfdf5;padding:1.2rem;border-radius:10px;text-align:center;margin-top:1rem;">
            <h4>💡 AI가 추천하는 상세 전략을 확인해보세요</h4>
            <p><b>외식행태 경영실태 통계 보고서</b>를 참고한 <b>맞춤형 개선 전략</b>이 자동 생성됩니다.</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🧠 AI 상세 진단 리포트 생성 (RAG)", use_container_width=True):
            run_ai_report("v3", "🧠 AI 약점 진단 및 개선 전략 리포트")

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))


# =====================================================
# 🚚 배달 플로우
# =====================================================
elif st.session_state.step == "C_1":
    render_store_input("C_2")

elif st.session_state.step == "C_2":
    mct_id = st.session_state.mct_id.strip()

    if not mct_id:
        st.warning("가맹점 ID를 입력해주세요.")
    else:
        st.markdown("<div class='card welcome-card'><h3 style='text-align:center;'>🚚 배달 도입 성공 예측</h3></div>", unsafe_allow_html=True)

        # 🔥 버튼 없이 바로 실행
        with st.spinner("AI가 배달 성공 확률을 예측 중입니다..."):
            result = generate_marketing_report(mct_id, mode="v4", rag=False)

        if "error" in result:
            st.error(f"⚠️ {result['error']}")
        else:
            # 기본 정보
            st.markdown(f"""
            <div class="card" style="background:#f8fafc;padding:1.2rem;">
                <h4>{result.get('emoji', '📍')} {result.get('store_name', '알 수 없음')} ({result.get('store_code', '-')})</h4>
                <p><b>업종:</b> {result.get('store_type', '-')}</p>
                <p><b>위치:</b> {result.get('district', '-')} {result.get('area', '-')}</p>
                <hr>
                <p style="font-size:1.5rem;"><b>✅ 성공 확률: {result.get('success_prob', 0):.1f}%</b></p>
                <p style="font-size:1.2rem;"><b>❌ 실패/중립 확률: {result.get('fail_prob', 0):.1f}%</b></p>
                <p><b>성공 가능성:</b> {result.get('status', '-')}</p>
            </div>
            """, unsafe_allow_html=True)

            # 권장사항
            st.markdown("<h4>💡 권장사항</h4>", unsafe_allow_html=True)
            st.markdown(f"<div class='card'>{result.get('message', '')}</div>", unsafe_allow_html=True)

            # 주요 근거
            reasons = result.get('reasons', [])
            if reasons:
                st.markdown("<h4>🔍 주요 근거</h4>", unsafe_allow_html=True)
                for reason in reasons:
                    status = reason.get('status', 'neutral')
                    if status == 'positive':
                        icon = "✅"
                    elif status == 'negative':
                        icon = "❌"
                    elif status == 'warning':
                        icon = "⚠️"
                    else:
                        icon = "📊"

                    st.markdown(f"""
                    <div class="card" style="padding:0.8rem;margin-bottom:0.5rem;">
                        <p><b>{icon} {reason.get('factor', '-')}: {reason.get('value', '-')}</b></p>
                        <p style="margin-left:1.5rem;">→ {reason.get('message', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)

    # 하단 버튼 유지
    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("C_1"))
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
