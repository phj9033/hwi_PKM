# 기능 상세 & 유즈케이스

`pkm` CLI 의 운영자용 매뉴얼. CLI surface 한 줄 요약은 `README.md` 에, 디자인 근거는 `docs/superpowers/specs/` 에. 이 문서는 **무엇을 어떻게 쓰는가**와 **언제 쓰는가** 두 가지에 집중한다.

목차:

- [기능 상세](#기능-상세) — 9 개 그룹, 각 그룹마다 명령 · 게이트 · 게이트가 만드는 에러 코드
- [슬래시 커맨드](#슬래시-커맨드) — Claude Code 세션용 워크플로우 표
- [유즈케이스](#유즈케이스) — 9 시나리오 walk-through
- [더 깊이](#더-깊이) — 사양·플랜·에러 단일 진실 포인터

---

## 기능 상세

### 1. Capture · Chunks · Extract

| 명령 | 용도 |
|---|---|
| `pkm capture create --slug S --title T [--url U] [--from-file F]` | 단건 노트 — stdin 또는 `--from-file` 로 본문 |
| `pkm capture {list,show,set-status,rm}` | 라이프사이클 조회·전환 |
| `pkm chunks new <topic>` | `data/raw/chunks/<topic>/` 폴더 + `README.md` |
| `pkm chunks {add,list,show,set-status,rm}` | 다중 소스 큐레이션 (collecting → curating → ready) |
| `pkm extract <file> [--out P]` | PDF/HTML → markdown (`[extract]` extra 필요) |

**라이프사이클 규칙:**
- 슬러그에 날짜 prefix 가 없으면 `YYYY-MM-DD-` 자동 추가
- `status: reviewed` 이후 본문 변경은 `RAW_BODY_MUTATED` warning (compounding 위반 감지)
- chunks `set-status ready` → `pkm write new --from-chunks <topic>` 으로 합성 진입

---

### 2. Index · Search · Related

```bash
pkm reindex db [<path>] [--full] [--scope wiki|raw|writing|all|projects] [--low-memory]
pkm search <q> [-n N] [--scope ...|project[:<id>]] [--expand] [--no-rerank] [--with-related] [--explain]
pkm related <path> [--mode backlinks|semantic|both]
```

**Search 파이프라인 (5 단계):**

1. **쿼리확장** (`--expand` 옵트인) — AI CLI 셸아웃, 변형 2~3 개. 실패 시 `EXPAND_FAILED` hard-fail
2. **병렬 retrieval** — 변형마다 BM25 (FTS5) top-50 + 벡터 (bge-m3 → vec0 코사인) top-50
3. **RRF 융합** — `score = Σ 1/(60 + rank)`, top-30 후보
4. **Cross-encoder rerank** — `bge-reranker-v2-m3` (`--no-rerank` 시 skip)
5. **top-K 노출** + 모든 점수 (`--explain` 시)

**Scope (`--scope`):**

| 값 | 검색 범위 |
|---|---|
| `wiki` | `data/wiki/**` (cwd 가 미등록 프로젝트일 때 디폴트) |
| `raw` / `writing` | 각각 `data/raw/**` / `data/writing/**` |
| `all` | 전체 데이터 repo |
| `projects` | `data/projects/**` 전체 |
| `project:<id>` | 특정 프로젝트만 |
| `project` | cwd resolver 가 식별한 현재 프로젝트 (`NOT_LINKED` 면 hard-fail) |

> **Default scope (M13):** cwd 가 등록된 프로젝트면 `project:<id>`, 아니면 `wiki`.

**한국어 토크나이저 (M12):** `[korean]` extra 설치 후 `pkm migrate --apply` 로 `m002` 가 적용되면 BM25 가 Kiwi 형태소 분석 + FTS5 `unicode61` 로 전환. 미설치 시 trigram 으로 silently 유지. 상태는 `pkm doctor` 의 `tokenizer` 행.

`--with-related` 출력 (각 hit 에 합성):

```json
"related": {
  "wikilinks_out": [...], "wikilinks_in": [...],
  "derived_from": [...], "tags": [...],
  "semantic_neighbors": [{"path":"...","similarity":0.78}]
}
```

---

### 3. Promote · Demote · Wiki edit (라이프사이클 게이트)

```bash
pkm promote <ref> --to concepts|entities|notes|reports [--slug S] [--keep-source]
pkm demote <wiki-path>
pkm wiki edit <ref> --replace|--patch          # stdin = 본문 또는 unified diff
pkm wiki suggest <slug> [-n K] [--threshold T] # 단일 페이지 MISSING_LINK_CANDIDATE
```

`<ref>` 은 capture slug · 절대 path · `data/writing/<slug>.md` 모두 받음.

**게이트:**

- **Capture → wiki**: `status: reviewed` 필수. 아니면 `STATUS_NOT_REVIEWED`
- **Writing → wiki (M11 grounding gate)**: `status: final` + 4 룰
  - `R1 CITATION_NOT_DERIVED` — 본문의 `[<path>]` 인용은 모두 frontmatter `derived_from` 안에 있어야 함
  - `R2 DERIVED_NOT_CITED` — `derived_from` 의 모든 path 는 본문에 ≥1 회 인용
  - `R3 UNGROUNDED_WRITING` — 본문 ≥ 400자 인데 인용 0 개. `purpose: essay` 또는 `grounding_exempt: true` 만 면제 (R1/R2/R4 는 그대로 적용)
  - `R4 BROKEN_CITATION` — 인용 path 가 디스크에 존재
  - 같은 4 룰이 `pkm lint` warning 으로도 노출 (promote 전 미리보기)
- **부수효과**: source = `archived` (기본; `--keep-source` 면 보존), wiki = `status: stub` + `promoted_from`, auto-commit, `data/log.md` append

**`pkm wiki edit` 는 strict 모드에서 wiki 변경의 유일한 escape valve** — `.claude/settings.json` 이 `data/wiki/**` 를 deny-write 하기 때문에 AI 의 `Edit` 툴은 직접 못 쓴다.

---

### 4. Writing (AI 합성 워크스페이스)

```bash
pkm write new --slug S [--from-search "..." | --from-chunks <topic>] [--purpose guideline|report|summary|essay]
pkm write {list,set-status}    # set-status: draft | final | abandoned
```

`data/writing/` 는 wiki 와 달리 **AI 가 `Edit` 로 직접 작성 가능** (strict 모드에서도). 표준 흐름:

1. `pkm write new --from-chunks <topic>` → frontmatter 의 `derived_from` 이 chunks 파일들로 자동 시드
2. AI 가 `Edit` 로 본문 작성 — `[<path>]` 인용 필수
3. `pkm write set-status <s> final` → `pkm promote data/writing/<s>.md --to <bucket>`

별도의 `finalize` 명령은 없다 — `promote` 가 writing 도 받는다.

---

### 5. Lint (정합성 게이트)

```bash
pkm lint [--fix] [--errors-only] [--json]
```

| 코드 | 종류 | 의미 | `--fix` |
|---|---|---|:-:|
| `MISSING_FIELD` | error | 필수 frontmatter 누락 | ✅ `created_at`, `slug` |
| `INVALID_VALUE` | error | enum 위반 (e.g. `status: foo`) | — |
| `DUPLICATE_SLUG` | error | 같은 slug 가 2 곳 이상 | — |
| `BROKEN_WIKILINK` | error | `[[link]]` 가 실재하지 않는 경로 | — |
| `BROKEN_DERIVED_FROM` | error | `derived_from:` 의 source 누락 | — |
| `ORPHAN_PROMOTED_SOURCE` | error | wiki 의 `promoted_from` 이 source 와 mismatch | ✅ |
| `MISSING_PROJECT_FIELD` (M13) | error | `data/projects/<id>/` frontmatter `project` 누락/불일치 | ✅ |
| `INVALID_CATEGORY` (M13) | error | category 가 {decisions, pitfalls, snippets, qna, notes} 외 | — |
| `CATEGORY_PATH_MISMATCH` (M13) | error | path 카테고리와 frontmatter `category` 불일치 | ✅ |
| `ORPHAN_PROJECT_DIR` (M13) | error | `data/projects/<id>/` 에 `index.md` 없음 또는 `git_remotes` 비어있음 | — |
| `STALE_DRAFT` / `STALE_STUB` | warning | N 일 이상 방치 | — |
| `ORPHAN_WIKI` | warning | 인바운드 link 0 인 wiki | — |
| `LARGE_CHUNK_NEVER_PROMOTED` | warning | chunks 가 ready 인데 미승격 | — |
| `LANG_INCONSISTENT` | warning | 본문 언어와 frontmatter `lang` 불일치 | — |
| `RAW_BODY_MUTATED` | warning | reviewed 이후 본문 해시 변경 | — |
| `BROKEN_CITATION` | warning | `[<path>]` 인용 경로 없음 | — |
| `CITATION_NOT_DERIVED` (M11) | warning | promote 시 hard gate (R1) | — |
| `DERIVED_NOT_CITED` (M11) | warning | promote 시 hard gate (R2) | — |
| `UNGROUNDED_WRITING` (M11) | warning | promote 시 hard gate (R3) | — |
| `SIMILAR_KNOWLEDGE_CANDIDATE` (M13) | warning | 두 프로젝트 항목 코사인 유사도 ≥ 0.92 | — |

`--errors-only` 는 warning 무시 + error 만으로 exit 게이트 (CI/pre-commit 용).

---

### 6. Dashboard

```bash
pkm dashboard build [--out PATH]   # 기본 ./dashboard/, 단일 명령으로 9 페이지 생성
```

생성물 (모두 정적 HTML, 외부 CDN 없음, 오프라인 동작):

- `index.html` — 통계 · lint 요약 · 최근 log 20개 · 빠른 링크
- `captures.html` / `chunks.html` / `wiki.html` / `writing.html` — 필터바 (status/lang/tags) + 표
- `doc/<path>.html` — frontmatter 사이드바 + 본문 + Backlinks/Outgoing/Semantic neighbors/Provenance
- `search.html` — 클라이언트 substring + 태그 매칭 (진지한 검색은 `pkm search`)
- `help.html` — `SCHEMA.md` 렌더 + CLI 치트시트
- `status.html` — `pkm doctor --json` + 마스킹된 config + 권한 모드
- `graph.html` — wiki 링크 그래프 (vis-network) + MISSING_LINK_CANDIDATE 제안 오버레이

**Graph 페이지 (M10):**
- 노드 색 = bucket, 점선 = `derived_from`, 빨간 점선 = suggested
- 결정론: 초기 좌표 = `sha256(path)` 시드 (같은 corpus → 같은 좌표)
- M13 신규 그룹: `projects/{decisions,pitfalls,snippets,qna,notes}`
- 노드 cap (`max_nodes=1000`) 초과 시 connectivity 낮은 순 drop, `stats.trimmed` 카운트
- 인덱스 (`.pkm/index.db`) 부재 시 unavailable 카드

```toml
# .pkm/config.toml
[dashboard.graph]
max_nodes              = 1000
include_writing        = false
include_captures       = false
overlay_suggestions    = true
include_projects       = true   # M13
project_filter         = []     # 빈 = 전체
```

빌드 트리거는 수동 (`pkm dashboard build`) — 자동화하려면 git post-commit 훅. `dashboard/` 는 gitignore.

---

### 7. Migration (M12)

```bash
pkm migrate              # = --check (dry-run)
pkm migrate --apply      # 각 마이그레이션은 SAVEPOINT 안에서 동작
```

`pkm/store/migrations/m<NNN>_*.py` 모듈을 자동 발견 → ID 순 정렬 → `schema_version` 보다 큰 것만 적용.

| ID | DEPENDS_ON_EXTRA | 설명 |
|---|---|---|
| 1 | — | V1 baseline (no-op marker) |
| 2 | `korean` | `chunks_fts` 토크나이저 → Kiwi pre-tokenization (한국어 BM25 recall ↑) |
| 3 | — | `chunks` 테이블에 `project`, `category`, `session_id` 컬럼 + `idx_chunks_project_category` |

**격리:**
- 의존 extra 가 import 안 되면 silently skip — 에러 아님, schema_version 그대로
- 마이그레이션 raise → SAVEPOINT 롤백 + `MIGRATION_FAILED`
- FTS5 DDL 은 SAVEPOINT 보장이 약해 m002 는 swap 가드 사용 (`chunks_fts_old` 로 rename → 검증 → drop, 실패 시 복원)
- `pkm doctor --strict` + 미적용 마이그레이션 = `MIGRATION_PENDING` 으로 exit 1

---

### 8. Projects (M13)

`data/projects/<id>/` 아래에 프로젝트별 노하우를 5 카테고리로 (decisions / pitfalls / snippets / qna / notes) 별도 레이어로 보관. 코드 repo cwd 에서 `pkm project link` 한 번 박아두면 git remote 정규화로 PC 간 동일성이 자동 매칭.

| 명령 | 용도 |
|---|---|
| `pkm project link --id <slug>` | cwd git remote 등록 (멱등 — 이미면 `ALREADY_LINKED`, exit 0) |
| `pkm project current` | cwd → project_id 5단계 resolver (env / overrides / git remote / local_paths / NOT_LINKED) |
| `pkm project {list,show,rm}` | 조회 / 제거 (`--keep-data` 면 index 만 삭제) |
| `pkm project rebuild-index <id>` | `data/projects/<id>/index.md` 결정론적 재생성 |
| `pkm doctor --fix` | `.pkm-link` 마커 누락/불일치/orphan/invalid 4종 자동 복구 |
| `pkm project knowledge add --project <id> --category <cat> --slug <s> --title <t>` | 새 노하우 markdown (stdin = 본문) |

**Resolver 우선순위 (`pkm project current` · `--scope project` 가 사용):**

1. `PKM_PROJECT` env (1회용 override)
2. `.pkm/config.local.toml` `[project_overrides]` cwd 매치 (PC 별)
3. cwd git remote 정규화 → frontmatter `git_remotes` 매치 (SoT)
4. cwd 경로 → `data_repo_local_paths` 매치 (드문 fallback)
5. None → `NOT_LINKED`

**cwd 마커 (`.pkm-link`):** `pkm project link` 는 cwd 에 `.pkm-link` 파일을 생성한다 (내용: `<project_id>\n`). 이 마커는 `~/.claude/CLAUDE.md` 의 PKM 컨텍스트 로딩 fast-path 가 미링크 디렉토리에서 `pkm project current` 호출을 회피하기 위한 hint 다. ProjectIndex 가 여전히 SoT 이므로 마커 동기화 실수가 데이터 무결성에 영향을 주지 않는다. `pkm doctor --fix` 가 4종 진단 (`MARKER_MISSING/MISMATCH/ORPHAN/INVALID`) 을 자동 복구. 팀이 같은 PKM data repo 를 공유하지 않는다면 `.pkm-link` 를 `.gitignore` 에 추가하는 것을 권장 (per-machine link state).

권장 `~/.claude/CLAUDE.md` 블록 (사용자가 직접 교체):

````markdown
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Quick check: is `.pkm-link` present in cwd? If not, silently proceed.
2. If marker exists, run `pkm project current --json 2>/dev/null`.
3. If `ok: true`: invoke the `pkm:recalling-project-context` skill.
4. If marker exists but `ok: false`: silently proceed.
````

---

### 9. Sessions · Skills · Install · Context (M14)

Claude Code 세션 transcript 를 발견 · 추출 · 프로젝트 노하우로 저장하는 V3 레이어.

```bash
# Session — transcript 메타 관리 (CLI 가 추출하지 않음)
pkm session list  [--project ID] [--unprocessed] [--since DATE] [--until DATE] [--min-messages N=5]
pkm session show  <uuid>                                # transcript_path + project_id + 메타
pkm session forget <uuid>                               # PC-local 처리 마커 제거
pkm session mark-processed <uuid> --extracted-count N   # 메타파일 emit (idempotent)

# Install — PC 별 1 회 글로벌 통합
pkm install --for claude-code --data-repo <PATH> [--uninstall]

# Context — cwd 프로젝트 → index.md 본문을 stdout 에 주입
pkm context inject [--project ID] [--max-tokens N=600] [--quiet-on-not-linked/--no-quiet]
```

**Session 동작:** `~/.claude/projects/**/*.jsonl` 스캔 → cwd 매핑 프로젝트 세션만 반환. `--unprocessed` 는 메타파일 (`.pkm/sessions/<project>/<uuid>.json`, gitignore — PC-local) 없는 것만. `pkm session show` 의 출력을 `extracting-session-knowledge` 스킬이 받아 `Read` 툴로 transcript 직접 읽음 — **CLI 는 추출하지 않음, Claude 본인이 함**.

`PKM_TRANSCRIPT_ROOT` env 로 transcript 루트 override 가능 (기본 `~/.claude/projects`).

**Install 산출물 (4 가지, 모두 멱등):**

1. `~/.pkm/config.toml` — `data_repo` SoT
2. `~/.claude/CLAUDE.md` — managed 블록 (HTML 코멘트 마커 사이) 삽입/교체. 마커 외부 사용자 콘텐츠 보존
3. `~/.claude/commands/pkm-{recall,extract-session,backfill,project}.md` — 4 슬래시 명령
4. `~/.claude/skills/pkm/{recalling-project-context,extracting-session-knowledge,backfilling-sessions}/` — 3 스킬 번들

3+4 는 frontmatter 가 필요해 in-file 마커 못 씀 → `~/.pkm/install_manifest.json` 에 emit 절대 경로 기록 → `--uninstall` 이 manifest 만큼 정확히 삭제.

> 지원하지 않는 target (`codex`, `cursor`, ...) 은 `NOT_IMPLEMENTED` — V4 예정.

**Context inject 동작:** cwd → 프로젝트 resolver 후 `data/projects/<id>/index.md` 본문 (frontmatter 제외) 출력. 4-char/token 휴리스틱으로 budget 초과 시 마지막 마침표에서 cut + `(truncated; run /pkm-recall ...)` 노티스 추가. 기본 `--quiet-on-not-linked` (NOT_LINKED 면 silent exit 0). `~/.claude/CLAUDE.md` 의 managed 블록이 `pkm:recalling-project-context` 스킬 invoke → 스킬이 이 명령을 호출.

---

## 슬래시 커맨드

설치 경로는 두 갈래 — `pkm init` 이 깔아주는 데이터 repo 9 종 (워크플로우용) + `pkm install --for claude-code` 가 깔아주는 글로벌 4 종 (M14 전용).

### 데이터 repo `.claude/commands/` (V1~V2)

| 커맨드 | 입력 | 핵심 동작 |
|---|---|---|
| `/collect <url\|text>` | URL/텍스트 | WebFetch → 요약 + 태그 → `pkm capture create --status draft` |
| `/research <topic>` | 토픽 | 다중 WebSearch + WebFetch → 3~6 capture + 옵션 chunks 묶음 |
| `/review-captures` | (없음) | draft 순회 → `set-status reviewed` 또는 `rm` |
| `/promote` | (없음) | reviewed 검토 → bucket 결정 → `pkm promote` |
| `/lint [--fix]` | (옵션) | `pkm lint --json` 보고 + 필요 시 `--fix` |
| `/ask <question>` | 질문 | `pkm search` → top-K Read → 인용 grounded 답변 |
| `/write <topic>` | 토픽 | `pkm write new` → Edit 본문+인용 → `final` → `promote` |
| `/style-import <url\|file>` | URL/파일 | WebFetch + manual fallback → `data/style/<slug>.md` |
| `/blog "<주제>" \| --random` | 주제 또는 무인자 | search/sample 기반 outline → `blog/<slug>.md` 또는 `blog/seeds/` |

### 글로벌 `~/.claude/commands/` (M14)

| 커맨드 | 핵심 동작 (스킬 invoke) |
|---|---|
| `/pkm-recall <topic>` | `pkm:recalling-project-context` — `pkm project current` → `pkm context inject` → 옵션 `pkm search --scope project` |
| `/pkm-extract-session [uuid]` | `pkm:extracting-session-knowledge` — transcript Read → 5 카테고리 후보 → 2 라운드 사용자 검토 → `pkm project knowledge add` × N + `pkm session mark-processed` |
| `/pkm-backfill [--since ...]` | `pkm:backfilling-sessions` — `pkm session list --unprocessed` → 첫 세션 자세히 / 이후 일괄 모드 / 중단 시점부터 재개 |
| `/pkm-project [verb]` | `pkm project link/current/list/show` 의 thin wrapper |

> **슬래시 ↔ 스킬 매핑**: 슬래시는 사용자 입력 surface, 실제 워크플로우는 `~/.claude/skills/pkm/<id>/SKILL.md` 가 정의. `pkm install` 한 번에 모두 설치.

### `/ask` 인용 계약 (Karpathy grounding)

- 모든 사실 주장 끝에 `[<wiki-path>]`. 다중 출처는 `[a.md][b.md]`
- 검색 결과 부족 시 "wiki 에 관련 내용이 부족합니다" + 종료 — 추측 금지
- 인용 경로는 path-resolvable — `pkm lint` 가 `BROKEN_CITATION` warning 으로 사후 검증
- 답변을 capture 로 저장하려면 frontmatter `derived_from: [...인용 경로 모두]` 필수 (compounding)

**Anti-pattern**: "내가 알기로는...", "일반적으로는...", 인용 없는 일반 지식 — 모두 금지.

---

## 유즈케이스

### UC1. 새 PC 셋업부터 첫 캡처까지

```bash
# 의존성 + 소스 repo
brew install uv
git clone <소스-repo> ~/Downloads/Claude_lab/hwi_PKM
cd $_ && uv sync --all-extras
uv tool install --reinstall -e ".[ml,extract,korean]"

# 데이터 repo (이미 있으면 clone, 없으면 빈 dir)
git clone <데이터-repo> ~/Documents/pkm
cd ~/Documents/pkm
pkm bootstrap                    # init 자동 skip → doctor --download → reindex --full → dashboard build
pkm doctor --strict              # 모두 ✓

# 첫 캡처
echo "본문" | pkm capture create --slug hello --title "첫 노트"
pkm capture set-status hello reviewed
pkm reindex db data/raw/captures/2026-05-04-hello.md
pkm search "첫" --scope raw
```

빈 디렉토리에서 시작하면 `mkdir + cd + pkm bootstrap` 만 — `init` 도 자동 prepend. 모델 캐시 (~8 GB) 는 `~/.cache/pkm/models/` 한 번만 받고 모든 venv·repo 가 공유.

### UC2. 단일 URL → wiki 승격

```
Claude Code 세션:
  /collect https://example.com/oauth-tokens
  → WebFetch + 요약 + tags → data/raw/captures/2026-05-04-oauth-tokens.md (draft)

  /review-captures
  → 본문 확인 → set-status reviewed

  /promote
  → bucket = "concepts" 결정
  → pkm promote oauth-tokens --to concepts
  → data/wiki/concepts/oauth-tokens.md (stub)
  → 원본 capture status → archived (자동), git commit (자동)

수정이 필요하면 (escape valve):
  pkm wiki edit concepts/oauth-tokens --replace < new_body.md
  pkm wiki edit concepts/oauth-tokens --patch   < unified.diff
```

`data/wiki/**` 는 `.claude/settings.json` 으로 deny-write — Claude `Edit` 툴이 못 쓴다. 유일한 경로가 `pkm wiki edit`.

### UC3. 다중 소스 → writing 합성 → 승격

"Embedding 모델 비교" 같은 종합 토픽.

```
1) 리서치
   /research "embedding model comparison 2026"
   → 5~6 capture 자동 생성
   → pkm chunks new embedding-comparison
   → pkm chunks add embedding-comparison <captures...>
   (옵션) PDF: pkm extract paper.pdf --out data/raw/chunks/embedding-comparison/paper.md
   → pkm chunks set-status embedding-comparison ready

2) 합성
   /write embedding-comparison
   → pkm write new --slug embedding-models --from-chunks embedding-comparison --purpose summary
   → derived_from 자동 시드 (chunks 파일 목록)
   → AI 가 Edit: derived_from 각 파일 Read → 종합 + [<chunk-path>] 인라인 인용
   → pkm write set-status embedding-models final

3) 승격 (M11 grounding gate 통과 필수)
   pkm promote data/writing/embedding-models.md --to reports
   → data/wiki/reports/embedding-models.md (stub)
```

이 경로가 본 PKM 의 **compounding** 핵심 — 매 검색마다 재합성하지 않고 wiki 가 누적된다.

### UC4. wiki 에 답이 있는지 `/ask` 로 묻기

```
/ask "OAuth refresh token 은 어디에 저장하나요?"

내부:
  1. pkm search "..." --scope wiki -n 8 --json    # config 에 expand_query 정의 시 --expand
  2. top-K 파일을 Read 툴로 읽기
  3. 본문만 근거로 합성 — 모든 사실에 [<wiki-path>] 첨부
  4. wiki 가 비면 "관련 내용 부족" + 종료

답변 예:
  OAuth refresh token 은 httpOnly secure cookie 에 저장한다.
  [data/wiki/concepts/oauth-token-storage.md]
  로컬스토리지 저장은 XSS 노출 위험이 있어 권장하지 않는다.
  [data/wiki/concepts/oauth-token-storage.md][data/wiki/notes/web-auth-pitfalls.md]
```

검증: 다음 `pkm lint` 가 인용 경로 실재 여부 자동 검사 (`BROKEN_CITATION`).

### UC5. lint 실패 흐름 + `--fix`

```bash
pkm lint --json
# error MISSING_FIELD            data/raw/captures/foo.md  (slug 누락)
# error BROKEN_WIKILINK          data/wiki/concepts/baz.md → [[non-existent]]
# error ORPHAN_PROMOTED_SOURCE   data/wiki/notes/qux.md
# warn  STALE_DRAFT              data/raw/captures/old.md  (45일 방치)
# warn  BROKEN_CITATION          data/wiki/notes/qux.md   ([data/wiki/missing.md])

pkm lint --fix --json
# 자동: MISSING_FIELD(slug, created_at), ORPHAN_PROMOTED_SOURCE
# 잔여: BROKEN_WIKILINK, BROKEN_CITATION, STALE_DRAFT — 사람 결정

pkm lint --errors-only          # CI/pre-commit 게이트
```

`/lint` 슬래시가 위 흐름을 한 번에 — `--json` 보고 + 필요 시 `--fix` + 잔여 수동 안내.

### UC6. 대시보드 빌드 + 새 PC 복원

```bash
pkm dashboard build
open dashboard/index.html

# 새 PC 에서 데이터 repo 통째로 복원
git clone <데이터-repo> && cd $_
pkm bootstrap                    # doctor --download → reindex --full → dashboard build
```

`dashboard/` · `.pkm/index.db` 는 gitignore — markdown 만으로 결정론적 재생성. 첫 1 회 모델 다운로드 후엔 추가 다운로드 0.

자동화 (선택): `.git/hooks/post-commit` 에:
```bash
#!/usr/bin/env bash
pkm dashboard build > /dev/null
```

### UC7. AI CLI 셸아웃 옵트인 (`search --expand`)

기본 검색은 결정론 (BM25 + vec0 + RRF + reranker — 모두 로컬). 쿼리확장이 정확도에 도움이 될 때만 옵트인.

```toml
# .pkm/config.local.toml (gitignore — PC 별 비공개)
[ai_cli.commands.my-claude]
exec    = ["claude", "--model", "haiku", "-p", "{prompt}"]
input   = "arg"          # arg | stdin | file:{path}
timeout = 30
env     = { ANTHROPIC_LOG = "error" }

[ai_cli.tasks]
expand_query = "my-claude"
```

```toml
# .pkm/config.toml (커밋 — 공용 디폴트만)
[ai_cli]
default        = "my-claude"
fallback_order = ["my-claude", "codex", "gemini"]
```

> ⚠️ `exec` / `env` / credentials 패턴 키를 `.pkm/config.toml` 에 두면 `pkm doctor` 가 에러로 차단 — `config.local.toml` 로 옮기라는 hint 출력.

```bash
pkm doctor                                  # ai_cli row: detected: my-claude
pkm search "OAuth 토큰 저장" --expand       # 셸아웃 + 변형 2~3 → 병렬 검색
PKM_AI_CLI=ollama-local pkm search "..." --expand   # 1회용 override
```

해석 순서: 셸 훅 (`.pkm/hooks/<task>.sh`) → config tasks → config default → 자동탐지 → 모두 실패 시 명확한 에러.

`--expand` 안 쓰면 AI CLI 자체 불필요 — 본 PKM 은 **API 키 0 개, 외부 SDK 미사용** 으로도 모든 핵심 기능이 돈다.

### UC8. 세션 추출 → 프로젝트 등록 (M14)

상황: hwi_PKM 작업 중 결정 + 함정 + 스니펫이 transcript 에 쌓였다.

```
Claude Code 세션 안에서:
  /pkm-extract-session
  → pkm:extracting-session-knowledge 스킬:
    1. CLAUDE_SESSION_ID env 또는 최근 세션 → uuid 결정
    2. pkm session show <uuid> → transcript_path
    3. transcript Read 툴로 읽기
    4. 5 카테고리 후보 빌드 (decisions 3, pitfalls 1, snippets 5, qna 0, notes 2)
    5. 사용자에게 markdown 표 제시 → "decisions 3 빼고 진행" 응답
    6. 반영 후 재출력 → "OK"
    7. pkm project knowledge add 항목별 호출 (× N) — auto-commit
    8. pkm session mark-processed
    9. pkm project rebuild-index hwi-pkm
   10. pkm reindex db --scope project:hwi-pkm

결과:
  data/projects/hwi-pkm/decisions/2026-05-07-*.md (2)
  data/projects/hwi-pkm/pitfalls/2026-05-07-*.md  (1)
  data/projects/hwi-pkm/snippets/2026-05-07-*.md  (5)
  data/projects/hwi-pkm/notes/2026-05-07-*.md     (2)
  .pkm/sessions/hwi-pkm/<uuid>.json (메타, gitignore)
  data/projects/hwi-pkm/index.md  (자동 갱신)
```

다음 세션에서 `/pkm-recall OAuth` 하면 검색에 즉시 잡힘.

### UC9. 과거 세션 일괄 backfill (M14)

상황: PKM 처음 도입, `~/.claude/projects/-Users-me-Code-app/` 에 47 개 세션 누적.

```
1) cd ~/Code/my-app
2) pkm project link --id my-app
3) /pkm-backfill --project my-app --since 2026-01-01

   → pkm:backfilling-sessions 스킬:
     - pkm session list --unprocessed → 47 세션
     - 사용자 확인 + 모드 선택: "첫 세션 자세히 / 이후 일괄"
     - 첫 세션: 2 라운드 검토 → 8 항목 등록
     - 두 번째부터 일괄 모드 — 한 번 보여주고 yes/skip/edit/stop
     - 세션 12 에서 사용자 stop-batch
     - 처리: 12/47, ~80 항목

4) 다음에 /pkm-backfill 재호출 → 13 부터 자동 재개
```

중단 안전 — 처리된 세션은 `.pkm/sessions/my-app/<uuid>.json` 에 기록되어 재처리 안 됨. 특정 세션 재처리는 `pkm session forget <uuid>` 후 backfill 재실행.

---

## 더 깊이

| 자료 | 위치 |
|---|---|
| 디자인 사양 (V1, V2, V3) | `docs/superpowers/specs/2026-05-{01,06,07}-*.md` |
| 마일스톤 플랜 (M1~M14) | `docs/superpowers/plans/2026-05-*-pkm-m*.md` |
| 운영자 매뉴얼 (AI 진입점) | 데이터 repo 의 `SCHEMA.md` |
| 에러 코드 단일 진실 | `pkm/errors.py` (커버리지: `tests/test_failure_mode_matrix.py`) |
| CLI surface 단일 진실 | `pkm --help` + 각 서브명령 `--help` |
