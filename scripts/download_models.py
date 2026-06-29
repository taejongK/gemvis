#!/usr/bin/env python3
"""Gemvis 모델 다운로더.

scripts/models.yaml 에 정의된 HuggingFace 모델/파일을 models/ 로 내려받는다.
기본 모델은 unsloth/gemma-4-E2B-it-GGUF (Q4_K_M, ~2GB) — llama.cpp 용.

Usage:
    python3 scripts/download_models.py                    # 기본 모델
    python3 scripts/download_models.py --all              # 등록된 전부
    python3 scripts/download_models.py gemma-4-e2b-q8     # 특정 모델
    python3 scripts/download_models.py --list             # 목록만
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import yaml
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub.utils import (
        EntryNotFoundError,
        GatedRepoError,
        RepositoryNotFoundError,
    )
except ImportError as exc:
    sys.exit(
        f"❌ 필요한 패키지 누락: {exc.name}\n"
        f"   pip install -r scripts/requirements.txt"
    )


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "scripts" / "models.yaml"


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        sys.exit(f"❌ 레지스트리 없음: {REGISTRY_PATH}")
    with REGISTRY_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_token() -> str | None:
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGINGFACE_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    )


def download_one(name: str, spec: dict, token: str | None) -> Path:
    local_dir = ROOT / spec["local_dir"]
    local_dir.mkdir(parents=True, exist_ok=True)

    repo_id = spec["repo_id"]
    files = spec.get("files")
    size_gb = spec.get("size_gb", "?")
    purpose = spec.get("purpose", "N/A")

    print(f"📦 [{name}] {repo_id}")
    print(f"   → {local_dir.relative_to(ROOT)}")
    print(f"   용도: {purpose}")
    print(f"   예상 크기: {size_gb}GB")

    try:
        if files:
            # 특정 파일만 다운로드
            for filename in files:
                print(f"   ⬇️  {filename}")
                path = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=str(local_dir),
                    token=token,
                )
                print(f"      → {Path(path).relative_to(ROOT)}")
        else:
            # 전체 저장소 스냅샷
            path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
                token=token,
            )
            print(f"   → {Path(path).relative_to(ROOT)}")
    except GatedRepoError:
        sys.exit(
            f"\n❌ {repo_id} 접근 거부.\n"
            f"   1) https://huggingface.co/{repo_id} 방문 → 라이선스 동의\n"
            f"   2) huggingface-cli login  또는  export HF_TOKEN=hf_xxx"
        )
    except RepositoryNotFoundError:
        sys.exit(
            f"\n❌ {repo_id} 존재하지 않음.\n"
            f"   scripts/models.yaml 의 repo_id 를 확인하세요."
        )
    except EntryNotFoundError as exc:
        sys.exit(
            f"\n❌ 파일을 찾을 수 없음: {exc}\n"
            f"   https://huggingface.co/{repo_id}/tree/main 에서 파일명 확인"
        )

    print(f"✅ {name} 완료\n")
    return local_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemvis 모델 다운로더")
    parser.add_argument("names", nargs="*", help="다운로드할 모델 (생략 시 default)")
    parser.add_argument("--all", action="store_true", help="등록된 전체 다운로드")
    parser.add_argument("--list", action="store_true", help="등록된 모델 나열")
    args = parser.parse_args()

    registry = load_registry()
    all_models: dict = registry.get("models", {})
    default_name = registry.get("default")

    if not all_models:
        sys.exit("❌ scripts/models.yaml 에 모델이 없음")

    if args.list:
        print(f"{'이름':22}{'Repo':42}{'크기':>6}  용도")
        print("-" * 110)
        for name, spec in all_models.items():
            marker = " ★" if name == default_name else "  "
            print(
                f"{marker}{name:20}{spec['repo_id']:42}"
                f"{str(spec.get('size_gb', '?')) + 'GB':>6}  "
                f"{spec.get('purpose', '')}"
            )
        print("\n★ = 기본 모델 (인수 없이 실행 시)")
        return

    if args.all:
        targets = list(all_models.keys())
    elif args.names:
        targets = args.names
    else:
        if not default_name:
            sys.exit("❌ models.yaml 에 default 모델 지정 필요")
        targets = [default_name]
        print(f"ℹ️  기본 모델만 다운로드: {default_name} (--all 로 전체)")

    unknown = [n for n in targets if n not in all_models]
    if unknown:
        sys.exit(f"❌ 알 수 없는 모델: {unknown}\n   --list 로 확인")

    token = resolve_token()
    needs_auth = any(all_models[n].get("requires_auth") for n in targets)
    if needs_auth and not token:
        print("⚠️  일부 모델이 인증 필요. huggingface-cli login 또는 HF_TOKEN 설정.\n")

    total_gb = sum(all_models[n].get("size_gb", 0) for n in targets)
    print(f"🚀 {len(targets)}개 모델 다운로드 (총 ~{total_gb}GB)\n")

    for name in targets:
        download_one(name, all_models[name], token)

    print("🎉 다운로드 완료")
    print(f"   저장 위치: {(ROOT / 'models').resolve()}")


if __name__ == "__main__":
    main()
