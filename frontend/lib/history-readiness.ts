export const MIN_HISTORY_DAYS = 7;

type DatedValue = { date: string; value: number };
type AudienceBucket = { period_start: string; subscriber_count: number };

function ordered<T>(items: T[], dateOf: (item: T) => string) {
  return [...items].sort((left, right) => +new Date(dateOf(left)) - +new Date(dateOf(right)));
}

function delta(items: DatedValue[]) {
  const sorted = ordered(items, (item) => item.date);
  return sorted.length > 1 ? sorted.at(-1)!.value - sorted[0].value : 0;
}

export function historyReadiness({
  views,
  likes,
  comments,
  audience,
}: {
  views: DatedValue[];
  likes: DatedValue[];
  comments: DatedValue[];
  audience: AudienceBucket[];
}) {
  const dates = new Set<string>();
  for (const point of [...views, ...likes, ...comments]) dates.add(point.date.slice(0, 10));
  for (const bucket of audience) dates.add(bucket.period_start.slice(0, 10));
  const sortedDates = [...dates].sort();
  const sortedAudience = ordered(audience, (item) => item.period_start);
  const subscribersGain = sortedAudience.length > 1
    ? sortedAudience.at(-1)!.subscriber_count - sortedAudience[0].subscriber_count
    : 0;

  return {
    ready: sortedDates.length >= MIN_HISTORY_DAYS,
    trackedDays: sortedDates.length,
    remainingDays: Math.max(0, MIN_HISTORY_DAYS - sortedDates.length),
    firstDate: sortedDates[0] ?? null,
    viewsGain: delta(views),
    engagementGain: delta(likes) + delta(comments),
    subscribersGain,
  };
}
