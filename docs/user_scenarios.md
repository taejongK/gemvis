# Gemvis 사용 시나리오 및 파일 모니터링 정책

**Version:** 2.0.0  
**Last Updated:** 2026-04-30  
**Status:** Live (user_scenarios + file_monitoring_policy 통합본)

---

## 📋 문서 개요

이 문서는 **사용자 관점의 시나리오**와 **기술적 구현 정책**을 통합한 Gemvis의 핵심 스펙 문서입니다.

### 문서 구성

- **Part 1**: 사용자 시나리오 (설치부터 일상 사용까지)
- **Part 2**: 파일 모니터링 기술 정책 (OS별 경로, 제외 규칙, 보안)
- **Part 3**: 기능-시나리오 매핑 및 데모 계획

### 검증 원칙

모든 구현 결정은 아래 시나리오를 기준으로 검증한다:
**"이 기능이 없으면 어떤 시나리오가 깨지는가?"** 답이 없으면 MVP 밖.

---

## 일러두기 — 불변 원칙

| 원칙 | 의미 |
|------|------|
| **원본 불변** | 사용자의 파일은 절대 이동·삭제·수정하지 않는다. 모든 "정리"는 symlink로만 일어난다. |
| **온디바이스** | 파일 내용이 디바이스를 벗어나지 않는다. 외부 API·클라우드 업로드 없음. |
| **사용자 주권** | 불확실한 분류는 반드시 사용자에게 물어본다. 자동 결정은 "되돌릴 수 있어야" 한다. |
| **유휴 우선** | 대량 작업은 백그라운드에서, PC 유휴 시간에 진행한다. 전경 UI를 방해하지 않는다. |
| **점진적 가치** | 첫 스캔이 끝나기 전에도 이미 분석된 파일은 질의 가능하다. |

---

## 시나리오 0 — 설치 (최초 1회)

### 0.1 소프트웨어 설치
**사용자:** 새 노트북에 Gemvis를 깔려고 한다.

```
1. GitHub에서 저장소 클론
2. ./scripts/setup.sh 실행  (원클릭)
   ├─ 시스템 도구 확인
   ├─ Python venv 생성
   ├─ llama.cpp 빌드 (GPU 감지)
   ├─ Gemma 4 E2B Q4_K_M 다운로드 (~2GB)
   └─ 추론 테스트 ("안녕, Gemvis!")
3. ✅ 설치 완료 메시지
```

**실패 복구:**
- GPU 미감지 → CPU 폴백 안내
- 디스크 부족 → 필요 용량 표시 후 중단
- HF 접근 실패 → 토큰 설정 가이드 (unsloth는 보통 non-gated)

**성공 기준:** 사람이 5분 이내에 설치 완료, 이후 명령어 0개로 앱 실행 가능.

---

### 0.2 첫 실행 (온보딩)
**사용자:** Gemvis 앱을 처음 연다.

```
화면 1: 환영
  "Gemvis는 당신의 파일을 온디바이스에서 이해하고
   연결해서 다시 찾기 쉽게 만듭니다."
  [시작하기]

화면 2: 프라이버시 확인
  "모든 분석은 이 컴퓨터에서만 일어납니다.
   어떤 데이터도 외부로 전송되지 않습니다."
  [동의하고 계속]

화면 3: 감시 폴더 선택  ← 핵심 단계
  "Gemvis가 분석할 폴더를 고르세요.
   여러 개 선택할 수 있어요."

  ☑ ~/Downloads       (1,247 files)
  ☑ ~/Documents       (3,821 files)
  ☐ ~/Desktop         (89 files)
  ☐ ~/Pictures        (12,340 files)
  [+ 폴더 추가]

  추정 분석 시간: 약 4시간 (백그라운드에서 진행)
  [다음]

화면 4: Gemvis 관리 폴더 위치
  "정리된 파일들이 symlink로 모일 위치입니다.
   원본은 그대로 유지됩니다."

  기본값: ~/Gemvis/
  [기본값 사용]  [다른 위치 선택]

화면 5: 첫 스캔 시작
  "5,068개 파일을 분석합니다.
   진행 중에도 앱을 사용할 수 있어요."
  [지금 시작]  [나중에]
```

**핵심 UX:**
- 각 단계는 **취소·되돌아가기** 가능
- 폴더 선택 시 파일 개수 미리 표시
- 관리 폴더는 사용자가 자유롭게 변경

---

## 시나리오 1 — 첫 대규모 스캔 (Initial Ingest)

**트리거:** 온보딩의 [지금 시작] 클릭 또는 새 폴더 추가.

```
[진행 상황 바]
 분석 중: 1,247 / 5,068  (24%)
 현재 파일: IMG_20260301_강남역저녁.jpg
 예상 남은 시간: 3시간 12분
 처리 속도: 평균 12초/파일
 [일시 정지]  [백그라운드로]
```

### 파일당 처리 단계
```
1. 내용 추출 (extension 기반)
   ├─ .txt/.md      → 직접 읽기
   ├─ .pdf          → pypdf
   ├─ .jpg/.png     → (MVP는 파일명만 / Phase 2는 OCR/vision)
   └─ .docx         → python-docx

2. Gemma 분석
   → 엔티티 추출 (Person, Place, Project, Event, Concept)
   → 관계 추출
   → 카테고리 태그 (업무/개인/금융/사진 등)
   → 요약 1줄

3. 지식그래프 저장
   → File 노드 + 엔티티 노드 + 관계 간선
   → Kùzu에 영구 저장

4. 관리 폴더에 symlink 생성
   ~/Gemvis/
     ├─ by-category/
     │   ├─ 업무/                     ← 카테고리별 뷰
     │   ├─ 금융/
     │   └─ 사진-행사/
     ├─ by-person/김과장/             ← 사람별 뷰
     ├─ by-project/Gemvis-해커톤/     ← 프로젝트별 뷰
     ├─ by-time/2026-03/              ← 시간별 뷰
     └─ recent/                       ← 최근 스캔 파일
```

