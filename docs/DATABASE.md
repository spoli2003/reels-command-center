# Database model

## content_videos
Canonical content item independent from a platform.

## publications
A platform-specific upload linked to a canonical content item.

## metric_snapshots
Immutable metrics collected at a specific time. New synchronizations append rows instead of updating old snapshots.
