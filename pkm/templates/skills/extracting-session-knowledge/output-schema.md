# Extraction Output Schema

When building candidates internally, structure them like this. The CLI accepts category and body separately; this schema is for your internal organization before invoking `pkm project knowledge add`.

```json
{
  "decisions": [
    {
      "title": "string (3-10 words)",
      "summary": "string (1-3 sentences)",
      "rationale": "string (1-2 sentences explaining why this option won)",
      "tags": ["lowercase-hyphen", "..."]
    }
  ],
  "pitfalls": [
    {
      "title": "string",
      "summary": "string",
      "context": "string (when/where this trips you up)",
      "tags": ["..."]
    }
  ],
  "snippets": [
    {
      "title": "string",
      "language": "python|sql|bash|...",
      "code": "string (multi-line code block)",
      "purpose": "string (what this is for)",
      "tags": ["..."]
    }
  ],
  "qna": [
    {
      "question": "string",
      "answer": "string",
      "context": "string",
      "tags": ["..."]
    }
  ],
  "notes": [
    {
      "title": "string",
      "body": "string",
      "tags": ["..."]
    }
  ]
}
```

When invoking `pkm project knowledge add`, the body sent via stdin should be Markdown formatted from these fields:

For decisions/pitfalls/qna/notes — the summary + rationale/context/answer becomes prose paragraphs.
For snippets — `purpose` is the lead paragraph, then a fenced code block with `language`.
