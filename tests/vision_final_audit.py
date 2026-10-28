"""Read-only independent final SDK/image/source audit; no AI or application writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def images(value):
    if isinstance(value, list):
        for item in value:
            yield from images(item)
    elif isinstance(value, dict):
        if value.get("type") == "input_image":
            yield value["image_url"]
        for item in value.values():
            yield from images(item)


def run(directory: Path, runtime: str, reference_root: Path):
    root = Path(__file__).resolve().parents[1]
    read = lambda name: json.loads((directory / name).read_text(encoding="utf-8"))
    receipt = read("receipt.json")
    manifest = read("application-source-manifest.json")["files"]
    checks = []

    def check(name, condition, **details):
        checks.append(dict(name=name, passed=bool(condition), **details))

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    tracked = git("ls-files", "backend", "frontend").decode().splitlines()
    current = {name: digest((root / name).read_bytes()) for name in tracked}
    check("all tracked application files match start manifest", current == manifest, files=len(current))
    reference_raw, reference_newlines, reference_mismatch = [], [], []
    for name in tracked:
        actual = (root / name).read_bytes()
        reference = (reference_root / name).read_bytes()
        if actual == reference:
            reference_raw.append(name)
        elif actual.replace(b"\r\n", b"\n") == reference.replace(b"\r\n", b"\n"):
            reference_newlines.append(name)
        else:
            reference_mismatch.append(name)
    check("all application content matches final integration worktree", not reference_mismatch,
          raw_equal=len(reference_raw), newline_only=reference_newlines, mismatched=reference_mismatch)
    raw, newline_only, mismatched = [], [], []
    for name in tracked:
        expected = git("show", f"{runtime}:{name}")
        actual = (root / name).read_bytes()
        if expected == actual:
            raw.append(name)
        elif expected.replace(b"\r\n", b"\n") == actual.replace(b"\r\n", b"\n"):
            newline_only.append(name)
        else:
            mismatched.append(name)
    check("runtime Git content matches all application files", not mismatched,
          runtime=git("rev-parse", runtime).decode().strip(), raw_equal=len(raw),
          newline_only=newline_only, mismatched=mismatched)
    main = git("rev-parse", "origin/main").decode().strip()
    crop_files = ["frontend/photo-crop.js", "frontend/photo-workspace.js"]
    check("main photo crop implementation retained exactly",
          all(git("show", f"{runtime}:{name}") == git("show", f"{main}:{name}") for name in crop_files),
          main=main, files=crop_files)

    text = (directory / "sdk.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in text.splitlines() if line.strip()]
    requests = [event for event in events if event["kind"] == "REQUEST"]
    responses = [event for event in events if event["kind"] == "RESPONSE"]
    errors = [event for event in events if event["kind"] == "ERROR"]
    check("actual SDK requests all have one response and no error",
          len(requests) == len(responses) == 5 and not errors
          and sorted(e["trace_id"] for e in requests) == sorted(e["trace_id"] for e in responses))
    models = sorted({event["request"].get("model") for event in requests})
    efforts = sorted({event["request"].get("reasoning", {}).get("effort") for event in requests})
    check("all actual SDK calls use requested Luna and xhigh", models == ["gpt-6-luna"] and efforts == ["xhigh"])
    payloads = [part for event in requests for part in images(event["request"])]
    check("exactly three real image payload hashes recorded",
          len(payloads) == 3 and all(part.get("kind") == "data_uri" and part.get("raw_bytes", 0) > 0 for part in payloads))
    records = receipt["vision"]["photos"]
    check("encoded image bytes match saved photo observation hashes",
          sorted(part["raw_sha256"] for part in payloads) == sorted(record["encoded_sha256"] for record in records))
    check("trace contains no base64 image copy", "data:image/" not in text)
    bundle = read("01-observed.json")["bundle"]
    photos = {photo["photo_id"]: photo for photo in bundle["photos"]}
    response_ids = {event["response"]["id"] for event in responses}
    for record in records:
        check(f"photo {record['photo_id']} source crop bytes and actual response match",
              record["source_sha256"] == digest(Path(photos[record["photo_id"]]["file_path"]).read_bytes())
              and record["connection"]["response_id"] in response_ids)
    check("original user image bytes remain unchanged",
          all(photo["original_sha256"] == digest(Path(photo["original"]).read_bytes()) for photo in receipt["photos"]))
    check("actual UI completed all recorded assertions", receipt.get("completed") is True
          and not receipt["errors"] and all(item["pass"] for item in receipt["checks"]))
    report = dict(runtime=runtime, requests=len(requests), responses=len(responses), errors=len(errors),
                  models=models, efforts=efforts, images=payloads,
                  photos=[{key: record.get(key) for key in ("photo_id", "view", "source_sha256", "encoded_sha256", "connection")}
                          for record in records],
                  checks=checks, defects=[item for item in checks if not item["passed"]])
    (directory / "external-image-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(checks=len(checks), defects=len(report["defects"]), requests=len(requests),
                         images=len(payloads), application_files=len(current)), ensure_ascii=False))
    return not report["defects"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.directory, args.runtime, args.reference_root) else 1)