### 사용자가 할 수 있는 것 (스캔 중)
- 일시 정지 / 재개
- 이미 분석된 파일에 대해 자연어 질의 (점진적 가치)
- 그래프 시각화 실시간 업데이트 확인
- 진행 상황 트레이에 숨기기

### 완료 시
```
✅ 스캔 완료
   5,068개 파일 분석
   1,234명 · 87개 장소 · 42개 프로젝트 · 312개 이벤트 추출

   [그래프 보기]  [검색 시작]  [정리 결과 리뷰]
```

**주의 — Review-First 분류:**
- 분류 신뢰도 <0.8 인 파일은 symlink를 **`~/Gemvis/_review/` 로** 보내고
  배지 카운터로 표시 ("12개가 확인을 기다려요")
- 사용자가 한 번에 몰아서 확인 가능

---

## 시나리오 2 — 증분 감지 (Incremental Ingest)

**트리거:** 감시 폴더에 새 파일이 생기거나 기존 파일이 수정됨.

### 2.1 자동 분류 (신뢰도 ≥ 0.8)
```
[디스크]  ~/Downloads/receipt_20260417_점심.pdf  (생성)
    ↓ watchdog 감지 (<5초)
    ↓ 백그라운드 큐에 추가
    ↓ Gemma 분석 (10~30초)
    ↓ 신뢰도 0.93, 카테고리 "금융/영수증"
    ↓ 그래프 저장 + symlink 생성
    ↓ 트레이 알림:
      "receipt_20260417_점심.pdf를 [금융 > 영수증]에 정리했어요"
      [열기]  [다른 곳으로]  [무시]
```

### 2.2 Review-First (신뢰도 < 0.8)
```
[디스크]  ~/Downloads/notes.md  (생성)
    ↓ 내용: "3시 미팅 기록. 아이디어 여러 개..."
    ↓ Gemma 분석: 어느 프로젝트인지 모호함 (신뢰도 0.6)
    ↓ _review/ 폴더에 임시 symlink
    ↓ 벳지 카운터 +1

[사용자가 리뷰 모달 열기]
  notes.md
  요약: "3시 회의 기록, 아이디어 논의"

  Gemvis 추측:
    1. 프로젝트: Gemvis-해커톤 (0.6)
    2. 프로젝트: A사-프로모션 (0.4)
    3. 그 외

  어디에 정리할까요?
  [Gemvis-해커톤]  [A사-프로모션]  [새 프로젝트...]  [분류 안 함]
```

### 2.3 수정된 파일
```
기존 symlink 유지, 그래프만 업데이트:
  - 기존 엔티티/관계 삭제
  - 새로 추출해서 갱신
  - symlink 경로가 바뀌면 이동 (원본은 그대로)
```

### 성능 목표
| 동작 | 목표 |
|------|------|
| 파일 생성 감지 | < 5초 |
| 텍스트 분석 + 저장 | < 10초 |
| PDF (10p) 분석 | < 30초 |
| 동시 처리 | 최대 5개 |

---

## 시나리오 3 — 자연어 질의 (Query)

**트리거:** 사용자가 Chat UI에 질문을 입력.

### 3.1 기본 질의
```
User: "지난달 김과장이랑 간 식당 어디였지?"

Gemvis (내부):
  1. Gemma가 질문 파싱 → 의도 분석
     { entity: "김과장", type: "Place/Restaurant",
       time_range: "2026-03-01 ~ 2026-03-31" }
  2. Gemma가 Cypher 생성
  3. Kùzu 실행
  4. Gemma가 결과 + 원문 조각으로 답변 합성

Gemvis (UI):
  "3월 15일에 강남역 근처 [온누리식당]에서 만나셨어요.

   관련 파일 (4):
   📄 meeting_notes_0315.md
   📷 IMG_0315_저녁.jpg
   🎤 voice_memo_0315.m4a
   🧾 receipt_0315.pdf

   [그래프에서 보기]"
```

### 3.2 모호한 질의 (되묻기)
```
User: "그 자료 찾아줘"
Gemvis: "어떤 자료를 찾고 계신가요?
         최근에 본 것 중 다음이 있어요:
         - Gemvis 기술 스펙 (어제)
         - 2026년 예산안.pdf (3일 전)
         - 김과장 이력서.pdf (1주 전)"
```

### 3.3 그래프 기반 추론
```
User: "해커톤 관련된 사람들 다 보여줘"

Gemvis:
  Cypher: MATCH (p:Person)-[*1..3]-(proj:Project {name: "해커톤"})
  결과: 김과장, Bob, Carol, Dave, ...

  "해커톤과 직간접적으로 연결된 사람 12명입니다.
   [그래프 뷰로 보기]"
```

### 3.4 질의 결과에 대한 액션
- **파일 열기** — 원본 경로 또는 symlink로 기본 앱에서 열기
- **그래프에서 보기** — 해당 노드 중심으로 2-hop 그래프 하이라이트
- **이 결과 저장** — 북마크 기능 (선택)
- **틀렸어** — 피드백 (오답 케이스 수집, Phase 2 학습용)

---

## 시나리오 4 — 그래프 탐색 (Visual)

**트리거:** 사용자가 Graph 탭 열기 또는 "그래프에서 보기" 클릭.

