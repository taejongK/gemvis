# Gemvis 해커톤 실행 계획 (v1, 초기 계획)

> ⚠️ **이 문서는 2026-04-29 기준 초기 실행 계획입니다.** 현재 구현 상태는 [docs/ARCHITECTURE_V2.md](docs/ARCHITECTURE_V2.md) · [docs/FEATURES_SIDEBAR.md](docs/FEATURES_SIDEBAR.md) · [README.md](README.md)를 참조하세요. 본문의 "Kùzu" 표기 등은 초기 가정입니다(실제는 rdflib TTL).

**기간**: 2026-04-29 ~ 2026-05-19 (20일)  
**전략**: 기존 작업 통합 → 미완성 기능 완성 → UI/UX 고도화  
**마일스톤**: 5/9 전원 PC 설치 테스트

---

## 📊 현재 상황 (2026-04-29 기준)

### 진행된 브랜치 분석

| 브랜치 | 주요 작업 | 상태 | 담당 |
|--------|----------|------|------|
| **main** | 기본 아키텍처, 문서, backend 구조 (Kùzu 기반) | ✅ 확정 | 인규 |
| **feature/multi-agent** | rdflib 지식그래프, SPARQL, 하이브리드 검색, FastAPI | ✅ 완성 | 준혁 |
| **hanhj/poc** | React 프론트엔드 (FullCalendar 캘린더 포함) | ✅ 완성 | 혜지 |
| **tj/poc** | Multi-agent SSE 스트리밍 검색 (agents.py) | ✅ 완성 | 태종 |
| **test/vision** | Gemma 4 비전 + llama.cpp 테스트 | ✅ 완료 | 인규 |

### ✅ 확정된 사항 (이미 완료)

#### 백엔드 (feature/multi-agent + tj/poc)

**feature/multi-agent**:
- ✅ **지식그래프**: rdflib + RDF/Turtle + SPARQL
- ✅ **임베딩 검색**: sentence-transformer 로컬 모델
- ✅ **하이브리드 검색**: SPARQL 구조 쿼리 + 벡터 유사도
- ✅ **API 엔드포인트**:
  - `POST /api/search` - 하이브리드 검색
  - `GET /api/dashboard` - 통계
  - `GET /api/graph/data` - 그래프 노드/엣지
  - `POST /api/watcher/start|stop` - 파일 감시
  - `POST /api/file/open-folder` - 폴더 열기

**tj/poc 추가**:
- ✅ **Multi-agent 파이프라인**: Retriever → Reader → Synthesizer (gemvis/agents.py)
- ✅ **SSE 스트리밍**: `POST /api/search/stream` - 실시간 채팅 응답

**공통**:
- ✅ **파일 분석**: PDF/이미지/텍스트 자동 분류·요약·태깅·엔티티 추출
- ✅ **실시간 감시**: watchdog 파일 변경 감지
- ✅ **FastAPI 서버**: gemvis/api.py

#### 프론트엔드 (hanhj/poc)

- ✅ **5개 뷰**: Dashboard, Calendar, GraphView, Search, Settings
- ✅ **Spotlight 검색**: Ctrl+K 글로벌 검색 오버레이
- ✅ **그래프 포커싱**: Ctrl+Alt+V로 파일 하이라이트
- ✅ **폴더 열기**: Enter로 OS 파일 탐색기 바로 열기
- ✅ **캘린더 뷰**: FullCalendar 기반 완성 (일일/주간/월간 요약 생성 기능 포함)
- ✅ **API 클라이언트**: frontend/src/api.ts (백엔드 엔드포인트와 매칭)

#### 인프라

- ✅ llama.cpp 백엔드 + Gemma 4 E2B GGUF
- ✅ OpenAI 호환 LLM 클라이언트 (gemvis/llm_client.py)

---

## 👥 팀 구성 및 R&R (통합 기준)

| 역할 | 담당자 | 주요 책임 |
|------|--------|----------|
| **프로젝트 리더** | 박인규 | 브랜치 통합 실행<br>충돌 해결 및 최종 검토<br>통합 테스트<br>해커톤 제출 자료 총괄 |
| **프론트엔드** | 한혜지 | ✅ UI 완성 (hanhj/poc)<br>백엔드 API 연동 확인<br>SSE 스트리밍 UI 구현<br>최종 UX 개선 |
| **지식그래프** | 박준혁 | ✅ 백엔드 완성 (feature/multi-agent)<br>API 검증 및 보완<br>GraphView 데이터 포맷 확인<br>성능 최적화 |
| **채팅 백엔드** | 김태종 | ✅ Multi-agent 완성 (tj/poc)<br>SSE 통합 검증<br>응답 품질 개선<br>대화 히스토리 관리 |

