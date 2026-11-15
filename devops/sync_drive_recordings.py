#!/usr/bin/env python3
"""
Cloud Recording Handoff & Targeted Google Drive Sync (`devops/sync_drive_recordings.py`)

Enables seamless multi-machine workflows between a recording workstation (e.g., Desktop PC)
and a post-processing machine (e.g., Home Server) via Google Drive:
  - `--action list`: Lists all local recording sessions (and their size/files) so you can pick which to upload.
  - `--action push`: Uploads raw & split session components (`.mp4`, `_screen.mp4`, `_camera.mp4`,
    `_voice.wav`, `_desktop.wav`, `_recompiled_1x.mp4`, `*_telemetry.jsonl`, `*.yaml`) into
    Google Drive under `<parent_folder>/recordings/<session_name>/` with MD5 checksum verification.
    Supports targeted uploads via `--sessions <s1> <s2>...` or `--manifest <file.txt|yaml>` so you
    never re-upload older sessions that you intentionally deleted from Drive to save space.
  - `--action pull`: Downloads recording sessions from Google Drive `<parent_folder>/recordings/`
    to the local machine and verifies MD5 checksums for offline post-processing.
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
from collections import defaultdict
from pathlib import Path


def load_drive_service(vault_path: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    with open(vault_path, "r", encoding="utf-8") as f:
        vault = json.load(f)
    token_info = vault["google"]["token"]
    creds = Credentials.from_authorized_user_info(token_info)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        vault["google"]["token"] = json.loads(creds.to_json())
        with open(vault_path, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=2)
    return build("drive", "v3", credentials=creds)


def compute_md5(file_path: Path) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_or_create_folder(service, name: str, parent_id: str = None, create_if_missing: bool = True) -> str:
    safe_name = name.replace("'", "\\'")
    q = f"mimeType='application/vnd.google-apps.folder' and name='{safe_name}' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    res = service.files().list(q=q, pageSize=10, fields="files(id, name)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    if not create_if_missing:
        return None

    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    created = service.files().create(body=meta, fields="id").execute()
    return created["id"]


def resolve_drive_path(service, drive_path: str, explicit_folder_id: str = None) -> str:
    if explicit_folder_id:
        return explicit_folder_id

    parts = [p.strip() for p in drive_path.strip("/").split("/") if p.strip()]
    if not parts:
        raise ValueError("drive_path cannot be empty")

    curr_parent = None
    start_idx = 0
    for idx, part in enumerate(parts):
        found_id = find_or_create_folder(service, part, parent_id=None, create_if_missing=False)
        if found_id:
            curr_parent = found_id
            start_idx = idx + 1
            break

    if curr_parent is None:
        raise RuntimeError(
            f"Could not find root folder from '{drive_path}' in Google Drive. "
            f"Ensure '{parts[0]}' (or '{parts[min(1, len(parts)-1)]}') is shared with the active token account."
        )

    for part in parts[start_idx:]:
        curr_parent = find_or_create_folder(service, part, parent_id=curr_parent, create_if_missing=True)

    return curr_parent


def infer_session_group(filename: str, file_path: Path = None) -> str:
    """Groups split & raw recording files + telemetry into a single unified session folder (`session_YYYY-MM-DD_HH-MM-SS`).
    If a telemetry `.jsonl` file contains an `OBS_FILE_START:<mp4_name>` marker, links it directly to that video's session folder!"""
    if file_path and file_path.exists() and file_path.suffix.lower() == ".jsonl":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for _ in range(2000):
                    line = f.readline()
                    if not line:
                        break
                    if "OBS_FILE_START:" in line:
                        m_obs = re.search(r"OBS_FILE_START:(\d{4}-\d{2}-\d{2})[ _](\d{2}-\d{2}-\d{2})", line)
                        if m_obs:
                            return f"session_{m_obs.group(1)}_{m_obs.group(2)}"
        except Exception:
            pass

    m = re.search(r"(\d{4}-\d{2}-\d{2})[ _](\d{2}-\d{2}-\d{2})", filename)
    if m:
        return f"session_{m.group(1)}_{m.group(2)}"
    return "session_unclassified"


