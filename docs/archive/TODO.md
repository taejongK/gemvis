# TODO: Gemvis Implementation Roadmap (v1, 초기 백로그)

> ⚠️ **이 문서는 초기 작업 백로그입니다.** 현재 진행 상황 및 기능 상세는 [docs/ARCHITECTURE_V2.md](docs/ARCHITECTURE_V2.md) · [docs/FEATURES_SIDEBAR.md](docs/FEATURES_SIDEBAR.md) · [README.md](README.md)를 우선 참조하세요.

## 🎨 UX/UI (Interface)
- [ ] **3 Core Views**
  - File List View: Hierarchical structure & metadata
  - File Graph View: Entity-Relation visualization
  - Calendar View: Time-based event & document history
- [ ] **Interactive Q&A System**
  - Unified Chat: Global natural language query interface
  - Cross-View Highlighting: Sync query results to highlight files/nodes/dates in real-time

## ⚙️ Backend & Algorithm (Engine)
- [ ] **LLM Serving & Optimization**
  - llama.cpp runtime optimization
  - System prompt refinement for KG schema & view coordinates
- [ ] **Document Analysis Pipeline**
  - Automation: Cron (periodic) | Hook (real-time event)
  - Pipeline: File Detection | Text Extraction | Entity Extraction | Graph Update
- [ ] **Knowledge Graph Refinement**
  - Schema: Detailed relation definitions (Person, Place, Project, Event)
  - Query: Natural Language | Cypher/Kùzu query conversion optimization

## 🛠️ Quality & Edge-Cases
- [ ] **Indexing Feedback**: Real-time progress indicator
- [ ] **Entity Resolution**: Deduplication & manual merge UI
- [ ] **Privacy Audit**: Full air-gapped environment verification

## 📅 Priority Roadmap
1. Backend Analysis Pipeline & KG Engine
2. 3 Core Views (List, Graph, Calendar)
3. Chat Query | View Highlighting integration
4. Entity Refinement & Final Optimization

---

# TODO: Gemvis 구현 로드맵 (한글 버전)

## 🎨 UX/UI (인터페이스)
- [x] **3대 핵심 뷰 구현** ✅ 완료 (2026-05-11)
  - Dashboard: 통계 + 최근 파일 (Bento Grid 레이아웃)
  - GraphView: react-force-graph-2d 시각화 + 하이라이트 모드
  - Calendar: FullCalendar 기반 일일/주간/월간 요약
- [x] **인터랙티브 질의응답 시스템** ✅ 완료 (2026-05-11)
  - Spotlight 검색 (Ctrl+K): 글로벌 오버레이
  - Search 페이지: 하이브리드 검색 + LLM 답변 생성
  - 교차 뷰 연동: Ctrl+Alt+V로 GraphView 하이라이트

## ⚙️ 백엔드 및 알고리즘 (엔진)
- [ ] **LLM 서빙 및 최적화**
  - llama.cpp 런타임 최적화
  - KG 스키마 및 뷰 좌표 출력을 위한 시스템 프롬프트 정교화
- [ ] **문서 분석 파이프라인**
  - 자동화: Cron (주기적) | Hook (실시간 이벤트)
  - 파이프라인: 파일 감지 | 텍스트 추출 | 엔티티 추출 | 그래프 업데이트
- [ ] **지식그래프 고도화**
  - 스키마: 인물, 장소, 프로젝트, 이벤트 간 상세 관계 정의
  - 쿼리: 자연어 | Cypher/Kùzu 쿼리 변환 최적화

## 🛠️ 품질 및 엣지 케이스
- [x] **인덱싱 피드백** ✅ 완료 (2026-05-11)
  - 스캔 진행률 UI (total/processed/current_file)
  - 일시정지/재개 기능
  - 완료 토스트 알림
- [ ] **엔티티 정제**: 중복 제거 및 수동 병합 UI (Phase 2)
- [x] **보안 검증** ✅ 완료 (2026-05-11)
  - 100% 로컬 동작 (외부 API 호출 없음)
  - ~/.gemvis/ 로컬 저장소
  - 원본 파일 불변 (Symbolic Link 전용)

## 📅 우선순위 로드맵

### ✅ Phase 1 완료 (2026-05-11)
1. ✅ 백엔드 분석 파이프라인 및 지식그래프 엔진 고도화
2. ✅ 5대 핵심 뷰 (Dashboard, GraphView, Calendar, Search, Settings) 구현
3. ✅ 채팅 질의 + 뷰 하이라이팅 연동

### 🚀 Phase 2 (향후)
4. 엔티티 정제 및 최종 최적화
5. 멀티모달 확장 (오디오, 비디오)
6. Mobile + 동기화
