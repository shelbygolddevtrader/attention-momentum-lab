# Your first work session

## Goal

By the end of this session you will have a working Python environment, a verified Alpaca paper connection, one historical stock-day downloaded, a replay log, and two charts.

## 1. Create the Alpaca paper account

Create or sign into Alpaca Trading API, switch to **Paper Trading**, and generate paper API keys. Copy both values immediately. Do not fund a live account and never paste keys into ChatGPT or GitHub.

## 2. Open Terminal

If this folder is in Downloads:

```bash
cd ~/Downloads/attention-momentum-lab
```

## 3. Bootstrap

```bash
chmod +x scripts/bootstrap_mac.sh
./scripts/bootstrap_mac.sh
source .venv/bin/activate
```

## 4. Add the paper keys

```bash
nano .env
```

Replace the placeholders, save with `Control+O`, Return, then exit with `Control+X`.

## 5. Verify Alpaca

```bash
python -m aml.cli check-account
```

## 6. Run the first demo

```bash
python -m aml.cli demo --symbol GME --date 2024-05-13
open artifacts/GME/2024-05-13
```

Then run an ordinary comparison:

```bash
python -m aml.cli demo --symbol AAPL --date 2024-05-13
open artifacts/AAPL/2024-05-13
```

## 7. Push to a private GitHub repository

Verify `.env` is not listed by `git status`, then:

```bash
git init
git add .
git status
git commit -m "Initial point-in-time replay foundation"
git branch -M main
git remote add origin YOUR_PRIVATE_GITHUB_REPOSITORY_URL
git push -u origin main
```

## Done today

- Alpaca paper connection works.
- GME and AAPL demos complete.
- `pytest` passes.
- Project is in a private repository.
- No live trading or funding occurred.
