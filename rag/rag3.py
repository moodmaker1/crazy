"""
RAG3: 요식업 가맹점 문제 진단 및 해결 컨설팅 시스템

사용법:
1. 아래 GEMINI_API_KEY와 data_folder 경로 설정
2. python rag3.py 실행
3. consulting_response.txt 파일 확인
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
    """LLM 기반 요식업 컨설팅 시스템"""
    
    # 12개 문제 유형 정의
    PROBLEM_TYPES = {
        "재방문율 저조": "충성 고객 확보를 위한 쿠폰/스탬프 제도 도입",
        "신규고객 유입 부족": "신규 고객 타겟 배달앱 할인 또는 첫 방문 이벤트",
        "객단가 하락": "가치 상승을 위한 세트 메뉴 개발 또는 메뉴 고급화",
        "충성도 하락": "단골 고객 대상 특별 혜택 또는 재방문 감사 프로모션",
        "매출 변동성 심화": "안정적 매출 확보를 위한 점심 구독 서비스 또는 정기 이벤트 기획",
        "고객 이탈 심화": "고객 피드백 채널 마련 및 서비스 만족도 개선 캠페인",
        "상권 내 경쟁 심화": "경쟁점과 차별화되는 우리 가게만의 시그니처 메뉴 개발",
        "유동고객 의존도 심화": "주변 거주/직장인 대상 로컬 마케팅 강화",
        "배달 효율 저하": "배달 주문 전용 메뉴 개발 또는 최소주문금액 조정",
        "특정고객 쏠림 심화": "새로운 고객층 유입을 위한 타겟 프로모션 (예: 1020세대 이벤트)",
        "매출 규모 감소": "매출 증대를 위한 피크타임 세트 메뉴 출시 또는 배달 활성화",
        "고객 방문 빈도 감소": "재방문 유도를 위한 마일리지 제도 또는 요일별 이벤트"
    }
    
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
                
                # 텍스트 변환
                content_parts = [file_name]
                content_parts.append(" ".join([str(col) for col in df.columns if pd.notna(col)]))
                
                for idx, row in df.head(30).iterrows():
                    row_text = " ".join([str(val) for val in row if pd.notna(val) and str(val).strip()])
                    if row_text:
                        content_parts.append(row_text)
                
                content = " ".join(content_parts)
                
                self.documents.append({
                    'file_name': file_name,
                    'content': content,
                    'raw_data': df.to_string()[:1500]
                })
                
                print(f"  ✓ {file_name}")
                
            except Exception as e:
                print(f"  ✗ {file_path.name}: {str(e)}")
        
        print(f"\n✅ 총 {len(self.documents)}개 문서 로드 완료!\n")
    
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
    
    def search_documents(self, problem_name, industry, store_name, market_context, top_k=2):
        """RAG 문서 검색"""
        
        if len(self.documents) == 0 or self.doc_embeddings is None:
            return []
        
        search_query = f"{problem_name} {industry} {store_name} {market_context} 외식 소비자 행태 마케팅"
        
        print(f"🔍 RAG 문서 검색 중...")
        print(f"  문제: {problem_name}")
        print(f"  업종: {industry}")
        print(f"  상권: {market_context}")
        
        query_embedding = self.model.encode([search_query])
        similarities = cosine_similarity(query_embedding, self.doc_embeddings)[0]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        print(f"\n📊 관련도 높은 상위 {top_k}개 문서:\n")
        
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
        """컨설팅 답변 생성"""
        
        print("=" * 80)
        print("🎯 컨설팅 답변 생성 중...")
        print("=" * 80)
        print()
        
        # 프롬프트 구성
        top_issue = modeling_data['analysis']['diagnosis_top3'][0]
        problem_name = top_issue['약점']
        severity = top_issue['심각도']
        
        # 기본 솔루션 가져오기
        base_solution = self.PROBLEM_TYPES.get(problem_name, "맞춤 전략 개발 필요")
        
        # 모든 문제 정리
        all_issues = ""
        for idx, issue in enumerate(modeling_data['analysis']['diagnosis_top3'], 1):
            base_sol = self.PROBLEM_TYPES.get(issue['약점'], "맞춤 전략 필요")
            all_issues += f"{idx}. **{issue['약점']}** (심각도 {issue['심각도']}/100)\n"
            all_issues += f"   → 기본 솔루션: {base_sol}\n\n"
        
        docs_info = ""
        for doc in relevant_docs:
            docs_info += f"**[{doc['rank']}] {doc['file_name']}** (유사도 {doc['similarity']:.0f}%)\n"
            docs_info += f"```\n{doc['raw_data']}\n```\n\n"
        
        industry = modeling_data.get('industry', '요식업')
        market_context = modeling_data['analysis']['market_type_context']
        
        prompt = f"""당신은 요식업 마케팅 전문가입니다. 
        
