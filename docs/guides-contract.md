# Guides repo contract

The sync job (`jobs/sync`, module `buddy_sync`) reads four things from the Guides repository besides the guide files themselves. Two of them (`sections.yaml` and `GUIDES_INDEX.md`) are files that live in the Guides repo and are parsed here, so their format is a contract between the two repositories. This document is the single place that describes them. Examples use made-up names and `example.invalid` URLs.

The reference implementation is `jobs/sync/buddy_sync/video_map.py` (video links) and `jobs/sync/buddy_sync/guides_index.py` (`GUIDES_INDEX.md`).

## Overview

| Input | Location in the Guides repo | Written by | Read by |
|-------|-----------------------------|------------|---------|
| `sections.yaml` | `videos/<topic>/sections.yaml` | A person, next to the video sources | `buddy_sync.video_map.load_sections_file` |
| `durations.json` | `videos/<topic>/out/durations.json` | The video build script | `buddy_sync.video_map.resolve_video_links` |
| README video table | `README.md` | A person | `buddy_sync.video_map.parse_readme_videos` |
| `GUIDES_INDEX.md` | `GUIDES_INDEX.md` | `python -m buddy_sync guides-index` | `buddy_sync.guides_index.check_guides_index` |

The sync turns the first three into one `VideoLink` row per chunk (full-video URL, part number, start offset in seconds, source) and stores it in `index.db` (see [index-format.md](index-format.md)). Nothing downstream parses them.

## sections.yaml

One file per video, at `videos/<topic>/sections.yaml`. It maps scene ids to headings of one guide. No text matching is done between narration and headings: a scene link exists only when an entry names the heading.

```yaml
schema: 1
guide: AI-Engineering/DEMO_GUIDE.md
video: demo
sections:
  - scene: S02Intro
    h2: "1. Basics"
  - scene: S03Chunking
    h2: "1. Basics"
    h3: Chunking
```

| Key | Type | Meaning |
|-----|------|---------|
| `schema` | integer, must be `1` | Version of this format |
| `guide` | string | Path of the guide file relative to the Guides repo root, with `/` separators |
| `video` | string | Must equal the name of the folder that holds the file (`videos/<topic>/`) |
| `sections` | list | Entries below; may be empty |
| `sections[].scene` | string | A key of `durations.json` |
| `sections[].h2` | string | Exact text of a `##` heading of the guide, as the chunker reads it |
| `sections[].h3` | string, optional | Exact text of a `###` heading under that `##` |

Rules:

- The file is read with `yaml.safe_load` only, after a size check (at most 262144 bytes). Unknown keys are rejected, so a typo cannot silently drop an entry.
- Most specific wins. An entry with `h3` applies to the chunks under that `###`. An entry with only `h2` applies to the text before the first `###` of that `##` and to every `###` of it that has no entry of its own.
- First listed wins. When two entries target the same `h2` (and `h3`), the first is used and the sync logs a warning.
- A section of a mapped guide with no matching entry is not an error; it gets the fallback described below.
- Two `sections.yaml` files may not map the same guide.

Every one of these makes the sync fail with `VideoMapError`, naming the file and the key (no silent drift):

- the file is larger than the size cap, is not valid YAML, uses a non-standard tag such as `!!python/object`, has an unknown key, or has `schema` other than `1`;
- `video` differs from the folder name;
- `guide` is absolute, contains `..` or a backslash, or is not a guide file the chunker indexed;
- the guide has no video in the README table;
- `durations.json` is missing or malformed;
- a `scene` is not a key of `durations.json`, or belongs to a part the README does not list;
- an `h2` or `h3` has no chunk in that guide;
- the README is missing while a `sections.yaml` exists.

## durations.json

One file per video, at `videos/<topic>/out/durations.json`, written by the video build script. It is a JSON object from scene id to the scene's length in seconds:

```json
{"S01Title": 10.0, "S02Intro": 20.5, "S03Chunking": 30.0}
```

- Key order is narration order. The start of a scene is the sum of the durations of the scenes before it in the same part, in key order. Reordering the keys changes every offset after the moved scene.
- Values are non-negative finite numbers. Anything else fails the sync.
- Multi-part videos prefix scene ids with `P<n>` (`P1S01Title`, `P2S01Recap`). The number is the part. Offsets restart at 0 in each part, so the first scene of part 2 starts at 0.0 in part 2, not at the end of part 1. Ids without a prefix belong to part 1.

With the example above, `S03Chunking` starts at 10.0 + 20.5 = 30.5 seconds. The link stores the offset as `start_seconds`; consumers compose the playable URL with `buddy_core.models.video_link`, which appends `#t=<whole seconds>` (here `#t=30`).

