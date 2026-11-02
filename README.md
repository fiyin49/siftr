# SIFTR prototype

SIFTR is a browser dashboard for collecting historical stock data before later
screening and research reporting. This first stage retrieves real daily Yahoo
Finance data, summarizes availability, exports CSV, and charts a selected
symbol's prices and volume. Screening and AI reporting are explicitly planned;
there is no OpenAI integration or API-key requirement in this stage.

The intended stakeholder is Kehinde Adesina. His screening rules have not been
supplied, and the example symbols do not represent his trading process.

## Open SIFTR from a new computer

For the hosted website, you only need an internet connection and a web browser.
You do not need to install Python, Git, or SIFTR, clone this repository, or
provide an API key.

**Website address:** a verified deployed SIFTR URL has not yet been added to
this README. Ask the project owner for the exact website address before
following the steps below. The GitHub repository URL opens the source code;
it does not open the running dashboard.

1. Open your web browser on the new computer.
2. Paste the SIFTR website address shared by the project owner into the address
   bar and press Enter. Use the deployed app's complete URL, including
   `https://`; a Community Cloud address ends in `.streamlit.app`.
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

If no hosted address is available, the owner must deploy the app using that
section's Community Cloud instructions and share the assigned URL. Publishing
source code to GitHub alone does not establish a running website.

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

**What is available now:** Market Data and the basic price/volume portion of
Stock Details. **Screener** and **AI Report** show planned functionality only;
they do not yet screen stocks or generate reports. Data persists while moving
between views in the same session; a new session or server restart may require
another fetch.

## Requirements and setup

Use Windows PowerShell and Python 3.11 or later; development uses Python
3.12.10. An internet connection is needed for dependency installation and Yahoo
requests. Direct dependencies are pinned in `requirements.txt`;
`requirements-dev.txt` adds pytest. No paid data service, credentials, or
private dataset is needed.

| Dependency | Pinned version | Purpose |
| --- | --- | --- |
| Streamlit | 1.66.1 | Browser dashboard, session state, request cache. |
| pandas | 3.1.0 | Daily dates, tabular normalization, and CSV. |
| Plotly | 7.1.0 | Interactive price and volume charts. |
| yfinance | 1.7.0 | Yahoo Finance historical-data client. |
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
3. Open **Advanced settings**, select **Python 3.12**, leave secrets empty, and
   save. This stage requires no API keys or secrets.
4. Select **Deploy** and inspect the build/runtime logs. Once the dashboard
   reports the app running, open its assigned URL and try a real Yahoo fetch.
   Yahoo can throttle or reject requests from cloud hosts, so local success
   does not establish hosted data availability.

These steps follow the [official deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
The root `.streamlit/config.toml` and `requirements.txt` follow Streamlit's
[repository layout guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).
The recorded verification below covers the local application; Community Cloud
deployment requires its own running-app and live-data check.

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
| `ui.py` | Navigation, session state, request cache and controls, status displays, CSV export, and charts. |
| `market_data.py` | Validated requests, Yahoo access, normalization, and per-symbol outcomes; reusable without Streamlit. |
| `.streamlit/config.toml` | Dashboard theme and Streamlit settings. |
| `.gitignore` | Excludes credentials, installed environments, and runtime caches from the source repository. |
| `tests/test_market_data.py` | Deterministic provider-normalization and failure tests using explicitly synthetic fixtures. |
| `tests/test_app.py` | Application state and interaction checks without relying on Yahoo availability. |

The next stage is to obtain explicit stakeholder screening rules, implement
deterministic metrics and explainable pass/fail results in a separate screening
module, then review them with the stakeholder. A later reporting module can
send verified data and calculated facts to OpenAI for explanation. It must not
invent prices, metrics, news, sentiment, or company-reputation evidence;
qualitative claims need supporting sources. No screening or reporting module
is presented as implemented here.

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
