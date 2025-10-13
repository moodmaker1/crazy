"""
RAG3: 요식업 가맹점 문제 진단 및 해결 컨설팅 시스템 (웹페이지용)
- LLM이 모델링 결과와 RAG 문서를 분석하여 맞춤형 솔루션 생성
- 웹페이지에 표시할 간결한 답변 형식
- 3개 섹션: 인사이트 2개 + 전략 2개 + 솔루션 2개
"""

import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
import warnings
import google.generativeai as genai

warnings.filterwarnings('ignore')


class RAG3ConsultingSystem:
    """LLM 기반 요식업 컨설팅 시스템 (웹페이지용)"""
    
    def __init__(self, data_folder_path, gemini_api_key):
        self.data_folder = Path(data_folder_path)
        
        print("🔄 요식업 컨설팅 시스템 초기화 중...")
        self.model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        self.documents = []
        self.doc_embeddings = None
    
    def load_documents(self):
        """RAG 문서 로딩"""
        print("\n📚 RAG 문서 데이터베이스 구축 중...")
        
        excel_files = list(self.data_folder.glob('*.xlsx'))
        
        for file_path in excel_files:
            try:
                df = pd.read_excel(file_path, sheet_name=0)
                file_name = file_path.stem
                content = self._extract_content_from_df(df, file_name)
                
                self.documents.append({
                    'file_name': file_name,
                    'content': content,
                    'raw_data': df.to_string()[:3000]
                })
                
                print(f"  ✓ {file_name}")
                
            except Exception as e:
                print(f"  ✗ {file_path.name}: {str(e)}")
        
        print(f"\n✅ 총 {len(self.documents)}개 문서 로드 완료!\n")
        
    def _extract_content_from_df(self, df, file_name):
        """데이터프레임 → 텍스트 변환"""
        content_parts = [file_name]
        content_parts.append(" ".join([str(col) for col in df.columns if pd.notna(col)]))
        
        for idx, row in df.head(30).iterrows():
            row_text = " ".join([str(val) for val in row if pd.notna(val) and str(val).strip()])
            if row_text:
                content_parts.append(row_text)
        
        return " ".join(content_parts)
    
    def build_embeddings(self):
        """문서 임베딩 생성"""
        if len(self.documents) == 0:
            print("❌ 문서가 없습니다!")
            return False
        
        print("🔄 문서 임베딩 생성 중...")
        contents = [doc['content'] for doc in self.documents]
        self.doc_embeddings = self.model.encode(contents, show_progress_bar=True)
        print("✅ 임베딩 생성 완료!\n")
        return True
    
    def search_documents(self, problem_name, industry, store_name, market_context, top_k=3):
        """
        LLM 기반 유연한 RAG 문서 검색
        - 문제명 + 업종 + 매장명 + 상권 특성으로 검색 쿼리 자동 생성
        """
        
        if len(self.documents) == 0 or self.doc_embeddings is None:
            return []
        
        # 검색 쿼리 생성 (모든 컨텍스트 활용)
        search_query = f"{problem_name} {industry} {store_name} {market_context} 외식 소비자 행태 마케팅"
        
        print(f"🔍 RAG 문서 검색 중...")
        print(f"  문제: {problem_name}")
        print(f"  업종: {industry}")
        print(f"  상권: {market_context}")
        print(f"  검색 쿼리: {search_query}\n")
        
        # 임베딩 검색
        query_embedding = self.model.encode([search_query])
        similarities = cosine_similarity(query_embedding, self.doc_embeddings)[0]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        print(f"📊 관련도 높은 상위 {top_k}개 문서:\n")
        
        for rank, idx in enumerate(top_indices, 1):
            doc = self.documents[idx]
            similarity_score = similarities[idx] * 100
            
            results.append({
                'rank': rank,
                'file_name': doc['file_name'],
                'similarity': similarity_score,
                'raw_data': doc['raw_data']
            })
            
            print(f"  {rank}. [{similarity_score:.1f}%] {doc['file_name']}")
        
        print()
        return results
    
    def generate_consulting_response(self, modeling_data, relevant_docs):
        """
        웹페이지용 컨설팅 답변 생성
        - 간결하고 읽기 쉬운 형식
        - LLM이 모델링 결과와 RAG 문서를 분석하여 맞춤형 답변 생성
        """
        
        print("=" * 80)
        print("🎯 웹페이지용 컨설팅 답변 생성 중...")
        print("=" * 80)
        print()
        
        # 프롬프트 생성
        prompt = self._build_prompt(modeling_data, relevant_docs)
        
        try:
            response = self.gemini_model.generate_content(prompt)
            
            print("✅ 컨설팅 답변 생성 완료!\n")
            print("=" * 80)
            print("📋 컨설팅 답변")
            print("=" * 80)
            print()
            print(response.text)
            print()
            print("=" * 80)
            
            return response.text
            
        except Exception as e:
            print(f"❌ Gemini API 오류: {str(e)}")
            return None
    
    def _build_prompt(self, modeling_data, relevant_docs):
        """
        웹페이지용 프롬프트 생성
        - 간결한 답변 형식
        """
        
        # 최우선 문제
        top_issue = modeling_data['analysis']['diagnosis_top3'][0]
        problem_name = top_issue['약점']
        severity = top_issue['심각도']
        
        # 기타 문제들
        other_issues = ""
        for idx, issue in enumerate(modeling_data['analysis']['diagnosis_top3'][1:], 2):
            other_issues += f"{idx}순위: {issue['약점']} (심각도 {issue['심각도']})\n"
        
        # RAG 문서 정보 (속도 개선: 1000자로 축소)
        docs_info = ""
        for doc in relevant_docs:
            docs_info += f"\n**[문서 {doc['rank']}] {doc['file_name']}** (관련도 {doc['similarity']:.0f}%)\n"
            docs_info += f"```\n{doc['raw_data'][:1000]}\n```\n"
        
        # 추천사항
        recommendations = "\n".join([f"- {rec}" for rec in modeling_data.get('recommendations', [])])
        
        industry = modeling_data.get('industry', '요식업')
        market_context = modeling_data['analysis']['market_type_context']
        
        prompt = f"""당신은 요식업 전문 경영 컨설턴트입니다. 매장의 문제를 진단하고 실행 가능한 해결책을 제시합니다.

## 📍 매장 정보
- **매장명**: {modeling_data['store_name']}
- **업종**: {industry}
- **상권 특성**: {market_context}

## 🚨 모델링 진단 결과

### 최우선 해결 과제
**문제**: {problem_name}
**심각도**: {severity}/100

### 기타 발견된 문제
{other_issues}

### 모델링 추천사항
{recommendations}

## 📚 RAG 참고 문서 (외식업 빅데이터)
{docs_info}

---

## 📝 답변 작성 지시사항

웹페이지에 표시할 간결한 컨설팅 답변을 작성하세요.

### 📊 섹션 1: 시장 인사이트 (2개)

RAG 문서에서 발견한 핵심 인사이트 2가지를 분석하세요.

**작성 형식**:
- 💡 **인사이트 1**: [핵심 트렌드]
  * 데이터: [문서명]에서 "..." (간단히)
  * 적용 방법: 1-2문장으로 우리 매장에 어떻게 적용할지

- 💡 **인사이트 2**: [소비자 행태]
  * 데이터: [문서명]에서 "..."
  * 적용 방법: 1-2문장

---

### 🎯 섹션 2: 매장 맞춤 전략 (2개)

상권 특성({market_context})과 업종({industry})을 반영한 차별화 전략을 제시하세요.

**작성 형식**:
- 🎯 **전략 1**: [전략명]
  * 이유: 1문장으로 왜 필요한지
  * 방법: 2-3문장으로 구체적 실행 방법
  * 효과: ~할 것으로 예상됩니다 (1문장)

- 🎯 **전략 2**: [전략명]
  * 이유: 1문장
  * 방법: 2-3문장
  * 효과: ~에 도움이 될 것입니다 (1문장)

---

### 🔧 섹션 3: 최우선 문제 해결 전략 ⭐

**문제**: {problem_name} (심각도 {severity}/100)

#### 원인 분석
모델링 결과와 상권 특성을 바탕으로 이 문제가 발생한 원인을 2-3문장으로 간결하게 분석하세요.

#### 실행 솔루션 (2개)

💡 **솔루션 1**: [제목]
  * 실행 방법: 
    - 3-4문장으로 구체적으로 설명
  * 예산: 약 X만원
  * 기간: X주
  * RAG 근거: [문서명]의 데이터를 인용하여 근거 제시
  * 예상 효과: ~하는 데 도움이 될 것으로 예상됩니다 (1-2문장)

💡 **솔루션 2**: [제목]
  * 실행 방법:
    - 3-4문장으로 구체적으로 설명
  * 예산: 약 X만원
  * 기간: X주
  * RAG 근거: [문서명]의 데이터를 인용
  * 예상 효과: ~할 것으로 기대됩니다 (1-2문장)

---

## ⚠️ 작성 원칙
1. **웹페이지용 간결한 답변**: 과도하게 길지 않게
2. **전문적이지만 읽기 쉽게**: 친근한 톤
3. **RAG 데이터 근거 제시**: 반드시 문서명과 데이터 인용
4. **실행 가능성**: 구체적이고 현실적인 방법 제시
5. **{industry} 특성 반영**: 업종에 맞는 맞춤형 솔루션

전문 컨설턴트답게 실용적이고 구체적인 답변을 작성하세요!
"""
        
        return prompt


