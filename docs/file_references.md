# JACKPOT and your files — a guide to storage state

JACKPOT is a metadata database that knows where your files live. It
does not, by default, copy your files. When you point JACKPOT at a
FASTQ on your lab's NAS, JACKPOT records its location and reads it in
place at pipeline time. The original stays where it is.

This is a deliberate design choice, and an important one. A typical
clinical sequencing lab runs roughly 96 samples a week at around
5 GB of paired-end FASTQ per sample — about 500 GB a week. If JACKPOT
copied every file at ingest, a year of routine work would chew through
25+ TB of duplicated storage that the lab does not need to spend.
Multiply that across a state public-health agency or a university
research-computing platform and the math gets worse. JACKPOT registers,
it does not copy, and that is what makes the platform viable on the
shared filesystems where genomics data already lives.

The rest of this document explains what that means for you in practice:
how registration works, when JACKPOT does eventually copy, what the
storage states mean, and what to do when something goes wrong.

## The five storage states

Every file JACKPOT knows about has a `storage_state`. There are five.

| State | Meaning | Lifecycle owner | When you see it |
|---|---|---|---|
| `EXTERNAL` | The file lives at a URI JACKPOT does not own. JACKPOT reads it in place; deletion or relocation is up to you. | You | Default for every file you register. The vast majority of files in a typical deployment. |
| `MANAGED` | JACKPOT owns this file. It lives in JACKPOT-controlled storage, and JACKPOT decides when to delete it. | JACKPOT | Pipeline outputs. Files you explicitly handed off via promotion. |
| `MIRRORED` | JACKPOT keeps its own copy, but an external original still exists and is considered authoritative. | JACKPOT (with origin tracking) | When you want JACKPOT to have a stable copy without giving up the original — e.g., the original sits on a collaborator's drive. |
| `STAGED` | A short-lived copy that JACKPOT made for one specific pipeline run, usually because the run had to cross a compute boundary. Auto-cleaned after the run. | JACKPOT | Briefly, during a run that pulls on-prem data into cloud compute. You rarely interact with these directly. |
| `BROKEN` | An EXTERNAL or MIRRORED file JACKPOT could not reach the last time it tried. Terminal until you fix it. | n/a | When a NAS goes offline, a path is renamed, a bucket is rotated, or a file is deleted out from under JACKPOT. |

A few concrete examples:

- **EXTERNAL.** A FASTQ at
  `/srv/sequencing/runs/240501/sample01_R1.fastq.gz` that you registered
  through the upload page. JACKPOT recorded the path and the file's
  fingerprint; the file itself never moved.
- **MANAGED.** The assembled FASTA that the PHoeNIx pipeline produced
  for that sample. JACKPOT wrote it to its own results bucket and is
  responsible for keeping it around.
- **MIRRORED.** A reference genome you originally pointed at on a
  collaborator's S3 bucket. You promoted it to MIRRORED so JACKPOT keeps
  an authoritative copy locally; if the collaborator's bucket
  disappears, the data is still there.
- **STAGED.** A FASTQ pulled from your on-prem NAS to a GCS work bucket
  for one GCP Batch run. The copy was deleted automatically after the
  run finished.
- **BROKEN.** A FASTQ that used to live at
  `/srv/seq/runs/240501/sample01_R1.fastq.gz` until somebody renamed
  the run directory. JACKPOT's nightly verification job tried to stat
  the file, could not reach it, and transitioned the row to BROKEN.

## What "registration" means

When you give JACKPOT a file — through the upload page, the API, a CSV
import, a Globus deposit — JACKPOT **registers** the file. It does not
copy it.

Here is what happens at registration:

1. JACKPOT verifies it can read the URI you supplied. For a local path
   that means a stat call; for a `gs://` or `s3://` URI a HEAD request;
   for an `sra://` accession a metadata lookup.
2. JACKPOT computes a cheap fingerprint: the file's size, a hash of the
   first 64 KB, and a hash of the last 64 KB. This is fast — about a
   second for a typical FASTQ — because JACKPOT only reads the first
   and last chunk, never the whole file.
3. JACKPOT checks for an existing file row with the same fingerprint.
4. **If a match exists**, JACKPOT links your sample to the existing
   file row. No duplicate row is created. If your URI is different from
   the one already on record, it is added as an alternate URI on the
   existing row.
5. **If no match exists**, JACKPOT creates a new file row with
   `storage_state = EXTERNAL` and a `last_verified_at` timestamp.
6. In the background, a job picks up the new row and computes the full
   SHA-256 hash. This is lazy: it runs every five minutes or so and
   does not block your ingest.

```
You: "register this FASTQ"
        |
        v
[ stat / HEAD ]  <-- proves the URI works
        |
        v
[ cheap fingerprint ]  <-- size + first 64 KB hash + last 64 KB hash
        |
        v
[ does a row already match? ]
   |                    |
   yes                  no
   |                    |
   v                    v
link to             new row,
existing row        storage_state = EXTERNAL
        |                    |
        +----------+---------+
                   |
                   v
         [ background: compute full SHA-256 ]
```

