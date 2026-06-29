# Gemvis 문서 트리

> **🌐 Root README:** [🇺🇸 English](../README.md) · [🇰🇷 한국어](../README_ko.md)
>
> **마지막 업데이트**: 2026-05-12 (v2, `geminsight-develop` 브랜치)
> **이 문서 하나로 전체 레포를 타고타고 파악할 수 있습니다.** 레포 루트의 [README.md](../README.md)가 최상위 진입점, 이 파일은 **문서 맵**입니다.

---

## 🗺️ 한눈에 보기 (권장 읽기 순서)

```
0. 루트 README.md              ← 프로젝트 소개 + 빠른 시작
     │
     ├── 1. 무엇을 만드는가
     │     ├── docs/gemvis_team_direction.md   (프로젝트 본질)
     │     ├── docs/problem_analysis.md        (해결하려는 문제)
     │     └── docs/user_scenarios.md          (6가지 사용자 시나리오)
     │
     ├── 2. 어떻게 돌아가는가 (v2, 현재 구현)
     │     ├── docs/ARCHITECTURE_V2.md         ⭐ GemInsight SSoT 설계
     │     ├── docs/GEM_INSIGHT.md             (GemInsight 개념)
     │     ├── docs/FEATURES_SIDEBAR.md        ⭐ 사이드바 메뉴별 기능 + 필드 매핑
     │     ├── docs/FEATURES.md                (컴포넌트/계층 관점 기능)
     │     └── API_CONTRACT.md                 ⭐ 프론트↔백 API 계약 (v2)
     │
     ├── 3. 어떻게 품질을 담보하는가
     │     ├── docs/QA_REPORT_V2.md            (자동화 QA 33/33 통과 결과)
     │     ├── docs/QA_MANUAL_CHECKLIST.md     ⭐ 릴리즈 전 수동 QA 10 섹션
     │     └── tests/test_v2_hydration.py      (v2 자동화 테스트)
     │
     ├── 4. 해커톤 실행 기록 (v1, 초기)
     │     ├── plan.md                         (20일 실행 계획)
     │     ├── docs/hackathon_strategy.md      (해커톤 전략)
     │     ├── docs/mvp_roadmap.md             (초기 5주 로드맵)
     │     ├── TODO.md                         (초기 백로그 체크리스트)
     │     └── docs/GEMINSIGHT_IMPACT.md       (✅ 완료된 rename 리팩터 회고)
     │
     └── 5. 초기 설계 (v1, 역사 기록)
           ├── docs/architecture.md            (초기 4-레이어 다이어그램)
           └── docs/technical_spec.md          (초기 기술 스펙)
```

⭐ = v2 현재 기준의 **정답 문서**. `v1`으로 표시된 문서는 상단에 deprecation 배너가 있으며, 실제 구현과 다를 수 있으니 ⭐ 문서를 우선 참조하세요.

---

## 📂 파일별 역할

### 🏠 루트 레벨

| 파일 | 역할 | 업데이트 |
|------|------|---------|
| [README.md](../README.md) | 프로젝트 최상위 진입점 + 빠른 시작 + 주요 기능 요약 | 최신 |
| [API_CONTRACT.md](../API_CONTRACT.md) | 프론트↔백엔드 HTTP API 계약 (v2 `/api/files*` + v1 deprecated) | v2 |
| [.claude/CLAUDE.md](../.claude/CLAUDE.md) | Claude Code용 프로젝트 가이드라인 | 최신 |

### 🏗️ 아키텍처·기능 스펙 (docs/)

| 파일 | 역할 | 업데이트 |
|------|------|---------|
| **[ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)** ⭐ | GemInsight SSoT + raw_insight + 4-state 머신 설계 | v2 |
| **[FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md)** ⭐ | 사이드바 메뉴 5개별 기능 + GemInsight 필드 매핑 | v2 |
| [GEM_INSIGHT.md](GEM_INSIGHT.md) | GemInsight 개념 정의 + 저장 구조 | v2 |
| [FEATURES.md](FEATURES.md) | 컴포넌트/계층 관점 기능 레퍼런스 | 최신 |
| [architecture.md](architecture.md) | 초기 4-레이어 아키텍처 (Kùzu 가정) | v1 (deprecated) |
| [technical_spec.md](technical_spec.md) | 초기 기술 스펙 (Tauri/Cypher 가정) | v1 (deprecated) |

### 🧪 QA·테스트 (docs/ + tests/)

| 파일 | 역할 | 업데이트 |
|------|------|---------|
| [QA_REPORT_V2.md](QA_REPORT_V2.md) | v2 자동화 QA 결과 (33/33 통과, 버그 1건 포착·수정) | v2 |
| **[QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md)** ⭐ | 릴리즈/데모 전 라이브 Gemma 4 수동 검증 10개 섹션 | v2 |
| [tests/test_v2_hydration.py](../tests/test_v2_hydration.py) | v2 전 레이어 자동화 테스트 (33개) | v2 |