매장의 **가장 큰 문제점**과 이를 해결할 **구체적이고 실행 가능한 마케팅 아이디어**를 RAG 데이터 근거와 함께 제시하세요.

## 📍 매장 정보
- **매장명**: {modeling_data['store_name']}
- **업종**: {industry}
- **상권 특성**: {market_context}

## 🚨 진단 결과 (모델링 분석)
{all_issues}

## 📚 RAG 참고 문서 (외식업 데이터)
{docs_info}

---

## ✅ 답변 형식 (반드시 준수)

# {modeling_data['store_name']} 마케팅 컨설팅 리포트

## 🎯 1. 핵심 문제 진단

### 최우선 해결 과제: **{problem_name}** (심각도 {severity}/100)

**[문제 상황]**
- 현재 상황: (상권 특성과 연계하여 1-2문장)
- 발생 원인: (RAG 데이터 근거 1-2문장)

**[RAG 데이터 근거]**
- **[문서1]**: (핵심 데이터 인용, 수치 포함)
- **[문서2]**: (추가 근거 데이터, 트렌드)

---

## 💡 2. 맞춤 마케팅 전략 (실행 중심)

### 전략 1: [구체적 전략명]
- **목표**: {problem_name} 해결을 위한 핵심 목표
- **실행 방법**: 
  1. (구체적 실행 단계 1 - 누가, 언제, 무엇을)
  2. (구체적 실행 단계 2)
  3. (구체적 실행 단계 3)
- **예상 효과**: (수치 목표 포함)
- **RAG 근거**: [문서명]의 (데이터 인용)

### 전략 2: [보조 전략명]
- **목표**: 2순위 문제 해결
- **실행 방법**: 
  1. (실행 단계)
  2. (실행 단계)
- **예상 효과**: (측정 가능한 목표)

---

## 🚀 3. 즉시 실행 캠페인 (2개)

### 캠페인 1: "💪 [캠페인명]!" 
- **실행 기간**: (예: 1개월, 2주 등)
- **타겟**: (구체적 고객층)
- **실행 내용**: 
  - (구체적 방법 1)
  - (구체적 방법 2)
  - (홍보 채널)
- **예상 효과**: {problem_name} 개선 목표 (수치)

### 캠페인 2: "📸 [캠페인명]!"
- **실행 기간**: 
- **타겟**: 
- **실행 내용**: 
  - (방법)
  - (방법)
- **예상 효과**: 

---

## 📊 4. 기대 효과 요약
- **{problem_name}** → (개선 목표치, 예: 20% 향상)
- 2순위 문제 → (개선 목표)
- 전체 매출 영향 → (예상 수치)

**작성 원칙**: 
1. **문제 진단**을 가장 앞에 명확히 제시
2. 모든 전략은 **RAG 문서 데이터를 근거**로 제시
3. **{industry} 특성**을 반영한 실행 방안
4. **측정 가능한 목표** 제시
5. 이모지 활용하여 가독성 향상 (💰📈🎯📊)
"""
        
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
    
    def save_response(self, modeling_data, relevant_docs, response, output_file="consulting_response.txt"):
        """컨설팅 답변 저장"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("📋 요식업 가맹점 마케팅 컨설팅 리포트\n")
                f.write("=" * 80 + "\n\n")
                
                # 매장 정보
                f.write(f"📍 매장명: {modeling_data['store_name']}\n")
                f.write(f"📍 업종: {modeling_data.get('industry', '요식업')}\n")
                f.write(f"📍 상권: {modeling_data['analysis']['market_type_context']}\n")
                f.write(f"📅 생성일: {pd.Timestamp.now().strftime('%Y년 %m월 %d일 %H:%M')}\n\n")
                
                # 진단 결과
                f.write("🚨 진단 결과 (12개 문제 유형 분석)\n")
                f.write("-" * 80 + "\n")
                for idx, issue in enumerate(modeling_data['analysis']['diagnosis_top3'], 1):
                    problem = issue['약점']
                    severity = issue['심각도']
                    solution = self.PROBLEM_TYPES.get(problem, "맞춤 전략 필요")
                    
                    if idx == 1:
                        f.write(f"\n🔴 {idx}순위 (최우선): {problem}\n")
                    else:
                        f.write(f"\n🟠 {idx}순위: {problem}\n")
                    f.write(f"   - 심각도: {severity}/100\n")
                    f.write(f"   - 기본 솔루션: {solution}\n")
                
                # RAG 참고 문서
                f.write("\n\n📚 참고한 외식업 데이터\n")
                f.write("-" * 80 + "\n")
                for doc in relevant_docs:
                    f.write(f"  [{doc['similarity']:.1f}%] {doc['file_name']}\n")
                
                f.write("\n\n" + "=" * 80 + "\n\n")
                
                # AI 생성 컨설팅 답변
                f.write(response)
            
            print(f"\n📄 컨설팅 답변이 '{output_file}' 파일로 저장되었습니다.")
            return True
            
        except Exception as e:
            print(f"⚠️  파일 저장 오류: {str(e)}")
            return False