---

## 🔄 브랜치 통합 전략

### 우선순위

1. **main ← feature/multi-agent** (gemvis/ + frontend/ 추가)
2. **main ← tj/poc** (gemvis/agents.py + api.py 업데이트)
3. **main ← hanhj/poc** (frontend/ 완전 교체)
4. **통합 테스트 및 검증**

### 디렉토리 구조

```bash
# 현재 main 브랜치
backend/          # Kùzu 기반 구버전 (삭제 예정)

# feature/multi-agent 브랜치
gemvis/           # rdflib 기반 신버전 백엔드
frontend/         # 프론트엔드 (일부 구현)

# tj/poc 브랜치
gemvis/agents.py  # Multi-agent 파이프라인 추가
gemvis/api.py     # /api/search/stream 엔드포인트 추가

# hanhj/poc 브랜치
frontend/         # 완성된 프론트엔드 (5개 뷰 + 캘린더)

# 통합 후 최종 구조
gemvis/           # 백엔드 메인 (feature/multi-agent + tj/poc 통합)
frontend/         # 프론트엔드 메인 (hanhj/poc)
backend/          # 삭제 (구버전)
```

---

## ⚠️ 확정 필요 사항

### 1. API 엔드포인트 정렬

**백엔드 제공 (feature/multi-agent + tj/poc)**:
```python
POST /api/search              # 하이브리드 검색
POST /api/search/stream       # SSE 스트리밍 검색 (tj/poc)
GET  /api/dashboard           # 통계
GET  /api/graph/data          # 그래프 노드/엣지
POST /api/watcher/start       # 파일 감시 시작
POST /api/watcher/stop        # 파일 감시 중지
GET  /api/watcher/status      # 감시 상태
POST /api/watcher/scan        # 수동 스캔
POST /api/config              # 설정 저장
DELETE /api/graph             # 그래프 초기화
POST /api/file/open-folder    # 폴더 열기
```

**프론트엔드 사용 (hanhj/poc)**:
```typescript
api.dashboard()               # ✅ 일치
api.graphData()               # ✅ 일치 (/api/graph/data)
api.search(question)          # ✅ 일치 (/api/search)
api.watcherStart/Stop/Status  # ✅ 일치
api.saveConfig()              # ✅ 일치
api.clearGraph()              # ✅ 일치
api.openFolder(path)          # ✅ 일치
api.getSchedule()             # ⚠️ 백엔드에 없음
api.listSummaries()           # ⚠️ 백엔드에 없음
api.getDaySummary(date)       # ⚠️ 백엔드에 없음
api.generateSummary()         # ⚠️ 캘린더 요약 API 누락
```

→ **액션**: 캘린더 요약 관련 API 4개 백엔드 구현 필요

### 2. 기술 스택 확정

| 항목 | 실제 구현 | 상태 |
|------|----------|------|
| **Graph DB** | rdflib + SPARQL | ✅ 확정 |
| **프론트엔드** | Vite + React | ✅ 확정 (Tauri 래핑은 Phase 3) |
| **검색 방식** | SPARQL + 임베딩 하이브리드 | ✅ 확정 |
| **채팅** | Multi-agent SSE 스트리밍 | ✅ 확정 |

---

## 📋 추가 필요 내용

### 백엔드 (준혁님 + 인규님)

| 작업 | 우선순위 | 예상 소요 | 설명 |
|------|---------|----------|------|
| **브랜치 통합** | ★★★ | 0.5일 | feature/multi-agent + tj/poc → main |
| **캘린더 요약 API** | ★★★ | 1일 | `/api/summary/*` 4개 엔드포인트 구현 |
| **API 검증** | ★★★ | 0.5일 | 프론트 api.ts와 백엔드 정렬 확인 |
| **GraphView 포맷** | ★★ | 0.5일 | react-force-graph 데이터 형식 확인 |
| **성능 최적화** | ★ | 1일 | 쿼리 속도, 메모리 사용량 개선 |

### 프론트엔드 (혜지님)

| 작업 | 우선순위 | 예상 소요 | 설명 |
|------|---------|----------|------|
| **브랜치 통합 확인** | ★★★ | 0.5일 | hanhj/poc → main 머지 후 동작 확인 |
| **SSE 스트리밍 UI** | ★★★ | 1일 | `/api/search/stream` 연결, 실시간 렌더링 |
| **캘린더 API 연동** | ★★ | 0.5일 | 백엔드 API 완성 후 연결 |
| **에러 핸들링** | ★★ | 0.5일 | API 실패 시 사용자 피드백 |
| **UI 폴리싱** | ★ | 1일 | 애니메이션, 로딩 상태 개선 |

### 채팅 (태종님)

