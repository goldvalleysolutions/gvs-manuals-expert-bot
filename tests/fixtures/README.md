# Test fixtures

- `gameready-cold-unit.pdf`: made from `gameready-cold-unit.txt` with
  `soffice --headless --convert-to pdf` (LibreOffice 25.2). The font is a subset
  TrueType (LiberationMono) whose glyph codes (`<0102..>` hex strings in TJ arrays)
  only become text through the font's ToUnicode CMap. It is the same kind of file the
  2026-11-01 real-model panel uploaded. Before the fix it was accepted but indexed
  nothing.
