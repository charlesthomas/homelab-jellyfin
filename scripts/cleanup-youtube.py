import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

JELLYFIN_URL = os.environ["JELLYFIN_URL"].rstrip("/")
TOKEN = os.environ["JELLYFIN_TOKEN"]
USER_ID = os.environ["JELLYFIN_USER_ID"]
LIBRARY_ID = os.environ["JELLYFIN_LIBRARY_ID"]
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/media")).resolve()

VIDEO_EXTS = {
    ".mkv", ".mp4", ".m4v", ".ts", ".m2ts", ".avi", ".mov",
    ".wmv", ".webm", ".mpg", ".mpeg", ".flv",
}


def api(method, path, params=None):
    url = f"{JELLYFIN_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        method=method,
        headers={"Authorization": f'MediaBrowser Token="{TOKEN}"'},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    return json.loads(body) if body else None


def watched_unfavorited():
    data = api("GET", "/Items", {
        "userId": USER_ID,
        "parentId": LIBRARY_ID,
        "recursive": "true",
        "isFolder": "false",
        "mediaTypes": "Video",
        "isPlayed": "true",
        "isFavorite": "false",
        "fields": "Path",
    })
    return data["Items"]


def files_to_delete(video):
    stem = video.stem
    video_stems = {
        f.stem for f in video.parent.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS
    }
    video_stems.add(stem)
    matches = [video]
    for f in video.parent.iterdir():
        if f == video or not f.is_file():
            continue
        owners = [s for s in video_stems if f.name.startswith(s + ".")]
        if owners and max(owners, key=len) == stem:
            matches.append(f)
    return matches


def main():
    deleted = 0
    for item in watched_unfavorited():
        raw = item.get("Path")
        if not raw:
            print(f"skip {item['Id']} {item.get('Name')!r}: no path")
            continue
        video = Path(raw).resolve()
        if MEDIA_ROOT not in video.parents:
            print(f"skip {item['Id']} {raw}: outside {MEDIA_ROOT}")
            continue
        if not video.is_file():
            print(f"skip {item['Id']} {raw}: not a file")
            continue
        for f in files_to_delete(video):
            print(f"delete {f}")
            f.unlink()
        deleted += 1

    print(f"{deleted} video(s) removed")
    if deleted:
        api("POST", f"/Items/{LIBRARY_ID}/Refresh", {
            "Recursive": "true",
            "ImageRefreshMode": "Default",
            "MetadataRefreshMode": "Default",
            "ReplaceAllImages": "false",
            "RegenerateTrickplay": "false",
            "ReplaceAllMetadata": "false",
        })
        print(f"triggered refresh of library {LIBRARY_ID}")


if __name__ == "__main__":
    sys.exit(main())