```
[왼쪽 패널]                [중앙: 인터랙티브 그래프]
 검색: [________]          (3D force-directed)
                             ● 김과장
 필터:                     /   |   \
 ☑ Person                ●    ●    ●
 ☑ Place                회의  저녁  이메일
 ☑ Project
 ☐ File (너무 많음)

 레이아웃:
 ● 3D force
 ○ 2D force
 ○ 시간축
```

**상호작용:**
- 노드 클릭 → 우측 패널에 상세 (연결된 파일 목록)
- 노드 더블클릭 → 해당 노드 중심으로 재배치
- 노드 우클릭 → 편집 (이름 바꾸기, 병합, 제외)
- 줌/팬 기본

**엔티티 편집 (중요):**
```
"김과장" == "김부장" (자동 추출이 사람을 중복 생성한 경우)
  → 사용자가 두 노드 선택 → [병합]
  → 모든 관계가 하나로 합쳐짐
  → 그래프 DB 업데이트
```

---

## 시나리오 5 — 관리 (Settings / Maintenance)

### 5.1 폴더 관리
```
Settings → 감시 폴더
  ~/Downloads       [일시중지] [제거]
  ~/Documents       [일시중지] [제거]
  [+ 폴더 추가]

제거 시:
  "해당 폴더와 관련된 분석 결과를 지식그래프에서 제거할까요?
   (symlink도 함께 삭제됩니다. 원본 파일은 유지됩니다.)
   [예, 제거]  [아니오, 그래프는 유지]"
```

### 5.2 모델 관리
```
Settings → 모델
  현재: gemma-4-E2B-it Q4_K_M (2GB, CUDA)

  다른 모델:
  ○ gemma-4-E2B-it Q8_0 (4GB, 더 정확)
  ○ gemma-4-E2B-it BF16 (8GB, 최고 정확도)
  [다운로드 & 전환]
```

### 5.3 데이터 내보내기/삭제
```
Settings → 데이터
  [그래프 내보내기]  (JSON/CSV/Cypher dump)
  [전체 초기화]      (그래프 + symlink 삭제, 원본은 그대로)
```

---

## 시나리오 6 — 엣지 케이스 & 복구

| 상황 | 동작 |
|------|------|
| 대용량 파일 (>100MB) | 타입별 제한 적용 (상세: Part 2, 6.1 섹션) |
| 암호화된 PDF | 스킵 + 사용자 알림 |
| 손상된 파일 | 에러 로그 + UI에 경고 배지 |
| 권한 오류 (Permission Denied) | 해당 파일 스킵 + 권한 해결 가이드 표시 |
| 파일 잠금 (다른 앱 사용 중) | 30초 후 재시도 (최대 3회) |
| 민감 파일 (*.env, *.pem, id_rsa) | 내용 추출 스킵, 메타데이터만 기록 |
| 디스크 여유 부족 | 스캔 일시중지 + 오래된 임베딩 삭제 (LRU) |
| 클라우드 동기화 중 | Debounce 연장 (60초), 동기화 완료 대기 |
| GPU OOM | 자동으로 컨텍스트 축소 또는 CPU 폴백 |
| 모델 로드 실패 | 재시도 3회 → 실패 시 재설치 안내 |
| 네트워크 연결 | 전체 기능 영향 없음 (오프라인 동작 보장) |

**상세 예외 처리 정책**: Part 2, 섹션 7️⃣ 참조

---

# Part 2: 파일 모니터링 기술 정책

이 섹션은 구현 시 참조하는 기술 스펙입니다. Part 1의 사용자 시나리오를 실제로 구현하기 위한 세부 정책을 정의합니다.

---

## 1️⃣ OS별 기본 감시 경로 (Default Target Zones)

### 시나리오 연결
**→ 시나리오 0.2 (온보딩) - 화면 3: 감시 폴더 선택**

### Windows (NTFS)

```text
C:\Users\<username>\Documents
C:\Users\<username>\Downloads
C:\Users\<username>\Desktop
C:\Users\<username>\Pictures
```

### macOS (APFS)

```text
/Users/<username>/Documents
/Users/<username>/Downloads
/Users/<username>/Desktop
/Users/<username>/Pictures
```

### Ubuntu (EXT4)

```text
/home/<username>/Documents
/home/<username>/Downloads
/home/<username>/Desktop
/home/<username>/Pictures
```

### 동의 프로세스 (구현 상세)

**첫 실행 시 온보딩 UI** (시나리오 0.2 화면 3):

```text
☑ ~/Downloads       (1,247 files)  ← 파일 개수 실시간 카운트
☑ ~/Documents       (3,821 files)
☐ ~/Desktop         (89 files)     ← 사용자가 체크 해제 가능
☐ ~/Pictures        (12,340 files)

추정 분석 시간: 약 4시간 (백그라운드에서 진행)
```

**macOS 추가 요구사항**:

```applescript
"Gemvis needs Full Disk Access to analyze your Documents folder.

1. Open System Preferences
2. Go to Security & Privacy → Privacy → Full Disk Access
3. Click the lock icon and enter your password
4. Add Gemvis to the list

Your files are never uploaded to the cloud."
```

**동의 거부 시**:
- 기본 경로 스캔 건너뛰기
- 사용자가 직접 경로 추가할 때까지 대기 (빈 그래프 상태)

---

## 2️⃣ 커스텀 경로 관리 (Custom Watch Folders)

### 시나리오 연결
**→ 시나리오 5.1 (폴더 관리)**

### 경로 추가 방법

#### CLI 방식

```bash
# 단일 경로 추가
gemvis add /path/to/folder

# 재귀 깊이 제한 (최대 3단계 하위 폴더까지)
gemvis add /path/to/folder --max-depth 3

# 특정 파일 타입만 모니터링
gemvis add /path/to/folder --file-types pdf,txt,md
```