def parse_selection_list(sessions_arg: list = None, manifest_path: str = None) -> list:
    """Combines CLI `--sessions` and optional `--manifest` (newline or YAML list) into a list of target filters."""
    targets = []
    if sessions_arg:
        for item in sessions_arg:
            for part in item.split(","):
                if part.strip():
                    targets.append(part.strip())

    if manifest_path and os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.split("#", 1)[0].strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                line = line.strip("'\"")
                if line:
                    targets.append(line)
    return targets


def matches_any_target(group_name: str, filename: str, targets: list) -> bool:
    if not targets:
        return True
    norm_group = group_name.replace(" ", "_")
    norm_file = filename.replace(" ", "_")
    for t in targets:
        norm_t = t.replace(" ", "_")
        if norm_t in norm_group or norm_t in norm_file or t in filename or t in group_name:
            return True
    return False


def discover_local_sessions(local_dir: Path) -> dict:
    valid_exts = {".mp4", ".mkv", ".mov", ".wav", ".jsonl", ".yaml", ".yml", ".srt", ".json"}
    sessions = defaultdict(list)
    if not local_dir.exists():
        return sessions
    for p in sorted(local_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in valid_exts:
            group = infer_session_group(p.name, p)
            sessions[group].append(p)
    return dict(sessions)


def list_local_sessions(local_dir: Path):
    sessions = discover_local_sessions(local_dir)
    if not sessions:
        print(f"No recording sessions found in {local_dir}")
        return
    print(f"Local Recording Sessions in {local_dir}:")
    print("-" * 78)
    for group, files in sorted(sessions.items()):
        total_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
        exts = sorted(set(f.suffix.lower() for f in files))
        print(f"  {group:<28} | {len(files):2d} files | {total_mb:8.2f} MB | types: {', '.join(exts)}")
        for f in files:
            print(f"      - {f.name} ({round(f.stat().st_size / 1048576, 2)} MB)")
    print("-" * 78)


def list_drive_children(service, folder_id: str) -> dict:
    children = {}
    page_token = None
    while True:
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=500,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType, size, md5Checksum)",
        ).execute()
        for f in res.get("files", []):
            children[f["name"]] = f
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return children


def push_recordings(service, local_dir: Path, recordings_folder_id: str, targets: list = None):
    from googleapiclient.http import MediaFileUpload

    sessions = discover_local_sessions(local_dir)
    files_to_push = []
    for group_name, file_list in sorted(sessions.items()):
        for fp in file_list:
            if matches_any_target(group_name, fp.name, targets):
                files_to_push.append((group_name, fp))

    if not files_to_push:
        print(f"No recording files in {local_dir} matched targets={targets!r}.")
        return 0

    session_folder_cache = {}
    session_contents_cache = {}
    uploaded_count = 0
    skipped_count = 0

    for group_name, fp in files_to_push:
        if group_name not in session_folder_cache:
            session_folder_cache[group_name] = find_or_create_folder(
                service, group_name, parent_id=recordings_folder_id, create_if_missing=True
            )
            session_contents_cache[group_name] = list_drive_children(service, session_folder_cache[group_name])

        target_folder_id = session_folder_cache[group_name]
        existing = session_contents_cache[group_name].get(fp.name)
        local_size = fp.stat().st_size
        local_md5 = compute_md5(fp)

        if existing and int(existing.get("size", -1)) == local_size and existing.get("md5Checksum") == local_md5:
            print(f"  [SKIP] {group_name}/{fp.name} already verified on Drive (md5={local_md5})")
            skipped_count += 1
            continue

        mime_type, _ = mimetypes.guess_type(str(fp))
        if not mime_type:
            mime_type = "application/octet-stream"

        print(f"  [PUSH] Uploading {group_name}/{fp.name} ({round(local_size / 1048576, 2)} MB)...")
        media = MediaFileUpload(str(fp), mimetype=mime_type, chunksize=16 * 1024 * 1024, resumable=True)
        meta = {"name": fp.name, "parents": [target_folder_id]}
        req = service.files().create(body=meta, media_body=media, fields="id,size,md5Checksum")
        resp = None
        while resp is None:
            _, resp = req.next_chunk()

        if resp.get("md5Checksum") != local_md5 or int(resp.get("size", -1)) != local_size:
            raise RuntimeError(f"MD5 mismatch after uploading {fp.name}!")

        session_contents_cache[group_name][fp.name] = resp
        uploaded_count += 1
        print(f"  [OK]   Verified {group_name}/{fp.name} (md5={local_md5})")

    print(f"[OK] Push complete! Uploaded: {uploaded_count}, Skipped (already verified): {skipped_count}")
    return uploaded_count


