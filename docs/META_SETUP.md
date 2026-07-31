# Meta setup for local RCC

This is the operator checklist for Facebook and Instagram through **Instagram
API with Facebook Login / Facebook Login for Business**. RCC never asks for a
Facebook or Instagram password; Meta issues the access token through OAuth.

## 1. Local URLs

Use the same hostname everywhere:

- RCC frontend: `http://localhost:3000`
- RCC backend: `http://localhost:8000`
- Valid OAuth redirect URI:
  `http://localhost:8000/api/platforms/meta/callback`

Do not replace one of these with `127.0.0.1`; the Meta OAuth session cookie is
host-scoped and the state check will fail.

## 2. Active Login Configuration permissions

In Meta for Developers open the RCC app, then:

`Facebook Login for Business → Configurations → active configuration → Edit → Permissions`

For the complete Facebook + Instagram feature set grant:

- `pages_show_list`
- `business_management`
- `pages_read_engagement`
- `pages_read_user_content`
- `pages_manage_engagement`
- `read_insights`
- `instagram_basic`
- `instagram_manage_comments`

For this Facebook Login for Business Configuration, Instagram insights are
validated through the granted `read_insights` permission. Do not add
`instagram_manage_insights` to RCC's required set when Meta does not expose it
in the active Configuration editor.

`business_management` is required for the real Page because it belongs to a
Business Portfolio. Instagram requires a professional **Business or Creator**
account linked to the selected Facebook Page.

## 3. Reissue the grant after changing permissions

Changing a Configuration does not add scopes to an already-issued token.

1. Save the Configuration.
2. In Facebook settings open **Business Integrations / Integracje biznesowe**.
3. Remove the old RCC integration grant.
4. In RCC open `http://localhost:3000/platforms/instagram`.
5. Choose **Connect Instagram**, complete Meta consent and select the Facebook
   Page that shows the linked Instagram Business/Creator account.

RCC creates the Instagram `PlatformAccount` and immediately attempts the first
content + comment sync. A transient first-sync error leaves the account
connected so it can be retried without repeating OAuth.

## 4. Verify the real flow

On the Instagram page confirm:

- the professional username is shown as connected;
- missing permissions is empty;
- the first-sync message reports imported media/comments;
- Reels/posts appear under **Videos**;
- real `views`/`plays`, reach, saves and shares appear only where Meta provides
  them (reach is never relabelled as views);
- Community shows comments and replies;
- **Synchronize now** completes and updates both content and comment status.

The credential-free server diagnostic can be inspected with:

```bash
docker compose logs backend --tail=150 | grep -E "meta_oauth_(token|me_accounts|permissions)_diagnostics"
```

No access token, App Secret, OAuth code or state value should appear in those
logs.

## 5. Optional automatic sync

After the real manual flow works, set in `.env`:

```env
META_SYNC_ENABLED=true
META_SYNC_INTERVAL_HOURS=6
```

Then recreate the backend:

```bash
docker compose up -d --force-recreate backend
```

The Meta scheduler uses the same synchronization service as the initial and
manual flows. Facebook and Instagram failures are isolated from each other.
