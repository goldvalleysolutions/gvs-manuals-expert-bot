---
name: lookup
description: Search the on-box manuals and answer from the matching pages only.
---

# Look up equipment manuals

The owner asks about a machine they already have. Do not browse the web.

1. **Search** — Call `search_manuals` with the owner's words (model, symptom,
   or job: "descale", "paper jam", "sanitize ice"). If nothing matches, try
   one shorter query (the model name, or one symptom).
2. **Cite** — Name the manual title in the first sentence. If two manuals hit,
   say which one you are using and why.
3. **Answer** — Give the steps in the order the manual gives them. Keep the
   owner's tools (water, cloth, the key they already have). Do not invent
   part numbers, voltages, or safety steps that are not in the hit.
4. **Gap** — If the manuals do not cover the question, say so in one line and
   offer the closest page. Do not guess.
5. **Clock** — Use `clock.now` only when a date or "today" is part of the job
   (for example a 30-day descale reminder).
