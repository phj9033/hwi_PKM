# 기능 상세 & 유즈케이스

`pkm` CLI 의 기능을 6 레이어 → 명령 → 슬래시 커맨드 → 유즈케이스 순서로 설명한다. 디자인 사양 (`docs/superpowers/specs/2026-05-01-pkm-design.md`) 의 운영자용 발췌본.

---

## 1. 6 레이어 개요

본 PKM 은 **사용자 요구 6 가지** 를 6 개의 레이어 (capture / chunks / wiki / writing / search / dashboard) 로 매핑한다. 각 레이어는 디렉토리 + frontmatter status 라이프사이클 + 결정론적 CLI 명령으로 구성된다.

| # | 레이어 | 디렉토리 | 사용자 요구 | 다루는 명령 |
|---|---|---|---|---|
| 1 | **Capture** | `data/raw/captures/` | URL·텍스트 단건 수집 | `pkm capture *`, `/collect` `/research` |
| 2 | **Chunks** | `data/raw/chunks/<topic>/` | 다중 소스 토픽 폴더 | `pkm chunks *`, `pkm extract` |
| 3 | **Wiki** | `data/wiki/{concepts,entities,notes,reports}/` | 정제된 누적 지식 (compounding) | `pkm promote`, `pkm demote`, `pkm wiki edit` |
| 4 | **Search / RAG** | (인덱스: `.pkm/index.db`) | 한국어 강한 하이브리드 검색 | `pkm search`, `pkm related`, `pkm reindex` |
| 5 | **Writing** | `data/writing/` | AI 가 CLI 로 합성하는 워크스페이스 | `pkm write *`, `/write`, `/ask` |
| 6 | **Dashboard** | `dashboard/` (gitignore) | 정적 HTML 8 페이지 | `pkm dashboard build`, `pkm bootstrap` |

### 라이프사이클 게이트

```
  capture(draft) ──reviewed──→ promote ──→ wiki(stub) ──active──→ deprecated
                  │                               ▲
                  └──archived (자동, --keep-source 으로 보존)
                                                  │
  writing(draft) ────final──→ promote ────────────┘
                  │
                  └─ abandoned
```

- raw 본문은 `reviewed` 이후 immutable. 정정은 새 capture 또는 wiki 에서.
- wiki 는 strict 모드에서 **deny-write**. 변경은 `pkm promote` 또는 `pkm wiki edit` 두 경로뿐.
- 모든 mutate 명령은 자동 git 커밋 (감사로그 = `git log` + `data/log.md`).

---

## 2. 명령별 상세

전체 명령 surface 는 `pkm --help`, 각 서브명령은 `pkm <cmd> --help`. 아래는 그룹별 핵심.

### 2.1 Setup

```bash
pkm init                                 # 빈 디렉토리 → data/ .pkm/ SCHEMA.md .claude/ 스캐폴드
pkm doctor [--strict] [--download] [--json]
                                         # 환경/모델/AI CLI/DB 헬스체크
                                         # --download: HF 에서 bge-m3 + reranker 페치 (~8 GB)
                                         # --strict:   누락 1 건이라도 있으면 exit ≠ 0 (CI 게이트)
                                         # --json:     status.html 이 그대로 렌더 (보안 화이트리스트)
pkm bootstrap [--json]                   # 새 PC / 새 dir idempotent 셋업:
                                         # (init 필요 시) → doctor --download → reindex --full → dashboard build
```

`pkm doctor` 출력 항목 (모두 `--json` 의 `items` 배열):
- `index.db` — 존재 + chunk count
- `bge-m3` / `bge-reranker` — `~/.cache/pkm/models/` 안 모델 무결성
- `ai_cli` — PATH 자동탐지 결과 (이름만 노출, exec 미노출)
- `system` — 가용 RAM + 권장 batch_size

기본 종료코드는 항상 0 — 누락이 있어도 리포트만 한다 (대시보드 빌드가 내부 호출해도 안전). `--strict` 만 게이트 모드.

### 2.2 Capture (URL·텍스트 단건)

```bash
pkm capture create --slug SLUG --title "..." [--url URL]
                                  [--from-file PATH]   # 본문은 stdin 또는 --from-file
                                  [--status draft|reviewed]
                                  [--lang ko|en|mixed] [--json]
pkm capture list   [--status draft|reviewed|archived] [--lang ...] [--json]
pkm capture show   <id-or-slug> [--json]
pkm capture set-status <id-or-slug> <status>
pkm capture rm     <id-or-slug>
```

