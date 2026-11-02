# SIFTR prototype

**[Open SIFTR](https://siftrdash.streamlit.app/)** — use the dashboard in your browser.

SIFTR is a browser dashboard for historical stock data and company research.
It retrieves daily Yahoo Finance data, summarizes availability, exports CSV,
and charts a selected symbol's prices and volume. Its **AI Report** view also
generates a watchlist report with company background and recent news grounded
in retrieved evidence when the server has an OpenAI API key. Configurable
stock screening remains planned.

The intended stakeholder is Kehinde Adesina. His screening rules have not been
supplied, and the example symbols do not represent his trading process.

## Open SIFTR from a new computer

For the hosted website, you only need an internet connection and a web browser.
You do not need to install Python, Git, or SIFTR, or clone this repository.
Visitors do not enter an API key in the website. The owner configures report
credentials on the server; without them, the AI Report view explains the
missing setup. Hosted AI Report availability also requires deploying this
version of the source.

**Website address:** [https://siftrdash.streamlit.app/](https://siftrdash.streamlit.app/).
The GitHub repository URL opens the source code; use the website link above
to open the running dashboard.

1. Open your web browser on the new computer.
2. Open [SIFTR](https://siftrdash.streamlit.app/), or paste
   `https://siftrdash.streamlit.app/` into the address bar and press Enter.
3. Wait for the SIFTR dashboard to load. If access requires an invitation or
   sign-in, ask the owner for access and follow the on-screen instructions.
4. Open **Market Data** in the sidebar, then follow
   [How to use the website](#how-to-use-the-website) below. Bookmark the
   website address so you can return to it.

`http://127.0.0.1:8501` works only after a SIFTR server has been started on
that same computer. It is not a hosted website address to share with another
machine. To run your own local copy, first install Python 3.12 and Git, then
follow the standalone clone/setup/launch commands in
[Source repository and Community Cloud](#source-repository-and-community-cloud).
Those installation steps are optional for hosted-website visitors.

If the hosted website is unavailable, ask the owner to check its Community
Cloud deployment. Publishing source code to GitHub alone does not establish
a running website.

## How to use the website

After opening SIFTR using the access instructions above:

1. **Open Market Data.** Use the **Workspace** navigation in the left sidebar.
   On a smaller screen, expand the sidebar to access navigation and inputs.
2. **Enter your watchlist.** In **Yahoo symbols**, enter comma-separated
   symbols such as `AAPL, MSFT, NVDA`. You can use up to 10 unique symbols.
   Spaces and letter case are normalized, duplicates are removed, and Yahoo
   punctuation such as `BRK-B` is preserved.
3. **Choose a historical period.** The default is **6 months**. Choose another
   preset, or select **Custom** to edit **Start date** and **End date
   (inclusive)**. Start must be on or before end; future dates and ranges
   longer than 1,830 days are rejected. Both dates are included when trading
   observations exist; weekends and holidays may have no data.
4. **Click Fetch market data.** Wait for the Yahoo request to finish. Opening
   the website, editing inputs, or changing views does not automatically
   download data. The example watchlist is editable, not a screening result.
5. **Check Availability by symbol.** Review each symbol's status, number of
   daily rows, first observation, latest observation, and explanatory message.
   Successful symbols remain available if another symbol fails. Compare the
   requested dates with the actual available coverage and the last successful
   fetch timestamp. Daily observation dates are separate from fetch time;
   these are not real-time quotes.
6. **Explore prices and volume.** Under **Explore history**, choose an
   **Inspect symbol** value. Hover over the interactive price and aligned
   volume charts to inspect a date. Alternatively, open **Stock Details**
   from the sidebar to inspect the selected stock. Your watchlist, retrieved
   dataset, requested period, and selected symbol carry between views without
   another download. Prices are split- and dividend-adjusted; volume is
   provider-reported, and missing values remain missing.
7. **Download the dataset.** In **Market Data**, scroll to **Retrieved
   dataset** to preview recent rows, then click **Download retrieved CSV**.
   The CSV includes all retrieved rows, symbols, dates, OHLCV values, and
   source/period/adjustment/fetch-time metadata. It exports the current
   snapshot; changing sidebar inputs alone does not change that snapshot.
8. **Refresh when needed.** Clicking **Fetch market data** again with the
   same inputs may reuse the application's 15-minute cache. Click **Refresh
   from Yahoo** to bypass the matching cache entry for the current sidebar
   settings. Check the displayed fetch time and cache label afterward. If a
   fetch or refresh fails, any previous successful snapshot remains available
   with a **STALE RETAINED DATA** warning.

**If something goes wrong:** inspect the per-symbol messages. Check unsupported
or mistyped symbols, choose a range containing trading days, and correct invalid
dates before retrying. For connection failures, check your connection and try
again; for Yahoo throttling, wait several minutes before refreshing. No sample
data is substituted for failed requests. If the sidebar settings differ from
the snapshot, click **Fetch market data** to apply them.

**What is available now:** Market Data, the basic price/volume portion of
Stock Details, and the company-background/recent-news AI Report described
below. **Screener** remains planned and does not make screening decisions.
Data and reports persist while moving between views in the same session; a
new session or server restart may require retrieval or generation again.

## Generate a company and news report

1. Set the current watchlist in the sidebar, then open **AI Report**. This view
   uses those current symbols and does not require a historical-price fetch.
   Its news lookback is separate from the Market Data historical period.
2. Set **News lookback (calendar days)** to 1 through 30 **UTC calendar days**.
   The default is 7: today and the previous six UTC dates. For example, a
   report requested on November 2, 2026 UTC covers October 27 through
   November 2 inclusive.
3. Select **Generate watchlist report**. The server retrieves company profiles
   and recent Yahoo news, then asks the configured OpenAI model to summarize
   the supplied evidence. Progress and per-company outcomes remain visible;
   one symbol's failure does not discard successful company sections.
4. Expand each company section. Compare its background and news summary with
   the linked sources, publication dates, content-availability labels, and
   retrieval/generation messages. Background uses the available name, ticker,
   sector, industry, business description, and company website; missing fields
   are identified. Explanations of why developments may matter are labeled as
   inference. A provider failure is distinct from an empty result; neither
   establishes that nothing happened to a company.
5. Select **Download complete report as Markdown**. It records the watchlist,
   requested news window, model, timestamps, company sections, and source links.
   If the inputs change afterward, **Previous inputs** identifies the report
   as belonging to its original settings; generate again to apply the new
   ones. If a later attempt entirely fails, **Retained report** identifies the
   previous completed report that remains available.

Report retrieval and paid generation occur only after the explicit generation
action. Moving between views, opening an expander, or downloading a report
does not make another model call. Public Yahoo evidence is cached for 15
minutes across sessions on the same server. Successful generated sections are
reused privately within the current session when the actual evidence, model,
and news window match. Failed generation is not cached. Expired or changed
evidence, a changed model/window, a cleared session, or a failed section can
require another paid request after another explicit generation action.

The reporting feature explains company background and retrieved news. It does
not apply stakeholder screening rules, rank the watchlist, or explain
deterministic screening metrics; those remain future work.

## Requirements and setup

Use Windows PowerShell and Python 3.11 or later; development uses Python
3.12.10. An internet connection is needed for dependency installation and Yahoo
requests. Direct dependencies are pinned in `requirements.txt`;
`requirements-dev.txt` adds pytest. Historical market data needs no API key.
AI report generation requires a server-side OpenAI API key with access to the
configured model, sends the retrieved company/news evidence to OpenAI, and
incurs API usage charges. No private dataset is needed.

| Dependency | Pinned version | Purpose |
| --- | --- | --- |
| Streamlit | 1.66.1 | Browser dashboard, session state, request cache. |
| pandas | 3.1.0 | Daily dates, tabular normalization, and CSV. |
| Plotly | 7.1.0 | Interactive price and volume charts. |
| yfinance | 1.7.0 | Yahoo Finance historical-data client. |
| OpenAI Python SDK | 3.42.1 | Server-side, structured company/news report generation. |
| Pydantic | 2.14.2 | Validation of generated report structure. |
| pytest | 9.2.0 | Deterministic development checks. |

Start in the existing `siftr` workspace root. For this checkout:

```powershell
Set-Location 'C:\Users\fades\ece570\siftr'
```

Create the development environment beside `siftr`, outside the submission tree.
These commands avoid activation and PowerShell execution-policy changes:

```powershell
$venvPath = Join-Path (Split-Path (Get-Location) -Parent) '.siftr-venv'
python -m venv $venvPath
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
& $pythonPath -m pip install --no-cache-dir -r supporting/prototype/requirements-dev.txt
```

The development environment for this checkout is
`C:\Users\fades\ece570\.siftr-venv`. Yahoo runtime databases are stored in
the sibling `.siftr-runtime\yfinance` directory on Windows. On Linux, including
Community Cloud, they use the system temporary directory's
`siftr-runtime/yfinance` path. To use a different runtime parent, set
`SIFTR_CACHE_DIR` to an absolute directory outside the application checkout or
course workspace before launch; the data layer adds its `yfinance` child
directory. The application's 15-minute request cache is held in memory.
Dependency caches, runtime data, credentials, and installed environments are
not submission artifacts.

### Enable AI Report locally

In the same PowerShell terminal used to launch SIFTR, run this before starting
the server. The hidden prompt works in Windows PowerShell as well as PowerShell
7 and keeps the key out of the command text:

```powershell
$secureApiKey = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secureApiKey).Password
Remove-Variable secureApiKey
$env:OPENAI_MODEL = 'gpt-5.4-mini'
```

`OPENAI_MODEL` is optional; the default is `gpt-5.4-mini`. Use a model available
to the owner's account that supports the structured response format used by
the application. Model availability can change; consult the
[official model reference](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
The app reads the key on the server. It provides no browser key-entry field
and does not write credentials to the source tree. After stopping the server,
remove the session variable with `Remove-Item Env:OPENAI_API_KEY` if desired.
See the [official OpenAI authentication guidance](https://developers.openai.com/api/reference/overview#authentication).

## Launch from the siftr root

Run these commands in PowerShell from the `siftr` root, including in a new
terminal after setup:

```powershell
$venvPath = Join-Path (Split-Path (Get-Location) -Parent) '.siftr-venv'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
Push-Location supporting/prototype
try {
    & $pythonPath -m streamlit run app.py --server.address 127.0.0.1
} finally {
    Pop-Location
}
```

Open `http://127.0.0.1:8501` if the browser does not open automatically.
Press Ctrl+C in PowerShell to stop the server. Launching from the prototype
directory makes Streamlit load its included `.streamlit/config.toml`.

## Source repository and Community Cloud

The deployment repository is [fiyin49/siftr](https://github.com/fiyin49/siftr).
Its Git root is the existing `supporting/prototype` directory: `app.py`,
`requirements.txt`, and `.streamlit/config.toml` appear directly at the
repository root. The course workspace keeps its current nesting, without a
second application or copied source tree. Course records, utilities, briefs,
and stakeholder evidence remain outside this application repository.

For a standalone source checkout, start in a directory without an existing
`siftr` checkout and use these PowerShell commands:

```powershell
git clone https://github.com/fiyin49/siftr.git
Set-Location siftr
$venvPath = Join-Path (Split-Path (Get-Location) -Parent) '.siftr-venv'
python -m venv $venvPath
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
& $pythonPath -m pip install --no-cache-dir -r requirements.txt
& $pythonPath -m streamlit run app.py --server.address 127.0.0.1
```

This source-only checkout does not include `guide_submission.py`,
`check_submission.py`, or other course submission files. To run its application
tests after stopping the server, use the same environment:

```powershell
& $pythonPath -m pip install --no-cache-dir -r requirements-dev.txt
& $pythonPath -m pytest tests -q -p no:cacheprovider
```

To host the repository with Streamlit Community Cloud:

1. Sign in to [Community Cloud](https://share.streamlit.io/) with the GitHub
   account that can access the repository and select **Create app**, then
   **Yup, I have an app**.
2. Set **Repository** to `fiyin49/siftr`, **Branch** to `main`, and **Main file
   path** to `app.py`.
3. Open **Advanced settings** and select **Python 3.12**. To enable AI Report,
   enter the following root-level values in the **Secrets** field, substituting
   the owner's actual key there, then save:

   ```toml
   OPENAI_API_KEY = "your-server-api-key"
   OPENAI_MODEL = "gpt-5.4-mini"
   ```

   These are server settings, not a file to commit. For the existing hosted
   app, update its secrets through app settings. Top-level secrets become
   environment variables; see [Streamlit secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management).
4. Select **Deploy** and inspect the build/runtime logs. Once the dashboard
   reports the app running, open its assigned URL and try a real Yahoo fetch.
   Yahoo can throttle or reject requests from cloud hosts, so local success
   does not establish hosted data availability.

These steps follow the [official deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
The root `.streamlit/config.toml` and `requirements.txt` follow Streamlit's
[repository layout guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).
The recorded verification below covers the local application; Community Cloud
deployment requires its own running-app and live-data check.

## Report evidence and limitations

- **Bounded news retrieval:** for each company, the provider request asks for
  its 20 latest news items. SIFTR filters by the requested UTC publication
  window, removes duplicates, and uses at most five articles. Yahoo's recent
  feed is not an exhaustive date-range archive, so a 30-day selection does not
  guarantee 30 days of coverage.
- **Content availability:** sources are labeled according to the retrieved
  full content, description, or headline-only evidence. A headline-only item
  is not presented as a full article read. The model receives only available
  source material and must describe evidence gaps instead of filling them
  from memory.
- **Sources and citations:** generated references are checked against supplied
  source IDs. The application renders links from validated source records,
  rather than accepting model-invented URLs. This checks citation membership,
  not whether every generated interpretation is correct; inspect the sources.
- **Partial results:** unavailable profiles, news retrieval failures, no
  in-window articles, invalid model output, and API failures are reported
  separately. An empty news result means no usable items were retrieved from
  that bounded feed, not that no relevant events occurred.
- **Generation bounds:** each company request has a 45-second OpenAI timeout,
  no automatic retries, and an output cap of 1,800 tokens. An incomplete or
  invalid structured response is rejected, not displayed as a completed
  briefing. A manual retry can incur another charge.
- **Scope:** reports do not invent prices, screening metrics, news, sentiment,
  or reputation claims. They describe the retrieved evidence and its limits.
  News publication time, evidence fetch time, and report generation time are
  distinct, labeled timestamps. The report is not a live market-data feed.

If Yahoo news proves unsuitable, a concrete alternative is the
[NewsAPI Everything endpoint](https://newsapi.org/docs/endpoints/everything),
which supports keyword and date filtering and publication-time ordering.
It requires a separate API key and integration, review of its plan and usage
terms, and comparable source normalization. Its content field is truncated to
200 characters where available; it does not promise full articles. NewsAPI is
**not implemented** in SIFTR.

## Data interpretation and limitations

- **Provider:** Yahoo Finance through the unofficial `yfinance` client. Network
  failures, provider throttling, unsupported instruments, and upstream changes
  can prevent retrieval. Yahoo access is not guaranteed, and no synthetic
  fallback is used.
- **Price policy:** `auto_adjust=True` explicitly requests split- and
  dividend-adjusted OHLC prices. Volume is the provider-reported volume. The
  dashboard and CSV identify this policy. Adjusted historical prices can change
  after corporate actions; they need not match a raw historical quote.
- **Daily observations:** the latest market date is separate from the fetch
  timestamp. These are historical daily bars, not real-time quotes. An
  observation for the current trading day can still be incomplete.
- **Coverage:** new listings, delistings, nontrading days, missing provider
  fields, and partial responses can shorten the actual available period. Rows
  without a usable positive closing price are omitted. Other absent numeric
  values stay missing; they are not converted to zero or forward-filled.
  A single observation is flagged as insufficient history.
- **CSV:** the current normalized dataset preserves symbol and daily date,
  contains adjusted OHLC and provider volume, and leaves missing values blank.
  Each exported row also includes `provider`, `adjustment_policy`,
  `requested_start`, `requested_end_inclusive`, and `fetched_at_utc`. This
  provenance remains visible beside the download. Daily dates describe
  exchange sessions, not intraday UTC times.
- **State:** data and selections persist across views in the same browser
  session. A server restart or a new session can clear this state. Requests
  cached in memory may be reused across sessions on the same server. There is
  no durable portfolio store or scheduled refresh.
- **Currency:** this stage does not perform currency conversion. Use the
  instrument's Yahoo listing currency when interpreting its price axis; the
  prototype is intended initially for the example US stocks.

## Modules and next stage

| File | Responsibility |
| --- | --- |
| `app.py` | Streamlit entry point; imports and launches the interface. |
| `ui.py` | Shared navigation/watchlist, market-data session state, request cache and controls, CSV export, and charts. |
| `market_data.py` | Validated requests, Yahoo access, normalization, and per-symbol outcomes; reusable without Streamlit. |
| `research_data.py` | Company-profile and recent-news retrieval, UTC-window filtering, source normalization, and evidence status. |
| `reporting.py` | OpenAI report generation from supplied evidence, structured-output and citation validation, and Markdown rendering. |
| `report_ui.py` | AI Report controls, progress, evidence/generation reuse, retained report state, company sections, and Markdown download. |
| `.streamlit/config.toml` | Dashboard theme and Streamlit settings. |
| `.gitignore` | Excludes credentials, installed environments, and runtime caches from the source repository. |
| `tests/test_market_data.py` | Deterministic provider-normalization and failure tests using explicitly synthetic fixtures. |
| `tests/test_app.py` | Application state and interaction checks without relying on Yahoo availability. |
| `tests/test_research_data.py` | Deterministic profile/news retrieval, source normalization, and evidence-failure cases. |
| `tests/test_reporting.py` | Deterministic model-output, citation, and report-rendering cases without paid calls. |
| `tests/test_ai_report_ui.py` | Report-view setup, generation, reuse, navigation, and partial-result interactions. |

The next stage is to obtain explicit stakeholder screening rules, implement
deterministic metrics and explainable pass/fail results in a separate screening
module, then review them with the stakeholder. The implemented reporting
module currently summarizes retrieved company and news evidence. A future
extension can also explain selected screening results after Python has
calculated their metrics and decisions. It must retain source grounding and
keep qualitative claims separate from deterministic calculations.

## Verification commands

From the course workspace's `siftr` root, using the environment above:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& $pythonPath -m pytest supporting/prototype/tests -q -p no:cacheprovider
& $pythonPath guide_submission.py inventory
& $pythonPath guide_submission.py status
```

The tests use synthetic fixtures and do not establish that Yahoo is reachable.
A live fetch must be assessed separately through the walkthrough. The course
readiness check is also separate from application verification: a preparation
mode result does not certify a final submission.

### Recorded verification - October 30, 2026

- All 19 deterministic checks passed: 16 provider cases and 3 Streamlit AppTest
  functions. They cover normalization, missing and empty data, partial symbol
  failures, no request on initial load, navigation across all four views,
  preserved watchlist/request/snapshot/MSFT selection, cache reuse, refresh,
  retained stale data after a failed refresh, uncached retry after failure,
  invalid dates, CSV provenance with blank missing values, Windows/course and
  Linux/cloud cache locations, external cache overrides, and rejection of
  cache paths inside application source. The dependency check remained clean
  after the cloud portability changes.
- An actual Yahoo request for `AAPL, MSFT, NVDA`, requesting April 30 through
  October 30, 2026 inclusive, succeeded with network access enabled after an
  initial restricted-environment connection failure. All three returned
  available coverage from April 30 through October 30: 128 rows each, 384 rows
  total. Fetch completion was **2026-10-30 19:06:36 UTC**. The October 30 bar was
  provisional because the trading session could still be in progress.
- `pip check` reported no dependency conflicts. The Streamlit server started
  successfully on `127.0.0.1:8517` for verification; both `/` and
  `/_stcore/health` returned HTTP 200. The normal launch command above uses
  port 8501.
- No connected browser-control tool was available, so visual browser
  inspection was not performed. AppTest inspected the rendered application
  programmatically; it does not establish visual appearance in a browser.
- The unchanged course guide's readiness check reported **NOT READY** for a
  final submission because student/brief/stakeholder/evidence placeholders and
  unconfirmed attestations remain. Preparation mode is intentional. These
  assignment gaps are separate from the application checks above.
- The structural checker passed in `format_test` mode with no errors,
  warnings, or incomplete checks. SHA-256 comparison confirmed that the course
  guide, checker, packager, requirements registry, template configuration,
  root README, root brief, and existing evidence were unchanged. No final
  submission ZIP was created.

### Report-feature verification - November 2, 2026

- All **61 tests passed** in 5.63 seconds: 19 existing price-data checks,
  19 research-data checks, 20 reporting checks, and 3 report-view AppTest
  checks. Tests cover navigation, successful-generation reuse, changed-input
  notices, missing configuration, per-company failures, provider normalization,
  and citation/output validation. The installed OpenAI 3.42.1 SDK was exercised
  with mocked HTTP responses, including structured-schema serialization and
  `responses.parse` / `output_parsed`; this used no network or real API key.
- A live Yahoo check at **2026-11-02 19:08 UTC** retrieved usable company
  profiles for `AAPL`, `MSFT`, and `NVDA`. Each news request asked for 20 items
  and returned an empty list for the October 27-November 2 report window. No
  positive live news payload was available to verify its content shape;
  synthetic provider fixtures cover supported nested and legacy formats.
  Empty results do not establish that no recent company events occurred.
- No local `OPENAI_API_KEY` was configured, so no paid live OpenAI generation
  was attempted. Hosted/cloud AI generation also remains unverified; the owner
  must configure server credentials and check a live report.
- `pip check` reported no dependency conflicts. The server started on
  `127.0.0.1:8520`, and both `/` and `/_stcore/health` returned HTTP 200.
  No browser-control tool was available, so visual browser inspection was not
  performed; AppTest provided programmatic interface verification.
- The unchanged course checker passed in `format_test` mode with no errors,
  warnings, or incomplete checks; all 16 supporting artifacts were registered.
  SHA-256 comparison confirmed that protected course files were unchanged.
  No student attestation was completed and no final ZIP was created.

The October 30 record above preserves verification of the earlier
historical-market-data stage.

Implementation references: [Streamlit request caching](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data),
[yfinance download API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html),
and [yfinance runtime caching](https://ranaroussi.github.io/yfinance/advanced/caching.html).

## Remaining assignment work

`submission.yaml` remains in `format_test` preparation mode. The original course
brief scaffold, student placeholders, stakeholder placeholders, evidence
placeholders, and unconfirmed attestations have been preserved. The intended
stakeholder's supplied name is context for this prototype; it does not establish
eligibility, consent, identity, or a completed review. No final ZIP was created.

The following gaps require student input and original evidence, independently
of whether the application works. The quoted requirements are from the root
`requirements.json`; use `python guide_submission.py explain REQ-ID` to inspect
them with the course tool.

- **Student and record details - REQ-C02:** "The submission must identify the
  student, product title, selected stakeholder path, and primary brief."
  The title is SIFTR; the student fields and stakeholder record still need
  factual completion.
- **Student brief - REQ-C03:** "The AI Product Brief must use the two required
  headings with nonempty student-written sections, contain no active HTML or
  unsafe link destination, and accurately state the concise value case and
  engineering credibility checks." The scaffold in `brief.md` must be replaced
  by the student, including truthful learning and feedback synthesis for
  Milestone 2 under the existing headings.
- **Attestations - REQ-C05:** "A final submission must contain no template
  placeholders and must include all four truthful student attestations, the
  student's name, and the attestation date." None has been completed by this
  development task.
- **Stakeholder details - REQ-R01:** "The real path must include at least one
  eligible non-Purdue-student stakeholder with identity, affiliation,
  relationship, direct interest, contact information, and the exact
  stakeholder-facing brief." The current real-path record is a template.
- **Agreement - REQ-R02:** "Each real stakeholder must have the applicable
  individual or shared agreement and approval evidence; email approval requires
  the approval-email PDF." The current pointers to `evidence/README.md` are
  placeholders, not agreement evidence.
- **Validation - REQ-R03:** "Institutional-email validation requires the
  institutional address; personal-email validation requires the personal
  address and a nonempty consent audio file in .wav, .mp3, .m4a, or .aac format."
  The appropriate method and original evidence still need to be supplied.
- **Own feedback - REQ-M2-R01:** "Each real stakeholder must provide feedback on
  the product or review in their own email, saved as a PDF, or in a PDF they
  signed; consent alone does not qualify, a student-written summary or
  recording does not replace it, and any format or rubric is accepted without
  transcribing ratings." No such feedback has been supplied in this workspace.
- **Review session - REQ-M2-R02:** "Each real stakeholder's review session must
  be documented by its full audio or video recording, a detailed written
  summary, or both; a recording is encouraged with the stakeholder's permission,
  and any submitted recording must be one file of at most 100 MB." No review
  session evidence has been supplied in this workspace.

The prototype files satisfy the implementation portion of **REQ-M2-01**;
feedback synthesis remains pending: "Milestone 2 must include the current brief,
which integrates the most consequential stakeholder feedback, what was learned,
and the resulting decisions or tests under its two required headings, and the
preliminary product: at least one supporting artifact of kind prototype plus a
prototype README, named in prototype.readme_file and listed as an included
supporting artifact, that explains what the prototype is, how to run or use it,
what to try, and its limitations." Existing source evidence and course
validation utilities remain unchanged.
