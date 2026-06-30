# Gemvis 수동 QA 체크리스트

> **용도**: 릴리즈 / 해커톤 데모 직전 라이브 Gemma 4 환경에서 확인해야 할 **자동화 불가능한** 검증 항목.
> **자동화 테스트**는 [tests/test_v2_hydration.py](../tests/test_v2_hydration.py) 33개가 이미 커버함 ([QA_REPORT_V2.md](QA_REPORT_V2.md) 참조).
> **기능 번호**는 [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md) 참조.

---

## 0. 사전 준비

### 0.1 환경 확인

- [ ] Python 3.11 가상환경 활성화 (`source venv/bin/activate`)
- [ ] 프론트엔드 의존성 설치 (`cd frontend && npm install`)
- [ ] llama-server 바이너리 + Gemma 4 GGUF 모델 존재
- [ ] `~/.gemvis/` 디렉터리가 비어있거나 백업 완료 (clean slate QA 필요 시)

### 0.2 서버 기동

```bash
# 터미널 1: Gemma 4 llama-server
./scripts/start_server.sh

# 터미널 2: Gemvis 백엔드 + 프론트 (macOS)
./scripts/start_mac.sh
```

확인:

- [ ] `http://localhost:8080/v1/models`에 Gemma 4 모델 응답
- [ ] `http://localhost:8000/docs`에서 FastAPI Swagger 로드
- [ ] 브라우저에서 `http://localhost:5173` 또는 기동 스크립트 제시 포트로 프론트 접속

---

## 1. 📊 대시보드 검증 ([기능 1.x](FEATURES_SIDEBAR.md#1--대시보드-))

### 1.A Hydration 상태 전이 (가장 중요)

1. `~/gemvis_watch/qa_hydration.md` 생성 (내용: "QA 테스트 파일")
2. 대시보드 새로고침

체크:

- [ ] **즉시** (~1초 이내) `⏳ 분석 대기` 배지로 등장 (Stage 1 skeleton)
- [ ] 수 초 후 `⚙️ 분석 중`으로 전환 (Stage 2 시작)
- [ ] LLM 분석 완료 후 `✅ 완료` 배지 + 요약/카테고리 셀 채워짐
- [ ] 파일 크기 KB 단위 표시
- [ ] 생성일/수정일이 OS stat과 일치

### 1.B 상태 필터 버튼

- [ ] `전체` 클릭 — 모든 파일 노출
- [ ] `⏳ 분석 대기` 클릭 — pending만, 카운트 일치
- [ ] `⚙️ 분석 중` 클릭 — processing만 (짧은 순간만 보임)
- [ ] `✅ 완료` 클릭 — completed만
- [ ] `❌ 실패` 클릭 — failed 파일만 (없으면 빈 테이블)

### 1.C 정렬

- [ ] `생성일` 헤더 클릭 → 내림차순 ↓, 재클릭 → 오름차순 ↑
- [ ] `수정일`, `추가일` 컬럼도 동일
- [ ] 정렬 상태가 페이지 이동 후에도 유지됨

### 1.D 페이지네이션

- [ ] 50개 초과 시 `← 이전` / `다음 →` 버튼 활성화
- [ ] 경계(페이지 1, 마지막 페이지)에서 버튼 비활성화

### 1.E 실패 케이스

1. 빈 내용의 `.md` 파일 드롭 → LLM이 실패 가능한 조건 유도
2. 또는 의도적으로 큰 파일 (~50MB) 드롭

체크:

- [ ] 실패 시 `❌ 실패` 배지
- [ ] 요약 셀에 `⚠ {error 메시지}` 표시
- [ ] 배지 툴팁에 error 상세

---

## 2. 📅 캘린더 검증 ([기능 2.x](FEATURES_SIDEBAR.md#2--캘린더-calendar))

### 2.A 기본 탐색

- [ ] 월간 캘린더 렌더
- [ ] 연/월 드롭다운 전환 동작
- [ ] 이전/오늘/다음 버튼 동작
- [ ] 파일 활동 있는 날에 이벤트 배지(🗂️ 또는 🏠) 표시

### 2.B 일일 요약 생성

- [ ] 오늘 날짜 클릭 → 우측 패널 열림 (work/personal 2블록)
- [ ] 비어 있는 블록에 "생성" 버튼 노출
- [ ] "생성" 클릭 → 확인 모달 → LLM 호출 → 한국어 내러티브 생성
- [ ] 생성된 요약에 파일 수 / `+created ~modified -deleted` 통계 표시
- [ ] `work_hours` 라벨이 업무 블록에 (설정 스케줄 반영)
- [ ] "관련 파일 N개" `<details>` 펼침 — 파일명 목록

