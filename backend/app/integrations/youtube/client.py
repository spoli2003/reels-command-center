import re
from datetime import datetime, timezone
from typing import Any


def parse_iso8601_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?", value)
    if not match:
        return None
    parts = {key: int(number or 0) for key, number in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


class YoutubeClient:
    def __init__(self, credentials: Any):
        from googleapiclient.discovery import build

        self.service = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def get_my_channel(self) -> dict[str, Any]:
        response = self.service.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()
        items = response.get("items", [])
        if not items:
            raise RuntimeError("Na zalogowanym koncie nie znaleziono kanału YouTube")
        return items[0]

    def list_upload_video_ids(self, playlist_id: str, max_items: int = 100) -> list[str]:
        ids: list[str] = []
        page_token = None
        while len(ids) < max_items:
            response = self.service.playlistItems().list(
                part="contentDetails", playlistId=playlist_id, maxResults=min(50, max_items - len(ids)), pageToken=page_token
            ).execute()
            ids.extend(item["contentDetails"]["videoId"] for item in response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return ids

    def get_videos(self, video_ids: list[str]) -> list[dict[str, Any]]:
        videos: list[dict[str, Any]] = []
        for start in range(0, len(video_ids), 50):
            response = self.service.videos().list(
                part="snippet,contentDetails,statistics", id=",".join(video_ids[start : start + 50]), maxResults=50
            ).execute()
            videos.extend(response.get("items", []))
        return videos

    # --- Community Inbox (Release 0.7.0) ------------------------------------

    def list_comment_threads_page(self, video_id: str, page_token: str | None = None) -> dict[str, Any]:
        """One page (up to 100) of top-level comment threads for a video, each
        including up to a few inline replies. Raises googleapiclient.errors.HttpError
        with reason "commentsDisabled" if the video has comments turned off."""
        return (
            self.service.commentThreads()
            .list(part="snippet,replies", videoId=video_id, maxResults=100, pageToken=page_token, textFormat="plainText", order="time")
            .execute()
        )

    def list_replies_page(self, parent_id: str, page_token: str | None = None) -> dict[str, Any]:
        """One page (up to 100) of replies under a top-level comment — used to
        backfill replies commentThreads.list didn't include inline (Part 4)."""
        return self.service.comments().list(part="snippet", parentId=parent_id, maxResults=100, pageToken=page_token, textFormat="plainText").execute()

    def insert_reply(self, parent_id: str, text: str) -> dict[str, Any]:
        return self.service.comments().insert(part="snippet", body={"snippet": {"parentId": parent_id, "textOriginal": text}}).execute()

    def update_comment(self, comment_id: str, text: str) -> dict[str, Any]:
        return self.service.comments().update(part="snippet", body={"id": comment_id, "snippet": {"textOriginal": text}}).execute()

    def delete_comment(self, comment_id: str) -> None:
        self.service.comments().delete(id=comment_id).execute()


def credentials_from_tokens(access_token: str, refresh_token: str | None, client_id: str, client_secret: str, token_uri: str = "https://oauth2.googleapis.com/token") -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(token=access_token, refresh_token=refresh_token, token_uri=token_uri, client_id=client_id, client_secret=client_secret)


def parse_published_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
