#!/usr/bin/env python3
"""
Cloud Recording Handoff & Google Drive Sync (`devops/sync_drive_recordings.py`)

Enables seamless multi-machine workflows between a recording workstation (e.g., Desktop PC)
and a post-processing machine (e.g., Home Server) via Google Drive:
  - `--action push`: Uploads raw & split session components (`.mp4`, `_screen.mp4`, `_camera.mp4`,
    `_voice.wav`, `_desktop.wav`, `_recompiled_1x.mp4`, `*_telemetry.jsonl`, `*.yaml`) into
    Google Drive under `<parent_folder>/recordings/<session_name>/` with MD5 checksum verification.
  - `--action pull`: Downloads recording sessions from Google Drive `<parent_folder>/recordings/`
    to the local machine and verifies MD5 checksums for offline post-processing.

Zero-hardcoding: Resolves Google Drive folder hierarchies dynamically by path name
(default: `12 Media/Uploads/recordings`, falling back to `Uploads/recordings`) or explicit `--drive-folder-id`.
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
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
    """Resolves a slash-separated Drive folder path (e.g. '12 Media/Uploads/recordings').
    If the root segment (e.g. '12 Media') isn't visible because only a child ('Uploads') was shared,
    automatically falls back to the first visible segment."""
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


def infer_session_group(filename: str) -> str:
    """Groups split & raw recording files + telemetry into a clean session folder name (`YYYY-MM-DD_HH-MM-SS`)."""
    # Match OBS recording timestamps like '2026-11-15 15-12-06_screen.mp4' or 'session_2026-11-15_14-40-30_telemetry.jsonl'
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ _](\d{2}-\d{2}-\d{2})", filename)
    if m:
        return f"session_{m.group(1)}_{m.group(2)}"
    return "session_unclassified"


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


def push_recordings(service, local_dir: Path, recordings_folder_id: str, session_filter: str = None):
    from googleapiclient.http import MediaFileUpload

    valid_exts = {".mp4", ".mkv", ".mov", ".wav", ".jsonl", ".yaml", ".yml", ".srt", ".json"}
    files = sorted([
        p for p in local_dir.iterdir()
        if p.is_file() and p.suffix.lower() in valid_exts
    ])

    if session_filter:
        files = [p for p in files if session_filter in p.name]

    if not files:
        print(f"No recording files found in {local_dir} matching filter={session_filter!r}.")
        return 0

    session_folder_cache = {}
    session_contents_cache = {}
    uploaded_count = 0
    skipped_count = 0

    for fp in files:
        group_name = infer_session_group(fp.name)
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


def pull_recordings(service, local_dir: Path, recordings_folder_id: str, session_filter: str = None):
    from googleapiclient.http import MediaIoBaseDownload

    local_dir.mkdir(parents=True, exist_ok=True)
    subfolders = list_drive_children(service, recordings_folder_id)
    downloaded_count = 0
    skipped_count = 0

    for folder_name, folder_meta in sorted(subfolders.items()):
        if folder_meta.get("mimeType") != "application/vnd.google-apps.folder":
            continue
        if session_filter and session_filter not in folder_name:
            continue

        files_in_session = list_drive_children(service, folder_meta["id"])
        for fname, fmeta in sorted(files_in_session.items()):
            if fmeta.get("mimeType") == "application/vnd.google-apps.folder":
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
        description="Sync raw & split recording sessions between Desktop and Home Server via Google Drive"
    )
    parser.add_argument(
        "--action",
        choices=["push", "pull"],
        default="push",
        help="'push' local recordings to Google Drive or 'pull' recordings from Google Drive to local dir",
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
        "--session",
        help="Optional timestamp/substring filter to push or pull a specific session (e.g. '2026-11-15 15-12-06')",
    )
    parser.add_argument(
        "--vault",
        default=os.environ.get("TWC_GOOGLE_VAULT", str(Path.home() / ".tokens" / "iris.json")),
        help="Path to Google token vault JSON (default: ~/.tokens/iris.json)",
    )
    args = parser.parse_args()

    svc = load_drive_service(Path(args.vault))
    target_id = resolve_drive_path(svc, args.drive_path, args.drive_folder_id)
    print(f"Resolved Google Drive target folder ('{args.drive_path}') -> ID: {target_id}")

    if args.action == "push":
        push_recordings(svc, Path(args.local_dir), target_id, session_filter=args.session)
    else:
        pull_recordings(svc, Path(args.local_dir), target_id, session_filter=args.session)