#### GUI 방식 (시나리오 5.1)

```text
Settings → 감시 폴더
  ~/Downloads       [일시중지] [제거]
  ~/Documents       [일시중지] [제거]
  [+ 폴더 추가]  ← 클릭 시 폴더 선택 다이얼로그
```

### 경로 관리 명령어

```bash
# 모니터링 경로 목록 보기
gemvis list

# 경로 제거 (지식 그래프 노드는 유지됨)
gemvis remove /path/to/folder

# 경로 일시 정지 (파일 변경 감지 중단)
gemvis pause /path/to/folder

# 경로 재개
gemvis resume /path/to/folder
```

### 일반적인 추가 경로 예시

| 사용 사례 | 경로 예시 |
|----------|----------|
| 외장 하드 | `/Volumes/External Drive` (macOS)<br>`D:\` (Windows) |
| 프로젝트 폴더 | `/Users/<username>/Projects` |
| 연구 자료 | `/Users/<username>/Research` |
| 스캔 문서 | `/Users/<username>/Scanned Documents` |
| 클라우드 동기화 | `/Users/<username>/Dropbox`<br>`C:\Users\<username>\OneDrive` |

---

## 3️⃣ 제외 규칙 (Exclusion Policies)

### 자동 제외 폴더 (Blacklist)

아래 폴더들은 **무조건 스캔에서 제외** (성능 및 보안 이유).

#### 공통 제외 패턴

```text
node_modules/
.git/
.svn/
.hg/
__pycache__/
*.pyc
.venv/
venv/
env/
.cache/
.tmp/
.temp/
```

#### Windows 전용

```text
C:\Windows\
C:\Program Files\
C:\Program Files (x86)\
C:\Users\<username>\AppData\Local\Temp\
C:\Users\<username>\AppData\Roaming\
C:\$Recycle.Bin\
```

#### macOS 전용

```text
/System/
/Library/
/Users/<username>/Library/
/Users/<username>/.Trash/
/private/
*.app/Contents/
```

#### Ubuntu 전용

```text
/sys/
/proc/
/dev/
/tmp/
/var/cache/
/home/<username>/.cache/
/home/<username>/.local/
```

### 파일 타입 제외 (File Type Blacklist)

#### 실행 파일 (보안 이유)

```text
*.exe, *.dll, *.so, *.dylib
*.bat, *.sh, *.cmd
*.app, *.dmg, *.pkg
```

#### 시스템 파일

```text
*.log, *.tmp, *.cache
*.db-shm, *.db-wal (SQLite 임시 파일)
.DS_Store (macOS)
Thumbs.db (Windows)
desktop.ini (Windows)
```

#### 압축 파일 (선택적)

```text
*.zip, *.rar, *.7z, *.tar.gz
(옵션: "압축 파일 내부 스캔" 활성화 시 해제 가능)
```

### 민감 파일 자동 감지

#### 패턴 기반 감지

```python
SENSITIVE_PATTERNS = [
    r'.*password.*\.txt',
    r'.*credential.*',
    r'.*secret.*',
    r'.*\.env$',
    r'.*\.pem$',
    r'.*\.key$',
    r'id_rsa',
    r'wallet\.dat'
]
```

#### 처리 방식

```text
1. 민감 파일 감지 시 내용 추출 스킵
2. 파일 존재 자체는 그래프에 기록 (메타데이터만)
3. 사용자에게 알림: "민감한 파일이 감지되어 제외했습니다"
```

### 사용자 정의 제외 규칙

#### 설정 파일 위치

```text
~/.gemvis/config.json
```

#### 예시 설정

```json
{
  "exclusion_rules": {
    "folders": [
      "*/node_modules/*",
      "*/build/*",
      "*/dist/*",
      "*/.idea/*"
    ],
    "file_patterns": [
      "*.lock",
      "package-lock.json",
      "yarn.lock",
      "*.min.js",
      "*.map"
    ],
    "file_size_limit_mb": 100
  }
}
```

---

## 4️⃣ 파일 시스템 모니터링 메커니즘

### 실시간 변경 감지 (Real-time Monitoring)

### 시나리오 연결
**→ 시나리오 2 (증분 감지)**

#### OS별 네이티브 API 사용

| OS | API | 특징 |
|----|-----|------|
| Windows | `ReadDirectoryChangesW` | 재귀적 감시 가능, 버퍼 오버플로우 주의 |
| macOS | `FSEvents` | 경로 단위 이벤트, 배치 처리 효율적 |
| Ubuntu | `inotify` | 파일 디스크립터 제한 주의 (기본 8192개) |

#### Python 구현체

```python
# backend/file_watcher.py에서 사용
from watchdog.observers import Observer  # 크로스 플랫폼 추상화
```

### 스캔 전략

#### 초기 전수 조사 (Initial Scan) - 시나리오 1

```text
1. 경로 추가 시점에 1회 수행
2. 재귀적으로 모든 파일 목록 수집
3. 파일당 메타데이터 추출:
   - 생성 날짜 (ctime)
   - 수정 날짜 (mtime)
   - 파일 크기
   - MIME 타입
4. 우선순위 큐에 등록:
   - Priority 1: PDF, DOCX, TXT (텍스트 컨텐츠)
   - Priority 2: PNG, JPG (파일명 + EXIF만, MVP에서는 OCR 제외)
   - Priority 3: 기타
