# Wend Wordlist

`words.txt` is the portable default wordlist used by the Wend solver.

It is normalized to uppercase ASCII words, filtered to alphabetic entries with lengths 3 through 16. The list was generated from the system `american-english` wordlist available in the development environment, with the Wend regression words included explicitly.

At runtime, `WEND_WORDLIST_PATH=/path/to/words.txt` can be used to add a custom wordlist without changing the repository data.
