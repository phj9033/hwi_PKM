# hwi_PKM

마크다운을 단일 진실(source of truth)로 두는 1인용 PKM. 결정론적 `pkm` CLI 가 capture · curation · indexing · wiki promotion · AI 보조 작성 · 정적 HTML 대시보드까지 담당하며, 일상 운용은 Claude Code 세션에서 한다.

전체 V1 디자인 사양: `docs/superpowers/specs/2026-05-01-pkm-design.md` (한국어).

## 두 개의 repo — 소스 vs 데이터

이 repo(`hwi_PKM`)는 **`pkm` CLI 의 소스 코드**다. 사용자의 노트가 들어가는 **PKM 데이터 repo** 는 별도 디렉토리에 둔다 — `pkm init` 이 깨끗한 빈 디렉토리에 `data/`, `.pkm/`, `SCHEMA.md`, `.claude/` 를 스캐폴딩하고 새 git repo 로 초기화한다.

```
~/Downloads/Claude_lab/hwi_PKM/   ← 소스 (이 repo)
~/Documents/pkm/                   ← 데이터 (개인 노트, 별도 git repo)
```

따라서 이 소스 repo 안에 `data/` 가 없는 것이 정상이다.

## Quick start (5 분)

새 PC 에서 한 번씩만:

```bash
# 1) uv 가 없으면 먼저 설치
brew install uv

# 2) 소스 repo clone + 의존성 동기화
git clone <repo> ~/Downloads/Claude_lab/hwi_PKM
cd ~/Downloads/Claude_lab/hwi_PKM
uv sync --all-extras

# 3) 글로벌 `pkm` 커맨드 설치 (editable — 소스 수정이 즉시 반영)
#    `[ml,extract]` 는 sentence-transformers · sqlite-vec · huggingface_hub · pdfplumber · markdownify
#    까지 함께 받음. zsh 에서 `[` 가 glob 문자라 따옴표 필수.
uv tool install --reinstall -e ".[ml,extract]"
which pkm                         # 예: ~/.local/bin/pkm

# 4) 데이터 repo 생성 + 한 번에 셋업
#    빈 dir 이면 `pkm bootstrap` 이 자동으로 init → doctor --download (~8 GB)
#    → reindex → dashboard 까지 한 흐름으로 처리 (이미 init 된 dir 이면 init 단계는 스킵).
mkdir -p ~/Documents/pkm && cd ~/Documents/pkm
pkm bootstrap

# 5) 인수 검증 — 모든 row 가 ✓ 여야 정상
pkm doctor --strict

# 6) 첫 캡쳐 → 검색 → 대시보드 미리보기
pkm capture create --slug hello --title "첫 노트" --url https://example.com <<<"본문"
pkm capture set-status hello reviewed
pkm reindex db --full
pkm search "첫"
open dashboard/index.html
```

> 단계를 분리해서 가고 싶다면: `pkm init` → `pkm doctor --download` → `pkm reindex db --full` → `pkm dashboard build`. `pkm bootstrap` 은 이 4단계의 idempotent wrapper.

## 명령어 한눈에

| 그룹 | 명령 |
|---|---|
| Setup | `pkm init`, `pkm doctor [--strict] [--download] [--json]`, `pkm bootstrap` |
| Capture / chunks | `pkm capture {create,list,show,set-status,rm}`, `pkm chunks {new,add,list,show,set-status}` |
| Index / search | `pkm reindex db [--full] [--low-memory]`, `pkm search <q> [--no-rerank] [--expand] [--with-related] [--json]`, `pkm related <path> [--mode backlinks\|semantic\|both]` |
| Promote / lint | `pkm promote <ref> --to <bucket>`, `pkm demote <ref>`, `pkm wiki edit <ref> {--replace\|--patch}`, `pkm lint [--fix] [--json] [--errors-only]` |
| Extract | `pkm extract <file>` (PDF/HTML → md, `[extract]` extra 필요) |
| Writing | `pkm write {new,list,set-status}` (writing → wiki promotion 은 동일하게 `pkm promote` 사용) |
| Dashboard | `pkm dashboard build [--out PATH]` |
| Bench | `pkm bench [--docs N=100] [--real] [--json]` (M7) |
| Log | `pkm log` |

`pkm init` 이 데이터 repo 에 자동으로 깔아주는 슬래시 커맨드: `/collect`, `/research`, `/review-captures`, `/promote`, `/lint`, `/ask`, `/write` — Claude Code 세션에서 바로 사용 가능.

## 디렉토리 구조 (데이터 repo 기준)

```
data/                # 마크다운 단일 진실 (raw/, wiki/, writing/)
.pkm/                # 로컬 인덱스 + 설정 (.pkm/config.toml 만 git 추적)
.pkm/index.db        # SQLite + sqlite-vec
dashboard/           # 정적 HTML (gitignored — `pkm dashboard build` 로 재생성)
.claude/commands/    # 슬래시 커맨드 템플릿
SCHEMA.md            # AI 에이전트가 따르는 워크플로우 룰북
```

소스 repo(이 디렉토리) 의 디자인 문서·마일스톤 플랜은 `docs/superpowers/{specs,plans}/`.

## 모델 캐시

`pkm doctor --download` 가 받는 두 모델:

- `BAAI/bge-m3` — 임베더 (~6.4 GB)
- `BAAI/bge-reranker-v2-m3` — search 의 rerank 단계 (~2.1 GB)

저장 위치: `~/.cache/pkm/models/` (HuggingFace 표준 layout, 합 약 8 GB). 모든 venv·데이터 repo 가 공유하므로 한 번만 받으면 된다. 위치 변경은 `PKM_MODEL_CACHE=/some/path` 환경변수로.

## 실패 계약 (failure contract)

모든 에러는 `PKMError` 의 서브클래스로 안정적인 `code` 를 가진다 (예: `NOT_FOUND`, `STATUS_NOT_REVIEWED`, `EXPAND_FAILED`). 실패 시:

- 비-0 종료 코드
- stderr 에 `Error [<CODE>]: <message>` 출력
- `--json` 모드에서는 stdout 에 `{"ok": false, "error": {"code", "message", "hint"}}`

전체 코드 목록의 단일 진실: `pkm/errors.py`. 커버리지 검증: `tests/test_failure_mode_matrix.py`.

## 진행 상황

- [x] M1 — Foundation
- [x] M2 — Capture & Chunks
- [x] M3 — Indexing & Search
- [x] M3.5 — Git Auto-commit
- [x] M4 — Promote, Lint & Extract
- [x] M5 — AI bridge & Writing
- [x] M6 — Dashboard
- [x] M7 — Hardening (V1 GA, 태그 `m7-hardening`)

V1 인수 체크리스트: `docs/M7-SHIP-CHECKLIST.md`.