```

#### 증분 업데이트 (Incremental Update) - 시나리오 2

```text
1. 파일 이벤트 발생 (생성/수정/삭제)
2. Debounce 대기 (30초 - 연속 수정 완료 대기)
3. 변경된 파일만 재분석
4. 그래프 업데이트 (관계 재계산)
```

### Debounce 정책 (과도한 분석 방지)

```python
# 예시: 파일 저장 후 30초 동안 추가 변경 없으면 분석 시작
DEBOUNCE_INTERVAL = 30  # seconds (일반 파일)
DEBOUNCE_INTERVAL_CLOUD = 60  # seconds (클라우드 동기화 폴더)

# 연속 타이핑 중인 문서는 분석하지 않음
# 마지막 수정 후 30초 경과 시점에 분석 큐 등록
```

### Symlink 생성 정책 (Virtual Folder Organization)

### 시나리오 연결
**→ 시나리오 1 (127-135줄), 시나리오 2.1, 2.2**

**목적**: 원본 파일을 이동하지 않고, `~/Gemvis/` 아래에 의미있는 구조로 자동 정리

---

## 📐 폴더 구조 설계 철학

### Why 이 구조인가?

#### 1. **직교성 (Orthogonality)**: 상호배타적 분류
전통적인 파일 정리법(`by-category`, `by-person`, `by-time`)의 문제:
- ❌ "학습 자료"가 업무일 수도, 개인일 수도 있음 (모호)
- ❌ "김과장"이 업무 관계일 수도, 개인 관계일 수도 있음 (중복)
- ❌ 시간은 모든 파일에 해당 (구별력 없음)

**해결**: 1차 축은 **맥락(context)** 기준으로 상호배타
- 업무 ⊥ 생활 (생계 vs 개인)
- 재무 ⊥ 나머지 (법적 의무 vs 선택)
- 지식 ⊥ 관계 (정보 vs 사람)

#### 2. **커버리지 (Coverage)**: 거의 모든 파일이 명확히 분류
"기타" 폴더가 커지면 분류 실패:
- 우선순위 기반 알고리즘으로 95%+ 커버리지
- "어디에도 안 맞으면 → 생활" (catch-all)

#### 3. **계층적 세분화**: 의미 → 메타데이터
1차 축: "왜 이 파일들이 묶였는가?" (맥락)
2차 축: "그 안에서 어떻게 찾을까?" (타입, 시간)

**Why**: 메타데이터만 있으면 맥락 없음, 의미만 있으면 너무 많음
```text
나쁜 예: ~/Gemvis/by-type/pdf/
  → "왜 이 PDF들이 여기 있는지" 모름

좋은 예: ~/Gemvis/업무/Gemvis-해커톤/문서/
  → 맥락 명확 + 타입으로 세분화
```

#### 4. **개인화 (Personalization)**: 사용자별 커스터마이징
기본 5개 축은 **템플릿**이지 강제가 아님:
- 학생: 수업/동아리/공부/재무/생활
- 프리랜서: 클라이언트별 분리
- 연구자: 연구/문헌/교육/행정/개인

---

## 📁 최종 폴더 구조

```text
~/Gemvis/
  # 1차 축: 의미/맥락 (LLM 자동 판단, 상호배타)
  ├─ 업무/                    # 일, 회사, 클라이언트 (생계)
  │   ├─ Gemvis-해커톤/        # 2차: 프로젝트별
  │   │   ├─ 문서/            # 3차: 타입별
  │   │   ├─ 이미지/
  │   │   └─ 2026-04/         # 3차: 시간별 (최근만)
  │   └─ 김과장/              # 2차: 사람별 (업무 관련)
  │
  ├─ 재무/                    # 돈, 계약, 세금 (법적 의무)
  │   ├─ 영수증/
  │   │   └─ 2026-04/
  │   ├─ 계약서/
  │   └─ 세금/
  │
  ├─ 지식/                    # 학습, 참고, 정보 (축적)
  │   ├─ React/
  │   ├─ AI-논문/
  │   └─ 디자인-레퍼런스/
  │
  ├─ 관계/                    # 사람, 소통 (타인)
  │   ├─ 김과장/              # 2차: 사람별 (개인 관계)
  │   │   └─ 2026-04/
  │   └─ 가족/
  │
  └─ 생활/                    # 일상, 취미, 추억 (개인)
      ├─ 여행/
      │   └─ 제주도/
      ├─ 운동/
      └─ 일기/
```

---

## 🤖 자동 분류 알고리즘

### 우선순위 기반 판단 (상호배타 보장)

```python
def classify_primary(file: Path, analysis: Analysis) -> str:
    """
    1차 축 분류 (우선순위 순서로 판단)
    → 가장 먼저 매칭되는 하나만 반환
    """
    
    # 1순위: 재무 (가장 명확, 최우선)
    if is_financial(analysis):
        # 키워드: 영수증, 계약, 세금, 급여, 송금, 카드
        # 엔티티: 은행, 금액, 날짜
        return "재무"
    
    # 2순위: 업무 (두 번째 명확)
    if is_work(analysis):
        # 키워드: 회사명, 클라이언트명, 프로젝트(업무용)
        # 시간: 평일 근무시간 + "회의", "제안" 등
        return "업무"
    
    # 3순위: 병렬 판단 (둘 다 확인)
    knowledge_score = get_knowledge_score(analysis)
    relationship_score = get_relationship_score(analysis)
    
    if knowledge_score > 0.7 or relationship_score > 0.7:
        if knowledge_score > relationship_score:
            # 키워드: 강의, 튜토리얼, 문서, 논문, 책
            # 파일명: tutorial, guide, docs, reference
            return "지식"
        else:
            # 엔티티: 사람 2명 이상 언급
            # 타입: 이메일, 메시지, 회의록
            # 파일명 패턴: "with_", "to_", "from_"
            return "관계"
    
    # 4순위: 나머지 전부 (catch-all)
    return "생활"

