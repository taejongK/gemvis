# Gemvis 사용자 데이터 영속성

> **목적**: 사용자 설정·검색 히스토리·학습 데이터가 재시작·업데이트 후에도 유지되도록 보장
> **작성일**: 2026-05-16
> **관련**: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md), [QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md)

---

## 📋 개요

Gemvis는 **프라이버시 우선** 원칙에 따라 모든 사용자 데이터를 **로컬에만 저장**합니다.
재시작·업데이트 후에도 "사용의 연속성"을 보장하기 위해 다음 데이터를 영구 보존합니다.

---

## 🗂️ 저장 위치 및 역할

### 1. 백엔드 영속성 (Python 기반)

| 파일 | 경로 | 역할 | 크기 (예시) | 복구 가능 |
|------|------|------|------------|----------|
| **preferences.json** | `~/.gemvis/preferences.json` | 사용자 설정 (감시 폴더, 언어, 이미지 분석) | ~200B | ❌ 수동 재설정 필요 |
| **graph.ttl** | `~/.gemvis/graph.ttl` | 지식그래프 (파일 메타데이터 + 엔티티 + 관계) | ~500KB (154 파일) | ⚠️ 재스캔으로 일부 복구 |
| **embeddings.npz** | `~/.gemvis/embeddings.npz` | 임베딩 벡터 (의미 검색용) | ~300KB | ⚠️ 재스캔으로 복구 |
| **events.ttl** | `~/.gemvis/events.ttl` | 파일 활동 이벤트 (생성/수정/삭제 시간) | ~80KB | ⚠️ 재스캔 시 일부 손실 (수정 이력 없음) |

#### preferences.json 스키마

```json
{
  "analyze_lang": "ko",
  "watch_dirs": [
    "/Users/username/Documents",
    "/Users/username/Downloads",
    "/Users/username/gemvis_watch",
    "/Users/username/Pictures"
  ],
  "analyze_images": true
}
```

**필드 설명**:
- `analyze_lang` (string): 분석 언어 (`ko` | `en`)
- `watch_dirs` (array): 감시 폴더 절대 경로 목록
- `analyze_images` (boolean): 이미지 파일 Vision 분석 여부

**저장 시점**: UI Settings 탭에서 "설정 저장" 클릭 또는 토글 변경 시

---

### 2. 프론트엔드 영속성 (localStorage 기반)

| Key | 데이터 | 역할 | 복구 가능 |
|-----|--------|------|----------|
| **gemvis.onboardingCompleted** | `'1'` | 온보딩 스플래시 표시 여부 | ✅ 설정에서 "온보딩 재설정" 가능 |
| **gemvis.searchSessions** | `JSON` | 대화 검색 세션 (질문·답변·파일 컨텍스트) | ❌ 손실 시 복구 불가 |
| **gemvis.activeSessionId** | `string` | 현재 활성 세션 ID | ❌ 자동 복구 (신규 세션 생성) |
| **gemvis.language** | `'ko'` \| `'en'` | UI 언어 | ✅ 언어 선택 버튼으로 재설정 |
| **gemvis.graphTheme** | `'default'` \| ... | 지식그래프 색상 테마 | ✅ 설정에서 재선택 |
| **gemvis.dockPosition** | `'left'` \| `'bottom'` | Floating Dock 위치 | ✅ 설정에서 재선택 |
| **gemvis.statusbar** | `'1'` \| `'0'` | 상태바 표시 여부 | ✅ `Ctrl+Shift+S`로 토글 |
| **gemvis.sessionsOpen** | `'1'` \| `'0'` | Search 탭 세션 목록 펼침 상태 | ✅ UI에서 다시 펼치기 |
| **gemvis.graphSettings.{key}** | `JSON` | 그래프 시각화 설정 (링크 거리, degree weight 등) | ✅ 기본값으로 리셋 가능 |

**저장 시점**: 각 설정 변경 즉시 localStorage에 자동 저장

---

## 🔄 설정 우선순위

