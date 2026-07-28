# Architecture

Reels Command Center separates original content from platform publications.

- `ContentVideo` is the canonical reel/video created by the user.
- `Publication` is one upload of that content to a platform.
- `MetricSnapshot` is an immutable point-in-time metric record for a publication.

This model lets one reel aggregate Facebook, Instagram, TikTok and YouTube results without overwriting history.
