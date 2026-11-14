#!/usr/bin/env python3
"""
YouTube Channel & Video Analytics Fetcher (`fetch_analytics.py`)

Queries the YouTube Analytics API v2 and YouTube Data API v3 for the authenticated
channel, exporting daily and per-video metrics (views, watch time minutes, average view
duration, average percentage viewed, subscribers gained/lost) to JSON or Markdown.
"""

import argparse
import datetime
import json
import os

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_clients(secrets_file="client_secrets.json", token_file="token_analytics.json"):
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
    yt_data = build("youtube", "v3", credentials=creds)
    yt_analytics = build("youtubeAnalytics", "v2", credentials=creds)
    return yt_data, yt_analytics


def fetch_report(days: int = 28, output_json: str = None):
    _, yt_analytics = get_clients()
    end_date = datetime.date.today().isoformat()
    start_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    resp = yt_analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost",
        dimensions="video",
        sort="-views",
        maxResults=25,
    ).execute()

    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    rows = [dict(zip(headers, r)) for r in resp.get("rows", [])]

    report = {
        "window": {"start_date": start_date, "end_date": end_date},
        "videos": rows,
    }

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Saved analytics report -> {output_json}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch YouTube Analytics API v2 performance metrics")
    parser.add_argument("--days", type=int, default=28, help="Lookback window in days (default: 28)")
    parser.add_argument("--out", help="Optional path to save JSON report")
    args = parser.parse_args()
    fetch_report(args.days, args.out)
