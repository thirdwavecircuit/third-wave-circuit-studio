#!/usr/bin/env python3
"""
Declarative YouTube GitOps Publisher (`sync_video.py`)
Uploads or updates a YouTube video's title, description (with auto-formatted chapters),
tags, category, privacy status, and custom thumbnail from a declarative `video.yaml` file.
"""

import argparse
import os
import sys
import yaml

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def get_youtube_client(secrets_file="client_secrets.json", token_file="token.json"):
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def render_description(manifest: dict) -> str:
    body = manifest.get("description_body", "").strip()
    chapters = manifest.get("chapters", [])
    if chapters:
        chapter_lines = "\n".join(f"{c['time']} {c['title']}" for c in chapters)
        return f"{body}\n\n⏱️ Chapters:\n{chapter_lines}\n"
    return body


def sync_manifest(manifest_path: str, video_file: str = None):
    from googleapiclient.http import MediaFileUpload

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    youtube = get_youtube_client()
    description = render_description(manifest)

    body = {
        "snippet": {
            "title": manifest["title"],
            "description": description,
            "tags": manifest.get("tags", []),
            "categoryId": str(manifest.get("category_id", "28")),
        },
        "status": {
            "privacyStatus": manifest.get("privacy_status", "unlisted"),
            "selfDeclaredMadeForKids": bool(manifest.get("made_for_kids", False)),
        },
    }

    video_id = manifest.get("video_id", "").strip()
    if not video_id:
        if not video_file:
            print("Error: No video_id in manifest and no --video-file provided for initial upload.", file=sys.stderr)
            sys.exit(1)
        print(f"Uploading new video '{video_file}'...")
        media = MediaFileUpload(video_file, chunksize=10 * 1024 * 1024, resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                print(f"  Upload progress: {int(status.progress() * 100)}%")
        video_id = resp["id"]
        manifest["video_id"] = video_id
        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True)
        print(f"Uploaded! Saved video_id={video_id} back to {manifest_path}")
    else:
        print(f"Updating metadata for existing video_id={video_id}...")
        body["id"] = video_id
        youtube.videos().update(part="snippet,status", body=body).execute()
        print("Metadata synced!")

    thumb_rel = manifest.get("thumbnail")
    if thumb_rel:
        thumb_path = os.path.join(os.path.dirname(manifest_path), thumb_rel)
        if os.path.exists(thumb_path):
            print(f"Uploading custom thumbnail '{thumb_path}'...")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumb_path),
            ).execute()
            print("Thumbnail updated!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync declarative video.yaml to YouTube")
    parser.add_argument("--manifest", required=True, help="Path to video.yaml")
    parser.add_argument("--video-file", help="Path to .mp4/.mkv for initial upload")
    args = parser.parse_args()
    sync_manifest(args.manifest, args.video_file)
