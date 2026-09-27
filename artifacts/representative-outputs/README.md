# Representative outputs

These files are unmodified copies selected from `raw/responses/`. The full siblings remain under the corresponding path in `raw/responses/`.

- `l3-2609.28614-full_reference-openai-a1.json` — L3, strongest observed GPT-6 Luna full-reference artifact; full siblings: `raw/responses/l3/full_reference/openai/`.
- `l3-2609.28614-selective-gemini-a1.json` — L3, weak selective Gemini example; full siblings: `raw/responses/l3/selective/gemini/`.
- `l3-judge-2609.28614-full_reference-openai-a1.json` — L3 judge, blind judge example; full siblings: `raw/responses/l3/judges/openai/`.
- `l2-2609.28614-A-r1-a1.json` — L2 A, abstract-only comparison artifact; full siblings: `raw/responses/l2/A/`.
- `l2-2609.28614-B-r1-a1.json` — L2 B, whole-PDF native comparison artifact; full siblings: `raw/responses/l2/B/`.
- `l2-2609.28614-C-r1-a1.json` — L2 C, selective page-image artifact; full siblings: `raw/responses/l2/C/`.
- `l2-2609.28614-D-r1-a1.json` — L2 D, full extracted-text reference artifact; full siblings: `raw/responses/l2/D/`.
- `l2-2609.30217-C-r1-a1.json` — L2 C, selective evasion-paper artifact; full siblings: `raw/responses/l2/C/`.
- `l2-2609.30217-D-r1-a1.json` — L2 D, reference evasion-paper artifact; full siblings: `raw/responses/l2/D/`.
- `l2-2609.29095-C-r1-a1.json` — L2 C, selective exactly-once artifact; full siblings: `raw/responses/l2/C/`.
- `l2-2609.29095-D-r1-a1.json` — L2 D, reference exactly-once artifact; full siblings: `raw/responses/l2/D/`.
- `l2-2609.29095-B-r1-a2.json` — L2 B, one outage attempt; full siblings: `raw/responses/l2/B/`.
- `l2-2609.29095-B-r1-resume1-a1.json` — L2 B, clean resume after outage; full siblings: `raw/responses/l2/B/`.
- `l1-2609.29808-jev-a1.json` — L1 JEV, the 503 attempt; full siblings: `raw/responses/l1/jev/`.
- `l1-2609.29808-jev-a2.json` — L1 JEV, successful retry; full siblings: `raw/responses/l1/jev/`.

The flat filenames are kept exactly as selected; path context and all other response records remain available in the raw mirror.

## Reading the index

The L2 quartet for 2609.28614 shows how abstract-only, whole-PDF, selective-image, and extracted-text inputs differed on the same paper. The 2609.30217 and 2609.29095 pairs expose the selective misses directly.

The 2609.29095 B pair keeps both an outage attempt and the clean resume so the successful measurement is not mistaken for an uninterrupted call. The 2609.29808 JEV pair likewise keeps the 503 and retry.

The L3 pair and judge file give one generator artifact, one weak selective artifact, and one blind evaluation record. All other artifacts remain in `raw/responses/`, with their original subdirectories and filenames.

No representative file is a rewritten excerpt. The copies are byte-identical to the selected raw response records.
