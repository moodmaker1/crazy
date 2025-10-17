import sys, os, re, html, base64, time
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from analyzer.report_generator import generate_marketing_report

# ------------------------------
# 기본 설정
# ------------------------------
st.set_page_config(page_title="지피지기 마케팅 리포트", layout="centered")
with open("app/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

#def debug_session_state():
#    st.sidebar.write("🧠 **Session Debug Info**")
#    st.sidebar.json({
#        "step": st.session_state.get("step"),
#        "mct_id": st.session_state.get("mct_id"),
#        "category": st.session_state.get("category"),
#    })
#
#debug_session_state()



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
# 세션 초기화 (최초 1회만)
# ------------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.step = "start"
    st.session_state.mct_id = ""
    st.session_state.category = None
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
    "channel": "추천 채널",
    "message": "홍보 문구 예시",
    "execution": "실행 방법",
    "evidence": "근거",
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


def _strip_html_tags(text: str) -> str:
    """HTML 태그를 제거하고 텍스트만 반환"""
    if not text:
        return ""
    # HTML 태그 제거 (정규식 사용)
    # <tag> 및 </tag> 형태 제거 (여러 번 실행하여 중첩된 태그도 제거)
    cleaned = text
    while re.search(r'<[^>]+>', cleaned):
        cleaned = re.sub(r'<[^>]+>', '', cleaned)

    # HTML 엔티티 디코드
    cleaned = cleaned.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    cleaned = cleaned.replace('&nbsp;', ' ').replace('&apos;', "'")

    # 연속된 공백 정리
    cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned.strip()


def _split_highlight_entries(value: str):
    if not value:
        return []

    # ✅ HTML 태그 제거
    #value = _strip_html_tags(value)

    entries = []
    buffer = []
    for raw_line in value.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if buffer:
                entries.append(" ".join(buffer))
                buffer = []
            continue
        # ✅ bullet point 인식: -, •, ○, *
        if stripped.startswith(("-", "•", "○", "*")):
            stripped = stripped.lstrip("-•○*").strip()
            if buffer:
                entries.append(" ".join(buffer))
                buffer = []
            if stripped:
                entries.append(stripped)
        else:
            buffer.append(stripped)

    if buffer:
        entries.append(" ".join(buffer))

    formatted = []
    for entry in entries:
        parts = [html.escape(part.strip()) for part in entry.split("\n") if part.strip()]
        formatted.append("<br>".join(parts))
    return formatted


def _normalize_section_heading(value: str) -> str:
    if not value:
        return ""
    stripped = value.strip()
    stripped = stripped.lstrip("# ").strip()
    if stripped.startswith("☕"):
        return ""
    stripped = re.sub(r"^\[[^\]]+\]\s*", "", stripped)
    return stripped


def extract_highlight_sections(summary: str):
    if not summary:
        return {}, summary

    cleaned_text = summary
    extracted = {}
    label_stop = "|".join(re.escape(value) for value in HIGHLIGHT_LABELS.values())
    stop_lookahead = (
        rf"(?=(\n[ \t]*(?:{label_stop})\s*[:：-])|\Z)"
        if label_stop
        else r"(?=\Z)"
    )
    for key, label in HIGHLIGHT_LABELS.items():
        pattern = re.compile(
            rf"(^|\n)[ \t]*{re.escape(label)}\s*[:：-]*\s*(.*?){stop_lookahead}",
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

    # ✅ 마크다운 제거 (Gemini가 **bold** 형식으로 생성하는 경우 대비)
    summary = summary.replace("**", "")

    lines = summary.splitlines()
    used = [False] * len(lines)

    cards = []
    heading = None
    current_item = None
    current_field = None
    card_counter = 0

    def start_new_item(title: str = "", fallback_title: str = ""):
        nonlocal current_item, current_field, card_counter
        card_counter += 1
        title_clean = (title or "").strip()
        fallback_clean = (fallback_title or "").strip()
        resolved_title = title_clean or fallback_clean or f"추천 전략 #{card_counter}"
        current_item = {
            "title": resolved_title,
            "channel": "",
            "message": "",
            "execution": [],
            "evidence": [],
        }
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

        normalized = stripped.lstrip("-•○* ").strip()

        if normalized.startswith("[") and "]" in normalized[:6]:
            flush_item()
            heading = normalized
            mark_used(i)
            i += 1
            continue

        # [A]/[B] 구분 헤더 인식 추가
        if re.match(r"\[[A-Z]\]", normalized):
            flush_item()
            heading = normalized.strip()
            mark_used(i)
            i += 1
            continue

        # 숫자형 항목(1., 2. 등) 인식
        if re.match(r"\d+\.", normalized):
            flush_item()
            start_new_item(normalized, heading)
            mark_used(i)
            i += 1
            continue

        matched_label = False
        for key, label in HIGHLIGHT_LABELS.items():
            label_variants = [label]
            plain_label = re.sub(r"^[^\w가-힣]+", "", label).strip()
            if plain_label and plain_label not in label_variants:
                label_variants.append(plain_label)
            compact_label = re.sub(r"\s+", "", plain_label or label)
            if compact_label and compact_label not in label_variants:
                label_variants.append(compact_label)

            for variant in label_variants:
                # ✅ HTML 태그 제거 후 bullet point (•, -, ○, *) 제거 후 매칭
                cleaned_for_match = _strip_html_tags(stripped.lstrip("-•○* ").strip())
                if cleaned_for_match.startswith(variant):
                    value = cleaned_for_match[len(variant):].lstrip(" :：-")
                    mark_used(i)
                    matched_label = True
                    if current_item is None:
                        fallback_title = _normalize_section_heading(heading) if heading else ""
                        start_new_item("", fallback_title)
                    current_field = key
                    if key in {"channel", "message"}:
                        current_item[key] = append_text(current_item.get(key, ""), value)
                    else:
                        bucket = current_item.setdefault(key, [])
                        if value:
                            bucket.append(value)
                    break

            if matched_label:
                mark_used(i)
                break

        if matched_label:
            i += 1
            continue

        if current_item and current_field:
            mark_used(i)
            if current_field in {"channel", "message"}:
                current_item[current_field] = append_text(current_item[current_field], normalized)
            else:
                current_item.setdefault(current_field, []).append(normalized)
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

    # RAG 결과
    rag_summary = result.get("rag_summary")
    if rag_summary:
        rag_summary = re.sub(r"^\s*[#☕][^\n]*(\n|$)", "", rag_summary, count=1).strip()
        st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)

        action_cards, remaining_for_highlights = extract_action_cards(rag_summary)
        highlight_sections, remaining_summary = extract_highlight_sections(remaining_for_highlights)

        if action_cards:
            current_heading = None
            for card in action_cards:
                heading_text = _normalize_section_heading(card.get("heading", ""))
                if heading_text and heading_text != current_heading:
                    st.markdown(
                        f"<h4 class='proposal-section__title'>{html.escape(heading_text)}</h4>",
                        unsafe_allow_html=True,
                    )
                    current_heading = heading_text

                channel_items = _split_highlight_entries(card.get("channel", ""))
                message_items = _split_highlight_entries(card.get("message", ""))
                entry_count = max(len(channel_items), len(message_items))
                if entry_count == 0:
                    continue

                exec_items = _split_highlight_entries(card.get("execution", ""))
                evidence_items = _split_highlight_entries(card.get("evidence", ""))

                detail_sections = []
                if exec_items:
                    detail_sections.append(
                        "<div class='proposal-card__detail'><h5>실행 방법</h5><ul>"
                        + "".join(f"<li>{item}</li>" for item in exec_items)
                        + "</ul></div>"
                    )
                if evidence_items:
                    detail_sections.append(
                        "<div class='proposal-card__detail'><h5>근거</h5><ul>"
                        + "".join(f"<li>{item}</li>" for item in evidence_items)
                        + "</ul></div>"
                    )
                detail_html = (
                    "<div class='proposal-card__details'>" + "".join(detail_sections) + "</div>"
                    if detail_sections
                    else ""
                )

                title_html = html.escape(card.get("title", "").strip())
                default_title = "추천 전략"
                for idx in range(entry_count):
                    channel_html = channel_items[idx] if idx < len(channel_items) else ""
                    message_html = message_items[idx] if idx < len(message_items) else ""

                    chips = []
                    if channel_html:
                        chips.append(f"**추천 채널**  \n{_strip_html_tags(channel_html)}")
                    if message_html:
                        chips.append(f"**홍보 문구 예시**  \n{_strip_html_tags(message_html)}")

                    chips_html = "<br><br>".join(chips)
                                        
                    
                    
                    

                    summary_title = title_html or default_title
                    if entry_count > 1:
                        if title_html:
                            summary_title = f"{title_html} #{idx + 1}"
                        else:
                            summary_title = f"{default_title} #{idx + 1}"

                    card_html = f"""
                    <details class="proposal-card">
                        <summary>
                            <div class="proposal-card__summary">
                                <div class="proposal-card__heading">{summary_title}</div>
                                <div class="proposal-card__chips">{chips_html}</div>
                            </div>
                        </summary>
                        {detail_html}
                    </details>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

        elif highlight_sections.get("channel") or highlight_sections.get("message"):
            channel_items = _split_highlight_entries(highlight_sections.get("channel", ""))
            message_items = _split_highlight_entries(highlight_sections.get("message", ""))

            exec_items = _split_highlight_entries(highlight_sections.get("execution", ""))
            evidence_items = _split_highlight_entries(highlight_sections.get("evidence", ""))

            detail_sections = []
            if exec_items:
                detail_sections.append(
                    "<div class='proposal-card__detail'><h5>실행 방법</h5><ul>"
                    + "".join(f"<li>{item}</li>" for item in exec_items)
                    + "</ul></div>"
                )
            if evidence_items:
                detail_sections.append(
                    "<div class='proposal-card__detail'><h5>근거</h5><ul>"
                    + "".join(f"<li>{item}</li>" for item in evidence_items)
                    + "</ul></div>"
                )
            detail_html = (
                "<div class='proposal-card__details'>" + "".join(detail_sections) + "</div>"
                if detail_sections
                else ""
            )

            entry_count = max(len(channel_items), len(message_items))
            if entry_count == 0:
                entry_count = 1
            for idx in range(entry_count):
                channel_html = channel_items[idx] if idx < len(channel_items) else ""
                message_html = message_items[idx] if idx < len(message_items) else ""
                chips = []
                if channel_html:
                    chips.append(
                        f"""
                        <div class="proposal-card__chip">
                            <span class="proposal-card__label">추천 채널</span>
                            <span class="proposal-card__value">{channel_html}</span>
                        </div>
                        """
                    )
                if message_html:
                    chips.append(
                        f"""
                        <div class="proposal-card__chip">
                            <span class="proposal-card__label">홍보 문구 예시</span>
                            <span class="proposal-card__value">{message_html}</span>
                        </div>
                        """
                    )
                chips_html = "".join(chips)

                summary_title = "추천 제안"
                if entry_count > 1:
                    summary_title = f"추천 제안 #{idx + 1}"

                card_html = f"""
                <details class="proposal-card">
                    <summary>
                        <div class="proposal-card__summary">
                            <div class="proposal-card__heading">{summary_title}</div>
                            <div class="proposal-card__chips">{chips_html}</div>
                        </div>
                    </summary>
                    {detail_html}
                </details>
                """
                st.markdown(card_html, unsafe_allow_html=True)

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

    
    # ✅ 키워드 트렌드 섹션 (RAG 이후에 표시)
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



# =====================================================
# ✅ 공통 함수 2: AI 리포트 실행
# =====================================================
def run_ai_report(mode: str, title: str):
    mct_id = st.session_state.get("mct_id", "")
    if not mct_id:
        st.warning("가맹점 ID를 먼저 입력한 후 다시 시도해주세요.")
        return

    image_candidates = [
        "app/spinner1.png",
        "app/spinner2.png",
        "app/spinner3.png",
    ]
    available_images = [path for path in image_candidates if os.path.exists(path)]

    status_placeholder = st.empty()
    overlay_placeholder = st.empty()
    status_placeholder.markdown("⏳ AI가 분석 중입니다...")

    def _run_task():
        return generate_marketing_report(mct_id, mode=mode)

    try:
        if not available_images:
            with st.spinner("AI가 분석 중입니다..."):
                result = _run_task()
        else:
            encoded_images = []
            for path in available_images:
                try:
                    with open(path, "rb") as fp:
                        encoded_images.append(
                            f"data:image/png;base64,{base64.b64encode(fp.read()).decode()}"
                        )
                except Exception:
                    continue

            if not encoded_images:
                with st.spinner("AI가 분석 중입니다..."):
                    result = _run_task()
            else:
                spinner_style = """
                <style>
                .global-spinner-overlay {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    z-index: 9999;
                    width: 90px;
                    height: 90px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 8px;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.9);
                    box-shadow: 0 18px 36px -24px rgba(15, 23, 42, 0.35);
                }
                .global-spinner-overlay img {
                    width: 72px;
                    height: 72px;
                    object-fit: contain;
                }
                </style>
                """
                overlay_placeholder.markdown(spinner_style, unsafe_allow_html=True)

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_run_task)
                    image_cycle = cycle(encoded_images)
                    while not future.done():
                        overlay_placeholder.markdown(
                            f"""
                            {spinner_style}
                            <div class="global-spinner-overlay">
                                <img src="{next(image_cycle)}" alt="loading">
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        time.sleep(0.6)
                    result = future.result()
    except Exception as exc:
        overlay_placeholder.empty()
        status_placeholder.empty()
        st.error(f"⚠️ 분석 도중 오류가 발생했습니다: {exc}")
        return

    overlay_placeholder.empty()
    status_placeholder.empty()
    display_ai_report(result, title)