The original file does not move. Your project directory, your NAS, your
Lustre scratch — wherever it was when you registered it, that is where
it still is.

## When JACKPOT does copy

JACKPOT will only put bytes on its own storage in four situations, and
each one is explicit.

1. **You ask for it at ingest.** When you register a file, you can say
   "JACKPOT, take ownership of this file" — for example, when you are
   working with data on a temporary collaborator's drive that may
   disappear next week, or when you want JACKPOT to be the durable
   home for a one-off dataset. The file is copied into JACKPOT-managed
   storage and the row starts life as MANAGED (or MIRRORED, if you
   want JACKPOT to keep a copy without claiming the original is dead).

2. **A pipeline produces an output.** Pipeline outputs default to
   MANAGED because JACKPOT owns the lifecycle of derived data. If
   PHoeNIx produces an assembly, JACKPOT wrote that assembly, JACKPOT
   stores it, and JACKPOT decides when it expires. You did not provide
   it, so JACKPOT does not have to assume your storage strategy
   applies.

3. **You promote an existing file.** You can run `jackpot files
   promote` on a file that is currently EXTERNAL and tell JACKPOT to
   take ownership (`--to managed`) or to keep a parallel copy
   (`--to mirrored`). This is the right move when you originally
   registered a file from a location that is now going away — a
   sequencer's local disk, a temporary scratch directory, a
   contractor's drive.

4. **A pipeline run has to cross a compute boundary.** If you launch a
   run on GCP Batch but the input lives on an on-prem NAS, JACKPOT
   stages a temporary copy in cloud storage so the compute nodes can
   read it. The staged copy is tagged STAGED, scoped to that run, and
   cleaned up automatically once the run finishes and a short
   retention window passes. You do not manage these copies — JACKPOT
   does, end to end.

In every other case — including the everyday case of registering a
FASTQ on your lab's NAS and running a pipeline on the same NAS —
nothing is copied. Ever. JACKPOT reads in place.

## When the same file shows up twice

Real labs reuse data. The same control sample gets sequenced across
runs. Two researchers register the same SRA accession a year apart.
A FASTQ exists once on the run drive and again, eventually, on the
archive bucket. JACKPOT recognizes these cases.

The story usually goes like this. Lab member A registers a FASTQ from
`/srv/seq/runs/240501/sample01_R1.fastq.gz`. Six months later, lab
member B re-registers what turns out to be the same file from the
lab's archive at
`gs://lab-archive/2024/240501/sample01_R1.fastq.gz`. JACKPOT computes
the cheap fingerprint of B's URI, sees that a file row with the same
fingerprint already exists, and links B's sample to the existing row
rather than creating a duplicate. The new URI is added to the row's
list of alternate URIs. Both samples now point to one canonical file
with two known locations, and either URI can be used to read the
content.

This is also why the older `samples.fastq_r1_uri` style fields — one
URI per sample, attached directly to the sample row — are being phased
out. They assumed every sample had exactly one file at exactly one
location, which does not match how genomics data actually moves
through real institutions. A single file may belong to several
samples. A single sample's file may exist at several URIs across
on-prem and cloud storage. The file row is the unit of truth; the
sample is one of possibly many things that reference it.

## When a file goes BROKEN

JACKPOT runs a verification job on a 24-hour cycle. For every file in
EXTERNAL or MIRRORED state, it re-stats the URI and confirms the file
is still there and still the right size. When that check fails — the
NAS is offline, a path was renamed, a bucket was rotated, the file
was deleted out from under JACKPOT — the row transitions to BROKEN.

In the UI you will see the affected sample flagged with a red banner
that calls out the broken file and tells you which sample it belongs
to. From there you have three options:

- **Re-locate.** The file moved but still exists. Provide the new URI
  through the file's UI page or the API. JACKPOT re-verifies, confirms
  the fingerprint matches, and clears the BROKEN state.
- **Re-upload.** The original is gone but you still have a copy
  somewhere. Re-register the file from its new location. If the
  fingerprint matches the one on record, JACKPOT links the existing
  row to the new URI and clears BROKEN.
- **Mark the sample inactive.** The file is genuinely lost and you
  cannot recover it. Mark the sample inactive so it is excluded from
  reports and pipeline launches.

Pipelines refuse to launch if any input file is BROKEN. This is on
purpose: failing fast at launch time is much cheaper than failing
mid-run, after compute resources have already been allocated. If you
try to launch a pipeline against a sample whose input is BROKEN,
JACKPOT will refuse the launch and tell you which file needs
attention.

## Storage backends across deployment scenarios

The no-copy default behaves the same on every deployment, but the
practical shape changes a little depending on where you have JACKPOT
installed.

**Laptop (Scenario A laptop case).** Your data lives in your project directories,
or anywhere else you keep files locally. JACKPOT registers them as
EXTERNAL and reads from your filesystem at pipeline time. MinIO is
optional — if you skip it, any MANAGED files (pipeline outputs,
promoted files) land under `~/.jackpot/data/` on your local disk.

