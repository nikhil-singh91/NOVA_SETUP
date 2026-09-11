# NOVA Media Matching & Playback Reliability Diagnosis

## Executive Summary
This audit investigates why NOVA's YouTube media playback sometimes played the wrong song version, selected unrelated videos, or chose an arbitrary episode for show requests. It analyzes the search collection and selection pipeline and details why choosing the first unranked search result fails in real-world usage.

---

## 1. Root Cause Analysis of Media Selection Failures

### A. How Search Results Were Previously Collected
* Previously, in `browser/sites/youtube.py`:
  ```python
  matches = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", html_txt)
  if video_ids:
      return f"https://www.youtube.com/watch?v={video_ids[0]}", title
  ```
* **Critical Flaws:**
  1. **Blind First-Match Selection:** The system took the very first video ID string regex match (`video_ids[0]`).
  2. **Unlinked Titles:** The title was extracted with a disconnected single regex `title_match = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', html_txt)`, which frequently belonged to a channel promo, featured reel, or completely different card in the HTML payload.
  3. **No Candidate Collection:** Only 1 candidate was inspected; no candidate ranking, filtering, or scoring was performed.

### B. Vulnerability to Irrelevant Content Types
Because `video_ids[0]` was selected blindly without parsing structured items:
1. **Shorts Selection:** An 8-second YouTube Short containing `#shorts` in its title could be selected instead of a full episode.
2. **Playlists and Mixes:** Auto-generated YouTube Mixes (`RD...`) or playlist links could be chosen instead of standalone videos.
3. **Unrelated Remixes / Covers:** A low-quality slowed+reverb remix or fan cover often ranked above the official song in certain search algorithms.
4. **Episode Mismatch:** When the user asked for *"Motu Patlu episode 1"*, if a trending clip of Episode 220 appeared on YouTube's results page, the unranked regex selected Episode 220.

---

## 2. Distinction: Search Success vs. Media Match Success

* **Search Success:** Sending an HTTP request to YouTube and receiving a 200 OK HTML payload.
* **Media Match Success:** Extracting 5–10 candidate video cards, evaluating each against a deterministic **`MediaMatchScore`**, respecting media types (Song vs. Episode vs. Tutorial vs. Short), verifying requested episode numbers and modifiers (*"remix"*, *"original"*, *"official"*, *"live"*), and ensuring the selected video title and duration are genuinely what the user requested.

---

## 3. The Overhaul Solution (Media Matching V2)

```mermaid
flowchart TD
    SPEECH[User Command: 'Play Motu Patlu episode 1' / 'Play Kesariya remix'] --> NORM[Intent & Normalizer]
    NORM --> REQ[MediaRequest Structure\nquery, media_type, episode_number, modifiers]
    REQ --> SEARCH[YouTube ytInitialData Search Extractor\nFetch Top 5-10 Candidate Video Cards]
    SEARCH --> CANDIDATES[Candidate Cards List\ntitle, video_id, channel, duration, badges]
    CANDIDATES --> SCORER[MediaMatchScore Engine\nExact Title, Token Overlap, Episode Match,\nModifier Alignment, Duration Filter]
    SCORER --> RANK[Ranked Candidates]
    RANK -->|Top Score >= High Threshold| PLAY[Navigate Directly to Top Ranked Video URL]
    RANK -->|Top Score < Medium Threshold| REFINE[Search Query Refinement (Max 2 Attempts)]
    REFINE --> SEARCH
    PLAY --> POST_VERIF[Post-Playback Title & Watch URL Verification]
    POST_VERIF --> RESULT[Verified Spoken Response]
```