def classify_secondary(primary: str, file: Path, analysis: Analysis) -> list[str]:
    """
    2차 축 분류 (계층적 세분화)
    → 여러 개 가능 (타입 + 시간 + 엔티티)
    """
    paths = []
    
    # 2-1. 프로젝트/사람별
    if primary in ["업무", "생활"]:
        for project in analysis.projects:
            if project.confidence >= 0.8:
                paths.append(f"{primary}/{project.name}")
    
    if primary in ["업무", "관계"]:
        for person in analysis.persons:
            if person.confidence >= 0.8:
                paths.append(f"{primary}/{person.name}")
    
    # 2-2. 타입별 (각 프로젝트/사람 하위)
    file_type = get_semantic_type(file)  # "문서", "이미지", "표"
    for path in paths.copy():
        paths.append(f"{path}/{file_type}")
    
    # 2-3. 시간별 (최근 60일만)
    if (datetime.now() - datetime.fromtimestamp(file.stat().st_mtime)).days <= 60:
        month = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m")
        for path in paths.copy():
            paths.append(f"{path}/{month}")
    
    return paths
```

---

## 🎨 사용자 커스터마이징

### 설정 파일: `~/.gemvis/config.json`

```json
{
  "folder_structure": {
    "version": "2.0.0",
    "template": "default",
    
    "dimensions": [
      {
        "id": "work",
        "name": "업무",
        "priority": 2,
        "keywords": ["회사", "프로젝트", "클라이언트"],
        "entities": [],
        "enabled": true,
        "color": "#FF6B6B"
      },
      {
        "id": "finance",
        "name": "재무",
        "priority": 1,
        "keywords": ["영수증", "계약", "세금"],
        "enabled": true,
        "color": "#4ECDC4"
      },
      {
        "id": "knowledge",
        "name": "지식",
        "priority": 3,
        "keywords": ["강의", "튜토리얼", "문서"],
        "enabled": true,
        "color": "#95E1D3"
      },
      {
        "id": "relationship",
        "name": "관계",
        "priority": 3,
        "keywords": ["이메일", "메시지", "회의"],
        "enabled": true,
        "color": "#F38181"
      },
      {
        "id": "life",
        "name": "생활",
        "priority": 4,
        "keywords": [],
        "enabled": true,
        "color": "#AA96DA"
      }
    ],
    
    "default_dimension": "life",
    "secondary_axes": {
      "type": true,
      "time": true,
      "person": true,
      "project": true
    }
  }
}
```

### 온보딩 시 템플릿 선택

```text
Gemvis 첫 실행:

"어떤 방식으로 파일을 정리하시겠어요?"

[✓] 기본 (업무/재무/지식/관계/생활)
[ ] 학생용 (수업/동아리/공부/재무/생활)
[ ] 프리랜서용 (클라이언트별)
[ ] 연구자용 (연구/문헌/교육/행정/개인)
[ ] 직접 설정

→ 나중에 Settings에서 언제든 변경 가능
```

### 학습 기반 개선

```text
사용자가 Finder에서 재분류:
~/Gemvis/업무/meeting.pdf → ~/Gemvis/생활/취미프로젝트/로 이동