# =====================================================
# ✅ 공통 함수 3: 가맹점 코드 입력 폼
# =====================================================
def render_store_input(next_step: str):
    category = st.session_state.get("category")

    intro_map = {
        "카페": {
            "image": "app/1.png",
            "heading": "안녕하세요! 카페 사장님",
            "message": "사장님의 가게를 신속하고 정확하게 분석해<br><strong>최고의 마케팅 전략</strong>을 제시해드릴게요.",
        },
        "요식업": {
            "image": "app/2.png",
            "heading": "안녕하세요! 요식업 사장님",
            "message": "매장의 운영 데이터를 AI가 정밀 분석해<br><strong>가장 효과적인 성장 전략</strong>을 알려드릴게요."
        },
        "배달": {
            "image": "app/3.png",
            "heading": "배달 도입을 고민중이신가요?",
            "message": "매장의 운영 데이터를 AI가 정밀 분석해<br><strong>배달 도입시 성공,실패 예측 진단</strong>을 해드릴게요."
        }
    }

    if category in intro_map:
        config = intro_map[category]
        intro_cols = st.columns([1, 2])
        with intro_cols[0]:
            if os.path.exists(config["image"]):
                st.image(config["image"], use_column_width=True)
        with intro_cols[1]:
            st.markdown(
                f"""
                <div class="intro-card">
                    <h3>{config['heading']}</h3>
                    <p>
                        {config['message']}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ✅ 폼으로 묶기
    with st.form("store_input_form", clear_on_submit=False):
        st.markdown(
            """
            <div class="card welcome-card">
                <h3>당신의 가맹점 코드를 입력해주세요.</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        mct_id_input = st.text_input(
            "가맹점 ID",
            value=st.session_state.get("mct_id", ""),
            placeholder="예: MCT12345"
        )

        submitted = st.form_submit_button("다음으로", use_container_width=True)
        if submitted:
            st.session_state.mct_id = mct_id_input.strip()
            go(next_step)

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
    st.markdown(
        f"""
        <div class="card card--surface-light">
            <h4>🏪 {info.get('가맹점명','알 수 없음')} ({mct_id})</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
            <li class="insight"> {info.get('매출등급_해석', '')}</li>
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
            <li class="insight"> {info.get('성장성_해석', '')}</li>
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
# ✅ 공통 함수 X: 에러 메시지 표시
# =====================================================
def show_error_message(result: dict):
    """모든 리포트 공통 에러 출력 함수"""
    error_msg = result.get("error", "오류가 발생했습니다.")
    industry = result.get("industry", None)
    store_code = result.get("store_code", None)

    # 🟡 업종 미지원
    if "업종" in error_msg and industry:
        st.warning(f"⚠️ '{industry}' 업종은 현재 카페 전용 모델에서만 분석 가능합니다.")
        st.info("☕ 카페, 커피전문점, 테마카페, 테이크아웃커피 업종만 지원됩니다.")
        st.markdown("""
        <div style="background:#f9fafb;padding:1rem;border-radius:10px;margin-top:1rem;">
            💡 다른 분석을 원하신다면 <b>요식업</b> 또는 <b>배달</b> 탭에서 진행해주세요.
        </div>
        """, unsafe_allow_html=True)

    # 🔴 매장 코드 없음
    elif "매장을 찾을 수 없습니다" in error_msg:
        st.error("❌ 입력하신 가맹점 코드를 찾을 수 없습니다.")
        st.info("입력한 매장 ID가 정확한지 다시 확인해주세요. 예: `A2781768EE`")

    # ⚪ 일반 예외
    else:
        st.error(f"⚠️ {error_msg}")


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

    st.markdown("<h3 class='center-heading'>어떤 전략을 추천받고 싶으세요?</h3>", unsafe_allow_html=True)
    st.button("마케팅 채널 추천", use_container_width=True, on_click=lambda: go("A_3"))
    st.button("재방문율 향상 전략", use_container_width=True, on_click=lambda: go("A_4"))
    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("A_1"))

elif st.session_state.step == "A_3":
    st.markdown(
        """
        <div class="card welcome-card">
            <h3>고객 분석 및 마케팅 채널 추천</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
            status_class = "status-card status-card--positive"
            emoji = "🎉"
        elif "안정적" in status:
            status_class = "status-card status-card--info"
            emoji = "✅"
        elif "보완" in status or "필요" in status:
            status_class = "status-card status-card--warning"
            emoji = "⚠️"
        else:
            status_class = "status-card status-card--critical"
            emoji = "🚨"

        detail_html = f'<p class="status-card__detail">{status_detail}</p>' if status_detail else ""

        st.markdown(
            f"""
            <div class="{status_class}">
                <h3>{emoji} {store_name}</h3>
                <p class="status-card__summary">{status}</p>
                {detail_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. 핵심 고객 요약 카드
        analysis = result.get('analysis', {})
        summary = analysis.get('summary', '')
        cluster = analysis.get('cluster', '-')

        st.markdown(
            f"""
            <div class="accent-card accent-card--primary">
                <h4>👥 핵심 고객 요약</h4>
                <p class="accent-card__body">{summary}</p>
                <p class="accent-card__note">🗺️ 상권 클러스터: <b>{cluster}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 3. 주요 인사이트 카드
        insights = analysis.get('insights', [])[:2]
        if insights:
            insights_html = "".join(f"<li>{insight}</li>" for insight in insights)
            st.markdown(
                f"""
                <div class="accent-card accent-card--warning">
                    <h4>💡 주요 인사이트</h4>
                    <ul class="list-with-icon">
                        {insights_html}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # RAG 버튼 안내
        st.markdown(
            """
            <div class="callout-card callout-card--positive">
                <h4>💡 AI가 추천하는 상세 전략을 확인해보세요</h4>
                <p><b>외식행태 경영실태 통계 보고서</b>를 참고한 <b>맞춤형 마케팅 전략</b>이 자동 생성됩니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # RAG 버튼
        if st.button("마케팅 채널 & 홍보 문구 제안 (RAG)", use_container_width=True):
            run_ai_report("v1", "AI 마케팅 채널 & 홍보 전략 리포트")
    else:
        show_error_message(result)

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

elif st.session_state.step == "A_4":
    st.markdown(
        """
        <div class="card welcome-card">
            <h3>🔁 재방문율 향상 전략 제안</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("AI 리포트 생성", use_container_width=True):
        run_ai_report("v2", " AI 재방문율 향상 리포트")
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

            st.markdown("<h3 class='center-heading'>어떤 분석을 원하시나요?</h3>", unsafe_allow_html=True)
            st.button("재방문율 향상 전략 보기", use_container_width=True,
                      on_click=lambda: go("B_high" if rate >= 30 else "B_low"))
            st.button("매장 문제 진단", use_container_width=True, on_click=lambda: go("B_problem"))

    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("B_1"))


elif st.session_state.step == "B_high":
    st.markdown("<h3 class='center-heading'>🎉 축하드립니다!</h3>", unsafe_allow_html=True)
    st.write("재방문율이 **30% 이상**입니다! 이미 충성 고객을 많이 확보하셨네요👏")
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
elif st.session_state.step == "B_low":
    st.markdown("<h3 class='center-heading'>재방문율이 30% 미만입니다</h3>", unsafe_allow_html=True)

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
        store_name = result.get("store_name", "알 수 없음")
        store_code = result.get("store_code", "-")

        if revisit < 30:
            status_class = "status-card status-card--critical"
        elif revisit < 40:
            status_class = "status-card status-card--warning"
        else:
            status_class = "status-card status-card--positive"

        revisit_text = f"{revisit:.1f}%"
        if benchmark_rate > 0:
            revisit_text += f" (유사 매장 평균 {benchmark_rate:.1f}% 대비)"

        detail_sections = [
            f'<p class="status-card__detail"><b>현재 재방문율:</b> {revisit_text}</p>',
            f'<p class="status-card__detail">📍 상권 유형: {market_type}</p>',
        ]
        if message:
            detail_sections.append(f'<p class="status-card__detail">💬 {message}</p>')
        detail_html = "".join(detail_sections)

        st.markdown(
            f"""
            <div class="{status_class}">
                <h3>🏪 {store_name} ({store_code})</h3>
                <p class="status-card__summary">{status_text}</p>
                {detail_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ✅ 혼합형, 유동형 또는 재방문율 양호 시 별도 안내
        show_strategy_button = True  # 기본적으로 전략 버튼 표시

        if market_type == "혼합형":
            st.markdown(
                """
                <div class="accent-card accent-card--primary">
                    <h4>ℹ️ 혼합형 상권 특성</h4>
                    <p>혼합형 상권은 <b>거주, 직장, 유동 고객이 골고루 분포</b>된 지역입니다.</p>
                    <p>다양한 고객층을 대상으로 하기 때문에, 특정 고객군에 집중하기보다는
                       <b>시간대별 맞춤 전략</b>이 필요합니다.</p>
                    <ul class="list-with-icon">
                        <li>🌅 점심: 직장인 대상 빠른 서비스</li>
                        <li>🌆 저녁/주말: 거주민 대상 편안한 분위기</li>
                        <li>☀️ 평일 낮: 유동 고객 대상 테이크아웃 강화</li>
                    </ul>
                    <p class="accent-card__note">💡 혼합형 매장은 <b>매장 약점 진단</b>을 통해 개선점을 찾는 것이 더 효과적입니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_strategy_button = False  # 혼합형은 재방문율 전략 버튼 숨김

        elif market_type == "유동형":
            st.markdown(
                """
                <div class="accent-card accent-card--warning">
                    <h4>⚡ 유동형 상권 특성</h4>
                    <p>유동형 상권은 <b>재방문율보다 매출액과 회전율</b>이 더 중요한 지표입니다.</p>
                    <p><b>신규 고객 유입</b>이 핵심이며, 빠른 서비스와 높은 가시성이 성공 요소입니다.</p>
                    <ul class="list-with-icon">
                        <li>💰 <b>객단가 향상</b>: 세트 메뉴, 업셀링 전략</li>
                        <li>🚚 <b>배달 서비스</b>: 온라인 채널 확장</li>
                        <li>📣 <b>가시성 강화</b>: 간판, SNS 마케팅</li>
                        <li>⚡ <b>회전율 개선</b>: 빠른 서비스, 메뉴 단순화</li>
                    </ul>
                    <p class="accent-card__note">💡 유동형 매장은 <b>매장 약점 진단</b>을 통해 매출 증대 전략을 찾는 것이 더 효과적입니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_strategy_button = False  # 유동형은 재방문율 전략 버튼 숨김

        elif status_text == "양호":
            st.markdown(
                """
                <div class="accent-card accent-card--positive">
                    <h4>✅ 재방문율이 양호합니다</h4>
                    <p>현재 운영 방식을 유지하면서, <b>추가 성장</b>을 위한 전략이 필요합니다:</p>
                    <ul class="list-with-icon">
                        <li>✨ <b>신규 고객 유입 확대</b> (SNS, 배달 플랫폼)</li>
                        <li>💰 <b>객단가 향상</b> (세트 메뉴, 업셀링)</li>
                        <li>🎁 <b>단골 고객 우대 프로그램 강화</b></li>
                    </ul>
                    <p class="accent-card__note">💡 더 나은 성과를 위해 <b>매장 약점 진단</b>을 받아보세요.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_strategy_button = False  # 양호한 경우 재방문율 전략 버튼 숨김

        # ✅ 클러스터 정보 요약 (거주형/직장형만)
        if result.get("cluster_info"):
            ci = result["cluster_info"]
            st.markdown(
                f"""
                <div class="accent-card accent-card--secondary">
                    <h4>🏷️ AI 분류 결과</h4>
                    <p>당신의 매장은 <b>‘{ci.get('cluster_name', '-')}’</b> 유형으로 분석되었습니다.</p>
                    <p>{ci.get('cluster_description', '비슷한 운영 특성을 가진 매장과 비교해 분석되었습니다.')}</p>
                    <p>이 그룹은 총 <b>{ci.get('cluster_size', 0)}개 매장</b>으로 구성되어 있으며,
                       그중 <b>{ci.get('success_count', 0)}개({ci.get('success_rate', '-')})</b>가 개선에 성공했습니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ✅ 데이터 차이 요약
        if result.get("gaps"):
            g = result["gaps"]
            st.markdown(
                f"""
                <div class="accent-card accent-card--warning">
                    <h4>📉 데이터 차이 요약</h4>
                    <ul class="list-with-icon">
                        <li>💰 객단가: 평균 대비 <b>{g.get('객단가', {}).get('gap', 0):+.2f}</b> 낮음</li>
                        <li>💬 충성도: 벤치마크보다 <b>{g.get('충성도', {}).get('gap', 0):+.2f}</b> 낮음 → 단골 확보 필요</li>
                        <li>🚚 배달비율: <b>{g.get('배달비율', {}).get('gap', 0):+.2f}</b> 부족 → 온라인 채널 확장 여지 있음</li>
                    </ul>
                    <p class="accent-card__note">➡️ 위 3가지 요인이 <b>재방문율 저하</b>에 가장 큰 영향을 주는 것으로 분석됩니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ✅ 다음 단계 안내 카드 및 버튼 (조건부 표시)
        if show_strategy_button:
            st.markdown(
                """
                <div class="callout-card callout-card--positive">
                    <h4>💡 AI가 제시하는 맞춤 전략을 확인해보세요</h4>
                    <p>고객 재방문을 늘릴 수 있는 <b>단기·중기·장기 전략</b>이 자동 생성됩니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ✅ 버튼
            if st.button("AI 재방문율 향상 전략 보기", use_container_width=True):
                run_ai_report("v2", "AI 재방문율 향상 전략 리포트")
        else:
            # 혼합형/양호 매장은 매장 약점 진단 추천
            st.markdown(
                """
                <div class="callout-card callout-card--muted">
                    <h4>💡 더 나은 성과를 위한 전략이 필요하신가요?</h4>
                    <p><b>매장 약점 진단</b>을 통해 개선점을 찾아보세요.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("🔍 매장 약점 진단 받기", use_container_width=True, on_click=lambda: go("B_problem")):
                pass

    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))

elif st.session_state.step == "B_problem":
    st.markdown(
        """
        <div class="card welcome-card">
            <h3>🧩 매장 약점 및 개선 전략</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
                st.markdown("<h4 class='center-heading'>⚠️ 주요 약점 Top 3</h4>", unsafe_allow_html=True)

                for i, weakness in enumerate(analysis["diagnosis_top3"], 1):
                    severity = weakness.get('심각도', 0)
                    # 심각도에 따른 색상
                    if severity >= 70:
                        severity_class = "card weakness-card severity-high"
                        severity_text = "높음"
                    elif severity >= 40:
                        severity_class = "card weakness-card severity-medium"
                        severity_text = "보통"
                    else:
                        severity_class = "card weakness-card severity-low"
                        severity_text = "낮음"

                    st.markdown(
                        f"""
                        <div class="{severity_class}">
                            <h4>{i}. {weakness.get('약점', '-')}</h4>
                            <p><b>심각도:</b> {severity}점 / 100점 ({severity_text})</p>
                            <div class="weakness-card__bar">
                                <div class="weakness-card__bar-fill" style="width:{severity}%;"></div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # 추천 전략 표시
        if result.get("recommendations"):
            st.markdown("<h4 class='center-heading'>💡 개선 전략</h4>", unsafe_allow_html=True)
            for i, rec in enumerate(result["recommendations"], 1):
                st.markdown(
                    f"""
                    <div class="card recommendation-card">
                        <p><b>{i}. {rec}</b></p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # RAG 버튼
        st.markdown("<hr style='margin:2rem 0;'>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="callout-card callout-card--positive">
                <h4>💡 AI가 추천하는 상세 전략을 확인해보세요</h4>
                <p><b>외식행태 경영실태 통계 보고서</b>를 참고한 <b>맞춤형 개선 전략</b>이 자동 생성됩니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("AI 상세 진단 리포트 생성 (RAG)", use_container_width=True):
            run_ai_report("v3", "AI 약점 진단 및 개선 전략 리포트")

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
        st.markdown(
            """
            <div class="card welcome-card">
                <h3>🚚 배달 도입 성공 예측</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 🔥 버튼 없이 바로 실행
        with st.spinner("AI가 배달 성공 확률을 예측 중입니다..."):
            result = generate_marketing_report(mct_id, mode="v4", rag=False)

        if "error" in result:
            st.error(f"⚠️ {result['error']}")
        else:
            # 기본 정보
            st.markdown(
                f"""
                <div class="card card--surface-light">
                    <h4>{result.get('emoji', '📍')} {result.get('store_name', '알 수 없음')} ({result.get('store_code', '-')})</h4>
                    <p><b>업종:</b> {result.get('store_type', '-')}</p>
                    <p><b>위치:</b> {result.get('district', '-')} {result.get('area', '-')}</p>
                    <hr>
                    <p class="stat-highlight">✅ 성공 확률: {result.get('success_prob', 0):.1f}%</p>
                    <p class="stat-highlight--muted">❌ 실패/중립 확률: {result.get('fail_prob', 0):.1f}%</p>
                    <p><b>성공 가능성:</b> {result.get('status', '-')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

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

                    reason_class = "card reason-card card--compact"
                    if status == "positive":
                        reason_class += " reason-card--positive"
                    elif status == "negative":
                        reason_class += " reason-card--negative"
                    elif status == "warning":
                        reason_class += " reason-card--warning"

                    st.markdown(
                        f"""
                        <div class="{reason_class}">
                            <p><b>{icon} {reason.get('factor', '-')}: {reason.get('value', '-')}</b></p>
                            <p class="reason-card__message">→ {reason.get('message', '')}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # 하단 버튼 유지
    st.button("← 이전으로", use_container_width=True, on_click=lambda: go("C_1"))
    st.button("← 처음으로", use_container_width=True, on_click=lambda: go("start"))
