# Adaptation notice

This folder contains works adapted from the **Tyndale Open Study Notes** and the **Tyndale Open Bible Dictionary**.

> Adapted from Tyndale Open Study Notes. The original work by Tyndale House Publishers is available for free at http://www.tyndaleopenresources.com.
>
> Adapted from Tyndale Open Bible Dictionary. The original work by Tyndale House Publishers is available for free at http://www.tyndaleopenresources.com.

The original works are copyright © Tyndale House Publishers and licensed under
[CC BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/). These adaptations are released under the same licence.

## Changes made

These changes were made automatically by `adaptTyndaleResources.py` (version 0.51)
to match the [Open English Translation](https://github.com/Freely-Given-org/OpenEnglishTranslation--OET) Readers’ Version (OET-RV):

- In the Bible dictionary, traditional (mostly NLT) forms of names were changed to the OET-RV forms from `OET-RV_names_table.tsv`.
  The traditional form is given after a slash at the first use in each article
  (and again after about 10 paragraphs), e.g., ‘Yeshua/Jesus’ then just ‘Yeshua’.
- In the study notes (which discuss the NLT text), the NLT names were kept,
  but the OET-RV form is given after a slash at the first use in each note
  (and again after about 10 paragraphs), e.g., ‘Samuel/Shmuel’ then just ‘Samuel’.
- Other wording changes (in the study notes, the NLT wording was kept, with the OET-RV wording added in parentheses
  after its first use in each note, e.g., ‘the LORD (Yahweh)’):
  - Sovereign LORD → master Yahweh
  - the LORD → Yahweh
  - LORD God → Yahweh God
  - Holy to the LORD → Holy to Yahweh
  - LORD → Yahweh
  - John the Baptist → John the immerser
  - Sabbath day → Rest Day
  - Sabbaths → Rest Days
  - Sabbath → Rest Day
  - synagogues → meeting halls
  - synagogue → meeting hall

Bible references, links, titles, Hebrew/Greek words, and text quoted from other Bible versions (e.g., ‘“…” (KJV)’) were not changed.
See `adaptation_log.tsv` for the number of times each change was made.

## Corrections

These errors in the original files were also corrected:

- `Tyndale Open Study Notes/BookIntros.xml`: a broken link to Acts 20:29-31 (with stray spaces and a backslash) in a book introduction was fixed
