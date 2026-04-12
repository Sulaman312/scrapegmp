# Facade Template Translations

Language files:

- `en.json`
- `fr.json`
- `gn.json` (German)
- `esp.json` (Spanish)

The renderer picks language from data JSON field:

```json
"language": "en"
```

Code mapping:

- `en` -> `en.json`
- `fr` -> `fr.json`
- `de`/`gn` -> `gn.json`
- `es`/`esp` -> `esp.json`

Priority order:

1. `LANGUAGE_OVERRIDE` in `generate_site.py` (testing only)
2. Persisted business `language`
3. Fallback `fr`
