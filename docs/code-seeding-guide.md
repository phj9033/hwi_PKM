# Code Seeding Guide — AI 행동 매뉴얼

> 신규 링크된 PKM 프로젝트의 "지식 0" 상태에서 출발할 때, AI 가 코드를 직접 훑어 자주 쓰이는 helper (snippets) 와 모듈 책임 (notes) 을 후보로 제안하고, **항목별 사용자 검토 후** 기존 `pkm project knowledge add` 로 시드한다. PKM 코어 코드는 손대지 않는다 — 이 markdown 한 파일이 전부의 행동 매뉴얼이다.

이 문서는 AI 에이전트 (Claude 등) 가 따라 읽고 그대로 실행하는 매뉴얼이다. 사람이 읽어도 되지만 일차 독자는 LLM.

목차:

1. [언제 쓰나](#1-언제-쓰나)
2. [사전 조건](#2-사전-조건)
3. [전체 단계 개요](#3-전체-단계-개요)
4. [Step 1 — 프로젝트 식별](#step-1--프로젝트-식별)
5. [Step 2 — 후보 풀링 (ripgrep)](#step-2--후보-풀링-ripgrep)
6. [Step 3 — Dedupe 휴리스틱](#step-3--dedupe-휴리스틱)
7. [Step 4 — 의미 부여 (Read)](#step-4--의미-부여-read)
8. [Step 5 — 검토 (round 1, round 2)](#step-5--검토-round-1-round-2)
9. [Step 6 — Knowledge add 호출](#step-6--knowledge-add-호출)
10. [Step 7 — 후처리](#step-7--후처리)
11. [Step 8 — 보고](#step-8--보고)
12. [Failure modes](#failure-modes)
13. [Self dry-run 예시 (본 hwi_PKM repo)](#self-dry-run-예시-본-hwi_pkm-repo)
14. [Provenance](#provenance)

---

## 1. 언제 쓰나

- 사용자가 **명시적으로** 호출했을 때만. 자동 트리거 (link 직후 / cron / git hook) **없음**.
- 트리거 예: "이 가이드 따라 코드 분석해서 시드해줘", "code-seeding-guide.md 따라 진행".
- 신규 링크 직후뿐 아니라 **언제든 재호출 가능** — 새 helper 가 추가됐을 때, 모듈 구조가 바뀌었을 때 등.

## 2. 사전 조건

- cwd 가 `pkm project link` 로 등록된 프로젝트일 것 (`pkm project current --json` 의 `ok: true`).
- `ripgrep` (`rg`) 설치 권장. 없으면 `grep -rE` fallback 으로 동등한 작업 가능 (정밀도 약간 ↓).

## 3. 전체 단계 개요

```
[1] pkm project current      → project_id 확정
[2] ripgrep 후보 풀링         → snippets / notes 후보 풀
[3] 기존 시드와 dedupe        → 충돌 후보 마크
[4] Read 로 의미 부여         → title / summary / tags
[5] 표 일괄 제시 → 라운드 1, 2 → OK
[6] pkm project knowledge add × N
[7] pkm project rebuild-index <id> + pkm reindex db --scope project:<id>
[8] 사용자에게 보고
```

---

## Step 1 — 프로젝트 식별

```bash
pkm project current --json
```

- `ok: false`, `code: NOT_LINKED` → "현 cwd 미링크. 먼저 `pkm project link --id <slug>` 실행해주세요." 출력하고 **stop**. 진행 X.
- `ok: true` → `project_id` 변수에 보관.

## Step 2 — 후보 풀링 (ripgrep)

### 2.1 snippets 후보 (자주 쓰이는 helper)

언어 무관 정의 시그니처 정규식. Python · TypeScript · Go · Rust · C# · Kotlin · Swift 를 공통 커버.

```bash
# 함수/메서드 정의 시그니처 — 이름만 추출
rg -nU --type-add 'src:*.{py,ts,tsx,js,jsx,go,rs,cs,kt,swift}' --type src \
  '^\s*(def |function |func |fn |public\s+\w+\s+|private\s+\w+\s+|internal\s+\w+\s+|protected\s+\w+\s+|static\s+\w+\s+)([a-z_][a-zA-Z_0-9]*)\s*\(' \
  --no-filename --no-line-number -o \
  | sed -E 's/.*[ \t]([a-z_][a-zA-Z_0-9]*)\s*\(/\1/' \
  | sort -u > /tmp/_defs.txt
```

각 이름의 호출 횟수 (정의 자체 포함됨 — 정의 1 회 차감 후 카운트):

```bash
while read name; do
  count=$(rg -c -w "$name" --type src 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  echo "$count $name"
done < /tmp/_defs.txt | sort -rn
```

**필터 룰:**

- `_` 시작 이름, `test_*`, `setUp`, `tearDown`, `main`, `register*` 같은 프레임워크/엔트리 이름은 제외.
- 호출 횟수 ≥ **5** (디폴트, 작은 repo 면 **2~3** 으로 낮춰라 — §"노이즈 통제" 참고).
- 상위 **20** 개 (디폴트) 가 후보.

각 후보의 정의 위치 1 곳 (대표 파일):

```bash
rg -n --type src "^\s*(def |function |func |fn |public\s+\w+\s+\w+\s+|private\s+\w+\s+)\b<name>\b\s*\(" -m1
```

### 2.2 notes 후보 (모듈/디렉토리 책임)

```bash
# depth 1~2 디렉토리, 파일 ≥ 5 개 또는 README/__init__/index 가 있는 곳
find . -maxdepth 3 -mindepth 1 -type d \
  -not -name '__pycache__' -not -name 'node_modules' -not -name '.git' \
  -not -name 'dist' -not -name 'build' \
  | while read d; do
      fcount=$(find "$d" -maxdepth 1 -type f \( -name '*.py' -o -name '*.ts' -o -name '*.go' -o -name '*.rs' -o -name '*.cs' \) | wc -l | tr -d ' ')
      has_marker=0
      for m in README.md README __init__.py "index.ts" "index.js" "mod.rs" "lib.rs"; do
        [ -f "$d/$m" ] && has_marker=1
      done
      [ "$fcount" -ge 5 ] || [ "$has_marker" = 1 ] && echo "$fcount $d"
    done | sort -rn
```

**필터 룰:**

- 본 프로젝트 루트 (cwd 자체) 는 제외 — 그건 README 의 영역.
- 상위 **10** 개 (디폴트) 가 후보.

### 2.3 노이즈 통제 — 작은 repo 대응

위 디폴트는 **중간 규모 repo** (≥ 50 파일) 기준. 후보가 0 으로 나오면:

| 상황 | 조치 |
|---|---|
| snippets 후보 0 + repo 가 작음 (< 50 파일) | 호출 횟수 임계를 **2** 로 낮추고 재실행 |
| notes 후보 0 + 디렉토리가 평면적 | depth 를 **2** 로 줄이고, marker 조건을 OR 가 아닌 모든 디렉토리로 확장 |
| 두 카테고리 모두 0 | "코드 시그널 부족" 보고 후 종료 — 사용자에게 강제로 후보를 만들지 마라 |

임계값은 사용자가 직접 지정 가능: "호출 ≥ 3 으로, top 30 으로 다시" 같은 요청을 받으면 그 값으로 다시 풀링.

### 2.4 ripgrep 미설치 fallback

`command -v rg` 실패 시:

```bash
grep -rE --include='*.py' --include='*.ts' --include='*.go' --include='*.rs' --include='*.cs' \
  '^\s*(def |function |func |fn |public\s+\w+\s+|private\s+\w+\s+)([a-z_][a-zA-Z_0-9]*)\s*\(' . \
  | sed -E 's/.*[ \t]([a-z_][a-zA-Z_0-9]*)\s*\(.*/\1/' \
  | sort -u > /tmp/_defs.txt
```

호출 횟수 카운트는 `grep -c -w '<name>' -r --include='*.py' .` 로 동등하게.

## Step 3 — Dedupe 휴리스틱

이전 호출에서 시드된 항목과 충돌 여부 검사. 별도 frontmatter 필드는 없으므로 **제목 + 본문 인용 path** 두 가지로 매칭.

```bash
# (a) 제목 충돌 — pkm 의 검색을 한 번 거친다
pkm search "<후보 title 또는 함수명>" --scope project --json -n 3 \
  | jq -r '.hits[]?.path'

# (b) 본문 인용 path 매칭 — 코드 파일 경로가 이미 어느 시드 항목에 인용된 적 있는지
grep -l "<source_path>" data/projects/<project_id>/snippets/*.md \
                      data/projects/<project_id>/notes/*.md 2>/dev/null
```

매칭이 **하나라도 잡히면** 후보 표에서 그 행에 마크를 단다:

```
1. **send_request** — http POST helper. _src:_ `pkm/llm_bridge.py:L42` _신호:_ 호출 12회  ⚠ 기존: `data/projects/x/snippets/2026-04-01-http-helper.md`
```

사용자가 round 1 에서 빼라고 하면 빠진다. 자동 제외하지 마라 — 사용자가 추가 메모로 보강하길 원할 수도 있다.

> **출처 시그널 규약:** 본 가이드로 시드되는 모든 항목은 `--tags code-seed` 를 반드시 포함한다. 새 `--source-type` enum 을 만들지 않으므로 `code-seed` 태그가 **유일한 출처 시그널** 이다. 기존 시드와 dedupe 할 때나 향후 grep / 검색으로 본 경로의 항목만 골라낼 때 이 태그를 단서로 쓴다.

## Step 4 — 의미 부여 (Read)

각 후보에 대해 정의/디렉토리 본문을 `Read` 툴로 읽고 다음 3 가지를 만든다:

| 필드 | 길이 / 형식 |
|---|---|
| `title` | 한 줄 (≤ 60 자). 함수명 그대로가 아니라 **무엇을 하는지** 의 한국어 (또는 사용자 문서 언어) 표현. 예: `send_request` → `JSON POST 요청 헬퍼` |
| `summary` | 3-4 문장. 입력/출력/부수효과/언제 쓰는지. 코드 줄을 옮겨 적지 마라. |
| `tags` | 3-5 개. 첫 태그는 무조건 `code-seed`. 나머지는 의미 (`http`, `migration`, `auth` 등). |

본문 (knowledge add 의 stdin) 템플릿:

```markdown
## 무엇

<summary 의 첫 1-2 문장>

## 사용 예

```<lang>
[<source_path>:Lstart-Lend]
<코드 인용 5-15 줄>
```

## 언제 쓰나

<summary 의 마지막 문장 + 호출처 1-2 곳 짧게>
```

코드 인용 라인 번호는 `Read` 결과의 line number 를 쓴다 — 추측 금지.

## Step 5 — 검토 (round 1, round 2)

`pkm/templates/skills/extracting-session-knowledge/review-protocol.md` 와 동형. 표를 한 번에 제시하고 사용자가 자연어로 일괄 응답.

### Round 1 포맷

```markdown
## snippets (N)
1. **<title>** — <summary 첫 문장>. _src:_ `<source_path>` _신호:_ 호출 X회
2. **<title>** — ... ⚠ 기존: `<existing path>`
3. ...

## notes (M)
1. **<title>** — <summary 첫 문장>. _src:_ `<dir>/`
2. ...
```

표 끝에:

> "위 N+M 후보 검토 후 변경/제외할 것 알려주세요 (예: 'snippets 3 빼고, notes 1 의 제목 storage-layer 으로 바꿔'). 다 OK 면 '진행'."

### Round 2

응답 적용 → 재출력 → "최종 OK?" 묻는다. OK 면 Step 6 으로. 더 수정하면 라운드 추가 (최대 3). 3 라운드 후에도 합의 안 되면 "후보를 명시적 리스트로 알려주세요" 요청 후 정확 매칭만 진행.

## Step 6 — Knowledge add 호출

각 승인 후보에 대해:

```bash
echo '<본문>' | pkm project knowledge add \
  --project '<project_id>' \
  --category snippets   # 또는 notes \
  --slug '<human-friendly-slug>' \
  --title '<title>' \
  --tags 'code-seed,<other-tags>' \
  --source-type ai_session \
  --json
```

**중요:**

- `--source-type` 은 기존 enum `ai_session` 을 재사용. 신규 source-type 을 만들지 마라.
- `--tags` 의 첫 태그는 `code-seed`. 빠뜨리면 dedupe / 향후 grep 이 깨진다.
- slug 는 사람이 읽기 좋은 형태 (`http-post-helper`, `storage-layer`). 날짜 prefix 는 CLI 가 자동 추가.

각 호출의 JSON 출력 `path` 를 보관 — Step 8 보고에서 쓴다.

## Step 7 — 후처리

```bash
pkm project rebuild-index <project_id>
pkm reindex db --scope project:<project_id>
```

- `rebuild-index` 가 실패하면 사용자에게 surface, 그래도 시드는 이미 들어간 상태이므로 손실 X.
- `reindex db` 가 실패해도 다음 자동 reindex 가 흡수. 사용자 결정 권한.

## Step 8 — 보고

다음 형식으로 사용자에게 보고:

```
코드 시드 완료. <project_id>:
  snippets: N개 추가
  notes: M개 추가

새 항목은 data/projects/<project_id>/{snippets,notes}/.
재호출 시 dedupe 휴리스틱이 이미 시드된 항목을 표에 ⚠ 마크합니다.
다음 세션에서 /pkm-recall <topic> 으로 검색됩니다.
```

---

## Failure modes

| 상황 | 동작 |
|---|---|
| `pkm project current` → NOT_LINKED | "현 cwd 미링크. `pkm project link --id <slug>` 먼저 실행" 안내 후 stop |
| `ripgrep` 미설치 | §2.4 의 `grep -rE` fallback 으로 동등 결과, 한 줄 노티스 |
| 후보 0 (양 카테고리) | "코드 시그널 부족 또는 이미 모두 시드됨" 보고, 종료 |
| 후보 0 (한 카테고리만) | 다른 한 카테고리만 진행 (예: snippets 만, notes 0) |
| `pkm project knowledge add` 실패 | 1 회 재시도. 두 번째 실패 시 verbatim surface, 나머지 후보는 시드 진행 (부분 성공 허용) |
| 라운드 3 까지 합의 안 됨 | "후보를 명시적 리스트로 알려주세요" 요청 후 정확 매칭만 시드 |
| 사용자 본 가이드 무시하고 자동 시드 요청 | 거부. "이 가이드는 사용자 검토를 강제 — 자동 모드 없음" |

## Self dry-run 예시 (본 hwi_PKM repo)

본 가이드를 본 repo 자기 자신에 §2 까지만 적용했을 때 (commit `8eb4332`) 나온 후보 풀 일부. 실제 시드 흐름까지는 가지 않은 dry-run.

### snippets 후보 (호출 횟수 ≥ 5, 필터 후 top 12)

| # | 함수 | 정의 파일 | 호출 횟수 | 후보 의미 (Read 후 작성될 title 의 예) |
|---|---|---|---:|---|
| 1 | `atomic_write` | `pkm/store/atomic_write.py` | 31 | 임시파일+rename 기반 안전 쓰기 헬퍼 |
| 2 | `connect` | `pkm/store/db.py` | 32 | sqlite + sqlite-vec 확장 로딩된 핸들 반환 |
| 3 | `apply` | `pkm/store/migrations/...` | 31 | migration 단위 SAVEPOINT 적용기 |
| 4 | `serialize` / `to_dict` | `pkm/store/frontmatter.py` 등 | 27 / 16 | YAML frontmatter 직렬화 / 역직렬화 |
| 5 | `resolve_project_id` | `pkm/store/project_resolver.py` | 19 | 5 단계 우선순위 cwd → project_id 변환 |
| 6 | `project_dir` / `project_index` | `pkm/store/project_paths.py` | 13 / 29 | 프로젝트 디렉토리 / index.md 경로 변환 |
| 7 | `wiki_path` | `pkm/store/wiki_paths.py` | 12 | bucket+slug 으로 wiki 경로 빌드 |
| 8 | `load_config` / `load_local_overrides` | `pkm/config/loader.py` | 10 / 12 | TOML config 로드 + local overrides 병합 |
| 9 | `rerank` | `pkm/search/rerank.py` | 20 | bge-reranker-v2-m3 cross-encoder 호출 |
| 10 | `cache_dir` | `pkm/config/paths.py` | 14 | `~/.cache/pkm/` 모델/캐시 루트 |

`search` (65 회), `parse` (50), `check` (45) 같은 너무 일반적인 이름은 false-positive 위험이 커서 round 1 표에선 사용자가 빼는 게 통상적 — 그래서 자동 필터링하지 않고 ⚠ 마크 + "이름이 너무 일반적임" 노티스로만 처리.

### notes 후보 (디렉토리, top 7)

| # | 디렉토리 | 파일 수 | marker | 후보 의미 (Read 후) |
|---|---|---:|---|---|
| 1 | `pkm/commands/` | 26 | `__init__.py` | Typer 서브앱 등록 — CLI surface 모음 |
| 2 | `pkm/store/` | 18 | `__init__.py` | path resolver / atomic-write / db / 마이그레이션 등 영속화 계층 |
| 3 | `pkm/search/` | 9 | `__init__.py` | BM25 + 벡터 + RRF + reranker 5 단 파이프라인 |
| 4 | `pkm/dashboard/pages/` | 8 | `__init__.py` | 정적 HTML 페이지 빌더 (9 종) |
| 5 | `pkm/lint/` | 6 | `__init__.py` | frontmatter / 인용 / project rule 검증 |
| 6 | `pkm/store/migrations/` | 6 | `__init__.py` | m001+ 자동 발견 / SAVEPOINT 격리 |
| 7 | `pkm/session/` | 4 | `__init__.py` | Claude Code transcript 발견·메타관리 (M14) |

### 이 dry-run 이 알려주는 것

- 본 repo 처럼 도메인 vocabulary 가 분명한 코드베이스에선 §2 의 디폴트 임계 (호출 ≥ 5, top 20 / top 10) 가 합리적이다.
- `search` / `parse` / `check` / `apply` 같이 **이름이 너무 일반적이라 다른 의미로 같은 토큰이 많이 매칭** 되는 함수는 round 1 표에 ⚠ 마크 + "일반 이름 — 의미 검토 필요" 노티스를 달아야 한다 (자동 제외 X).
- notes 의 `__init__.py` 만으로는 의미 부여가 빈약할 수 있어, depth 1 디렉토리는 그 안의 대표 파일 (가장 큰 .py / __init__ docstring) 도 같이 Read 해야 좋은 summary 가 나온다.

가이드를 수정한 뒤엔 본 dry-run 표도 같이 갱신하라 — 가이드 룰과 실제 산출물이 어긋나면 가장 먼저 깨지는 게 이 표다.

---

## Provenance

- **Last verified against commit:** `98c82cc` (§13 dry-run 표는 이 commit 시점의 본 repo 코드를 기준으로 한다 — 가이드를 수정할 때마다 표도 갱신).
- **검토 protocol 출처:** `pkm/templates/skills/extracting-session-knowledge/review-protocol.md` (라운드 패턴을 차용했으나 본 가이드는 그 스킬의 일부가 아님 — 별도 단독 문서).
- **PKM 코어 의존:** `pkm project current` · `pkm project knowledge add` · `pkm project rebuild-index` · `pkm reindex db` · `pkm search`. 이 명령들의 surface 가 바뀌면 본 가이드도 갱신 필요.
