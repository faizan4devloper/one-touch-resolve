#!/usr/bin/env python3
"""Generate the demo-video voiceover with Amazon Polly (neural).

Reads the teleprompter beats, synthesizes one MP3 per section (so each can be
synced to its on-screen beat), and stitches a single full-length track. SSML
adds natural pauses — especially on the commit-gate "twist" beat.

Usage:  python3 scripts/make_voiceover.py
Output: docs/voiceover/*.mp3  (per section) + one_touch_resolve_vo.mp3 (full)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "voiceover"
OUT.mkdir(parents=True, exist_ok=True)

REGION = "us-east-1"
VOICE = "Joanna"       # neural, clear US English
ENGINE = "neural"

# Each beat = (filename, SSML). <break> tags pace it to the shot plan.
BEATS: list[tuple[str, str]] = [
    ("00_hook",
     "Property insurance claims take <say-as interpret-as='cardinal'>40.7</say-as> days "
     "to settle on average <break time='400ms'/> the longest since two thousand eight. "
     "<break time='500ms'/> And the delay usually isn't the adjuster. It's that the customer, "
     "the repair shop, the parts supplier, and the lender never actually talk to each other. "
     "Nobody owns the coordination. <break time='400ms'/> "
     "This is One Touch Resolve <break time='250ms'/> an A I agent on Amazon Bedrock AgentCore "
     "that coordinates every party, across A W S Communication Developer Services, and drives the "
     "claim to settled."),
    ("01_fnol",
     "It starts when the policyholder reports a collision <break time='250ms'/> by sending a photo "
     "on WhatsApp. Amazon Bedrock Nova Pro vision reads the actual damage from that photo "
     "<break time='250ms'/> how severe it is, whether the car is drivable <break time='250ms'/> "
     "and opens the claim. You can see the state move to F N O L captured."),
    ("02_fanout",
     "Now the supervisor delegates to specialist sub agents <break time='250ms'/> one for each party. "
     "In parallel, it asks the repair shop for an estimate over R C S, and emails the lender a coverage "
     "notice through Amazon S E S. <break time='300ms'/> Watch the timeline: one coordinated update, "
     "fanning out to multiple parties, each on the right channel. The claim moves to parties engaged."),
    ("03_gate",
     "Then the twist. <break time='400ms'/> The part is back ordered <break time='250ms'/> five days. "
     "<break time='500ms'/> Watch the commit gate. It stays closed, because a required party is blocked. "
     "<break time='500ms'/> A single agent chatbot would just stall right here. <break time='400ms'/> "
     "Ours re plans. It reserves a real courtesy car from the managed fleet, tells the customer on "
     "WhatsApp what's happening, and sources the part from another supplier in two days. The parts "
     "supplier flips to committed."),
    ("04_approval",
     "Now every required party has committed <break time='250ms'/> so the gate opens. But no money "
     "moves without a human. The adjuster gets an approve or hold card <break time='250ms'/> and that's "
     "enforced in code, not just a prompt. <break time='350ms'/> And when the repair shop's R C S "
     "session drops, the same workflow just continues on S M S <break time='250ms'/> no lost context, "
     "because the state lives in AgentCore Memory, not in the channel."),
    ("05_settlement",
     "The adjuster approves. The engine issues the settlement letter through Amazon S E S and notifies "
     "the customer. <break time='400ms'/> Settled <break time='250ms'/> four thousand two hundred "
     "dollars <break time='250ms'/> in days, not weeks. <break time='350ms'/> And this is genuinely "
     "live. These are real message I Ds, returned by Amazon S E S and A W S End User Messaging."),
    ("06_close",
     "Five parties. Four C D S channels. One claim state. <break time='300ms'/> And the same engine "
     "re skins for utilities, retail, healthcare, and finance. Build it once <break time='200ms'/> "
     "sell it everywhere. <break time='400ms'/> This is One Touch Resolve."),
]


def synth(polly, ssml: str, dest: Path) -> None:
    r = polly.synthesize_speech(
        TextType="ssml",
        Text=f"<speak>{ssml}</speak>",
        OutputFormat="mp3",
        VoiceId=VOICE,
        Engine=ENGINE,
    )
    dest.write_bytes(r["AudioStream"].read())


def main() -> int:
    polly = boto3.client("polly", region_name=REGION)
    parts: list[Path] = []
    for name, ssml in BEATS:
        dest = OUT / f"{name}.mp3"
        synth(polly, ssml, dest)
        parts.append(dest)
        print(f"  synth {dest.name}  ({dest.stat().st_size} bytes)")

    # Stitch into one track with a short gap between beats.
    concat_list = OUT / "_concat.txt"
    gap = OUT / "_gap.mp3"
    # 400ms of silence as a beat separator.
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", "0.4", "-q:a", "9", str(gap)],
        check=True, capture_output=True,
    )
    lines = []
    for p in parts:
        lines.append(f"file '{p.name}'")
        lines.append(f"file '{gap.name}'")
    concat_list.write_text("\n".join(lines))
    full = OUT / "one_touch_resolve_vo.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(full)],
        check=True, capture_output=True, cwd=str(OUT),
    )
    # Report duration.
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(full)],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"==> full track: {full}  (~{float(dur):.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
