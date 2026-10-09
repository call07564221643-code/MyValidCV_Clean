# ATS optimisation and validation

Reduced repeated advert sentence parsing, stopped requirement-context scanning at the first match, compiled bounded cached term patterns, and evaluated mandatory sentence hints once per sentence. Cached patterns contain terms only, never CV text. Scoring weights and model version remain unchanged.

CV text is limited to 50,000 characters and job adverts to 20,000, without silent truncation. User-facing document validation explains these limits. The scorer rejects empty and oversized inputs, and historical reports retain stored results when their source documents cannot be rescored.

Individual analysis and enterprise bulk submissions lock the user's profile until their database transaction completes. Quota checks therefore serialize submissions for the same user on PostgreSQL. Monthly counter resets and increments also lock and refresh stored state, preventing stale instances from losing increments or resetting twice. Individual analysis holds this lock during document/job processing; concurrent requests from that user wait. Other users retain independent locks.

Compared with commit a78b494, six fixture pairs produced identical complete scoring output. Median local scoring improved 27–54%; the 40,000-character CV / 15,000-character advert case fell from 981 ms to 456 ms. Ninety-six local scoring requests across 1, 4 and 16 workers completed without errors. See ATS_OPTIMISATION_RESULTS_2026-10-09.json. These SQLite measurements do not establish production capacity or expert-rated accuracy.

ATS and accounts regression tests include empty/oversized inputs, stale usage increments and repeated monthly resets. PostgreSQL lock behavior needs production verification. Expert-rated CV/job evaluation remains necessary before claiming better matching accuracy. Short nonempty fragments remain accepted by the internal scorer for backwards compatibility; web workflows require a complete advert.