- 슬러그에 날짜 prefix 가 없으면 `YYYY-MM-DD-` 자동 추가.
- frontmatter: `title slug created_at status source_type lang` (필수) + `source_url fetched_at tags summary` (옵션).
- `status: reviewed` 이후 본문 변경은 `RAW_BODY_MUTATED` warning 으로 감지됨 (compounding 깨짐 방지).

### 2.3 Chunks (다중 소스 토픽 폴더)

```bash
pkm chunks new        <topic> [--description ...] [--json]   # 폴더 + README.md 스캐폴드
pkm chunks add        <topic> <files...> [--json]            # 파일 복사
pkm chunks list       [<topic>] [--json]
pkm chunks show       <topic> [--json]
pkm chunks set-status <topic> <collecting|curating|ready>
pkm chunks rm         <topic>
pkm extract           <file> [--out PATH] [--json]           # PDF/HTML → markdown
```

- chunks/ 는 multi-source 큐레이션 워크스페이스. 큐레이션 끝나면 `set-status ready` → `pkm write new --from-chunks <topic>` 으로 합성.
- `pkm extract` 는 `[extract]` extra 필요 (`pdfplumber`, `markdownify`).

### 2.4 Index / Search

```bash
pkm reindex db [<path>] [--full] [--scope wiki|raw|writing|all]
                        [--low-memory] [--json]
                        # 기본: 증분 (content_hash 비교) — 변경분만 재임베딩
                        # <path> : 특정 파일/글롭만
                        # --full : 전부 재구축 (FTS5 + vec0 모두 drop & rebuild)
                        # --low-memory: batch=4, reranker 무로드

pkm search <query> [-n N] [--scope wiki|raw|writing|all]
                   [--expand]      # 옵트인 — AI CLI 셸아웃으로 쿼리확장
                   [--no-rerank]   # cross-encoder skip (빠른 모드)
                   [--with-related]# 각 hit 에 backlinks + 의미적 이웃 합성
                   [--explain] [--json]

pkm related <path> [--mode backlinks|semantic|both] [-n N] [--json]
```

검색 파이프라인 (5 단계):
1. **쿼리확장** (`--expand` 시) — AI CLI 가 원 쿼리 + 영문 + 패러프레이즈 2~3 개 생성. 실패 시 `EXPAND_FAILED` hard-fail.
2. **병렬 retrieval** — 변형마다 BM25(FTS5 trigram) top-50 + 벡터(bge-m3 → vec0 코사인) top-50.
3. **RRF 융합** — `score = Σ 1/(k + rank)` (k=60). top-30 후보.
4. **재랭킹** (`--no-rerank` 미지정 시) — bge-reranker-v2-m3 cross-encoder.
5. **top-K** + 모든 점수 노출 (`--explain`).

`--with-related` 는 결과 각 hit 에 다음 추가:
```json
"related": {
  "wikilinks_out": ["..."], "wikilinks_in": ["..."],
  "derived_from": ["..."], "tags": ["..."],
  "semantic_neighbors": [{"path":"...","similarity":0.78}]
}
```

### 2.5 Promote / Demote / Wiki edit (라이프사이클 게이트)

```bash
pkm promote <ref> --to concepts|entities|notes|reports
                  [--slug NEW_SLUG]    # 기본: 캡처 슬러그에서 날짜 prefix 제거
                  [--keep-source]      # 미지정 시 source 가 archived 로
                  [--json]
                  # <ref> 는 (a) capture slug, (b) capture full path,
                  # (c) writing/<slug>.md 모두 받음

pkm demote <wiki-path>                 # promoted_from 따라 source 복원

pkm wiki edit <ref> --replace|--patch [--json]
                                       # strict 모드에서 wiki 변경의 유일한 escape valve
                                       # --replace: stdin = 전체 본문 (frontmatter 포함) 교체
                                       # --patch:   stdin = unified diff (git apply)
                                       # 둘 다 frontmatter + wikilink 무결성 검증 후 쓰기
```

게이트 조건:
- capture → wiki 승격: `status: reviewed` 필수. draft 면 `STATUS_NOT_REVIEWED` 에러.
- writing → wiki 승격: `status: final` 필수.
- wiki 페이지는 `status: stub` 으로 시작 + `promoted_from: <source path>` 자동 기재.
- 자동 부수효과: source 가 `archived` 로 (기본), git 자동 커밋, `data/log.md` append.