def pull_recordings(service, local_dir: Path, recordings_folder_id: str, targets: list = None):
    from googleapiclient.http import MediaIoBaseDownload

    local_dir.mkdir(parents=True, exist_ok=True)
    subfolders = list_drive_children(service, recordings_folder_id)
    downloaded_count = 0
    skipped_count = 0

    for folder_name, folder_meta in sorted(subfolders.items()):
        if folder_meta.get("mimeType") != "application/vnd.google-apps.folder":
            continue

        files_in_session = list_drive_children(service, folder_meta["id"])
        for fname, fmeta in sorted(files_in_session.items()):
            if fmeta.get("mimeType") == "application/vnd.google-apps.folder":
                continue
            if not matches_any_target(folder_name, fname, targets):
                continue

            dest_path = local_dir / fname
            remote_size = int(fmeta.get("size", -1))
            remote_md5 = fmeta.get("md5Checksum")

            if dest_path.exists() and dest_path.stat().st_size == remote_size:
                if not remote_md5 or compute_md5(dest_path) == remote_md5:
                    print(f"  [SKIP] {fname} already exists locally and matches MD5 ({remote_md5})")
                    skipped_count += 1
                    continue

            print(f"  [PULL] Downloading {folder_name}/{fname} ({round(remote_size / 1048576, 2)} MB)...")
            req = service.files().get_media(fileId=fmeta["id"])
            with open(dest_path, "wb") as out_f:
                downloader = MediaIoBaseDownload(out_f, req, chunksize=16 * 1024 * 1024)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            if remote_md5 and compute_md5(dest_path) != remote_md5:
                raise RuntimeError(f"MD5 mismatch after downloading {fname}!")
            downloaded_count += 1
            print(f"  [OK]   Verified {fname} (md5={remote_md5})")

    print(f"[OK] Pull complete! Downloaded: {downloaded_count}, Skipped (already verified): {skipped_count}")
    return downloaded_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="List, push, or pull targeted recording sessions between Desktop and Home Server via Google Drive"
    )
    parser.add_argument(
        "--action",
        choices=["list", "push", "pull"],
        default="push",
        help="'list' local sessions, 'push' recordings to Google Drive, or 'pull' from Google Drive",
    )
    parser.add_argument(
        "--local-dir",
        default=str(Path.home() / "Videos" / "ThirdWaveCircuit" / "00_Inbox_Raw"),
        help="Local directory containing recording files",
    )
    parser.add_argument(
        "--drive-path",
        default="12 Media/Uploads/recordings",
        help="Target folder hierarchy in Google Drive (default: '12 Media/Uploads/recordings')",
    )
    parser.add_argument(
        "--drive-folder-id",
        default=os.environ.get("TWC_DRIVE_RECORDINGS_FOLDER_ID"),
        help="Optional explicit Google Drive folder ID for the 'recordings' folder",
    )
    parser.add_argument(
        "--sessions",
        "--session",
        dest="sessions",
        nargs="*",
        help="One or more session timestamps or filenames to upload/download (e.g. --sessions '2026-11-15_15-12-06' '2026-11-15_14-51-28')",
    )
    parser.add_argument(
        "--manifest",
        help="Path to a text or YAML file listing specific session IDs or filenames to upload/download",
    )
    parser.add_argument(
        "--vault",
        default=os.environ.get("TWC_GOOGLE_VAULT", str(Path.home() / ".tokens" / "iris.json")),
        help="Path to Google token vault JSON (default: ~/.tokens/iris.json)",
    )
    args = parser.parse_args()

    local_p = Path(args.local_dir)
    if args.action == "list":
        list_local_sessions(local_p)
        raise SystemExit(0)

    target_filters = parse_selection_list(args.sessions, args.manifest)
    svc = load_drive_service(Path(args.vault))
    target_id = resolve_drive_path(svc, args.drive_path, args.drive_folder_id)
    print(f"Resolved Google Drive target folder ('{args.drive_path}') -> ID: {target_id}")
    if target_filters:
        print(f"Active target filter list: {target_filters}")

    if args.action == "push":
        push_recordings(svc, local_p, target_id, targets=target_filters)
    else:
        pull_recordings(svc, local_p, target_id, targets=target_filters)