Open assumption, to be confirmed live: a browser may ignore the `#t=` fragment, on a release download URL or on the authenticated bucket URL after the Google login redirect. The offset is stored separately for that reason, so another link syntax can be chosen later without a re-sync.

## Committing durations.json in the Guides repo

Rendered videos are ignored by git today with this rule in the Guides `.gitignore`:

```gitignore
videos/**/out/
```

The sync reads `durations.json` from a git checkout, so the file must be committed. A file inside an ignored directory cannot be re-included, so the directory rule has to change to a rule on its contents:

```gitignore
videos/**/out/*
!videos/**/out/durations.json
```

Everything else in `out/` (MP4, WAV, frames) stays ignored.

## README video table

`README.md` at the Guides root lists the full-video URL of every guide in markdown tables with the columns `Guide | Topic | Video`. The parser reads every table row whose first cell links a `.md` file.

```markdown
| Guide | Topic | Video |
|---|---|---|
| [Demo](AI-Engineering/DEMO_GUIDE.md) | Single video | [02:00](https://videos.example.invalid/demo.mp4) |
| [Multi](AI-Engineering/MULTI_GUIDE.md) | Two parts | [Part 1 · 01:00](https://videos.example.invalid/multi_part1.mp4)<br>[Part 2 · 01:30](https://videos.example.invalid/multi_part2.mp4) |
| [NoVideo](Foundations/NOVIDEO_GUIDE.md) | No video yet | — |
```

- First cell: a markdown link whose target is the guide path relative to the repo root (a leading `./` is dropped).
- Last cell: either a dash (`—`, `–` or `-`), meaning no video, or one or more `[label](https://….mp4)` links. A single link is part 1 whatever its label. With several links each label must start with `Part N`; parts are ordered by `N`.
- Only `https` links ending in `.mp4` are accepted.
- Lines that are not table rows, separator rows, and rows without a guide link (headers, other tables) are ignored.

The README table stays the source of the part list and of the file names. When `VIDEO_BUCKET` is set, the sync keeps each part but stores the hosted copy as its base URL, `https://storage.cloud.google.com/<VIDEO_BUCKET>/videos/<name>.mp4` (no query string; `<name>.mp4` is the last segment of the README URL), and appends `#t=<seconds>` for scene rows as before. `python -m buddy_sync upload-videos` puts the files there, so every README mp4 name must exist as a local file before the upload: under the Guides `videos/` tree, or in the directory the release assets were downloaded to (see [jobs/sync/README.md](../jobs/sync/README.md)). File names must be plain `*.mp4` names, and two different README URLs may not end in the same name. Without `VIDEO_BUCKET` the README URLs are stored unchanged.

Drift guard: a row that links a guide but has neither a dash nor at least one valid `.mp4` link, a link without `Part N` among several, a repeated part number, or a guide listed twice raises `VideoMapError`. The README format is therefore checked on every sync rather than silently producing guides without videos.

## GUIDES_INDEX.md

A generated map of the Guides headings (file, level, section, line), kept in the Guides repo so a reader can find a section without opening every guide. It is generated, never hand-edited:

```bash
python -m buddy_sync guides-index
```

Format: a first line `<!-- generated by buddy_sync guides-index; do not edit by hand -->`, then a markdown table with the columns `File | Level | Section | Line`, one row per heading, sorted by file and line. `Level` is the heading level, `Line` is 1-based, and a `|` in a title is written `\|`. Rows with absolute or `..` paths are rejected.

Drift policy: the chunker output is authoritative. At sync time the file is compared with the headings actually found, by file, level and title (missing, extra) and by line (moved). Every difference is logged as a warning and the sync continues. With `--strict` any drift, or a missing file, fails the sync. Regenerate the file when a guide changes.

## Fallback rules

For every chunk of a guide that has a video in the README table:

1. A matching `sections.yaml` entry gives the URL of that scene's part and its start offset, with source `scene`.
2. Otherwise the chunk gets the README URL, no offset and source `readme_fallback`. Its part is the part of the nearest preceding mapped chunk of the same guide in document order, or part 1 when there is none.
3. A guide whose README row is a dash gets no link at all; search hits for it carry no video.

An empty `sections: []` therefore makes every section of that guide use rule 2.

## Reversibility

Both file formats are rated costly to change (decisions D-03 for `sections.yaml` and D-23 for `GUIDES_INDEX.md`). Each is a contract between two repositories: changing a key, a column or a naming rule means editing every file in the Guides repo and the loader in `jobs/sync` together, in the same change window, and bumping `schema` where the format carries one. The README table and `durations.json` follow the same rule: a change on either side must land in both repositories before the next sync.
