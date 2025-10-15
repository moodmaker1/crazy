# 키워드 분석 도구
Gemini AI와 네이버 DataLab을 사용해서 업종별 인기 키워드를 찾아주는 프로그램입니다.
## 뭘 하는 프로그램인가요?
1. Gemini AI가 업종 관련 키워드 30개를 만듭니다
2. 네이버 DataLab에서 각 키워드의 실제 검색량을 확인합니다
3. 검색량이 높은 순서대로 10개를 선정합니다
4. 결과를 JSON 파일로 저장합니다
## 필요한 것
- Python 3.7 이상
- Gemini API 키
- 네이버 DataLab API 키
## 설치 방법
### 1단계: 라이브러리 설치
터미널에서 실행:
```bash
pip install google-generativeai python-dotenv
```
### 2단계: API 키 받기
#### Gemini API 키 받기
1. https://aistudio.google.com/app/apikey 접속
2. "Create API Key" 클릭
3. 키 복사
#### 네이버 API 키 받기
1. https://developers.naver.com 접속 후 로그인
2. "Application" 메뉴에서 "애플리케이션 등록" 클릭
3. 다음 항목 체크 (중요):
   - 검색
   - DataLab(검색어 트렌드)
4. 환경 설정:
   - 서비스 URL: `http://localhost` 입력
5. 등록 완료 후 Client ID와 Client Secret 복사
### 3단계: .env 파일 만들기
프로젝트 폴더에 `.env` 파일을 만들고 다음 내용을 입력:
```env
GOOGLE_API_KEY=여기에_Gemini_키_붙여넣기
NAVER_CLIENT_ID=여기에_네이버_ID_붙여넣기
NAVER_CLIENT_SECRET=여기에_네이버_Secret_붙여넣기
```
실제 예시:
```env
GOOGLE_API_KEY=AIzaSyABcD1234567890
NAVER_CLIENT_ID=AbCdEfGhIj
NAVER_CLIENT_SECRET=xyzabcdef123
```
## 실행 방법
터미널에서:
```bash
python test5naver.py
```
## 업종 바꾸는 법
`test5naver.py` 파일 맨 아래 부분을 수정:
```python
if __name__ == "__main__":
    industry = "중식 딤섬"  # 이 부분을 원하는 업종으로 변경
```
예시:
```python
industry = "일식 라멘"
industry = "베이커리"
industry = "카페"
```
## 동작 과정
```
1. Gemini AI가 키워드 30개 생성
   예: "샤오롱바오 맛집", "새우 딤섬", "하가우 딤섬" 등
2. 네이버 DataLab에 검색량 요청 (5개씩 6번)
   - 배치 1: 키워드 1~5
   - 배치 2: 키워드 6~10
   - ...
   - 배치 6: 키워드 26~30
3. 검색량 높은 순으로 정렬
4. 상위 10개 선정 및 저장
```
## 결과 파일
실행하면 다음과 같은 JSON 파일이 자동으로 생성됩니다:
파일명 예시: `keyword_analysis_naver_20251014_175216.json`
내용 예시:
```json
{
  "업종": "중식 딤섬",
  "분석_기간": "최근 3개월",
  "총_분석_키워드": 30,
  "검색량_확인": 13,
  "최종_키워드_TOP10": [
    {
      "keyword": "새우 딤섬",
      "평균검색비율": 81.32,
      "최고검색비율": 99.74,
      "최근검색비율": 37.29
    }
  ]
}
```
## API 사용 횟수
### 1회 실행 시
- Gemini API: 1번 사용
- 네이버 API: 6번 사용
### 무료 사용 가능 횟수
- **네이버 DataLab**: 하루 1,000회까지 무료
  - 1회 실행 = 6회 사용
  - 하루 최대 166번 실행 가능
- **Gemini API**: 하루 1,500회까지 무료
## 자주 발생하는 문제
### "GOOGLE_API_KEY가 없습니다" 에러
- `.env` 파일이 `test5naver.py`와 같은 폴더에 있는지 확인
- API 키가 제대로 입력되었는지 확인
### "네이버 API 키가 없습니다" 에러
- `.env` 파일에 네이버 키가 제대로 입력되었는지 확인
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 이름이 정확한지 확인
### "API 오류 (Error Code: 401)"
- 네이버 API 키가 틀렸을 가능성
- 네이버 개발자센터에서 키를 다시 확인
### "API 오류 (Error Code: 024)"
- DataLab API를 신청하지 않았을 가능성
- 네이버 개발자센터에서 애플리케이션 설정 확인
### "검색량 데이터를 가져올 수 없습니다"
- 30개 키워드의 검색량이 모두 너무 적을 경우 발생
- 더 일반적인 업종명으로 다시 시도
### 30개 중 일부만 데이터가 나옵니다
- 정상입니다
- 네이버는 검색량이 매우 적은 키워드는 데이터를 주지 않습니다
- 예: 30개 중 13개만 데이터 수집되는 경우도 있음
## 파일 구조
```
프로젝트 폴더/
├── test5naver.py                   # 실행 파일
├── .env                            # API 키 저장 파일 (직접 만들기)
├── keyword_analysis_naver_*.json   # 결과 파일 (자동 생성)
└── README.md                       # 이 파일
```
## 실행 시간
- 약 10~20초 소요
- 네이버 API 호출 6번 때문에 시간이 걸립니다
## 키워드 개수 변경하기
30개 말고 다른 개수를 원하면:
1. `get_keywords_from_gemini()` 함수에서:
   - 프롬프트의 "30개" 부분 수정
   - `return keywords[:30]` 부분 수정
2. 메인 실행 부분의 출력 메시지도 수정
예시 (20개로 변경):
```python
# 프롬프트
"정확히 20개 나열"
# 리턴
return keywords[:20]
```
## TOP 10 말고 다른 개수 선정하기
TOP 5 또는 TOP 15 등으로 변경하려면:
```python
# 이 부분 찾기
final_top10 = sorted(all_results, key=lambda x: x["평균검색비율"], reverse=True)[:10]
# 숫자만 변경
final_top10 = sorted(all_results, key=lambda x: x["평균검색비율"], reverse=True)[:5]
```
## 보안 주의사항
- `.env` 파일은 GitHub 같은 곳에 올리면 안 됩니다
- `.gitignore` 파일에 다음 내용 추가:
  ```
  .env
  *.json
  ```
## 라이선스
MIT License