| 작업 | 우선순위 | 예상 소요 | 설명 |
|------|---------|----------|------|
| **브랜치 통합 확인** | ★★★ | 0.5일 | tj/poc → main 머지 후 동작 확인 |
| **SSE 스트리밍 테스트** | ★★★ | 0.5일 | 프론트와 통합 테스트 |
| **응답 품질 개선** | ★★ | 1일 | 프롬프트 튜닝, Few-shot 예시 |
| **대화 히스토리** | ★ | 1일 | 세션 관리 (선택 사항) |

### 통합 및 테스트 (전원)

| 작업 | 우선순위 | 예상 소요 | 설명 |
|------|---------|----------|------|
| **E2E 테스트** | ★★★ | 1일 | 파일 추가 → 분석 → 검색 → 응답 전체 흐름 |
| **성능 벤치마크** | ★★ | 0.5일 | 처리 속도, 메모리 측정 |
| **에러 핸들링** | ★★ | 0.5일 | 주요 엣지 케이스 처리 |
| **README 업데이트** | ★ | 0.5일 | 설치 가이드, 스크린샷 |

---

## 📅 수정된 일정 (통합 중심)

### Phase 1 (4/29 ~ 5/2, 4일): 브랜치 통합 + 캘린더 API

**목표**: 3개 브랜치 통합 + 누락된 캘린더 API 구현

| 날짜 | 작업 | 담당 |
|------|------|------|
| **4/29 (월)** | • feature/multi-agent → main 머지<br>• tj/poc → main 머지<br>• `backend/` 삭제 | 인규 + 준혁 |
| **4/30 (화)** | • hanhj/poc → main 머지<br>• API 정렬 확인 (누락 항목 파악) | 인규 + 혜지 |
| **5/1 (수)** | • 캘린더 요약 API 4개 구현<br>• API 테스트 | 준혁 |
| **5/2 (목)** | • 프론트 캘린더 API 연동<br>• E2E 기본 테스트 | 혜지 + 전원 |

### Phase 2 (5/3 ~ 5/9, 7일): SSE + 최적화

**목표**: SSE 스트리밍 완성, 성능 최적화

| 날짜 | 작업 | 담당 |
|------|------|------|
| **5/3~4 (주말)** | • SSE 스트리밍 UI 구현<br>• 채팅 응답 품질 개선 | 혜지 + 태종 |
| **5/5 (월)** | • 성능 벤치마크<br>• 쿼리 최적화 | 준혁 + 인규 |
| **5/6 (화)** | • 에러 핸들링 강화<br>• UI 폴리싱 | 혜지 |
| **5/7 (수)** | • 전체 기능 통합 테스트 | 전원 |
| **5/8~9 (목~금)** | • **E2E 통합 테스트**<br>• 전원 PC 설치 → 실제 파일 테스트 | 전원 |

### Phase 3 (5/10 ~ 5/19, 10일): 데모 영상 + 제출

**목표**: 3분 데모 영상, 슬라이드, README 완성

| 날짜 | 작업 | 담당 |
|------|------|------|
| **5/10~11 (주말)** | • 버그 수정<br>• UI 최종 개선 | 전원 |
| **5/12 (월)** | • README 업데이트 (스크린샷, 설치 가이드) | 전원 |
| **5/13~14 (화~수)** | • 데모 시나리오 작성<br>• 데모 영상 촬영 (3분) | 전원 |
| **5/15~16 (목~금)** | • 발표 슬라이드 제작 (10장)<br>• 영상 편집 | 전원 |
| **5/17~18 (토~일)** | • 최종 검토<br>• 제출 자료 준비 | 전원 |
| **5/19 (월)** | • **제출 마감** | - |

---

## 🚀 즉시 실행 액션 (오늘 4/29)

### 인규님

```bash
cd ~/gemvis

# 1. feature/multi-agent 머지
git checkout main
git pull origin main
git merge origin/feature/multi-agent
# → gemvis/, frontend/ 추가됨

# 2. tj/poc 머지
git merge origin/tj/poc
# → gemvis/agents.py, gemvis/api.py 업데이트됨

# 3. 구버전 backend/ 삭제
rm -rf backend/

# 4. 커밋
git add .
git commit -m "chore: merge feature/multi-agent + tj/poc - rdflib graph + SSE streaming"
git push origin main
```

### 혜지님

```bash
cd ~/gemvis

# 1. main 최신화
git checkout main
git pull origin main

# 2. hanhj/poc 머지
git merge origin/hanhj/poc
# → frontend/ 완전 교체됨

# 3. 백엔드 API 확인
# frontend/src/api.ts와 gemvis/api.py 비교
# 누락된 API (summary 관련) 확인

# 4. 커밋
git add frontend/
git commit -m "feat: merge hanhj/poc - complete UI with calendar"
git push origin main
```

