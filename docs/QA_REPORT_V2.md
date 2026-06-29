# QA Report — `geminsight-develop` v2 Refactor

**Date**: 2026-05-12
**Branch**: `geminsight-develop`
**Tested by**: Claude Code + pytest + Vite build
**Status**: ✅ PASS (33/33 backend tests, frontend build green)

---

## 1. 검증 대상

1. **Data model** — `GemInsight` dataclass, `from_dict()/to_dict()`
2. **KG state machine** — `upsert_skeleton`, `update_status`, `rollback_processing_to_pending`
3. **Raw JSON 원본 보존** — `raw_insight` 속성 저장/복원
4. **Backward compat** — `raw_insight` 없는 pre-v2 노드 fallback
5. **Watcher hydration pipeline** — Stage 1 → Stage 2 → completed/failed 상태 전이
6. **FastAPI v2 엔드포인트** — `/api/files`, `/api/file/{id}`, `regenerate`, `retry-failed`
7. **v1 deprecated 엔드포인트** — 호환 유지 동작 확인
8. **Startup crash recovery** — `processing → pending` 롤백
9. **Frontend** — TypeScript strict + production build

## 2. 테스트 스위트

**파일**: [tests/test_v2_hydration.py](../tests/test_v2_hydration.py) (신규)

실행 방법 (레거시 `conftest.py`가 미설치 `kuzu` 모듈을 참조하므로 `--noconftest` 사용):

```bash
source venv/bin/activate
python -m pytest tests/test_v2_hydration.py --noconftest -v
```

## 3. 결과 요약

| 카테고리 | 테스트 개수 | 통과 | 실패 | 실제 버그 포착 |
|---------|-----------|------|------|-----------|
| GemInsight 데이터 모델 | 5 | 5 | 0 | 0 |
| KG state machine | 5 | 5 | 0 | 0 |
| raw_insight 영속화 | 3 | 3 | 0 | 0 |
| Backward compat (fallback) | 3 | 3 | 0 | 0 |
| Watcher hydration 파이프라인 | 4 | 4 | 0 | 0 |
| FastAPI /api/files | 9 | 9 | 0 | **1** |
| v1 deprecated 호환 | 3 | 3 | 0 | 0 |
| Startup 롤백 | 1 | 1 | 0 | 0 |
| **합계** | **33** | **33** | **0** | **1** |

실행 시간: 약 68초 (embedding 모델 lazy-load 첫 회 비용 포함)

## 4. QA 중 발견·수정된 실제 버그

### 🐛 BUG-1: `_node_to_insight()` fallback이 상태 필드를 복원하지 않음

**증상**: `POST /api/files/retry-failed`가 항상 `count: 0`을 반환.

**원인**: `InsightService._node_to_insight()` fallback 경로가 KG 노드의 `analysis_status`, `last_analyzed_at`, `size_bytes`, `error` 속성을 읽지 않고 무조건 `GemInsight()` 기본값(`"pending"`)을 씌움. 결과적으로 skeleton-only 노드(`raw_insight` 없음, 상태는 `failed`)를 조회하면 `failed` 상태가 `pending`으로 탈바꿈해 `retry-failed` 필터링에서 누락.

**수정**: [gemvis/insight_service.py](../gemvis/insight_service.py) `_node_to_insight()`에서 KG `node_dict`의 상태 필드를 그대로 읽어 복원 + `size_bytes` 문자열→int 변환.

**영향**: 테스트로 포착되지 않았다면 프로덕션에서 "실패 파일 재시도" 버튼이 silent로 동작하지 않았을 것. QA의 실질 가치 입증.

## 5. 커버리지 분석

| 파일 | v2 변경 라인 | 테스트 커버 | 미커버 영역 |
|------|-------------|-----------|-----------|
| `gemvis/insight.py` | `GemInsight` 확장 + `from_dict()` | ✅ 전부 | `generate_insight()` 내부 (LLM 호출 실경로) |
| `gemvis/knowledge_graph.py` | `upsert_skeleton/update_status/rollback` + `add_insight` `raw_insight` 저장 | ✅ 전부 | — |
| `gemvis/insight_service.py` | `get_insight` raw 우선 + fallback | ✅ 전부 (버그 1건 포착) | — |
| `gemvis/watcher.py` | 2-stage hydration | ✅ 전부 (LLM 모킹) | watchdog Observer 실제 파일시스템 이벤트 |
| `gemvis/api.py` | `FileRecord` + 4개 v2 엔드포인트 + startup 롤백 | ✅ 전부 | `/api/file/{id}/regenerate` 실행 경로 (LLM 모킹 필요) |

**미커버 항목은 실제 Gemma 4 llama-server 실행이 필요**하며 본 CI 범위 밖 (End-to-end 수동 검증 시 확인).

## 6. Frontend QA

```bash
cd frontend
npx tsc --noEmit        # ✅ 에러 0
npm run build           # ✅ built in 490ms (809 kB → 252 kB gzip)
```

- TypeScript strict 통과
- Vite production build 산출물 검증 완료
- Dashboard 4상태 배지 + 필터 버튼 렌더링 컴파일 확인
- Settings `FileRecord` 마이그레이션 타입 오류 없음

## 7. 수동 검증 권고 (라이브 Gemma 4 서버 필요)

> **상세 절차**: [QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md) — 대시보드/캘린더/그래프/검색/설정/크래시 복구/프라이버시 10개 섹션 체크리스트.

CI로 못 잡는 영역 — 해커톤 데모 직전 수동으로 1회 검증 권장:

1. `./scripts/start_server.sh` 로 llama-server 기동
2. `./scripts/start_mac.sh` 로 백엔드 + 프론트 기동
3. `gemvis_watch/`에 테스트 파일 드롭
4. Dashboard에서 다음 순서 확인:
   - [ ] 즉시 `⏳ 분석 대기` 배지로 등장
   - [ ] 몇 초 후 `⚙️ 분석 중` 전환
   - [ ] 완료 후 `✅ 완료` + 요약/카테고리 표시
5. 상태 필터 버튼(pending/processing/completed/failed) 각각 클릭 → 정상 필터
6. 임의 파일에서 강제 실패 (예: 빈 파일 내용) → `❌ 실패` 배지 + `POST /api/files/retry-failed` 호출 시 재시도 동작
7. 백엔드 강제 종료 중 `processing` 상태인 파일 → 재시작 시 자동으로 `pending`으로 롤백되는지 로그 확인

## 8. 결론

- ✅ 33개 자동화 테스트 전원 통과
- ✅ 프론트엔드 타입/빌드 클린
- ✅ 실제 버그 1건 QA에서 잡아 즉시 수정
- ⏭ 라이브 Gemma 4 연동 E2E는 수동 검증 항목으로 인계

**v2 merge 준비 완료.**
