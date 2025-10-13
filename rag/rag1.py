"""
RAG 기반 매장별 마케팅 채널 추천 시스템 (Google Gemini 2.5 Flash 버전)
- PyTrends로 업종 트렌드 분석
- 엑셀 파일에서 마케팅 전략 문서 로드
- 매장 특성과 문서 간 유사도 계산
- Gemini 2.5 Flash로 맞춤형 마케팅 전략 생성 (4개 섹션)
"""

import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
from pathlib import Path
import warnings
import google.generativeai as genai
from pytrends.request import TrendReq

warnings.filterwarnings('ignore')

class RAGMarketingSystem:
    def __init__(self, data_folder_path, gemini_api_key):
        """
        Args:
            data_folder_path: rag데이터_병진님 폴더 경로
            gemini_api_key: Google Gemini API 키
        """
        self.data_folder = Path(data_folder_path)
        
        # Sentence Transformer 모델 (검색용)
        print("🔄 임베딩 모델 로딩 중...")
        self.model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        
        # Gemini 설정
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # PyTrends 설정
        self.pytrends = TrendReq(hl='ko', tz=540)
        
        self.documents = []
        self.doc_embeddings = None
        
    def get_industry_trends(self, industry_keyword, timeframe='today 3-m'):
        """PyTrends로 업종 검색 트렌드 가져오기"""
        try:
            print(f"📈 '{industry_keyword}' 업종 트렌드 분석 중...")
            
            # 키워드 설정
            self.pytrends.build_payload([industry_keyword], timeframe=timeframe, geo='KR')
            
            # 시간별 관심도
            interest_over_time = self.pytrends.interest_over_time()
            
            # 지역별 관심도
            interest_by_region = self.pytrends.interest_by_region(resolution='REGION', inc_low_vol=True)
            
            # 관련 검색어
            related_queries = self.pytrends.related_queries()
            
            # 데이터 요약
            trend_summary = {
                'keyword': industry_keyword,
                'current_trend': 'N/A',
                'avg_interest': 0,
                'top_regions': [],
                'rising_queries': []
            }
            
            if not interest_over_time.empty:
                trend_summary['avg_interest'] = int(interest_over_time[industry_keyword].mean())
                latest_value = interest_over_time[industry_keyword].iloc[-1]
                prev_value = interest_over_time[industry_keyword].iloc[-5] if len(interest_over_time) > 5 else latest_value
                
                if latest_value > prev_value * 1.1:
                    trend_summary['current_trend'] = '상승세 📈'
                elif latest_value < prev_value * 0.9:
                    trend_summary['current_trend'] = '하락세 📉'
                else:
                    trend_summary['current_trend'] = '안정세 ➡️'
            
            if not interest_by_region.empty:
                top_regions = interest_by_region.nlargest(3, industry_keyword)
                trend_summary['top_regions'] = [
                    f"{region} ({int(value)})" 
                    for region, value in zip(top_regions.index, top_regions[industry_keyword])
                ]
            
            if related_queries[industry_keyword]['rising'] is not None:
                rising = related_queries[industry_keyword]['rising'].head(5)
                trend_summary['rising_queries'] = rising['query'].tolist() if not rising.empty else []
            
            print(f"  ✓ 트렌드: {trend_summary['current_trend']}")
            print(f"  ✓ 평균 관심도: {trend_summary['avg_interest']}/100")
            print()
            
            return trend_summary
            
        except Exception as e:
            print(f"  ⚠️  트렌드 분석 실패: {str(e)}")
            return {
                'keyword': industry_keyword,
                'current_trend': '데이터 없음',
                'avg_interest': 0,
                'top_regions': [],
                'rising_queries': []
            }
    
    def load_documents(self):
        """엑셀 파일들을 읽어서 문서 데이터베이스 구축"""
        print("\n📚 문서 로딩 중...")
        
        excel_files = list(self.data_folder.glob('*.xlsx'))
        
        for file_path in excel_files:
            try:
                # 엑셀 파일 읽기
                df = pd.read_excel(file_path, sheet_name=0)
                
                # 파일명에서 주제 추출
                file_name = file_path.stem
                
                # 데이터를 텍스트로 변환
                content = self._extract_content_from_df(df, file_name)
                
                self.documents.append({
                    'file_name': file_name,
                    'file_path': str(file_path),
                    'content': content,
                    'dataframe': df,
                    'raw_data': df.to_string()[:5000]  # 처음 5000자만 저장
                })
                
                print(f"  ✓ {file_name}")
                
            except Exception as e:
                print(f"  ✗ {file_path.name}: {str(e)}")
        
        print(f"\n총 {len(self.documents)}개 문서 로드 완료!\n")
        
    def _extract_content_from_df(self, df, file_name):
        """데이터프레임에서 의미있는 텍스트 추출"""
        content_parts = [file_name]
        
        # 열 이름들
        content_parts.append(" ".join([str(col) for col in df.columns if pd.notna(col)]))
        
        # 처음 30행의 데이터 샘플링
        for idx, row in df.head(30).iterrows():
            row_text = " ".join([str(val) for val in row if pd.notna(val) and str(val).strip()])
            if row_text:
                content_parts.append(row_text)
        
        return " ".join(content_parts)
    
    def build_embeddings(self):
        """문서들의 임베딩 벡터 생성"""
        if len(self.documents) == 0:
            print("❌ 로드된 문서가 없습니다!")
            print("해결방법:")
            print("  1. openpyxl 설치: pip install openpyxl")
            print("  2. 데이터 폴더 경로 확인")
            return False
        
        print("🔄 문서 임베딩 생성 중...")
        
        contents = [doc['content'] for doc in self.documents]
        self.doc_embeddings = self.model.encode(contents, show_progress_bar=True)
        
        print("✓ 임베딩 생성 완료!\n")
        return True
    
    def search_relevant_documents(self, store_data, top_k=2):
        """매장 데이터와 유사한 문서 검색"""
        
        if len(self.documents) == 0:
            print("❌ 검색할 문서가 없습니다!")
            return []
        
        if self.doc_embeddings is None or len(self.doc_embeddings) == 0:
            print("❌ 임베딩이 생성되지 않았습니다!")
            return []
        
        # 매장 특성을 텍스트로 변환
        query_text = self._store_data_to_text(store_data)
        
        print("🔍 매장 특성 분석:")
        print(f"  {query_text[:200]}...\n")
        
        # 쿼리 임베딩
        query_embedding = self.model.encode([query_text])
        
        # 코사인 유사도 계산
        similarities = cosine_similarity(query_embedding, self.doc_embeddings)[0]
        
        # 상위 K개 문서 인덱스
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        print(f"📊 관련도 높은 상위 {top_k}개 문서:\n")
        
        for rank, idx in enumerate(top_indices, 1):
            doc = self.documents[idx]
            similarity_score = similarities[idx] * 100
            
            results.append({
                'rank': rank,
                'file_name': doc['file_name'],
                'file_path': doc['file_path'],
                'similarity': similarity_score,
                'dataframe': doc['dataframe'],
                'raw_data': doc['raw_data']
            })
            
            print(f"  {rank}. [{similarity_score:.1f}%] {doc['file_name']}")
        
        print()
        return results
    
    def _store_data_to_text(self, store_data):
        """매장 JSON 데이터를 검색용 텍스트로 변환"""
        
        parts = []
        
        # 기본 정보
        parts.append(f"매장명: {store_data.get('store_name', '')}")
        parts.append(f"상권: {store_data['analysis'].get('trade_area', '')}")
        
        # 고객 특성
        analysis = store_data['analysis']
        parts.append(f"고객 페르소나: {analysis.get('persona', '')}")
        
        # 주요 세그먼트
        for seg in analysis.get('top_segments', []):
            parts.append(f"{seg['segment']} {seg['store_value']}")
        
        # 방문 유형
        for visit in analysis.get('visit_mix', []):
            parts.append(f"{visit['factor']} {visit['store_value']}")
        
        # 충성도
        loyalty = analysis.get('loyalty', {})
        parts.append(loyalty.get('summary', ''))
        
        # 인사이트
        for insight in analysis.get('insights', []):
            parts.append(insight)
        
        # 추천사항
        for rec in store_data.get('recommendations', []):
            parts.append(rec)
        
        return " ".join(parts)
    
    def generate_marketing_strategy_with_gemini(self, store_data, relevant_docs, trend_data=None):
        """Gemini 2.5 Flash를 사용하여 마케팅 전략 생성 (4개 섹션)"""
        
        print("=" * 80)
        print("🤖 Gemini 2.5 Flash로 마케팅 전략 생성 중...")
        print("=" * 80)
        print()
        
        # 프롬프트 구성
        prompt = self._build_gemini_prompt_v2(store_data, relevant_docs, trend_data)
        
        try:
            # Gemini API 호출
            response = self.gemini_model.generate_content(prompt)
            
            print("✅ 전략 생성 완료!\n")
            print("=" * 80)
            print("🎯 맞춤형 마케팅 전략")
            print("=" * 80)
            print()
            print(response.text)
            print()
            print("=" * 80)
            
            return response.text
            
        except Exception as e:
            print(f"❌ Gemini API 오류: {str(e)}")
            return None
    
    def _build_gemini_prompt_v2(self, store_data, relevant_docs, trend_data=None):
        """Gemini에게 전달할 프롬프트 생성 (간결한 4개 섹션 버전)"""
        
        analysis = store_data['analysis']
        
        # 매장 정보 요약
        store_summary = f"""
## 📍 매장 기본 정보
- **매장명**: {store_data['store_name']}
- **상권**: {analysis['trade_area']}
- **클러스터**: {analysis['cluster']}

## 👥 핵심 고객 특성
"""
        
        for seg in analysis['top_segments']:
            store_summary += f"- {seg['segment']}: {seg['store_value']} (평균 대비 {seg['gap']})\n"
        
        store_summary += "\n## 🚶 방문 유형\n"
        for visit in analysis['visit_mix']:
            store_summary += f"- {visit['factor']}: {visit['store_value']} (평균 대비 {visit['gap']})\n"
        
        store_summary += f"\n## 💎 충성도\n{analysis['loyalty']['summary']}\n"
        
        # 트렌드 정보 추가
        trend_section = ""
        if trend_data:
            trend_section = f"""
## 📈 업종 트렌드 (PyTrends)
- **키워드**: {trend_data['keyword']}
- **현재 추세**: {trend_data['current_trend']}
- **평균 관심도**: {trend_data['avg_interest']}/100
- **인기 지역**: {', '.join(trend_data['top_regions'][:3])}
- **급상승 검색어**: {', '.join(trend_data['rising_queries'][:3]) if trend_data['rising_queries'] else '없음'}
"""
        
        # 참고 문서 정보 (간결하게)
        docs_info = "\n## 📚 참고 데이터 소스\n\n"
        for doc in relevant_docs:
            docs_info += f"**[{doc['rank']}] {doc['file_name']}** (유사도 {doc['similarity']:.0f}%)\n"
            # 데이터 일부만 포함 (1500자로 제한)
            docs_info += f"```\n{doc['raw_data'][:1500]}...\n```\n\n"
        
        # 최종 프롬프트 (간결한 4개 섹션)
        prompt = f"""당신은 한국 외식업 마케팅 전문가입니다. 아래 정보를 바탕으로 **실행 가능하고 간결한** 마케팅 전략을 작성하세요.

{store_summary}

{trend_section}

{docs_info}

---

## 📝 요청사항

다음 **4개 섹션**으로 마케팅 전략을 작성하되, **각 섹션은 간결하게(3-5개 bullet points)** 작성하세요:

### 📊 섹션 1: RAG 문서 기반 인사이트
- 참고 문서에서 발견한 핵심 인사이트 3가지
- 해당 매장에 적용 가능한 시사점
- **형식**: 문서명 명시 + 인사이트 + 적용 방법

### 🎯 섹션 2: 매장 특성 기반 전략
- 모델링 데이터(고객층, 방문유형, 충성도)를 활용한 맞춤 전략 3가지
- RAG 문서의 추가 인사이트 결합
- **형식**: 데이터 근거 + 전략 + 실행 방법

### 📱 섹션 3: 우선순위 채널 전략
- 상위 3개 마케팅 채널만 선정 (예: Instagram, 카카오톡, 배달앱)
- 각 채널별 구체적 실행 아이디어 2-3개
- **형식**: 채널명 + 타겟 + 액션

### 🚀 섹션 4: 마케팅 채널 & 홍보안
- 즉시 실행 가능한 구체적인 홍보 캠페인 3-4개
- 각 캠페인의 실행 방법과 예상 효과를 명시
- 매장의 강점(재방문율, 특정 고객층 등)을 활용한 차별화 전략 포함

---

## ⚠️ 작성 가이드라인
1. **간결성**: 각 섹션은 스크롤 없이 한 화면에 보이도록
2. **구체성**: "소셜미디어 활용" ❌ → "인스타 릴스 3개/주, 해시태그 #답십리카페" ✅
3. **실행성**: 담당자가 바로 실행할 수 있는 수준
4. **근거 제시**: 각 전략마다 데이터/문서 출처 간단히 명시
5. **이모지 활용**: 가독성을 위해 적절히 사용

**총 분량**: A4 1장 이내 (약 800-1200자)
"""
        
        return prompt


