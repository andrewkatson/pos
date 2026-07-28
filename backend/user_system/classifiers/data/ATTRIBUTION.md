# Vendored data

## `ldnoobw_en.txt`

The English word list from the **List of Dirty, Naughty, Obscene, and
Otherwise Bad Words** (LDNOOBW) project, used by the local text pre-filter
(`classifiers/prefilter.py`, issue #393) to catch blatant profanity without an
LLM call.

- Source: https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words
- File: the repository's `en` list, copied verbatim (one term per line).
- License: Creative Commons Attribution 4.0 International (CC BY 4.0).

To refresh the list, re-copy the upstream `en` file over `ldnoobw_en.txt`. The
pre-filter loads it at import time and matches terms on whole-word / whole-phrase
boundaries, so no code change is needed when the list content changes.