def main():
    """메인 실행 함수"""
    
    # ========================================
    # 설정: 여기만 수정하세요!
    # ========================================
    
    # Gemini API 키 (필수)
    GEMINI_API_KEY = "AIzaSyDTd6l7sR7LakKLHe9-6oN2DamBlBWyzAc"
    
    # RAG 데이터 폴더 경로
    data_folder = r"C:\Temp\data\rag데이터_병진님"
    
    # 매장 정보 (분석할 매장 데이터)
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
    
    # ========================================
    # 실행 (아래 코드는 수정 안 해도 됨)
    # ========================================
    
    print("\n" + "=" * 80)
    print("🏪 RAG3 컨설팅 시스템 시작")
    print("=" * 80)
    
    # 1. 시스템 초기화
    try:
        rag = RAG3ConsultingSystem(data_folder, GEMINI_API_KEY)
    except Exception as e:
        print(f"❌ 초기화 오류: {str(e)}")
        return
    
    # 2. 문서 로드
    rag.load_documents()
    
    if len(rag.documents) == 0:
        print("\n⚠️  문서를 로드할 수 없습니다!")
        print("해결 방법: pip install openpyxl")
        return
    
    # 3. 임베딩 생성
    if not rag.build_embeddings():
        return
    
    # 4. 매장 정보 및 진단 결과 출력
    print("=" * 80)
    print("🏪 매장 정보")
    print("=" * 80)
    print(f"매장명: {modeling_data['store_name']}")
    print(f"업종: {modeling_data['industry']}")
    print(f"상권 특성: {modeling_data['analysis']['market_type_context']}")
    
    print(f"\n📊 진단 결과 (12개 문제 유형 중 발견된 문제):")
    for idx, issue in enumerate(modeling_data['analysis']['diagnosis_top3'], 1):
        problem = issue['약점']
        severity = issue['심각도']
        solution = RAG3ConsultingSystem.PROBLEM_TYPES.get(problem, "맞춤 전략 필요")
        
        if idx == 1:
            print(f"\n  🔴 {idx}순위: {problem} (심각도 {severity}/100) ⭐ 최우선")
        else:
            print(f"  🟠 {idx}순위: {problem} (심각도 {severity}/100)")
        print(f"      → 기본 솔루션: {solution}")
    
    print("\n" + "=" * 80 + "\n")
    
    # 5. RAG 문서 검색
    top_issue = modeling_data['analysis']['diagnosis_top3'][0]
    
    relevant_docs = rag.search_documents(
        problem_name=top_issue['약점'],
        industry=modeling_data['industry'],
        store_name=modeling_data['store_name'],
        market_context=modeling_data['analysis']['market_type_context'],
        top_k=2
    )
    
    if len(relevant_docs) == 0:
        print("❌ 관련 문서를 찾을 수 없습니다.")
        return
    
    # 6. 컨설팅 답변 생성
    response = rag.generate_consulting_response(modeling_data, relevant_docs)
    
    if not response:
        print("❌ 컨설팅 답변 생성에 실패했습니다.")
        return
    
    # 7. 결과 저장
    rag.save_response(modeling_data, relevant_docs, response)
    
    print("\n" + "=" * 80)
    print("✅ 모든 작업이 완료되었습니다!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