### 2.6 Writing (AI 합성 워크스페이스)

```bash
pkm write new --slug SLUG [--title ...]
              [--from-search "..." | --from-chunks <topic>]
              [--purpose guideline|report|summary|essay]
              [--lang ko] [--json]
                                         # 본문은 비움 — frontmatter 만 시드.
                                         # --from-chunks 는 derived_from 을 chunks 파일 목록으로 자동 채움.

pkm write list [--json]
pkm write set-status <id-or-slug> <draft|final|abandoned>
                                         # 별도 finalize 명령 없음 — pkm promote 가 writing/* 도 받음.
```

writing/ 는 `data/wiki/**` 와 달리 strict 모드에서도 **AI 가 직접 `Edit` 가능**. workflow:
1. `pkm write new --from-chunks <topic>` → frontmatter 시드 (본문 비움).
2. AI 가 `Edit` 로 본문 작성 — 인용 `[<wiki-path>]` 필수.
3. `pkm write set-status <s> final` → `pkm promote data/writing/<s>.md --to <bucket>`.

### 2.7 Lint (정합성 게이트)

```bash
pkm lint [--fix] [--errors-only] [--json]
```

| 코드 | 종류 | 의미 | --fix |
|---|---|---|---|
| `MISSING_FIELD` | error | frontmatter 필수 필드 누락 (`title`, `slug`, `created_at`, `status`, `lang` 등) | ✅ `created_at`, `slug` |
| `INVALID_VALUE` | error | enum 위반 (`status: foo`) | — |
| `DUPLICATE_SLUG` | error | 같은 slug 가 2 곳 이상 | — |
| `BROKEN_WIKILINK` | error | `[[link]]` 가 실재하지 않는 경로 | — |
| `BROKEN_DERIVED_FROM` | error | `derived_from:` 의 source 누락 | — |
| `ORPHAN_PROMOTED_SOURCE` | error | wiki 의 `promoted_from` 이 source 와 mismatch | ✅ |
| `STALE_DRAFT` | warning | draft 가 N 일 이상 방치 | — |
| `STALE_STUB` | warning | wiki stub 이 N 일 이상 방치 | — |
| `ORPHAN_WIKI` | warning | 인바운드 link 0 인 wiki 페이지 | — |
| `LARGE_CHUNK_NEVER_PROMOTED` | warning | chunks 가 ready 인데 미승격 | — |
| `LANG_INCONSISTENT` | warning | 본문 언어와 frontmatter `lang` 불일치 | — |
| `RAW_BODY_MUTATED` | warning | reviewed 이후 본문 해시 변경 (compounding 위반) | — |
| `BROKEN_CITATION` | warning | `[<path>]` 인용이 실존 path 아님 | — |

`--errors-only` 는 warning 을 숨기고 error 만으로 exit 게이트 — CI/pre-commit 용.

### 2.8 Dashboard

```bash
pkm dashboard build [--out PATH]    # 기본 ./dashboard/. 단일 명령으로 8 페이지 생성.
```

생성물 (모두 정적 HTML, 외부 CDN 없음, 오프라인 동작):
- `index.html` — 통계, lint 요약, 최근 log 20 개, 빠른 링크
- `captures.html` / `chunks.html` / `wiki.html` / `writing.html` — 필터바 (status/lang/tags) + 표
- `doc/<path>.html` — frontmatter 사이드바 + 본문 + Backlinks/Outgoing/Semantic neighbors/Provenance
- `search.html` — 클라이언트 사이드 substring + 태그 매칭 (진지한 검색은 `pkm search`)
- `help.html` — `SCHEMA.md` 렌더 + CLI 치트시트
- `status.html` — `pkm doctor --json` 렌더 + 마스킹된 config + 권한 모드

빌드 트리거는 수동 (`pkm dashboard build`) — 자동화하려면 git post-commit 훅. `dashboard/` 는 gitignore.

### 2.9 Bench / Log / Index

```bash
pkm bench [--docs N=100] [--real] [--json]
                                     # 합성 한국어 N 문서 → 인덱싱/검색 latency 측정 (soft 임계 — 출력만)
                                     # --real 은 stub 임베더 대신 실제 bge-m3 사용 (doctor --download 선행 필수)

pkm log                              # data/log.md tail
pkm index rebuild                    # data/index.md (TOC) 재생성 — 검색 인덱스와 별개
```

