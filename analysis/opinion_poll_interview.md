# Interviewing the expanded Fan Index

Fieldwork date: 2026-08-28 to 2026-08-29
Question: Who is the greatest Formula 1 driver of all time?

## What is in the base?

- 22,358 collected rows collapse to 16,364 unique public comments after cross-run deduplication.
- The sample covers 61 selected conversations on YouTube, Reddit, GTPlanet, Z4 Forum, and
  FORUMula1; 33 conversations have at least five valid votes.
- 1,632 unique authors make one explicit, non-conflicting all-time choice.
- YouTube contributes 1,576 valid choices, Reddit 37, and independent forums 19. Platform balancing
  prevents YouTube's much larger raw volume from determining the score by itself.
- No public handle, profile photo, or channel URL is stored; repeat voters are detected with a hash.
- The 2,000-vote stretch target was not reached. The classifier was not relaxed to turn comparisons,
  quoted claims, likes, or ambiguous multi-driver discussion into votes.

## Who leads?

Ayrton Senna ranks first with 653 of 1,632 raw votes (40.0%) and a 28.0% platform-balanced score.
Michael Schumacher is second at 20.6%, followed by Juan Manuel Fangio at 15.4%, Jim Clark at 9.2%,
and Lewis Hamilton at 8.9%.

Senna's balanced lead over Schumacher is 7.5 percentage points. The raw 95% Wilson interval around
Senna's 653/1,632 share is 37.7%–42.4%; it describes uncertainty inside this convenience sample,
not uncertainty about all Formula 1 fans.

## Do the sources agree?

Senna receives votes on all three platform groups and in 39 conversations. Schumacher, Fangio,
Clark, Hamilton, and Alonso also appear on all three groups. The ordering changes materially when
platforms are balanced: YouTube supplies 96.6% of raw valid choices, so reporting raw shares alone
would understate the smaller Reddit and forum samples. Sources with fewer than five valid choices
remain visible in provenance but do not influence the balanced score.

## What did classifier validation change?

An audit of accepted and rejected comments added explicit handling for descending rankings,
unnumbered top lists, multilingual endorsement phrases, and short answers to a direct prompt. It
also exposed false positives from relative comparisons (“Vettel is better than Alonso”), skeptical
frames, omitted-driver complaints, and search results about races or current-season rankings.
Those cases are now rejected or excluded at source curation. The published page emphasizes verified
choices and provenance rather than presenting non-vote conversation as an error metric.

## What can be claimed in the presentation?

Safe claim: **“Across selected public conversations on YouTube, Reddit, and independent forums,
Senna led the platform-balanced Fan Index among 1,632 unique explicit choices.”**

Unsafe claim: **“60% of Formula 1 fans believe Senna is the greatest.”** The sample is neither
random nor representative, and the source audiences are not the full fan population.

## What should the next iteration test?

1. Add X and Instagram only through authorized sessions and matched neutral prompts.
2. Retry rate-limited Reddit threads on a later fieldwork date rather than evading limits.
3. Expand the manual validation sample and publish precision/recall by language and rule family.
4. Freeze a second fieldwork date to measure whether active-driver recency changes the ranking.
5. Compare the opinion ranking with TelemetryOne's ELO ranking without combining their scores.
