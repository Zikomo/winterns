PR Review: feat: Implement Slack delivery channel (PR #60)

Findings

1) High: Unhandled network/client exceptions can bubble out and crash delivery.
   send_slack only catches SlackApiError, and SlackDelivery.deliver only catches
   SlackError, so aiohttp.ClientError/SlackClientError/invalid URL exceptions
   will escape instead of returning a failed DeliveryResult.
   Files: apps/api/src/wintern/delivery/slack.py:182, apps/api/src/wintern/delivery/slack.py:248

2) Medium: AsyncWebhookClient is created per send but never closed, which can
   leak aiohttp sessions and trigger warnings under repeated use. Use
   async with AsyncWebhookClient(...) or ensure client.close() is awaited.
   File: apps/api/src/wintern/delivery/slack.py:175

3) Medium: Slack mrkdwn formatting can break if titles/URLs contain '|' or '>'
   since they are interpolated directly into <url|title>. Consider escaping or
   sanitizing those characters.
   File: apps/api/src/wintern/delivery/slack.py:71

Open Questions

- Should rate-limit responses surface Retry-After to callers (from response
  headers) so scheduling can back off accurately?
