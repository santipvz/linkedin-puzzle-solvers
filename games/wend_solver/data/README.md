# Wend Wordlist

`words.txt` is the portable default wordlist used by the Wend solver. Runtime host dictionaries are not consulted, so identical deployments use identical vocabulary.

It contains the uppercase ASCII alphabetic entries of length 3 through 16 from Debian `wamerican` version `2020.12.07-2`, generated from SCOWL. The resulting file SHA-256 is `e45047c6c984f506e52deb93a6dc8691ae62e2613397c2090ef3b47909500d8e`.

Reproduce it with:

```bash
python3 scripts/build_wend_wordlist.py /usr/share/dict/american-english games/wend_solver/data/words.txt --proper-nouns games/wend_solver/data/proper_nouns.txt
```

`proper_nouns.txt` lists the 9,384 entries that appear only capitalized in that source (names, places and acronyms). `rare_words.txt` lists reviewed uncommon words, currently WEN. Both stay searchable: they only decide ties, as described in the solver README.

At runtime, `WEND_WORDLIST_PATH=/path/to/words.txt` can add a reviewed custom wordlist without changing the repository data. Missing configured files are treated as deployment errors.

`supplemental_words.txt` adds reviewed vocabulary missing from the base wordlist, currently BIOME and its plural BIOMES. These entries participate in the normal dictionary search for every board; the base file and its checksum remain reproducible.

See `SCOWL-NOTICE.txt` for the complete Debian/SCOWL copyright record and component notices.