def main():
    """메인 실행 함수"""
    
    # Gemini API 키
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "여기에_API_키_입력")
    
    if GEMINI_API_KEY == "여기에_API_키_입력":
        print("⚠️  Gemini API 키를 설정해주세요!")
        print("export GEMINI_API_KEY='your-api-key'")
        return
    
    # 1. RAG 시스템 초기화
    data_folder = r"C:\Temp\data\rag데이터_병진님"
    
    try:
        rag = RAG3ConsultingSystem(data_folder, GEMINI_API_KEY)
    except Exception as e:
        print(f"❌ 초기화 오류: {str(e)}")
        return
    
    # 2. 문서 로드 및 임베딩 생성
    try:
        rag.load_documents()
    except Exception as e:
        print(f"❌ 문서 로드 오류: {str(e)}")
        print("해결 방법: pip install openpyxl")
        return
    
    if len(rag.documents) == 0:
        print("\n⚠️  문서를 로드할 수 없습니다!")
        return
    
    if not rag.build_embeddings():
        return
    
    # 3. 샘플 데이터: 성동구 일식당
    modeling_data = {
        "store_code": "00803E9174",
        "store_name": "우동명가 왕십리점",
        "industry": "일식당",
        "status": "진단 완료",
        "analysis": {
            "type": "시계열 기반 하이브리드 진단",
            "market_type_context": "우동밀집형 상권 (경쟁 매장 12개)",
            "diagnosis_top3": [
                {
                    "약점": "상권 내 경쟁 심화",
                    "심각도": 92
                },
                {
                    "약점": "객단가 하락",
                    "심각도": 82
                },
                {
                    "약점": "매출 규모 감소",
                    "심각도": 62
                }
            ]
        },
        "recommendations": [
            "경쟁점과 차별화되는 우리 가게만의 시그니처 메뉴 개발",
            "가치 상승을 위한 세트 메뉴 개발 또는 메뉴 고급화",
            "매출 증대를 위한 피크타임 세트 메뉴 출시 또는 배달 활성화"
        ]
    }
    
    print("\n" + "=" * 80)
    print("🏪 매장 정보")
    print("=" * 80)
    print(f"매장명: {modeling_data['store_name']}")
    print(f"업종: {modeling_data['industry']}")
    print(f"상권 특성: {modeling_data['analysis']['market_type_context']}")
    print(f"\n최우선 문제: {modeling_data['analysis']['diagnosis_top3'][0]['약점']}")
    print(f"심각도: {modeling_data['analysis']['diagnosis_top3'][0]['심각도']}/100")
    print("=" * 80)
    
    # 4. RAG 문서 검색 (동적)
    top_issue = modeling_data['analysis']['diagnosis_top3'][0]
    
    relevant_docs = rag.search_documents(
        problem_name=top_issue['약점'],
        industry=modeling_data['industry'],
        store_name=modeling_data['store_name'],
        market_context=modeling_data['analysis']['market_type_context'],
        top_k=3
    )
    
    if len(relevant_docs) == 0:
        print("❌ 관련 문서를 찾을 수 없습니다.")
        return
    
    # 5. 웹페이지용 컨설팅 답변 생성
    response = rag.generate_consulting_response(modeling_data, relevant_docs)
    
    # 6. 결과 저장
    if response:
        try:
            output_file = "consulting_response.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("📋 컨설팅 답변\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"매장명: {modeling_data['store_name']}\n")
                f.write(f"업종: {modeling_data['industry']}\n")
                f.write(f"생성일: {pd.Timestamp.now()}\n\n")
                f.write(f"최우선 해결 과제: {top_issue['약점']} (심각도 {top_issue['심각도']}/100)\n\n")
                f.write("참고 문서:\n")
                for doc in relevant_docs:
                    f.write(f"  - [{doc['similarity']:.1f}%] {doc['file_name']}\n")
                f.write("\n" + "=" * 80 + "\n\n")
                f.write(response)
            
            print(f"\n📄 컨설팅 답변이 '{output_file}' 파일로 저장되었습니다.")
        except Exception as e:
            print(f"⚠️  파일 저장 오류: {str(e)}")


if __name__ == "__main__":
    main()