# ThreatFox Live IOC Feed

A small, dependency-light pipeline that pulls fresh malware **indicators of compromise (IOCs)** from [abuse.ch ThreatFox](https://threatfox.abuse.ch/), defangs them, and publishes them as a static JSON file your website can render — without ever exposing an API key to the browser.

Built to drop a live “threat intel” panel onto a personal site or dashboard, using a free GitHub Actions runner to do the work instead of a server.

```
ThreatFox API  ──>  GitHub Action (has the key)  ──>  threatfox.json  ──>  your site
                    pulls · defangs · commits          (static file)        (fetches & renders)
```

-----

## Why it’s built this way

The design is deliberate. The short version: **the browser never holds a secret and never talks to ThreatFox.**

There are two independent loops, joined only by a JSON file:

**Loop 1 — generation (runs on GitHub, on a schedule).**
A scheduled GitHub Action calls the ThreatFox API using your Auth-Key (stored in GitHub Secrets), defangs every indicator, slims the response to the fields a UI needs, and commits `threatfox.json` back to the repo.

**Loop 2 — display (runs in the visitor’s browser).**
Your website fetches the committed `threatfox.json` as an ordinary static file and renders it. It only ever talks to your own site.

This separation matters for three concrete reasons:

- **The Auth-Key stays secret.** It lives only in GitHub Secrets, used inside the Action. It is never written to the JSON, the repo, or the logs, and never shipped to the browser. A browser calling ThreatFox directly would expose the key in client-side code (and would be blocked by CORS anyway).
- **The work runs off your server.** No cron job, no Python environment, no always-on process on your own box. GitHub’s runners do the polling on a timer.
- **It’s polite to the source.** One scheduled pull every 30 minutes — regardless of how many people visit your site — keeps you well within abuse.ch’s fair-use limits. A thousand visitors means a thousand reads of your *own* static file, still just one API call upstream.

-----

## What’s in this repo

|File                             |Purpose                                                                                               |
|---------------------------------|------------------------------------------------------------------------------------------------------|
|`pull_threatfox.py`              |Runs inside the Action. Pulls IOCs, defangs them, writes `threatfox.json`. No edits needed.           |
|`.github/workflows/threatfox.yml`|The scheduled workflow. Runs the script every 30 min and commits the result. No edits needed.         |
|`threatfox.json`                 |The published feed. Ships with safe sample data; the Action overwrites it with live data on first run.|

-----

## Safety: indicators are defanged

Every indicator is **defanged** before it’s published, so the file (and any page rendering it) can’t accidentally route someone to live malicious infrastructure:

- `http://` → `hxxp://`
- `1.2.3.4` → `1.2.3[.]4`
- domains and URLs have their dots neutralised

If you render this on a web page, **do not turn indicators into clickable links.** Defanging plus no-hyperlinks is what keeps the page safe to publish.

-----

## Setup

You’ll need a free abuse.ch account and about ten minutes. All of this happens on GitHub — no server required for the feed itself.

### 1. Get a free ThreatFox Auth-Key

1. Sign in at **[auth.abuse.ch](https://auth.abuse.ch/)** (you can use a GitHub, Google, X, or LinkedIn login).
1. On your profile, generate an **Auth-Key**.
1. Connect a second login provider — abuse.ch recommends this so you don’t lose access if one provider goes away.

### 2. Use this repo

Fork it, or copy the three files into a repo of your own. A **public** repo gets unlimited free Actions minutes; a private one is metered (this job is tiny either way).

### 3. Add your Auth-Key as a repository secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

- **Name:** `THREATFOX_AUTH_KEY`
- **Value:** the key from step 1

This is the only place the key lives. It is encrypted and never appears in logs or output.

### 4. Run it once to confirm

Go to the **Actions** tab → select **Update ThreatFox feed** → **Run workflow**. After a minute, refresh: a green check means success, and `threatfox.json` in the repo will now show recent, real IOCs instead of the sample data.

From then on it runs automatically every 30 minutes, committing only when the indicators actually change.

-----

## Using the feed on a website

Your site fetches `threatfox.json` and renders it. The raw URL of the committed file looks like:

```
https://raw.githubusercontent.com/<your-username>/<your-repo>/main/threatfox.json
```

A minimal fetch:

```js
const res = await fetch('/threatfox.json');   // or the raw GitHub URL
const data = await res.json();
// data.iocs = [{ ioc, type, malware, confidence, first_seen }, ...]
// data.updated = unix timestamp of the last pull
```

**Two common ways to serve it:**

- **Pull-to-host:** a tiny scheduled task on your own server downloads the committed `threatfox.json` into your web root, and your site serves it locally. Keeps everything same-origin.
- **Direct from raw:** your front-end fetches the GitHub raw URL directly. Simpler, but subject to GitHub’s raw caching and CORS behaviour.

> If your origin runs a WAF (e.g. ModSecurity), be aware that a file full of malicious-looking URLs and payload strings may trip request/response rules. You may need a path exclusion for the JSON and the page that renders it. Tune any exclusion against your own audit log rather than disabling rules broadly.

-----

## The feed format

```json
{
  "updated": 1782349027,
  "source": "abuse.ch / ThreatFox",
  "count": 40,
  "iocs": [
    {
      "ioc": "1.2.3[.]4:443",
      "type": "ip:port",
      "malware": "Cobalt Strike",
      "confidence": 100,
      "first_seen": "2026-06-25 00:05:05 UTC"
    }
  ]
}
```

|Field              |Meaning                                        |
|-------------------|-----------------------------------------------|
|`updated`          |Unix timestamp of the last successful pull     |
|`iocs[].ioc`       |The defanged indicator                         |
|`iocs[].type`      |`url`, `domain`, `ip:port`, `sha256_hash`, etc.|
|`iocs[].malware`   |Associated malware family (printable name)     |
|`iocs[].confidence`|ThreatFox confidence level, 0–100              |
|`iocs[].first_seen`|When ThreatFox first observed it               |

## Configuration

A few constants at the top of `pull_threatfox.py`:

|Constant   |Default|What it does                           |
|-----------|-------|---------------------------------------|
|`DAYS_BACK`|`1`    |Pull IOCs added in the last N days     |
|`MAX_ROWS` |`40`   |How many indicators to keep in the file|

The schedule lives in `.github/workflows/threatfox.yml` as a cron expression (`*/30 * * * *` = every 30 minutes). Note that GitHub’s scheduled runs can be delayed by a few minutes under load, and the practical minimum interval is around 5 minutes.

-----

## Licensing & fair use

The ThreatFox **Community API is free under fair-use principles.** Use by companies, networks, or individuals with **commercial or for-profit needs may require a paid subscription** to abuse.ch’s commercial API.

Before publishing this feed anywhere public, **read the [ThreatFox Terms of Use / FAQ](https://threatfox.abuse.ch/faq/) and decide for yourself whether your use qualifies as non-commercial.** That call depends on your specific situation.

ThreatFox IOCs auto-expire after 6 months, so a feed built from this stays reasonably current by design.

Indicators shown via this project are TLP:CLEAR and defanged. Credit for the underlying data belongs to **[abuse.ch](https://abuse.ch/)** and the ThreatFox contributor community.

-----

## License

This pipeline code is provided under the MIT License — see `LICENSE`. The IOC data it retrieves is governed by abuse.ch’s terms, not this license.
