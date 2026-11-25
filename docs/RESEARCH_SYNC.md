# Research preservation workflow

Maintain engineering changes and this application's handoff alongside compact research records. Research is not complete until the private academic synchronization receipt is verified, or the pending leg and its cause are recorded explicitly.

Use the locally installed `research-sync` CLI. Prepare an explicit manifest and compact evidence package outside application repositories; consult the locally installed Research Sync documentation for the schema. Run `research-sync submit PACKAGE`, `research-sync validate`, `research-sync run --dry-run`, `research-sync run`, then `research-sync status` and `research-sync verify`. Retain the verified receipt and reference the application commit in the private record.

Keep unpublished results, research manifests, credentials, private paths, restricted samples and blind holdout labels out of public Git history. Public application changes must be publication-safe engineering or workflow documentation. Preserve failed, incomplete and superseded research with original dates, hashes and immutable revisions. Distinguish engineering tests and subjective observations from scientific validation.

Do not commit bulk audio, weights, stems, NPZ arrays or caches. Never run submitted scripts automatically. Preserve source data, uncommitted application work and ongoing recovery/inference. Report unresolved scientific conflicts; do not automatically resolve them. Preserve existing thermal safeguards for separately authorized GPU research.