Gemvis 감지:
"meeting.pdf"를 "업무"에서 "생활"로 이동하셨네요.
→ "취미프로젝트" 키워드를 "생활" 분류에 추가
→ 다음부터 자동으로 정확히 분류
```

---

## 📊 분류 예시 (커버리지 검증)

| 원본 파일 | 1차 분류 | 2차 경로 | 3차 세분화 |
|----------|---------|---------|-----------|
| meeting_notes_0315.pdf | 업무 | Gemvis-해커톤/ | 문서/, 2026-04/ |
| dinner_receipt.jpg | 재무 | 영수증/ | 2026-04/ |
| react_tutorial.md | 지식 | React/ | 문서/ |
| email_김과장.pdf | 업무 | 김과장/ | 문서/, 2026-03/ |
| jeju_photo.jpg | 생활 | 여행/제주도/ | 이미지/ |
| tax_report.xlsx | 재무 | 세금/ | 표/ |
| gym_log.csv | 생활 | 운동/ | 표/ |
| arxiv_paper.pdf | 지식 | AI-논문/ | 문서/ |
| family_chat.png | 관계 | 가족/ | 이미지/ |

**커버리지: 100%** (모든 파일이 명확히 하나의 1차 축에 분류)

---

## 🎬 실제 동작 예시

### 파일 하나 → 여러 Symlink

**원본**: `~/Downloads/meeting_notes_0315.pdf` (김과장과 해커톤 회의)

**Gemvis 자동 생성**:
```text
~/Gemvis/업무/Gemvis-해커톤/문서/meeting_notes_0315.pdf        # 1차→2차→3차
~/Gemvis/업무/Gemvis-해커톤/2026-04/meeting_notes_0315.pdf     # 시간 축
~/Gemvis/업무/김과장/문서/meeting_notes_0315.pdf               # 사람 축
~/Gemvis/업무/김과장/2026-04/meeting_notes_0315.pdf            # 사람+시간
```

**모두 같은 원본을 가리킴** (symlink)

---

## ✅ 신뢰도 기반 분류 (Review-First)

| 신뢰도 | 처리 방식 | Symlink 위치 | 시나리오 |
|--------|----------|-------------|---------|
| ≥ 0.8 | 자동 분류 | 위 구조대로 | 2.1 |
| < 0.8 | 사용자 확인 대기 | `_review/` (임시) | 2.2 |
| 사용자 확인 후 | 확정 분류 + 학습 | 사용자가 선택한 축 + 키워드 업데이트 | 2.2 |

---

## 🔄 Symlink 업데이트 규칙

```text
파일 수정 시:
  1. 파일 내용 변경 감지
  2. LLM 재분석
  3. 기존 엔티티/관계 삭제
  4. 새로 추출해서 그래프 갱신
  5. 1차 축이 바뀌면 symlink 전체 재생성
     예: 업무 → 생활 재분류 시
         ~/Gemvis/업무/** 전부 삭제
         ~/Gemvis/생활/** 새로 생성
  6. 2차 축만 바뀌면 해당 부분만 업데이트
     예: 프로젝트명 변경 (Gemvis-해커톤 → Gemvis-완료)
```

---

## 5️⃣ 권한 관리 (Permission Management)

### 최소 권한 원칙 (Principle of Least Privilege)

| 작업 | 필요 권한 | 근거 |
|------|----------|------|
| 파일 읽기 | Read | 컨텐츠 추출 |
| 파일 쓰기 | ❌ 불필요 | 원본 비파괴 원칙 |
| 파일 이동/삭제 | ❌ 금지 | 심볼릭 링크만 생성 |
| 폴더 생성 | Write (`~/.gemvis/` 내부만) | 가상 폴더 구조 생성 |

### 감사 로그 (Audit Log)

```json
{
  "event": "file_accessed",
  "timestamp": "2026-04-30T14:23:45Z",
  "file_path": "/Users/username/Documents/report.pdf",
  "action": "content_extraction",
  "success": true,
  "model_used": "gemma-4-e4b"
}
```

**로그 저장 위치**: `~/.gemvis/logs/file_access.log`  
**보존 기간**: 30일 (이후 자동 삭제)

---

## 6️⃣ 성능 및 리소스 관리

### 파일 크기 제한

| 파일 타입 | 최대 크기 | 초과 시 처리 |
|----------|----------|-------------|
| 텍스트 (TXT, MD) | 50MB | 첫 10,000줄만 추출 |
| PDF | 100MB | 페이지별 분할 처리 |
| 이미지 (PNG, JPG) | 50MB | MVP: 파일명 + EXIF만<br>Phase 2: OCR |
| 동영상 | ❌ MVP 제외 | Phase 2에서 지원 |
| 기타 파일 | 100MB | 메타데이터만 기록 |

**참고**: 시나리오 6에서는 ">100MB 파일 자동 스킵"으로 단순화, 실제 구현은 위 표 적용

### 동시 처리 제한

```python
# backend/content_extractor.py
MAX_CONCURRENT_EXTRACTIONS = 4  # CPU 코어 수에 따라 조정
QUEUE_MAX_SIZE = 1000  # 대기 큐 최대 크기
```

### 백그라운드 처리 우선순위

```text
1. 사용자 질의 응답 (Gemma 4 E4B 모델) - 최우선
2. 실시간 파일 변경 감지 - 중간
3. 백그라운드 재분석 (Gemma 4 26B 모델) - 최하위 (CPU 유휴 시간만)
```

### 성능 목표 (Performance Targets)

**시나리오 2 (206-213줄) 기준**

| 작업 | 목표 시간 | 사용 모델 | 시나리오 |
|------|----------|----------|---------|
| 파일 생성 감지 | < 5초 | watchdog (파일 시스템 API) | 2 |
| 텍스트 파일 분석 + 저장 | < 10초 | Gemma 4 E4B (실시간) | 2 |
| PDF (10페이지) 분석 | < 30초 | Gemma 4 26B (백그라운드) | 2 |
| 자연어 질의 응답 | < 1초 | Gemma 4 E4B (메모리 상주) | 3 |
| 그래프 시각화 렌더링 | < 500ms | Frontend (react-force-graph-3d) | 4 |

**모델 표기 통일 권장**: E2B → E4B (CLAUDE.md와 일치시키기)

---

## 7️⃣ 예외 상황 처리 (상세)

### 권한 거부 (Permission Denied)

```text
증상: "PermissionError: [Errno 13]"
처리:
1. 해당 파일 스킵 (에러 로그 기록)
2. 사용자에게 알림: "일부 파일은 권한이 없어 스캔하지 못했습니다"
3. macOS: Full Disk Access 설정 가이드 표시
4. Windows: UAC 권한 상승 안내
```

### 파일 잠금 (File Locked)

```text
증상: 다른 프로그램이 파일 사용 중
처리:
1. 30초 후 재시도 (최대 3회)
2. 실패 시 다음 스캔 주기로 연기
3. 로그 기록: "file.pdf - locked by another process"
```

### 디스크 공간 부족

```text
증상: 그래프 DB 또는 임베딩 저장 공간 부족
처리:
1. 사용자에게 경고 표시: "디스크 공간이 부족합니다 (5GB 미만)"
2. 가장 오래된 임베딩부터 삭제 (LRU)
3. 최소 5GB 여유 공간 확보 시까지 새 파일 분석 중단
4. 사용자에게 정리 제안 (오래된 파일 아카이브 또는 외부 저장소 이동)
```

### 외부 전송 금지 (보안 정책)

```python
# 코드 리뷰 시 체크리스트
❌ 금지:
- requests.post() to external API
- socket.connect() to remote server
- subprocess.run(['curl', 'https://...'])

✅ 허용:
- Local file I/O
- Local DB queries (Kùzu, ChromaDB)
- MLX inference (on-device)
```

---

## 8️⃣ 설정 파일 전체 예시

### `~/.gemvis/config.json`

```json
{
  "version": "2.0.0",
  "monitored_paths": [
    {
      "path": "/Users/username/Documents",
      "enabled": true,
      "recursive": true,
      "max_depth": -1,
      "exclude_patterns": []
    },
    {
      "path": "/Users/username/Projects",
      "enabled": true,
      "recursive": true,
      "max_depth": 3,
      "exclude_patterns": ["*/node_modules/*", "*/.git/*"]
    }
  ],
  "file_type_whitelist": [
    "pdf", "txt", "md", "docx", "pptx", "xlsx",
    "png", "jpg", "jpeg", "heic"
  ],
  "file_size_limit_mb": 100,
  "debounce_interval_seconds": 30,
  "debounce_interval_cloud_seconds": 60,
  "max_concurrent_extractions": 4,
  "enable_sensitive_file_detection": true,
  "audit_log_enabled": true,
  "audit_log_retention_days": 30,
  "symlink_base_path": "~/Gemvis",
  "review_confidence_threshold": 0.8
}
```

---

# Part 3: 기능-시나리오 매핑

---

## 기능 → 시나리오 매핑 (구현 우선순위)

| 기능 | 시나리오 | Part 2 섹션 | 우선순위 | Week |
|------|----------|-------------|---------|------|
| 원클릭 설치 | 0.1 | - | MUST | W1 ✅ |
| 온보딩 UI (폴더 선택) | 0.2 | 1️⃣ 동의 프로세스 | MUST | W3 |
| OS별 기본 경로 설정 | 0.2 | 1️⃣ | MUST | W1 |
| 제외 규칙 (blacklist) | - | 3️⃣ | MUST | W1 |
| watchdog 파일 감시 | 2 | 4️⃣.1 | MUST | W2 |
| Debounce 로직 | 2 | 4️⃣.3 | MUST | W2 |
| llama-server 상주 | 1, 2, 3 | - | MUST | W1 |
| Kùzu 스키마/CRUD | 1, 2, 3, 4 | - | MUST | W1 |
| 엔티티 추출 프롬프트 | 1, 2 | - | MUST | W1 |
| 신뢰도 기반 자동/리뷰 분기 | 1, 2 | 4️⃣.4 신뢰도 기반 분류 | MUST | W2 |
| symlink 가상 폴더 | 1, 2 | 4️⃣.4 Symlink 생성 | MUST | W2 |
| 민감 파일 자동 감지 | 6 | 3️⃣.3 | MUST | W2 |
| 파일 크기 제한 | 6 | 6️⃣.1 | MUST | W2 |
| NL2Cypher + 답변 합성 | 3 | - | MUST | W2 |
| 증분 Ingest 파이프라인 | 2 | 4️⃣.2 증분 업데이트 | MUST | W2 |
| Chat UI | 3 | - | SHOULD | W3 |
| 그래프 시각화 | 4 | - | SHOULD | W3 |
| 엔티티 병합/편집 | 4.편집 | - | SHOULD | W3 |
| 파일 되묻기 모달 | 2.2 | - | SHOULD | W3 |
| 커스텀 경로 관리 GUI | 5.1 | 2️⃣ | SHOULD | W3 |
| 감사 로그 | - | 5️⃣.3 | COULD | W4 |
| 이미지 OCR / 음성 전사 | 1 (미래) | - | COULD | W4 |
| 벡터 하이브리드 검색 | 3.2 | - | COULD | W4 |

---

## 데모 시나리오 (해커톤 제출용)

**"파일을 드롭하면 Gemvis가 이해합니다" (3분)**

```text
[Act 1 — Problem, 30초]
 화면: 어수선한 Downloads 폴더 (100+ 파일)
 나레이션: "디지털 기억은 쌓이기만 하고 다시 찾을 수 없습니다."

[Act 2 — Demo, 2분]
 1. Gemvis 실행, 감시 폴더로 Downloads 추가 (시나리오 0.2)
 2. 실시간 분석 진행 바 (타임랩스 가속) (시나리오 1)
 3. "~/Gemvis/by-person/김과장/" 자동 생성 보여주기 (Part 2, 4️⃣.4)
 4. Chat: "지난달 김과장이랑 간 식당 어디야?" (시나리오 3.1)
    → 답변 + 관련 파일 목록
 5. [그래프에서 보기] → 3D 지식그래프 인터랙션 (시나리오 4)
 6. 민감 파일 자동 제외 시연 (id_rsa 파일 스킵) (Part 2, 3️⃣.3)

[Act 3 — Why it matters, 30초]
 - "모든 것이 이 컴퓨터에서만 일어났습니다" (프라이버시)
 - "인터넷 연결이 끊겨도 작동합니다" (네트워크 끊고 질의)
 - "원본 파일은 그대로입니다" (symlink 폴더 구조 설명)
 - Powered by Gemma 4 (26B + E4B)
```

---

## 📚 관련 문서

- [CLAUDE.md](../CLAUDE.md) - 프로젝트 전체 가이드 (개발자용)
- [technical_spec.md](technical_spec.md) - 기술 스펙 상세 (백엔드 구현)
- [architecture.md](architecture.md) - 시스템 아키텍처
- [mvp_roadmap.md](mvp_roadmap.md) - 5주 개발 계획

---

## 🔄 변경 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|----------|
| 2.0.0 | 2026-04-30 | user_scenarios + file_monitoring_policy 통합 |
| 1.0.0 | 2026-04-15 | 초안 작성 (사용자 시나리오만) |

---

**문의**: Gemvis Team - `#gemvis-hackathon` (Slack)

**다음 단계**: 이 통합 문서를 기준으로 technical_spec.md와 mvp_roadmap.md를 업데이트하고, 백엔드 구현 시작.
