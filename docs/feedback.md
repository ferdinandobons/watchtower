# Structured feedback

Watchtower optimizes for useful interventions rather than intervention volume. Version `0.2.0` adds a local feedback record linked one-to-one with an intervention.

## Ratings

```text
useful
not_useful
incorrect
too_early
too_late
already_known
too_disruptive
action_accepted
action_rejected
```

A record may include a bounded local comment and a presentation channel. Updating feedback for the same intervention preserves its identity and original creation time while updating the rating, comment, channel, and timestamp.

## API

```text
PUT    /v1/interventions/{id}/feedback
DELETE /v1/interventions/{id}/feedback
GET    /v1/feedback
GET    /v1/metrics/quality
GET    /v1/metrics/summary
```

Example:

```json
{
  "rating": "too_early",
  "comment": "The diagnosis was right but arrived before the second attempt.",
  "channel": "dashboard"
}
```

## Local metrics

The quality endpoint returns:

- total feedback records;
- positive and negative counts;
- aggregate positive rate;
- counts by rating;
- the same breakdown by detector.

`useful` and `action_accepted` are counted as positive. The remaining non-neutral categories are counted as negative. These aggregates describe recorded user feedback only. They do not establish detector precision when the sample is small or missing.

## Privacy

Feedback is stored in the local SQLite database. Watchtower has no remote telemetry or feedback upload path in this release.

The summary endpoint reports exact local counts for events, interventions, open interventions, and checkpoints.
