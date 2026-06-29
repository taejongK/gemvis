# Setup Scripts Optimization

**Date**: 2026-05-17  
**Issue**: Windows setup 실패 (msstore 인증 오류, git/python/nodejs 미설치 시 중단)  
**Goal**: 새 PC에서 원클릭 설치 가능하도록 setup 스크립트 최적화

---

## 해결한 문제들

### 1. Windows: msstore 인증서 오류
**증상:**
```
원본을 검색하는 동안 실패함: msstore
0x8a15005e : 서버 인증서가 필요한 값과 일치하지 않습니다.
```

**원인:**  
`winget install llama.cpp` 실행 시 msstore를 자동 검색하다가 인증서 오류 발생

**해결:**  
`--source winget` 플래그 명시 → msstore 검색 스킵
```powershell
winget install --id ggml.llamacpp --source winget --accept-source-agreements
```

### 2. Git/Python/Node.js 미설치 시 중단
**증상:**
- git 없으면 repo clone 불가
- python 없으면 venv 생성 불가
- npm 없으면 frontend 빌드 불가

**해결:**
- **Pre-check 단계 추가**: 최초에 git/python 확인 → 없으면 자동 설치 또는 가이드
- **자동 설치 함수 추가** (Windows):
  ```powershell
  function Install-Winget-Package {
      param([string]$Id, [string]$Name)
      winget install --id $Id --source winget --accept-source-agreements --silent
      Refresh-Path
  }
  ```

### 3. Python 버전 호환성 (rdflib)
**증상:**  
Python 3.13/3.14는 rdflib/pyparsing과 호환성 문제 가능

**해결:**
- Python 3.11 우선 감지
- 3.13/3.14 감지 시 자동으로 3.11 설치 시도 (Windows)
- Mac/Linux는 권장 명령 출력

---

## 변경 사항

### Windows (`scripts/setup_windows.ps1`)

| 변경 | Before | After |
|------|--------|-------|
| Git 체크 | 없음 | Pre-check 추가, 없으면 자동 설치 |
| Python 체크 | 없으면 fail | 없으면 자동 설치, 3.13/3.14 감지 시 3.11 설치 |
| llama.cpp | `winget install llama.cpp` | `--id ggml.llamacpp --source winget` |
| Node.js | `winget install OpenJS.NodeJS.LTS` | `--id OpenJS.NodeJS.LTS --source winget` |
| 에러 처리 | `Warn` only | `Fail()` 함수 추가, 설치 가이드 출력 |

**핵심 개선:**
1. `Install-Winget-Package()` 유틸 함수 → 모든 winget 설치에 `--source winget` 적용
2. Git/Python 사전 체크 → 없으면 자동 설치 → 실패 시 수동 설치 가이드
3. `Fail()` 함수로 명확한 에러 메시지 + 대기 후 종료

### macOS/Linux (`scripts/setup_mac.sh`)

| 변경 | Before | After |
|------|--------|-------|
| Git 체크 | 없음 | Pre-check 추가, 없으면 설치 가이드 출력 |
| Python 체크 | 없으면 fail | 없으면 OS별 설치 명령 출력 |
| Node.js | 없으면 warn | macOS는 brew로 자동 설치 시도, Linux는 가이드 |
| 에러 처리 | 간단한 fail | `fail()` 포맷 개선 (빈 줄 추가) |

**핵심 개선:**
1. Git/Python 사전 체크 → OS별 설치 가이드
2. macOS Node.js 자동 설치 (`brew install node`)
3. 명확한 에러 메시지 + 설치 명령 출력

---

## 사용 시나리오

### ✅ 완전 새 PC (Git/Python/Node.js 없음)
**Windows:**
1. `scripts\setup_windows.bat` 더블클릭
2. Git 자동 설치 → Python 3.11 자동 설치 → llama.cpp 설치 → Node.js 설치
3. 새 PowerShell 열고 `scripts\start_windows.bat` 실행

**macOS:**
1. `./scripts/setup_mac.sh` 실행
2. Git 없으면 `brew install git` 가이드 출력 → 설치 후 재실행
3. Python 없으면 `brew install python@3.11` 가이드 → 설치 후 재실행
4. Node.js 없으면 자동 설치 (`brew install node`)
5. `./scripts/start_mac.sh` 실행

### ✅ Python 3.13 설치된 PC
**Windows:**
1. setup 실행 → Python 3.11 자동 설치
2. venv는 Python 3.11로 생성

**macOS:**
1. setup 실행 → Python 3.11 설치 가이드 출력
2. 설치 후 재실행

### ✅ Git 있지만 llama-server 없음
- setup 실행 → llama.cpp만 설치
- 나머지 단계 정상 진행

---

## 테스트 체크리스트

- [ ] Windows 10 완전 새 PC (Git/Python/Node.js 없음)
- [ ] Windows 11 Python 3.13 설치된 PC
- [ ] macOS (Intel) Git 없음
- [ ] macOS (Apple Silicon) Python 없음
- [ ] Linux (Ubuntu 22.04) 완전 새 환경
- [ ] WSL2 (Ubuntu) Git 있음, Python 없음

---

## 문서 업데이트 필요

다음 문서에 "새 PC 설치 가이드" 섹션 추가:
- [ ] `README.md` - Quick Start 섹션
- [ ] `README_ko.md` - 빠른 시작 섹션
- [ ] `docs/CONTRIBUTING.md` - Development Setup

---

## 다음 단계

1. ✅ **Windows setup 최적화** (msstore 이슈, 자동 설치)
2. ✅ **Mac setup 최적화** (사전 체크, 자동 설치)
3. ⏳ **테스트** (다른 PC에서 실제 실행)
4. ⏳ **문서 업데이트** (README 등)
5. ⏳ **CI/CD 통합** (GitHub Actions로 자동 테스트)

---

**Last updated**: 2026-05-17