---

## 3. 슬래시 커맨드 (Claude Code 세션용)

`pkm init` 이 데이터 repo 의 `.claude/commands/` 에 7 개 템플릿을 깔아준다. 모두 SCHEMA.md 의 워크플로우를 5~10 줄로 요약한 것.

| 커맨드 | 입력 | 동작 | 결과 |
|---|---|---|---|
| `/collect <url\|text>` | URL 또는 텍스트 | WebFetch → 1~3 줄 요약 + 1~4 태그 → `pkm capture create --status draft` | `data/raw/captures/<slug>.md` |
| `/research <topic>` | 토픽 | 다중 WebSearch + WebFetch → 3~6 capture 일괄 생성 → 선택적으로 `pkm chunks new` + `add` 로 묶음 | 다수 capture + 옵션 chunk |
| `/review-captures` | (없음) | `pkm capture list --status draft --json` 순회 → 각각 `set-status reviewed` 또는 `rm` | draft 청소 |
| `/promote` | (없음) | `pkm capture list --status reviewed --json` 검토 → bucket 결정 → `pkm promote --to ...` | 새 wiki stub |
| `/lint [--fix]` | (옵션) | `pkm lint --json` 보고 + 필요 시 `--fix` 자동수리 + 잔여물 사용자 안내 | 리포트 + 수정 |
| `/ask <question>` | 질문 | `pkm search --json` → top-K Read → Claude 본인이 인용 합성 (외부 AI CLI 불필요) | 인용 grounded 답변 |
| `/write <topic>` | 토픽/시드 | `pkm write new` (search/chunks/freeform 시드) → Edit 로 본문 + 인용 → `set-status final` → `pkm promote` | wiki 게시 |

### `/ask` 인용 계약 (Karpathy grounding)

- 모든 사실 주장은 끝에 `[<wiki-path>]` 를 붙인다. 다중 출처는 `[a.md][b.md]`.
- 검색에 없는 내용은 주장 금지 — 결과 부족 시 "wiki 에 관련 내용이 부족합니다" 라고 답하고 종료.
- 인용 경로는 path-resolvable 해야 함 — `pkm lint` 가 `BROKEN_CITATION` warning 으로 사후 검증.
- 답변을 capture 로 저장하려면 frontmatter `derived_from: [...인용 경로 모두]` 필수. (compounding)

**Anti-pattern**: "내가 알기로는...", "일반적으로는...", 인용 없는 일반 지식 — 모두 금지.

---

## 4. 유즈케이스 (시나리오 walk-through)

### UC1. 새 PC 셋업부터 첫 캡처까지

상황: 노트북 한 대 더 추가, GitHub 에 PKM 데이터 repo 가 있음.

```bash
# 1) 의존성
brew install uv
git clone <소스 repo> ~/Downloads/Claude_lab/hwi_PKM
cd ~/Downloads/Claude_lab/hwi_PKM
uv sync --all-extras
uv tool install --reinstall -e ".[ml,extract]"

# 2) 데이터 repo
git clone <데이터 repo> ~/Documents/pkm
cd ~/Documents/pkm
pkm bootstrap                    # init 은 자동 스킵 (이미 init 됨), doctor --download → reindex --full → dashboard build

# 3) 인수 검증
pkm doctor --strict              # 모두 ✓ 여야 함

# 4) 첫 캡처
echo "테스트 본문" | pkm capture create --slug hello --title "첫 노트" --status draft
pkm capture set-status hello reviewed
pkm reindex db data/raw/captures/2026-05-04-hello.md
pkm search "테스트" --scope raw
```

빈 디렉토리에서 시작하는 경우는 `mkdir ~/Documents/pkm && cd $_ && pkm bootstrap` — `pkm init` 도 자동으로 prepend 됨. 모델 캐시 (~8 GB) 는 `~/.cache/pkm/models/` 에 한 번만 받고 모든 venv·repo 가 공유한다.

### UC2. 단일 URL 캡처 → 검토 → wiki 승격

상황: 블로그 글 하나를 wiki 의 `concepts/oauth-token-storage.md` 로 만들고 싶다.