### 📜 역사·전략·맥락 (docs/)

| 파일 | 역할 |
|------|------|
| [gemvis_team_direction.md](gemvis_team_direction.md) | 프로젝트 본질 (팀 방향성) |
| [problem_analysis.md](problem_analysis.md) | 해결하려는 문제 분석 |
| [user_scenarios.md](user_scenarios.md) | 6가지 사용자 시나리오 |
| [hackathon_strategy.md](hackathon_strategy.md) | 해커톤 전략 |
| [mvp_roadmap.md](mvp_roadmap.md) | 초기 5주 MVP 로드맵 (v1, deprecated) |
| [GEMINSIGHT_IMPACT.md](GEMINSIGHT_IMPACT.md) | ✅ 완료된 AnalysisResult → GemInsight rename 회고 |

### ⚙️ Claude Code 하네스 (.claude/)

| 파일 | 역할 |
|------|------|
| [.claude/CLAUDE.md](../.claude/CLAUDE.md) | Gemvis 프로젝트 Claude Code 가이드 |
| [.claude/README.md](../.claude/README.md) | 하네스 구성 설명 |
| [.claude/harness.md](../.claude/harness.md) | 하네스 상세 |
| [.claude/rules/privacy.md](../.claude/rules/privacy.md) | 프라이버시 우선 규칙 (외부 송신 금지) |
| [.claude/rules/frontend.md](../.claude/rules/frontend.md) | 프론트엔드 코딩 규칙 |
| [.claude/rules/python-backend.md](../.claude/rules/python-backend.md) | Python 백엔드 규칙 |
| [.claude/rules/gemma-prompts.md](../.claude/rules/gemma-prompts.md) | Gemma 프롬프트 규칙 |
| [.claude/agents/](../.claude/agents/) | 전용 에이전트 (gemma-tester, graph-builder, mvp-guardian) |
| [.claude/skills/](../.claude/skills/) | 스킬 (week-checkin 등) |

### 🛠️ 서브디렉터리 README

| 파일 | 역할 |
|------|------|
| [frontend/README.md](../frontend/README.md) | 프론트엔드 개발 환경 |
| [models/README.md](../models/README.md) | 로컬 모델 캐시 위치 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 개발 환경 설정 + 테스트 + PR 가이드 |
| [ENV.md](ENV.md) | 환경 변수 참조 문서 |

### 📦 Archive (역사 기록)

| 파일 | 역할 |
|------|------|
| [archive/TODO.md](archive/TODO.md) | **[ARCHIVED]** v1 초기 백로그 체크리스트 |
| [archive/plan.md](archive/plan.md) | **[ARCHIVED]** v1 20일 해커톤 실행 계획 |
| [archive/llama_test/local-llm-test-guide.md](archive/llama_test/local-llm-test-guide.md) | **[ARCHIVED]** Ollama vs llama.cpp 비교 테스트 가이드 (현재: llama.cpp만 사용) |

---

## 🎯 목적별 탐색 가이드

| 하고 싶은 일 | 우선 볼 문서 |
|------|------|
| **처음 이 레포를 본다** | [README.md](../README.md) → 이 파일 → [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) |
| **특정 UI 기능의 동작이 궁금** | [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md) |
| **GemInsight 필드 의미/생성 경로** | [ARCHITECTURE_V2.md §1](ARCHITECTURE_V2.md) + [GEM_INSIGHT.md](GEM_INSIGHT.md) |
| **HTTP API 스펙** | [API_CONTRACT.md](../API_CONTRACT.md) |
| **기능 추가/수정 전 체크리스트** | [ARCHITECTURE_V2.md §5 불변식](ARCHITECTURE_V2.md) + [.claude/rules/privacy.md](../.claude/rules/privacy.md) |
| **릴리즈 전 최종 검증** | [QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md) |
| **자동화 테스트 실행** | `python -m pytest tests/test_v2_hydration.py` |
| **해커톤 목적/시나리오/전략** | [user_scenarios.md](user_scenarios.md) + [hackathon_strategy.md](hackathon_strategy.md) + [gemvis_team_direction.md](gemvis_team_direction.md) |

---

## 🔄 문서 버전 규칙

- **v2 (현재)**: `raw_insight` SSoT, `FileRecord` 단일 타입, `/api/files*` 통합 엔드포인트.
- **v1 (deprecated)**: 초기 가정(Tauri, Kùzu, 분산 저장 등) 기반의 기록. 상단 배너로 명시.
- 신규 기능 추가 시 **⭐ 표기 문서 4개**([ARCHITECTURE_V2.md](ARCHITECTURE_V2.md), [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md), [API_CONTRACT.md](../API_CONTRACT.md), [QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md)) 반드시 동기화.
- v1 문서는 **역사 기록으로 보존** — 삭제하지 않고 deprecation 배너만 유지.
