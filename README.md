# Crazy Creative - AI Marketing Report Generator

## 🧠 Overview
Crazy Creative는 상점 데이터를 기반으로 **AI가 자동으로 마케팅 리포트를 생성하는 시스템**입니다.  
Google **Gemini 2.5 Flash API**와 **FAISS 벡터 검색 (RAG)**을 결합해  
매장별 고객 분석, 재방문율 향상 전략, 약점 진단 보고서를 생성합니다.

---

## 🚀 Features
| Mode | Description |
|------|-------------|
| v0 | 기본 매장 상태 분석 및 운영 요약 |
| v1 | 고객 분석 및 마케팅 채널 추천 |
| v2 | 재방문율 분석 및 향상 전략 |
| v3 | 요식업 매장의 약점 진단 및 개선 아이디어 |

---

## 📁 Project Structure
crazy/
├── .env  
├── app/  
│   ├── main_app.py               (Streamlit UI 메인 앱)  
│   └── style.css                 (UI 스타일 시트)  
│  
├── analyzer/  
│   ├── __init__.py  
│   ├── utils.py                  (공통 유틸 함수)  
│   ├── paths.py                  (경로 상수 정의)  
│   ├── data_loader.py            (데이터 로드 및 전처리)  
│   ├── rag_engine.py             (RAG + Gemini 핵심 엔진)  
│   ├── report_generator.py       (v0~v3 통합 진입점)  
│   └── vector_dbs/               (버전별 벡터 DB 저장소)  
│       ├── shared/               (공통 세그먼트 임베딩)  
│       │   ├── marketing_segments.faiss  
│       │   └── marketing_segments_metadata.jsonl  
│       ├── v1/                   (v1용 리포트 임베딩)  
│       ├── v2/                   (v2: 재방문율 분석용)  
│       └── v3/                   (v3: 약점 진단용)  
│  
├── experiments/  
│   ├── _0_final/                 (스토어 상태 분석 실험)  
│   │   └── store_status.py  
│   ├── _1_final/                 (기초 RAG 모델 실험)  
│   │   ├── rag/  
│   │   └── report_generator.py  
│   ├── _2_final/                 (재방문율 분석 실험)  
│   │   ├── report_generator2.py  
│   │   ├── cluster_profiles.json  
│   │   ├── data_with_market_type.csv  
│   │   ├── resident_features.pkl  
│   │   ├── resident_kmeans.pkl  
│   │   ├── resident_scaler.pkl  
│   │   ├── office_features.pkl  
│   │   ├── office_kmeans.pkl  
│   │   └── office_scaler.pkl  
│   └── _3_final/                 (약점 진단 실험)  
│       ├── report_generator3.py  
│       ├── assets3/  
│       ├── clusters_k4_baseline/  
│       └── timeseries_models/  
│  
└── requirements.txt  

---

## ⚙️ Environment Setup
- Python 3.10 이상  
- macOS (M1/ARM64), Linux, Windows 지원  

### Installation
1. 가상환경 생성 및 활성화  
   - python3 -m venv .venv  
   - source .venv/bin/activate  

2. 패키지 설치  
   - pip install -r requirements.txt  

3. 환경변수 설정  
   - .env 파일에 다음 내용 추가  
     - GEMINI_API_KEY="YOUR_API_KEY"

4. 실행  
   - streamlit run app/main_app.py --server.fileWatcherType none  
   - (M1 Mac의 경우 segmentation fault 방지를 위해 위 옵션 필수)

---

## ⚙️ How It Works
1. **FAISS**가 사전 임베딩된 마케팅·매장 데이터를 로드  
2. **BGE-M3 모델**이 쿼리를 벡터로 변환  
3. **Gemini 2.5 Flash API**가 문맥 기반으로 리포트 생성  
4. **Streamlit**이 분석 결과를 카드형 UI로 시각화

---

## 🧩 Example Prompt
분석 대상 매장을 기준으로 비슷한 상권 데이터를 활용해  
AI 마케팅 리포트를 생성하라.  

1. 매장 요약  
2. 데이터 기반 인사이트  
3. 문제점 및 원인  
4. 단기/중기/장기 전략  
5. 결론 요약

---

## 🧰 Common Issues
| 문제 | 해결 방법 |
|------|------------|
| Segmentation fault | --server.fileWatcherType none 옵션 추가 |
| FAISS import error | pip install faiss-cpu==1.7.4 numpy==1.24.4 |
| KeyError: message | .get("message", "") 방식으로 수정 |
| API Key 오류 | .env 파일에 GEMINI_API_KEY 추가 |
| SentenceTransformer 오류 | pip install sentence-transformers 재설치 |

---

## 👨‍💻 Developer Info
- Author: **im-yeseol**  
- Project: **Crazy Creative**  
- Goal: AI 기반 자동 마케팅 인사이트 시스템 구축  

---

## 📜 License
본 프로젝트는 개인 연구 및 학습 목적용입니다.  
상업적 사용 시 사전 허가가 필요합니다.
