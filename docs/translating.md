# Translating DeckHub

DeckHub's source texts are in Spanish. Each extra language is one JSON file; no code changes are needed for the web dashboard.

## Web dashboard

1. Copy `py_modules/deckhub/web/i18n/en.json` to `<code>.json` (for example `pt.json`, `fr.json`, `de.json`).
2. Change `"_language"` to the language's own name (`"Português"`).
3. Translate the **values** (right side). Keep the keys (left side) untouched: they are the Spanish texts as they appear on screen.
4. `{}` marks a dynamic part (a number, a name…). Keep the same number of `{}` and in the same order.

The language appears automatically in the 🌐 selector. In automatic mode it is chosen from the Steam language (`py_modules/deckhub/i18n.py`, `STEAM_LANGS`): add your Steam language name there if it is missing.

Texts not found in the file are shown in Spanish, so partial translations work.

## Plugin (Quick Access menu)

The plugin strings are in `src/i18n.ts`: add a block with your language code next to `es` and `en`, with the same keys. Missing keys fall back to English.

## Finding new texts

When the dashboard changes, list the Spanish texts that are not translated yet:

```bash
node scripts/extract-i18n.cjs py_modules/deckhub/web/index.html out/keys.json   # dashboard texts
python scripts/extract-i18n-errors.py out/keys_py.json                         # daemon error messages
```

Then compare the keys with your JSON file (requires `pnpm install` for the TypeScript parser).
