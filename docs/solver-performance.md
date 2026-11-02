# Solver performance and Wend page input

Measured on 2026-10-29 with Python 3.12, one BLAS thread, bundled online OCR fonts, and the tracked `sample1.png` for each game. Baseline is commit `3dd9c0b`; updated measurements use this working tree. Runs were sequential, without the test suite running concurrently.

## Worker timings

`python3 scripts/solver_benchmark.py --hosted --runs 5` starts each puzzle with an empty temporary OCR cache, then measures five new worker processes that reuse that disk cache. Total timings include Python startup and imports, without profiling. Search timings come from a separate cProfile run. No network, Vercel scheduling or browser gestures are included.

| Game | Cold before | Cold after | Warm median before | Warm median after | Pure search after, profiled |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sudoku | 586 ms | 472 ms | 264 ms | 265 ms | 0.32 ms |
| Patches | 1267 ms | 553 ms | 320 ms | 302 ms | 1.12 ms |
| Zip | 541 ms | 298 ms | 545 ms | 289 ms | 3.82 ms |
| Wend, image input | 1562 ms | 1580 ms | 489 ms | 491 ms | 129.38 ms |

Cold timings are one measurement each and can vary. The warm medians show that Sudoku and Patches benefit primarily when their OCR training cache is absent. Zip improves on every isolated request because its template bank was rebuilt each time. Wend's image pipeline is unchanged within timing variation.

The search algorithms for the three numeric games already take milliseconds on these samples. These results support reducing OCR preparation and process overhead before considering a language rewrite. Harder boards can still require more search; the benchmark does not establish a worst-case bound or quantify hosted network latency.

## Changes

- Sudoku loads each font once and reuses rasterized masks while generating training augmentations.
- Patches renders a padded glyph once, deriving nine translations by slicing rather than rasterizing nine times.
- Zip prepares and bit-packs translated templates in NumPy batches.
- Compatibility tests compare the new training pixels and packed bits with individually rendered templates. A one-off comparison also found all 2688 locally generated augmented Sudoku samples identical to the baseline.

## Wend 143

The page exposed the letters, explicit holes, cell indices and five slot lengths directly in its DOM. Reading those visible fields produced the public board in `games/wend_solver/tests/fixtures/linkedin-2026-10-29.json`. Its exact letters have one solution: OAR, FLOOR, MIRROR, OREGANO and FOOTWORK. The original failed upload was unavailable, so the specific OCR error cannot be reconstructed.

The extension now sends those fields alongside the screenshot when every cell and answer-slot row is consistent and the page geometry matches the captured board. The API validates the structured data, separates its cache entry from image-only requests, and sends it to the same isolated worker over stdin. The worker skips image/OCR imports and solves the exact letters. Incomplete page reads retain the image pipeline. Real multiple covers continue to be rejected; diagnostic candidate word sets are returned under `details`.

Five fresh subprocess solves of the October 29 page board took 148, 169, 142, 150 and 143 ms, with a median of **148 ms**. These are local worker timings for this board, not a same-image before/after comparison or deployed latency measurements.

Both the extension and API need the updated code to use page input. Older API versions ignore the extra multipart field and continue using OCR. These changes have not been deployed by this task.


## Reusable hosted workers (2 November 2026)

The deployed API, before this change, returned the tracked Sudoku, Zip and Wend images in 2.014, 1.486 and 1.481 seconds on the first request in this measurement. Immediate identical-image requests took 0.277, 0.165 and 0.299 seconds. These are single end-to-end observations from this machine, including upload/network/platform overhead. The HTTP solution cache makes identical-image repeats unsuitable for measuring parsing and solving throughput, and these observations do not isolate Vercel cold starts.

Hosted execution now defaults to one persistent isolated child per API instance. Consecutive solves of the same game retain Python imports and OCR/template caches. A game switch replaces the child, bounding retained game memory. Timeout, crash or worker error kills and reaps it; the next request starts fresh. A process lock prevents overlapping transport messages and returns the existing retryable busy response. Application shutdown also closes the child. Local defaults stay on fresh subprocesses; `SOLVER_WORKER_MODE=subprocess` restores that behavior online.

Measurements below use the current working tree, Python 3.12, bundled fonts, one BLAS thread, and the tracked sample for each game. Commands ran sequentially with no concurrent test suite. Each game starts with an empty temporary disk cache and then runs five more times. Both modes bypass the HTTP solution cache and actually parse and solve each time. These are local worker measurements, excluding network, platform scheduling and browser input; they do not establish deployed performance or worst-case search time.

```bash
python3 scripts/solver_benchmark.py --hosted --runs 5 --mode subprocess
python3 scripts/solver_benchmark.py --hosted --runs 5 --mode persistent
```

| Game | Fresh process, cold | Reusable process, cold | Fresh process, warm median | Reusable process, warm median | Warm reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sudoku | 441 ms | 425 ms | 273 ms | 141 ms | 48.5% |
| Patches | 572 ms | 555 ms | 308 ms | 163 ms | 47.0% |
| Zip | 290 ms | 271 ms | 299 ms | 37 ms | 87.7% |
| Wend, image input | 1568 ms | 1520 ms | 490 ms | 218 ms | 55.5% |

The improvement applies while the same game stays warm in an API instance. A new instance or a game switch still pays initialization costs. The cold figures are single observations and do not show a meaningful cold-start improvement. Both the API change and the extension's first-use capture permission change still need deployment/extension reload before users receive them.


## Deployed API follow-up: processing versus cached upload (2 November 2026)

Four sequential pairs per game used the currently published API. Each pair uploads the same board pixels twice. A random PNG text field changes the file hash for the first request, forcing the image-hash solution cache to miss; the exact same bytes are then uploaded again. Thus upload size, image pixels and response contents are comparable between the pair. Requests used one HTTP client with connection reuse, without the start-capture header. Health requests immediately before and after each pair provide a basic latency reference. These measurements exercise the deployed version, not the pending persistent-worker change.

| Game | PNG upload | New hash, median total | Identical bytes repeated, median total | Difference of medians |
| --- | ---: | ---: | ---: | ---: |
| Sudoku | 62,990 bytes | 1155 ms | 290 ms | 866 ms |
| Zip | 13,090 bytes | 1676 ms | 160 ms | 1516 ms |
| Wend | 21,918 bytes | 1724 ms | 189 ms | 1535 ms |

Health request medians were approximately 90–102 ms. The difference between uncached processing and immediately repeating the same upload dominates these observations. This supports server-side processing as the main cost for these sample requests, rather than transfer size or browser input. It does not isolate OCR, Python startup, CPU scheduling, platform cold starts or individual worker phases in production. The difference of medians is an approximate comparison, not a measured internal phase duration. First uncached observations included 2606 ms for Sudoku and 4830 ms for Wend; there is insufficient instrumentation to label those events as Vercel cold starts specifically.

The local profiles place pure search at about 0.3 ms for Sudoku, 4 ms for Zip and 125 ms for Wend; most local worker time is outside search. Together with source inspection, this points to Python/import/OCR preparation and image processing as the optimization target. It remains an inference about the deployed breakdown until internal spans are measured. Reusable workers only amortize setup while a same-game child survives in the same API instance; first daily requests, instance replacement and game switches may see little improvement. A production before/after test with internal phase timings is required before asserting an end-to-end speedup or a percentage for online users.