### 2.C 재생성 / 삭제

- [ ] 기존 요약 블록에 "재생성" 버튼
- [ ] 재생성 확인 모달 → 덮어쓰기
- [ ] "삭제" 버튼 → 확인 모달 → 요약 제거, 빈 상태로 복귀

### 2.D 에지 케이스

- [ ] 활동이 전혀 없는 날 요약 생성 → "활동 없음" 메시지
- [ ] 업무 스케줄이 비어있는 요일 → work 요약은 "설정 안 됨" 안내

---

## 3. 🕸️ 지식그래프 검증 ([기능 3.x](FEATURES_SIDEBAR.md#3--지식그래프-graph))

### 3.A 기본 렌더링

- [ ] 7색 범례 표시 (file, person, place, project, event, date, tag)
- [ ] Force simulation이 자연스럽게 수렴
- [ ] 노드 드래그 동작
- [ ] 휠 줌 인/아웃 동작
- [ ] 빈 상태: "그래프가 비어있습니다..." 안내

### 3.B 포커스 모드

1. 스포트라이트 ⌘K → "김철수" 같은 엔티티명 검색 → Ctrl+Alt+V

체크:

- [ ] `/graph?focus={id}`로 이동
- [ ] 포커스 배너 상단 표시 + "검색" 버튼으로 스포트라이트 재오픈
- [ ] 포커스 노드 크게 + 청록 테두리
- [ ] 1-hop 이웃 노드 + 엣지 강조
- [ ] 나머지는 흐리게 (alpha 0.15)
- [ ] "하이라이트 해제" 버튼 → 정상 모드 복귀

### 3.C Hydration 시각화

1. 새 파일 드롭 (예: 동일 인물명 포함된 `qa_graph.md`)
2. 그래프 새로고침

체크:

- [ ] 신규 file 노드가 나타남
- [ ] 기존 person 노드와 `mentions` 엣지로 연결
- [ ] 기존 project/event 노드와도 관계 엣지 형성

---

## 4. 💬 대화 검색 검증 ([기능 4.x](FEATURES_SIDEBAR.md#4--대화-검색-search))

### 4.A 기본 대화

- [ ] 빈 상태에 제안 프롬프트 3개 노출
- [ ] 제안 클릭 → 즉시 검색 실행
- [ ] 답변이 마크다운으로 렌더 (불릿/굵기 반영)
- [ ] 타이핑 인디케이터 노출
- [ ] 답변 생성 후 스크롤 자동 하단 이동

### 4.B 쿼리 디버그 패널

- [ ] "쿼리 디버그" 토글로 열기
- [ ] `intent`, `search_terms`, `node_types` 표시
- [ ] `graph_results` 원본 노드 리스트 노출 (type/name/edge_type)

### 4.C 쿼리 정확도 (샘플)

아래 질의를 실제로 넣어보고 답변 품질 검토:

- [ ] `"회의"` → 회의록 카테고리 파일 우선
- [ ] `"사진"` → photo/screenshot 카테고리 필터 동작
- [ ] `"{인물명}이 참석한 회의"` → 인물 + 이벤트 매칭
- [ ] `"지난 주 수정한 파일"` → 날짜 매칭 (업무일수 기반)
- [ ] 존재하지 않는 키워드 → 정중한 "결과 없음" 메시지

### 4.D 스포트라이트 ⌘K ([기능 S.x](FEATURES_SIDEBAR.md#스포트라이트-오버레이-k-별도-메뉴-아님))

- [ ] ⌘K / Ctrl+K로 오버레이 오픈/닫기
- [ ] 입력 후 Enter → 검색 실행, 결과 목록 노출
- [ ] ↑↓ 키로 결과 간 이동
- [ ] Enter로 폴더 열기 (Finder/Explorer 창 뜸)
- [ ] Ctrl+Alt+V → `/graph?focus={id}`로 이동 + 오버레이 닫힘
- [ ] Esc로 오버레이 닫힘
- [ ] 포커스 복원: Explorer.exe가 포커스 뺏어가도 오버레이 재오픈 시 input에 자동 focus

---

## 5. ⚙️ 설정 검증 ([기능 5.x](FEATURES_SIDEBAR.md#5-%EF%B8%8F-설정-settings))

### 5.A 감시 폴더

- [ ] 기본 폴더 3개 (Downloads/Pictures/Documents) 체크박스로 토글
- [ ] 커스텀 폴더 추가 (절대경로 입력 + "폴더 추가")
- [ ] 폴더 제거 × 버튼
- [ ] "설정 저장 (감시 재시작)" → watcher 재기동 확인 (로그: "Watching directory: ...")

### 5.B 감시 제어

