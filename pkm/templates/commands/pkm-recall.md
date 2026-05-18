---
description: Recall prior decisions, patterns, snippets relevant to a task in the current PKM project.
allowed-tools: Bash, Read, Grep
---

User has invoked `/pkm-recall $ARGUMENTS`. Read `~/.claude/skills/pkm/recalling-project-context/SKILL.md` and follow its procedure, treating `$ARGUMENTS` as the topic to focus the search on.

If the procedure resolves NOT_LINKED, tell the user: "현 cwd 는 PKM 프로젝트로 등록 안 됨. `pkm project link` 먼저 실행하시거나, 일반 검색은 `pkm search '$ARGUMENTS' --scope wiki` 를 사용하세요."