```
Claude Code 세션에서:
  /collect https://example.com/oauth-tokens
  → 자동: WebFetch + 요약 + tags 추론 + pkm capture create
  → 결과: data/raw/captures/2026-05-04-oauth-tokens.md (status: draft)

  /review-captures
  → draft 본문 확인 → keep
  → pkm capture set-status oauth-tokens reviewed

  /promote
  → bucket = "concepts" 결정
  → pkm promote oauth-tokens --to concepts
  → 결과: data/wiki/concepts/oauth-tokens.md (status: stub, promoted_from: ...)
         + capture status → archived (자동)
         + git commit (자동)

수정이 필요하면:
  pkm wiki edit concepts/oauth-tokens --replace < new_full_body.md
  또는
  pkm wiki edit concepts/oauth-tokens --patch < unified.diff
```

키 포인트: `data/wiki/**` 는 `.claude/settings.json` 으로 deny-write — Claude 의 `Edit` 툴이 직접 못 쓴다. 유일한 escape valve 가 `pkm wiki edit`.

### UC3. 다중 소스 리서치 → chunk 큐레이션 → writing 합성 → 승격

상황: "Embedding 모델 비교" 같은 여러 소스를 종합해야 하는 토픽.

```
1) 리서치
  /research "embedding model comparison 2026"
  → 다중 WebSearch + WebFetch → 5~6 개 capture 생성
  → pkm chunks new embedding-comparison
  → pkm chunks add embedding-comparison data/raw/captures/<5-6 files>
  (옵션) PDF 가 있으면: pkm extract paper.pdf --out data/raw/chunks/embedding-comparison/paper.md
  → pkm chunks set-status embedding-comparison ready

2) 합성 워크스페이스 만들기
  /write embedding-comparison
  → pkm write new --slug embedding-models --from-chunks embedding-comparison --purpose summary
  → frontmatter 의 derived_from 이 chunks 파일들로 자동 시드됨
  → AI 가 Edit 로 본문 작성:
      - 각 derived_from 파일 Read
      - 종합 + 인라인 인용 [<chunk path>]
      - 결론 + 비교표
  → pkm write set-status embedding-models final

3) wiki 로 게시
  → pkm promote data/writing/embedding-models.md --to reports
  → 결과: data/wiki/reports/embedding-models.md (status: stub)
         + writing artifact status → promoted (또는 archived)
```

이 경로가 본 PKM 의 **compounding** 핵심이다 — 매 검색마다 재합성하지 않고 wiki 가 누적된다.

### UC4. wiki 에 답이 있는지 `/ask` 로 묻기

상황: "OAuth refresh token 어떻게 저장해야 하지?" 같은 질문.

```
Claude Code 세션:
  /ask "OAuth refresh token은 어디에 저장하나요?"

내부 동작:
  1. pkm search "OAuth refresh token 저장" --scope wiki -n 8 --json
     (만약 .pkm/config.local.toml 에 expand_query 가 정의되어 있으면 --expand 사용)
  2. top-K 결과의 파일을 Read 툴로 읽기
  3. Claude 가 본문만 근거로 합성 — 모든 사실 주장에 [<wiki-path>] 인용 첨부
  4. wiki 가 비어있으면 "wiki 에 관련 내용이 부족합니다. /collect 로 자료를 모아주세요" 후 종료
  5. (옵션) 답변을 capture 로 저장 — derived_from: [모든 인용 경로]

답변 예:
  OAuth refresh token 은 httpOnly secure cookie 에 저장한다.
  [data/wiki/concepts/oauth-token-storage.md]
  로컬스토리지 저장은 XSS 노출 위험이 있어 권장하지 않는다.
  [data/wiki/concepts/oauth-token-storage.md][data/wiki/notes/web-auth-pitfalls.md]
```

검증: 다음 `pkm lint` 실행 시 `[<path>]` 인용이 실존 경로인지 자동 검사 (`BROKEN_CITATION`).

### UC5. lint 실패 흐름 + `--fix` 자동 수리

상황: 캡처 만들 때 frontmatter 빠뜨렸거나, wiki 페이지에서 깨진 wikilink 가 있다.

