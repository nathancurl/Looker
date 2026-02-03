#!/usr/bin/env python3
"""Remove failing entries from config.json based on validation results."""

import json
from pathlib import Path

# Companies that passed validation (from the test run)
PASSED_GREENHOUSE = {
    "Airbnb", "Affirm", "Airtable", "Amplitude", "Anduril", "Anthropic", "Asana",
    "Ava Labs", "Block", "Brex", "Chime", "Cloudflare", "Cockroach Labs", "Coinbase",
    "Databricks", "Datadog", "Discord", "DoorDash", "Dropbox", "Duolingo", "Elastic",
    "Epic Games", "Faire", "Figma", "Flexport", "GitLab", "Grammarly", "Gusto",
    "HubSpot", "Instacart", "Lyft", "MongoDB", "Nuro", "Okta", "Oscar Health",
    "PagerDuty", "Pinterest", "Postman", "Reddit", "Robinhood", "Roku", "Scale AI",
    "SoFi", "Samsara", "SpaceX", "Stripe", "The Trade Desk", "Toast", "Twilio",
    "Unity", "Upstart", "Vercel", "Waymo", "Zscaler"
}

PASSED_LEVER = {"Kraken", "Olo", "Palantir", "Spotify", "Zoox"}

PASSED_ASHBY = {
    "Abridge", "Anyscale", "Benchling", "Braintrust", "Clerk", "Cohere", "Cursor",
    "Deepgram", "ElevenLabs", "Harvey", "LangChain", "Linear", "Modal", "Neon",
    "Notion", "OpenAI", "Perplexity", "Pinecone", "Pylon", "Railway", "Ramp",
    "Render", "Replit", "Resend", "Retool", "Sentry", "Supabase", "Temporal", "Vercel"
}

PASSED_WORKABLE = {
    "Bolt.eu", "Cal.com", "Hugging Face", "N8n", "PostHog", "Remote", "Slab"
}

PASSED_WORKDAY = {
    "Adobe", "Boeing", "Capital One", "Cisco", "Citi", "Dell", "General Motors",
    "HP", "HPE", "Intel", "MasterCard", "NVIDIA", "PayPal", "PwC", "Salesforce",
    "T-Mobile", "Target", "Walmart", "Workday"
}


def main():
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    sources = config["sources"]

    # Filter each source type
    if "greenhouse" in sources:
        sources["greenhouse"] = [
            c for c in sources["greenhouse"] if c.get("name") in PASSED_GREENHOUSE
        ]
        print(f"Greenhouse: kept {len(sources['greenhouse'])} companies")

    if "lever" in sources:
        sources["lever"] = [
            c for c in sources["lever"] if c.get("name") in PASSED_LEVER
        ]
        print(f"Lever: kept {len(sources['lever'])} companies")

    if "ashby" in sources:
        sources["ashby"] = [
            c for c in sources["ashby"] if c.get("name") in PASSED_ASHBY
        ]
        print(f"Ashby: kept {len(sources['ashby'])} companies")

    if "workable" in sources:
        sources["workable"] = [
            c for c in sources["workable"] if c.get("name") in PASSED_WORKABLE
        ]
        print(f"Workable: kept {len(sources['workable'])} companies")

    if "workday" in sources:
        sources["workday"] = [
            c for c in sources["workday"] if c.get("name") in PASSED_WORKDAY
        ]
        print(f"Workday: kept {len(sources['workday'])} companies")

    # Remove empty jobvite, icims, taleo for now
    if "jobvite" in sources:
        sources["jobvite"] = []
        print("Jobvite: cleared (API format different than expected)")

    if "icims" in sources:
        sources["icims"] = []
        print("iCIMS: cleared (needs per-company research)")

    if "taleo" in sources:
        sources["taleo"] = []
        print("Taleo: cleared (needs per-company research)")

    # Write back
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print("\nConfig updated!")


if __name__ == "__main__":
    main()