### 감시 폴더 (`WATCH_DIRS`)

```
1순위: GEMVIS_WATCH_DIRS 환경변수 (개발자 오버라이드)
   ↓
2순위: ~/.gemvis/preferences.json (사용자가 UI에서 저장)
   ↓
3순위: default_dirs (Documents/Downloads/Pictures/gemvis_watch)
```

**중요**: `.env` 파일에 `GEMVIS_WATCH_DIR`이 설정되어 있으면 **preferences.json이 무시**됩니다.
- 사용자 설정 우선 원칙: `.env`의 `GEMVIS_WATCH_DIR` 주석 처리 권장

---

## 📊 데이터 손실 시나리오 및 복구

### 시나리오 A: preferences.json 삭제

**손실**:
- ❌ 감시 폴더 설정 → 기본 4개로 리셋
- ❌ 언어/이미지 분석 설정 → 기본값 (ko, true)

**복구**:
1. 설정 탭 열기
2. 폴더 재선택 + "설정 저장"
3. 언어/이미지 분석 토글 재설정

**예방**: preferences.json을 주기적으로 백업 (파일 크기 ~200B)

---

### 시나리오 B: graph.ttl / embeddings.npz 삭제

**손실**:
- ❌ 모든 파일 분석 결과 (카테고리, 요약, 엔티티)
- ❌ 지식그래프 관계
- ❌ 검색 인덱스

**복구**:
1. 설정 탭 → "모든 데이터 초기화 & 재스캔"
2. 또는 "기존 파일 스캔" 클릭
3. ⚠️ **단, 이전 분석 결과와 100% 동일 보장 불가** (LLM 비결정성)

**예방**: 
- `~/.gemvis/` 디렉터리 전체를 주기적으로 백업
- 또는 git으로 graph.ttl/embeddings.npz 버전 관리 (용량 주의)

---

### 시나리오 C: localStorage 삭제 (브라우저 캐시 클리어)

**손실**:
- ❌ 대화 검색 세션 (질문·답변 히스토리)
- ❌ UI 설정 (언어, 테마, dock 위치)
- ❌ 온보딩 완료 상태

**복구**:
- 대화 검색 세션: ❌ 복구 불가 (백엔드에 저장 안 됨)
- UI 설정: ✅ 각 설정 화면에서 재선택
- 온보딩: 설정 탭 → "온보딩 재설정" → `F5`

**예방**: 
- 중요한 검색 결과는 파일로 저장 (미구현, Phase 2 기능)
- 브라우저 설정에서 "사이트 데이터 보존" 활성화

---

### 시나리오 D: 앱 업데이트 후 호환성 문제

**잠재 리스크**:
- graph.ttl 스키마 변경 → 기존 노드 속성 누락
- preferences.json 스키마 변경 → 필드 미인식

**완화**:
1. 업데이트 전 `~/.gemvis/` 백업
2. [CHANGELOG.md](../CHANGELOG.md)에서 Breaking Changes 확인
3. 문제 발생 시 백업 복원 후 "재스캔"

---

## 🔒 프라이버시 보장

### 외부 전송 금지

**절대 전송되지 않는 데이터**:
- ✅ 파일 내용 (텍스트, 이미지, PDF)
- ✅ 파일 경로
- ✅ 엔티티 이름 (사람, 장소, 프로젝트)
- ✅ 대화 검색 히스토리

**검증 방법**:
1. 브라우저 DevTools → Network 탭
2. 백그라운드에서 파일 분석 중 필터 `All` 또는 `Fetch/XHR`
3. 확인: `localhost` 또는 `127.0.0.1` 요청만 존재
4. 확인: 외부 도메인 (`*.com`, `*.ai`) 요청 **0건**

**위반 시**: [.claude/rules/privacy.md](../.claude/rules/privacy.md) 참조, 즉시 차단

---

## 🧪 테스트 체크리스트

### 설정 연속성 테스트

**목표**: 재시작 후에도 사용자 설정이 유지되는지 확인

