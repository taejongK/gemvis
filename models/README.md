# models/

llama.cpp 추론에 사용되는 GGUF 모델 파일 저장 위치.

## 구조

```
models/
├── README.md                                       (tracked)
├── .gitkeep                                        (tracked)
└── gemma-4-e2b/
    └── gemma-4-E2B-it-Q4_K_M.gguf                  (ignored, ~2GB)
```

실제 가중치는 `.gitignore` 로 제외됩니다. 이 README 와 `.gitkeep` 만 커밋됩니다.

## 원클릭 설치

```bash
./scripts/setup.sh
```

위 스크립트 한 번으로 다음이 모두 완료됩니다:
1. Python venv 생성 + 의존성 설치
2. llama.cpp 클론 + 빌드
3. 기본 모델 다운로드 (gemma-4-E2B-it Q4_K_M, ~2GB)
4. 추론 테스트

## 개별 작업

```bash
# 다른 양자화 레벨도 받기 (Q8_0, BF16)
python3 scripts/download_models.py --all

# 특정 모델만
python3 scripts/download_models.py gemma-4-e2b-q8

# 등록된 목록 보기
python3 scripts/download_models.py --list
```

## 기본 모델

| 항목 | 값 |
|------|-----|
| 모델 | `unsloth/gemma-4-E2B-it-GGUF` |
| 파일 | `gemma-4-E2B-it-Q4_K_M.gguf` |
| 크기 | ~2GB |
| 용도 | 백엔드 기본 모델 (llama.cpp) |

원래 CLAUDE.md에 언급된 Gemma 4 26B 전체 가중치 대신, 하드웨어 제약과
해커톤 일정을 고려해 2B GGUF 양자화 모델을 먼저 사용합니다. 필요 시
`scripts/models.yaml` 에 추가 모델을 등록하세요.

## 모델 레지스트리 수정

`scripts/models.yaml` 에서 모델 추가/변경:

```yaml
models:
  my-model:
    repo_id: org/repo
    local_dir: models/my-model
    files: [file.gguf]
    size_gb: 2
```

## 수동 추론 테스트

```bash
./third_party/llama.cpp/build/bin/llama-cli \
    -m ./models/gemma-4-e2b/gemma-4-E2B-it-Q4_K_M.gguf \
    -p "안녕, Gemvis!"
```
