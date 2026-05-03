# 🚀 FESTA 앱 배포 가이드

## 가장 추천: Streamlit Community Cloud (무료)

### 1단계: GitHub 계정 만들기
- https://github.com/signup 가입 (이메일만 있으면 OK)

### 2단계: 저장소 만들기
1. https://github.com/new 접속
2. Repository name: `festa-stock-app`
3. **Public** 선택
4. **Create repository** 클릭

### 3단계: 파일 업로드
1. 만든 저장소에서 **"uploading an existing file"** 링크 클릭
2. 다음 파일들을 드래그해서 업로드:
   - app.py
   - festa_logic.py
   - stock_list.py
   - portfolio.py
   - requirements.txt
   - README.md
   - .gitignore
3. ⛔ 업로드 제외 (개인 데이터):
   - watchlist.json
   - portfolio.json
4. 하단 **Commit changes** 클릭

### 4단계: Streamlit Cloud 배포
1. https://share.streamlit.io 접속
2. **Sign in with GitHub** 클릭 (GitHub 계정으로 로그인)
3. **Create app** 또는 **New app** 버튼 클릭
4. 입력:
   - Repository: `본인계정명/festa-stock-app`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL (선택): 원하는 이름 (예: `my-festa`)
5. **Deploy!** 클릭
6. 약 2~3분 빌드 완료 → URL 발급
   - 예: `https://my-festa.streamlit.app`

### 5단계: 접속 확인
- 받은 URL을 핸드폰/PC 어디서나 접속
- 카톡으로 공유 가능

---

## 🔄 코드 수정 후 자동 업데이트

GitHub에 새 파일 업로드만 하면 Streamlit Cloud가 자동으로 재배포합니다!

1. GitHub 저장소 페이지 이동
2. 수정할 파일 클릭 → 연필 아이콘(Edit)
3. 수정 후 **Commit changes**
4. 1~2분 후 자동 반영

---

## ⚠️ 무료 플랜 제한사항

| 항목 | 제한 |
|---|---|
| 메모리 | 1GB |
| 저장소 | Public만 |
| 슬립 모드 | 1주 미접속 시 자동 슬립 (재접속 시 30초 후 깨어남) |
| 동시 접속 | 제한 있음 (개인용으로는 충분) |

---

## 🔒 보안 주의사항

✅ **안전 (그대로 올려도 됨)**:
- app.py, festa_logic.py, stock_list.py, portfolio.py
- requirements.txt, README.md

❌ **올리면 안 됨**:
- watchlist.json (개인 관심종목)
- portfolio.json (개인 매수내역)
- API 키, 비밀번호 등

> .gitignore 파일이 있으면 위 파일들은 자동으로 제외됩니다.

---

## 🆘 문제 해결

### "ModuleNotFoundError" 에러
→ requirements.txt가 제대로 업로드되었는지 확인

### "App is sleeping" 메시지
→ 1주일 미접속으로 슬립모드. URL 클릭 후 30초 대기

### 배포 후 화면이 빈 채로 안 뜸
→ Streamlit Cloud 대시보드 → 본인 앱 → "Manage app" → 로그 확인

### finance-datareader 관련 에러
→ requirements.txt에 `finance-datareader>=0.9.50` 포함 확인
