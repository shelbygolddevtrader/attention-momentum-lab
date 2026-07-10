from pathlib import Path
import matplotlib.pyplot as plt

def price_chart(replay, path: Path):
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(replay["timestamp"], replay["price"], label="Close")
    ax.plot(replay["timestamp"], replay["session_vwap"], label="Session VWAP")
    hit = replay[replay["eligible"]]
    if not hit.empty:
        ax.scatter(hit["timestamp"], hit["price"], marker="^", s=70, label="Eligible")
    ax.set(title="Point-in-time price replay", xlabel="Time", ylabel="Price (USD)")
    ax.legend(); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)

def volume_chart(replay, path: Path):
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(replay["timestamp"], replay["volume"], width=0.0005, label="Minute volume")
    hit = replay[replay["eligible"]]
    if not hit.empty:
        ax.scatter(hit["timestamp"], hit["volume"], marker="^", s=70, label="Eligible")
    ax.set(title="Minute volume and eligible signals", xlabel="Time", ylabel="Shares")
    ax.legend(); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