```bash
pkm lint --json
# 출력 예 (요약):
# - error MISSING_FIELD       data/raw/captures/foo.md  (slug 누락)
# - error MISSING_FIELD       data/raw/captures/bar.md  (created_at 누락)
# - error BROKEN_WIKILINK     data/wiki/concepts/baz.md → [[non-existent]]
# - error ORPHAN_PROMOTED_SOURCE data/wiki/notes/qux.md (promoted_from 이 archived 안 됨)
# - warn  STALE_DRAFT         data/raw/captures/old.md  (45 일 방치)
# - warn  BROKEN_CITATION     data/wiki/notes/qux.md   ([data/wiki/missing.md])

pkm lint --fix --json
# 자동 수리: MISSING_FIELD(slug, created_at), ORPHAN_PROMOTED_SOURCE
# 잔여: BROKEN_WIKILINK, BROKEN_CITATION, STALE_DRAFT — 사람이 결정

# CI 게이트 (warning 무시, error 만으로 exit ≠ 0)
pkm lint --errors-only
```

`/lint` 슬래시는 위 흐름을 한 번에 — `--json` 보고 + 필요 시 `--fix` + 잔여 수동 안내.

### UC6. 대시보드 빌드 + 새 PC 에서 복원

대시보드는 매 mutate 마다 자동 빌드되지 않는다 — 명시적으로:
```bash
pkm dashboard build
open dashboard/index.html
```

새 PC 에서 데이터 repo 통째로 복원:
```bash
git clone <데이터 repo> && cd $_
pkm bootstrap          # doctor --download → reindex --full → dashboard build
```

`dashboard/` · `.pkm/index.db` 는 gitignore 이지만 markdown 만으로 결정론적 재생성 — 첫 1 회 모델 다운로드 후엔 매번 추가 다운로드 0.

자동화 (선택): 데이터 repo 의 `.git/hooks/post-commit` 에
```bash
#!/usr/bin/env bash
pkm dashboard build > /dev/null
```

GitHub Pages 로 배포하려면 별도 브랜치 (`dashboard-build`) 또는 별도 repo 분리. `status.html` 이 config 를 렌더하므로 공개 노출 시 `.pkm/config.local.toml` 미커밋 + 시크릿 마스킹 (자동) 확인.

### UC7. AI CLI 셸아웃 옵트인 (`--expand`)

기본 검색은 결정론 (BM25 + vec0 + RRF + reranker — 모두 로컬). 쿼리확장이 정확도에 도움이 될 때만 옵트인.

`.pkm/config.local.toml` (gitignore — 머신별 비공개):
```toml
[ai_cli.commands.my-claude]
exec    = ["claude", "--model", "haiku", "-p", "{prompt}"]
input   = "arg"          # arg | stdin | file:{path}
timeout = 30
env     = { ANTHROPIC_LOG = "error" }

[ai_cli.tasks]
expand_query = "my-claude"
```

`.pkm/config.toml` (커밋 — 공용 디폴트만):
```toml
[ai_cli]
default        = "my-claude"
fallback_order = ["my-claude", "codex", "gemini"]
```

⚠️ **`exec` / `env` / credentials 패턴 키는 `config.toml` 에 두면 `pkm doctor` 가 에러로 차단** — `config.local.toml` 로 옮기라는 hint 를 준다.

확인 + 사용:
```bash
pkm doctor                                        # ai_cli row 가 detected: my-claude
pkm search "OAuth 토큰 저장" --expand            # 셸아웃 + 변형 2~3 개 → 병렬 검색

# 한 회성 오버라이드 (config 변경 없이)
PKM_AI_CLI=ollama-local pkm search "..." --expand
```

해석 순서: 셸 훅 (`.pkm/hooks/<task>.sh`) → config tasks → config default → 자동탐지 → 모두 실패 시 명확한 에러.

`--expand` 안 쓰면 AI CLI 자체가 불필요하다. `/ask` 도 Claude Code 자체로 동작 — 즉 본 PKM 은 **API 키 0 개, 외부 SDK 미사용** 으로도 모든 핵심 기능이 돌아간다.

---

## 5. 더 깊이 들어가려면

- **디자인 사양** (1266 줄, 한국어): `docs/superpowers/specs/2026-05-01-pkm-design.md`
- **마일스톤 플랜**: `docs/superpowers/plans/2026-05-{01..03}-pkm-m{1..7}-*.md`
- **운영자 매뉴얼** (AI 진입점): 데이터 repo 의 `SCHEMA.md`
- **에러 코드 단일 진실**: `pkm/errors.py` (커버리지: `tests/test_failure_mode_matrix.py`)
- **CLI surface 단일 진실**: `pkm --help` + 각 서브명령 `--help`