- [ ] "감시 시작" / "감시 중지" 버튼 동작
- [ ] 상태 라인에 `running: true/false` 반영
- [ ] "기존 파일 스캔" → 백그라운드 스캔 시작, 하단 ScanToast 진행 상황 노출

### 5.C 업무 시간 스케줄

- [ ] 요일별 체크박스 on/off
- [ ] start/end time 입력
- [ ] 저장 → 캘린더의 `work_hours` 라벨에 반영 확인

### 5.D 파일 목록 펼침

- [ ] "감시 파일 목록 (N개, 분석 완료: M개)" 클릭으로 펼침
- [ ] 각 파일 앞에 4상태 아이콘 표시
- [ ] 실패 파일은 ❌ 툴팁에 error 메시지
- [ ] 카테고리 `(memo)` 꼬리표 (completed만)

### 5.E 데이터 초기화

- [ ] "🗑️ 모든 데이터 초기화 & 재스캔" → 확인 다이얼로그
- [ ] 확인 후 graph.ttl/events.ttl 초기화 로그
- [ ] 대시보드 비워짐 + 재스캔 자동 시작

---

## 6. 🔄 크래시 복구 검증 (v2 신규)

가장 까다로운 검증 — 실제 종료 필요.

### 6.A processing → pending 롤백

1. 대용량 파일 (예: 50MB `.pdf`) 드롭 → Stage 2가 오래 걸리도록
2. 상태가 `⚙️ 분석 중`일 때 백엔드 프로세스를 `kill -9`로 강제 종료
3. `./scripts/start_mac.sh`로 재기동

체크:

- [ ] 로그에 `Startup rollback: 1 node(s) processing → pending` 출력
- [ ] 대시보드에서 해당 파일이 `⏳ 분석 대기`로 복귀
- [ ] 자동 재스캔 또는 수동 재분석으로 복구

### 6.B retry-failed

1. 설정에서 감시 폴더에 일부러 LLM 실패 유도 파일 넣기 (크기 0인 `.md` 등)
2. `❌ 실패` 상태 확인
3. 브라우저 DevTools → `fetch('/api/files/retry-failed', {method:'POST'})` 실행
4. 또는 향후 UI 버튼이 생기면 사용

체크:

- [ ] 응답 `{status: "requeued", count: N}`
- [ ] 대시보드에서 해당 파일이 `⏳ pending`으로 바뀜
- [ ] watcher 다음 사이클에서 재분석

---

## 7. 🔒 프라이버시 검증 (Gemvis 핵심)

로컬 전용이 지켜지는지 확인.

- [ ] DevTools → Network 탭 열고 위 1~6 시나리오 재실행
- [ ] 외부 도메인 호출 0건 (localhost / 127.0.0.1 / llama-server 호스트만)
- [ ] `openai.com`, `googleapis.com`, `anthropic.com` 등 **절대 노출 금지**
- [ ] tcpdump 또는 Little Snitch로 백엔드 프로세스의 외부 연결 감시 (선택)

---

## 8. 📦 빌드 아티팩트 검증

릴리즈 전 1회.

```bash
cd frontend
npx tsc --noEmit   # 타입 에러 0
npm run build      # dist/ 생성, 오류 없음
```

- [ ] `dist/index.html`, `dist/assets/` 생성
- [ ] gzip 크기가 1MB 미만 (현재 252KB)
- [ ] 프로덕션 빌드를 `python run.py`로 띄워도 `/` 라우팅 정상 (백엔드가 `FRONTEND_DIR` mount)

---

## 9. 🧪 자동화 테스트 재확인

```bash
source venv/bin/activate
python -m pytest tests/test_v2_hydration.py --noconftest -q
```

- [ ] 33/33 통과
- [ ] 실행 시간 ~70초 이내 (임베딩 모델 lazy load 포함)

---

## 10. 📋 체크리스트 결과 기록

릴리즈 직전 통과 기록:

| 섹션 | 통과 | 담당 | 날짜 |
|------|------|------|------|
| 0. 사전 준비 | ☐ | | |
| 1. 대시보드 | ☐ | | |
| 2. 캘린더 | ☐ | | |
| 3. 지식그래프 | ☐ | | |
| 4. 대화 검색 + 스포트라이트 | ☐ | | |
| 5. 설정 | ☐ | | |
| 6. 크래시 복구 | ☐ | | |
| 7. 프라이버시 | ☐ | | |
| 8. 빌드 | ☐ | | |
| 9. 자동화 테스트 | ☐ | | |

**전 항목 통과 시에만 main 머지 / 해커톤 제출.**

---

**Last Updated**: 2026-05-12
**Related**: [QA_REPORT_V2.md](QA_REPORT_V2.md) · [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md) · [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)