### 준혁님

```bash
cd ~/gemvis

# 1. 통합 후 코드 확인
git checkout main
git pull origin main

# 2. 누락된 API 구현 계획 수립
# gemvis/api.py에 추가:
# - GET /api/schedule
# - POST /api/schedule
# - GET /api/summary
# - GET /api/summary/{date}
# - POST /api/summary/{date}/{period}
# - DELETE /api/summary/{date}/{period}

# 3. GitHub Issues 생성
# "캘린더 요약 API 6개 구현" 이슈 등록
```

### 태종님

```bash
cd ~/gemvis

# 1. 통합 후 코드 확인
git checkout main
git pull origin main

# 2. SSE 스트리밍 동작 확인
# gemvis/api.py의 /api/search/stream 엔드포인트 확인
# gemvis/agents.py의 SSEEvent 스트림 확인

# 3. 프론트 연동 준비
# frontend/src/pages/Search.tsx에서 SSE 처리 확인
```

---

## 📝 일일 체크인 (매일 저녁 9시, 카톡)

```text
[4/29] 이름 - 진행 상황

✅ 완료:
- 구체적인 작업 1
- 구체적인 작업 2

🚧 진행 중:
- 작업 A (70%)

❌ 블로커:
- 막힌 부분 (도움 요청)

📅 내일 계획:
- 작업 B
- 작업 C

[커밋] 링크 (있으면)
```

---

## 🎯 Phase 1 완료 체크리스트

### 통합 완료 ✅

- [x] feature/multi-agent → main 머지 완료
- [x] tj/poc → main 머지 완료
- [x] hanhj/poc → main 머지 완료
- [x] `backend/` 삭제 완료

### API 구현 및 연동 ✅

- [x] 캘린더 요약 API 6개 구현 완료
- [x] 프론트 캘린더 페이지 API 연동 완료
- [x] Dashboard API 동작 확인
- [x] GraphView API 동작 확인
- [x] Search API 동작 확인
- [x] GemInsight API 3개 추가 (insights, insight/:id, regenerate)
- [x] Tool Calling 구현 (complete_with_tools)

### 동작 확인 ✅

- [x] 파일 추가 → 자동 분석 동작 (watchdog)
- [x] Dashboard 통계 표시 (Bento Grid)
- [x] GraphView 렌더링 (react-force-graph-2d)
- [x] Search 검색 응답 (하이브리드)
- [x] Calendar 요약 생성 (자동 스케줄러)
- [x] 다중 감시 폴더 지원
- [x] 스캔 진행률 UI
- [x] EventLog 타임스탬프 수정 (file mtime 사용)
- [x] 데이터 초기화 버튼

### 📊 최종 달성 현황 (2026-05-11)

**MVP 목표 초과 달성**: 
- 계획: 기본 3개 뷰 + 검색
- 실제: 5개 완전한 뷰 + 고급 기능 (일일 요약, 자동 스케줄러, 다중 폴더)

---

## 💡 핵심 성공 요소

### 1. 이미 완성된 코드 활용

- ✅ 백엔드: rdflib + SPARQL + 임베딩 + SSE (준혁님 + 태종님)
- ✅ 프론트: 5개 뷰 완성 + 캘린더 UI (혜지님)
- ✅ 통합만 하면 80% 완성

→ **새로 만들 것: 캘린더 요약 API 6개만**

### 2. 빠른 통합

- 1일 만에 3개 브랜치 머지 가능
- 디렉토리 충돌 없음 (backend/ vs gemvis/)
- API 정렬만 하면 연결 완료

### 3. 실용적 스코프

- SSE 스트리밍: 선택 사항 (일반 POST도 OK)
- 대화 히스토리: Phase 2로 미뤄도 됨
- 에러 핸들링: 주요 케이스만

---

## ⚠️ 리스크 대응

| 리스크 | 대응책 |
|--------|--------|
| 브랜치 머지 충돌 | 디렉토리 다름 → 충돌 거의 없음 |
| 캘린더 API 구현 지연 | 프론트 목업 데이터로 먼저 테스트 |
| SSE 동작 안 함 | 일반 POST `/api/search`로 폴백 |
| 5/9 통합 테스트 실패 | 5/10~11 주말 집중 투입 |

---

## 📊 최종 마일스톤

- **5/2 (목)**: 브랜치 통합 + 캘린더 API 완료
- **5/9 (금)**: 전원 PC 설치 테스트 성공
- **5/12 (월)**: 개발 완료
- **5/19 (월)**: 제출

---

**지금 바로 통합 시작합니다! 화이팅! 🚀**