**Single lab server (Scenario A multi-server case).** Your data lives on a lab NAS or a
shared drive that the JACKPOT host can mount. Registered files are
EXTERNAL. Pipelines running on a local Slurm cluster see the same
paths through the same mounts and read the same bytes — zero copies,
zero staging.

**University research computing (Scenario B HPC).** Your data lives on
Lustre, GPFS, or whatever shared parallel filesystem your cluster
provides. Registered files are EXTERNAL. Pipelines running on the
cluster mount the same filesystem and read in place. JACKPOT does not
run its own object storage in this scenario — it cooperates with the
storage your institution already operates.

**Cloud (Scenarios D and E).** Your data lives in GCS or S3 buckets
your organization owns. JACKPOT registers files in those buckets as
EXTERNAL and references them by `gs://...` or `s3://...` URIs.
Pipelines running on GCP Batch or AWS Batch read from those buckets
directly. JACKPOT does not copy data into a separate JACKPOT bucket
unless you ask it to.

**SRA-imported data.** When you register a sample with an `sra://`
URI — for example `sra://SRR12345` — JACKPOT records the accession
and never makes a permanent copy. At pipeline time, `fasterq-dump`
runs on the compute node, pulls the data fresh from NCBI, processes
it, and the local copy disappears with the rest of the work
directory. You pay no permanent storage cost for SRA references.

## Promoting a file from EXTERNAL to MANAGED

When you do want JACKPOT to take ownership of a file you registered
earlier, use the promote command:

```bash
jackpot files promote --sample SAMPLE_ID --role R1 --to managed
```

This kicks off a background copy from the file's current URI into
JACKPOT-managed storage, transitions the row to MANAGED once the copy
completes, and records the original URI on the row so the history is
preserved.

Two flag variants matter:

- `--to managed` — JACKPOT becomes the authoritative home for the
  file. The original URI is recorded for traceability but is no
  longer considered the source of truth. Use this when the original
  location is going away or you simply want JACKPOT to own the
  lifecycle.
- `--to mirrored` — JACKPOT keeps a copy, but the original is still
  considered authoritative. The row tracks both. Use this when you
  want resilience without giving up the original.

You can promote a single file (`--sample ... --role ...`), every file
on a sample (`--sample ... --all-files`), or every file across a
project (`--project ...`).

## What runs automatically

A few jobs run on their own to keep the file registry honest. None of
them require operator intervention in the normal case; if anything
goes wrong, the audit log and the UI surface the problem.

- **Cheap fingerprint at registration.** Synchronous, around a second
  per file. If this fails, the registration fails up front and you
  see the error immediately.
- **Full SHA-256 computation.** Asynchronous, every five minutes by
  default. Picks up newly-registered rows and computes a full content
  hash. Failures here surface as a status on the file row but do not
  block ingest or pipeline launches — the cheap fingerprint is enough
  to keep the dedup logic working in the meantime.
- **Periodic verification of EXTERNAL files.** Asynchronous, every
  24 hours by default. Re-stats every EXTERNAL and MIRRORED file and
  transitions the row to BROKEN if the URI is no longer reachable or
  the size has changed.
- **Pre-launch verification.** Synchronous, runs the moment you click
  launch. Iterates every input file on the run and refuses the launch
  if any is BROKEN.

## Frequently asked questions

**If JACKPOT does not copy my data, what happens if I delete the file?**

JACKPOT will mark the file BROKEN at the next verification cycle, and
the affected samples will be flagged in the UI. You can re-upload the
file from another copy, point JACKPOT at a new URI for the same
content, or mark the sample inactive if the file is genuinely lost.
JACKPOT does not silently lose data — it surfaces the loss.

**Can I move my files after registering?**

Yes. If you want JACKPOT to keep an authoritative copy before you
move the original, promote the file to MIRRORED first; that copy will
survive the move. Otherwise, move the file and update the URI through
the UI or the API — JACKPOT will re-verify against the new location
and continue as before.

**Why does my pipeline output show up as MANAGED but my input is
still EXTERNAL?**

By design. JACKPOT owns what it produces, because it has to keep
those bytes alive on its own storage to make pipeline results usable.
JACKPOT does not own what you provided, because copying every input
would defeat the entire point of the no-copy default. The two
lifecycles are intentionally different.

**Can two of my samples share the same file?**

Yes, and they often do. When two samples reference content with the
same hash, JACKPOT keeps one file row and links both samples to it.
This is the right thing to happen when you re-process the same FASTQ,
share a control sample across runs, or independently register a
public dataset that another lab has already registered.

**Can a file have more than one URI?**

Yes. A file row tracks a list of alternate URIs alongside its primary
URI. Whenever JACKPOT recognizes that a newly-registered URI points
to content already on record, the new URI is appended to the list
rather than creating a duplicate row. Pipelines can read from any of
the known URIs.

**What if my filesystem is fast but my object store is slow?**

Verification and full-hash jobs respect a `skip_remote_full_hash`
setting that lets operators turn off full-hash computation for
remote-only files when bandwidth or latency makes it impractical.
The cheap fingerprint still runs and dedup continues to work. Talk
to your operator if you suspect this applies to your deployment.
