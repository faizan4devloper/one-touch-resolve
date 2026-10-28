#!/usr/bin/env python3
"""Voiceover matched to the ACTUAL demo recording (Media2.mp4).

The recording follows the severe-crash → tow path for Alex Rivera (not the
parts-back-order branch), runs ~2:14, and shows: intro slide → FNOL photo on
WhatsApp → Nova Pro vision (severe, fluid leak) → fan-out to roadside/rental/
repair → 4/4 committed → settled via Amazon SES + human-approval notice.

This script synthesizes narration timed to those on-screen beats so it syncs
cleanly when laid over the video. Output: docs/voiceover_v2/*.mp3 + the stitched
one_touch_resolve_vo_v2.mp3.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "voiceover_v2"
OUT.mkdir(parents=True, exist_ok=True)

REGION = "us-east-1"
VOICE = "Joanna"
ENGINE = "neural"

# (filename, SSML) — timed to the recording's beats (~2:14 total target).
BEATS = [
    ("00_intro",
     "Property insurance claims take <say-as interpret-as='cardinal'>40.7</say-as> days to settle "
     "on average <break time='350ms'/> the longest since two thousand eight. And the delay isn't "
     "the adjuster <break time='250ms'/> it's that the customer, the repair shop, and every other "
     "party never actually talk to each other. <break time='400ms'/> This is One Touch Resolve "
     "<break time='200ms'/> an A I agent on Amazon Bedrock AgentCore that coordinates every party, "
     "across A W S Communication Developer Services, and drives the claim to settled."),
    ("01_fnol",
     "Meet Alex Rivera. Alex has just been in a collision <break time='250ms'/> and never makes a "
     "single call. The insurer's agent reaches out first on WhatsApp, confirms Alex is safe, and "
     "asks for one photo of the damage. <break time='300ms'/> That photo is the only thing Alex does."),
    ("02_vision",
     "And the photo decides the plan. Amazon Bedrock Nova Pro vision reads the actual image "
     "<break time='250ms'/> it sees severe front-end damage and a fluid leak, judges the car not "
     "drivable, and opens the claim. <break time='300ms'/> This isn't a dropdown <break time='200ms'/> "
     "the journey branches on what the model really sees."),
    ("03_fanout",
     "Now the supervisor fans out to specialist sub agents <break time='250ms'/> one per party. It "
     "dispatches a tow over S M S, reserves a rental, and books the repair shop by email "
     "<break time='250ms'/> all coordinated in parallel, each on the right channel. On the operator "
     "console you can watch one shared claim state move as every party commits."),
    ("04_settle",
     "Every required party has committed <break time='250ms'/> four of four. The commit gate opens, "
     "and the engine issues the settlement letter through Amazon S E S, with the coverage and parts "
     "notices emailed too. <break time='300ms'/> But no money moves without a human <break time='200ms'/> "
     "the adjuster's approval is required before payout, enforced in code."),
    ("05_close",
     "Settled <break time='250ms'/> in days, not weeks. Four parties, multiple C D S channels, one "
     "claim state <break time='250ms'/> and the same engine re skins for utilities, retail, "
     "healthcare, and finance. This is One Touch Resolve."),
]


def synth(polly, ssml, dest):
    r = polly.synthesize_speech(TextType="ssml", Text=f"<speak>{ssml}</speak>",
                                OutputFormat="mp3", VoiceId=VOICE, Engine=ENGINE)
    dest.write_bytes(r["AudioStream"].read())


def main():
    polly = boto3.client("polly", region_name=REGION)
    parts = []
    for name, ssml in BEATS:
        d = OUT / f"{name}.mp3"
        synth(polly, ssml, d)
        parts.append(d)
        print(f"  {d.name}  {d.stat().st_size} bytes")
    gap = OUT / "_gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", "0.35", "-q:a", "9", str(gap)], check=True, capture_output=True)
    lst = OUT / "_c.txt"
    lst.write_text("\n".join(f"file '{p.name}'\nfile '{gap.name}'" for p in parts))
    full = OUT / "one_touch_resolve_vo_v2.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(full)], check=True, capture_output=True, cwd=str(OUT))
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", str(full)],
                         capture_output=True, text=True).stdout.strip()
    print(f"==> {full}  (~{float(dur):.1f}s)")


if __name__ == "__main__":
    main()
