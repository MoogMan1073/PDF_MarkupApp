---
tags: [ai, settings]
---

# AI Assist

AI is **optional and opt-in**. DSI Redline works fully without it; AI only helps
read or disambiguate wire numbers on scanned/low-confidence regions.

## Enable it

In [[Settings]] ▸ **OCR & AI assist**:

1. Tick **Enable Claude vision assist**.
2. Paste your key in **API key** (use **Show** to reveal it). The key is stored
   in the app config. Alternatively set the `ANTHROPIC_API_KEY` environment
   variable and leave the field blank.
3. Click **Check API status** to verify it.

## Status indicator

- **disabled** — AI is off.
- **No API key set** — enable and paste a key.
- **Key set** — present but not yet verified.
- **Key is valid** / **Invalid API key** — result of **Check API status**.
- **anthropic SDK not installed** — run `pip install anthropic`.

The model defaults to `claude-opus-4-8` and is configurable.

If the key is missing or invalid, extraction silently falls back to the text
layer and [[OCR]] — nothing breaks.

#ai