def main():
    """메인 실행 함수"""
    
    # 0. Gemini API 키 설정
    GEMINI_API_KEY = "여기에 내 키값 입력"
    
    # API 키가 설정되지 않았다면 환경변수에서 가져오기 시도
    if GEMINI_API_KEY == "여기에_당신의_Gemini_API_키를_입력하세요":
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("⚠️  Gemini API 키를 설정해주세요!")
            print("방법 1: 코드에서 GEMINI_API_KEY 변수에 직접 입력")
            print("방법 2: 환경변수 GEMINI_API_KEY 설정")
            print("\nAPI 키 발급: https://makersuite.google.com/app/apikey")
            return
    
    # 1. RAG 시스템 초기화
    data_folder = r"C:\Temp\data\rag데이터_병진님"
    
    try:
        rag = RAGMarketingSystem(data_folder, GEMINI_API_KEY)
    except Exception as e:
        print(f"❌ 시스템 초기화 오류: {str(e)}")
        return
    
    # 2. 문서 로드 및 임베딩 생성
    try:
        rag.load_documents()
    except Exception as e:
        print(f"❌ 문서 로드 오류: {str(e)}")
        return
    
    if len(rag.documents) == 0:
        print("\n" + "="*80)
        print("⚠️  문서를 로드할 수 없습니다!")
        print("="*80)
        print("\n해결 방법:")
        print("1. openpyxl 설치:")
        print("   pip install openpyxl")
        print("\n2. PyTrends 설치:")
        print("   pip install pytrends")
        print("\n3. 가상환경을 사용 중이라면 가상환경에 설치:")
        print("   (venv) pip install openpyxl pytrends")
        print("\n4. 데이터 폴더 경로 확인:")
        print(f"   현재 경로: {data_folder}")
        print(f"   폴더 존재 여부: {Path(data_folder).exists()}")
        return
    
    if not rag.build_embeddings():
        return
    
    # 3. 매장 데이터
    store_data = {
        "store_code": "003AC99735",
        "store_name": "메가커피 답십리점",
        "status": "재방문 고객층이 매우 탄탄해요",
        "industry_keyword": "카페",
        "analysis": {
            "summary": "핵심 고객은 10-20대 남성입니다",
            "persona": "핵심 고객은 10-20대 남성입니다 (클러스터 대비 +6.11pp)",
            "cluster": 3,
            "top_segments": [
                {"segment": "10-20대 남성", "store_value": "14.22%", "gap": "+6.11pp"},
                {"segment": "30대 남성", "store_value": "17.40%", "gap": "+3.52pp"}
            ],
            "visit_mix": [
                {"factor": "유동 고객 비중", "store_value": "53.05%", "gap": "+8.22pp"},
                {"factor": "직장 고객 비중", "store_value": "9.81%", "gap": "-5.52pp"},
                {"factor": "주거 고객 비중", "store_value": "37.14%", "gap": "-2.70pp"}
            ],
            "loyalty": {
                "summary": "재방문 고객 비중이 클러스터 평균보다 +4.55pp 높습니다",
                "metrics": [
                    {"metric": "재방문 고객 비율", "store_value": "36.99%", "gap": "+4.55pp"},
                    {"metric": "신규 고객 비율", "store_value": "4.70%", "gap": "-1.48pp"},
                    {"metric": "충성 고객 지수", "store_value": "32.29점", "gap": "+6.18점"}
                ]
            },
            "insights": [
                "10-20대 남성 비중이 클러스터 평균 대비 +6.11pp입니다.",
                "유동 고객 비중이 클러스터 평균보다 +8.22pp로 높습니다.",
                "재방문 고객 비율이 클러스터 평균보다 +4.55pp로 높습니다."
            ],
            "trade_area": "답십리"
        },
        "recommendations": [
            "10-20대 남성 고객 유입을 늘리세요.",
            "유동 고객을 위한 빠른 픽업을 강조하세요.",
            "충성 고객을 위한 프리미엄 멤버십을 확장하세요."
        ]
    }
    
    # 4. PyTrends로 업종 트렌드 분석
    try:
        trend_data = rag.get_industry_trends(store_data.get('industry_keyword', '카페'))
    except Exception as e:
        print(f"⚠️  트렌드 분석 오류 (계속 진행): {str(e)}")
        trend_data = None
    
    # 5. 관련 문서 검색
    try:
        relevant_docs = rag.search_relevant_documents(store_data, top_k=2)
    except Exception as e:
        print(f"❌ 문서 검색 오류: {str(e)}")
        return
    
    if len(relevant_docs) == 0:
        print("❌ 관련 문서를 찾을 수 없습니다.")
        return
    
    # 6. Gemini로 마케팅 전략 생성 (트렌드 데이터 포함)
    try:
        strategy = rag.generate_marketing_strategy_with_gemini(store_data, relevant_docs, trend_data)
    except Exception as e:
        print(f"❌ 전략 생성 오류: {str(e)}")
        return
    
    # 7. 결과를 파일로 저장 (옵션)
    if strategy:
        try:
            output_file = "marketing_strategy_output.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("🎯 맞춤형 마케팅 전략\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"매장: {store_data['store_name']}\n")
                f.write(f"생성일: {pd.Timestamp.now()}\n\n")
                
                # 트렌드 정보
                if trend_data:
                    f.write("📈 업종 트렌드:\n")
                    f.write(f"  - 키워드: {trend_data['keyword']}\n")
                    f.write(f"  - 추세: {trend_data['current_trend']}\n")
                    f.write(f"  - 관심도: {trend_data['avg_interest']}/100\n\n")
                
                # 참고 문서
                f.write("참고 문서:\n")
                for doc in relevant_docs:
                    f.write(f"  - [{doc['similarity']:.1f}%] {doc['file_name']}\n")
                f.write("\n" + "=" * 80 + "\n\n")
                f.write(strategy)
            
            print(f"\n📄 결과가 '{output_file}' 파일로 저장되었습니다.")
        except Exception as e:
            print(f"⚠️  파일 저장 오류: {str(e)}")


if __name__ == "__main__":
    main()