1. **감시 폴더 설정**
   - [ ] 설정 탭에서 폴더 4개 선택 + 저장
   - [ ] 백엔드 재시작 (`./scripts/stop_mac.sh && ./scripts/start_mac.sh`)
   - [ ] 설정 탭 다시 열기 → 4개 폴더 체크박스 모두 ON 확인

2. **언어 설정**
   - [ ] 설정 탭에서 언어 `English` 선택
   - [ ] `F5` 새로고침
   - [ ] UI가 영어로 표시되는지 확인

3. **그래프 테마**
   - [ ] 설정 탭에서 테마 `Aurora` 선택
   - [ ] 지식그래프 탭 이동 → 노드 색상 변경 확인
   - [ ] `F5` 새로고침 → 테마 유지 확인

4. **대화 검색 세션**
   - [ ] Search 탭에서 질문 3개 입력
   - [ ] `F5` 새로고침
   - [ ] 좌측 세션 목록에 3개 세션 남아있는지 확인

5. **온보딩 스플래시**
   - [ ] 설정 탭 → "온보딩 재설정" 클릭
   - [ ] `F5` 새로고침
   - [ ] HUD 스플래시 화면 다시 표시 확인

---

## 📁 백업 권장 사항

### 자동 백업 스크립트 (예시)

```bash
#!/usr/bin/env bash
# ~/gemvis_backup.sh

BACKUP_DIR=~/gemvis_backups
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/gemvis_data_$DATE.tar.gz" \
    ~/.gemvis/preferences.json \
    ~/.gemvis/graph.ttl \
    ~/.gemvis/embeddings.npz \
    ~/.gemvis/events.ttl

# 30일 이상 오래된 백업 삭제
find "$BACKUP_DIR" -name "gemvis_data_*.tar.gz" -mtime +30 -delete

echo "백업 완료: $BACKUP_DIR/gemvis_data_$DATE.tar.gz"
```

**사용**:
```bash
chmod +x ~/gemvis_backup.sh
# 매일 자동 실행 (cron)
crontab -e
# 0 2 * * * ~/gemvis_backup.sh  # 매일 새벽 2시
```

---

## 🚨 문제 해결

### Q: 설정 탭에서 추가한 폴더가 재시작 후 사라집니다

**원인**: `.env` 파일의 `GEMVIS_WATCH_DIR`이 `preferences.json`보다 우선순위 높음

**해결**:
```bash
# .env 파일 수정
nano .env
# GEMVIS_WATCH_DIR 줄을 주석 처리:
# GEMVIS_WATCH_DIR=/Users/username/gemvis_watch

# 백엔드 재시작
./scripts/stop_mac.sh && ./scripts/start_mac.sh
```

---

### Q: 대화 검색 히스토리가 브라우저 재시작 후 사라집니다

**원인**: 브라우저 시크릿 모드 사용 또는 "종료 시 쿠키 삭제" 설정

**해결**:
- 일반 모드에서 Gemvis 사용
- 브라우저 설정 → 사이트별 권한 → `localhost` → "쿠키 허용"

---

### Q: graph.ttl 파일이 너무 커져서 느려집니다 (>10MB)

**원인**: 수천 개 파일 분석 시 노드/엣지 증가

**해결**:
1. 불필요한 파일 제외 (설정 탭에서 특정 폴더 체크 해제)
2. "모든 데이터 초기화" → 필요한 파일만 재스캔
3. (Phase 2) 아카이브 기능으로 오래된 파일 비활성화

---

## 📝 참고 문서

- [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) — GemInsight SSoT 설계
- [QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md) — 수동 검증 체크리스트
- [.claude/rules/privacy.md](../.claude/rules/privacy.md) — 프라이버시 규칙
- [API_CONTRACT.md](../API_CONTRACT.md) — 프론트↔백 API 계약

---

**Last Updated**: 2026-05-16
**Status**: v2 기준 (geminsight-develop 머지 후)
