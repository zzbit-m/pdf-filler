# Trial Deployment (Render)

This is a **temporary private trial** deployed on Render's free tier. It is not the final product architecture.

## Known limitations

- **No authentication** — anyone with the URL can use the app and see/delete any template. Only share the URL directly and privately. Never post it publicly. Do not share the link with multiple testers simultaneously — they would share the same template list with no isolation.
- **Cold starts** — free tier spins down after 15 minutes of inactivity. The first request after idle takes 30-60 seconds to wake up. Warn testers before they click.
- **Ephemeral disk** — uploaded files, templates, and generated PDFs are stored on Render's ephemeral filesystem. Data may not survive a restart or redeploy. Do not use this for anything that needs to be kept long-term.
- **Single user at a time** — no multi-tenancy or user isolation. Templates created by one tester are visible to all others. For simultaneous use, coordinate with testers.

## Deploying updates

Push to the `master` branch. Render automatically rebuilds and redeploys.

```bash
git push origin master
```
