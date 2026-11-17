#!/usr/bin/env -S uv run
# -\*- coding: utf-8 -\*-
# SPDX-FileCopyrightText: © 2026 Robert Hunt <Freely.Given.org+OBD@gmail.com>
# SPDX-License-Identifier: CC0-1.0
#
# adaptTyndaleResources.py
#
# Script to adapt the Tyndale Open Resources (based on the NLT) to suit the OET-RV
#
# Copyright (C) 2026 Robert Hunt
# Author: Robert Hunt <Freely.Given.org+OBD@gmail.com>
# License: CC0-1.0 (the script itself)
#   The adapted Tyndale resources remain CC BY-SA 4.0 (see ADAPTATION_NOTICE.md)
#
"""
Adapt the Tyndale Open Study Notes and Tyndale Open Bible Dictionary
    (downloaded from https://tyndaleopenresources.com/ into the parent folder)
    to imitate how the OET Readers' Version (OET-RV) handles names and some wording.

Steps:
    1/ Delete and freshly re-copy the two downloaded folders from the parent folder into this one
        (so this script can always be re-run safely, e.g., after the names table changes).
    2/ Load OET-RV_names_table.tsv and also scan the OET-RV ESFM files
        to see how each name is actually explained there,
        e.g., 'Yeshua (Jesus; Grk. Yesus)' vs. 'Mosheh (Moses)'.
    3/ In every XML file, change NLT/traditional names to the OET-RV names,
        explaining the name on its first use in each item (study note/article/etc.)
        and again if it hasn't been explained within the last EXPLAIN_WINDOW_LINES lines,
        e.g., 'Jesus' -> 'Yeshua (Jesus; Grk. Yesus)' then just 'Yeshua'.
    4/ Apply the (configurable) terminology changes in TERMINOLOGY_RULES,
        e.g., 'the LORD' -> 'Yahweh'.
    5/ Write ADAPTATION_NOTICE.md (required by CC BY-SA) and adaptation_log.tsv.

Only element text is changed: never tag attributes (e.g., href="?bref=John.3.16"),
    link text (Bible references and dictionary cross-references),
    <title> elements (used as lookup keys), dictionary contents lists,
    or Hebrew/Greek/small-caps spans.

CHANGELOG:
    2026-11-17 First version
    2026-11-17 Normalise copied CRLF line endings to LF
"""
from collections import Counter, defaultdict
from csv import DictReader
from functools import lru_cache
from pathlib import Path
import re
import shutil
import sys


LAST_MODIFIED_DATE = '2026-11-17' # by RJH
PROGRAM_NAME = "Adapt Tyndale Open Resources for OET-RV"
PROGRAM_VERSION = '0.10'

THIS_FOLDER = Path(__file__).resolve().parent
DOWNLOADS_FOLDER = THIS_FOLDER.parent # where the zips were unzipped
SOURCE_FOLDER_NAMES = ('Tyndale Open Study Notes', 'TyndaleOpenBibleDictionary') # Same names are used in our output
OET_RV_FOLDER = Path('/srv/FreelyGiven/OpenEnglishTranslation--OET/translatedTexts/ReadersVersion/')
NAMES_TABLE_FILEPATH = OET_RV_FOLDER / 'OET-RV_names_table.tsv'

EXPLAIN_WINDOW_LINES = 10 # Re-explain a name if it was last explained more than this many lines ago
EXPLAIN_ONLY_FLAGGED_NAMES = False # True = only explain names with Explained=Y in the names table
    # (False explains every changed name on first use, because readers of an isolated note or article
    #   won't have seen the OET-RV book where the name might first be explained)

MAX_TRADITIONAL_FRACTION = 0.2 # Don't change a name if the OET-RV text itself uses the traditional form more than this fraction of the time

# Traditional names that are also common English words or otherwise unsafe to change automatically
SKIP_NAMES = { 'Abed', 'Agar', 'Bath', 'Beer', 'Behemoth', 'Carpus', 'Cherub', 'Clement', 'Col', 'Crates',
    'Destiny', 'Epicurean', 'Epicureans', 'Ether', 'Fortune', 'Gob', 'Leviathan', 'Macron', 'Manes',
    'Media', 'Mica', 'Mortar', 'Narcissus', 'Onus', 'Phoenix', 'Shamed', 'Stoic', 'Straight', 'Tidal', 'Weeks',
    'Hebrew', 'Hebrews', 'Greek', 'Greeks', 'Aramaic', 'Latin', # Mostly refer to languages (or a book) in these resources
    'Corinthians', 'Ephesians', 'Philippians', 'Thessalonians', 'Colossians', 'Galatians', 'Romans', # Mostly refer to NT books
    'Josephus', # The historian
    'Nazarene', 'Judea', # Table maps these to Nazaret and Yehudah, which don't suit NT commentary
    }

# Elements/classes whose contents are never changed
SKIP_ELEMENTS = {'a', 'title', 'refs', 'include'}
SKIP_CLASSES = {'hebrew', 'greek', 'sc', 'sn-ref', 'sn-ref-sc', 'sn-hebrew-chars', 'toc', 'artfile', 'lc', 'vn'}

# Terminology changes: (enabled, scopes, regex, replacement, description)
#   scopes: 'TOSN' = study/theme notes etc., 'TOBD' = Bible dictionary
#   Replacements keep the case of the first letter of the matched text (unless the replacement starts with '<').
#   Rules whose regex contains '<' are applied to the whole XML line (so must never match inside attributes),
#       all other rules are only applied to element text (outside skipped elements).
DIVINE = r'<span class="((?:sn-excerpt-)?divine-name)">'
TERMINOLOGY_RULES = [
    # The divine name (the NLT 'LORD' represents YHWH)
    (True, ('TOSN','TOBD'), rf'\b(?:[Tt]he )?[Ss]overeign {DIVINE}Lord</span>', r'the master <span class="\1">Yahweh</span>', "Sovereign LORD → master Yahweh"),
    (True, ('TOSN','TOBD'), rf'\b[Tt]he </span>{DIVINE}Lord(\W?)</span>', r'</span><span class="\1">Yahweh\2</span>', "the LORD → Yahweh"),
    (True, ('TOSN','TOBD'), rf'\b[Tt]he</span> {DIVINE}Lord(\W?)</span>', r'</span> <span class="\1">Yahweh\2</span>', "the LORD → Yahweh"),
    (True, ('TOSN','TOBD'), rf'\b[Tt]he {DIVINE}Lord(\W?)</span>', r'<span class="\1">Yahweh\2</span>', "the LORD → Yahweh"),
    (True, ('TOSN','TOBD'), rf'{DIVINE}Lord God</span>', r'<span class="\1">Yahweh God</span>', "LORD God → Yahweh God"),
    (True, ('TOSN','TOBD'), rf'{DIVINE}Holy to the Lord</span>', r'<span class="\1">Holy to Yahweh</span>', "Holy to the LORD → Holy to Yahweh"),
    (True, ('TOSN','TOBD'), rf'{DIVINE}Lord(\W?)</span>', r'<span class="\1">Yahweh\2</span>', "LORD → Yahweh"),
    (True, ('TOSN','TOBD'), r'\b(?:[Tt]he )?LORD\b', 'Yahweh', "LORD → Yahweh"),
    (True, ('TOSN','TOBD'), r'<span class="sn-excerpt"></span> ?(?=<span class="sn-excerpt-divine-name">)', '', "(remove excerpt spans emptied by the above)"),
    # Other OET-RV wording
    (True, ('TOSN','TOBD'), r'\bJohn the Baptist\b', 'John the immerser', "John the Baptist → John the immerser"),
    (True, ('TOSN',), r'\bSabbath days?\b', 'Rest Day', "Sabbath day → Rest Day"),
    (True, ('TOSN',), r'\bSabbaths\b', 'Rest Days', "Sabbaths → Rest Days"),
    (True, ('TOSN',), r'\bSabbath\b', 'Rest Day', "Sabbath → Rest Day"),
    (True, ('TOSN',), r'\bsynagogues\b', 'meeting halls', "synagogues → meeting halls"),
    (True, ('TOSN',), r'\bsynagogue\b', 'meeting hall', "synagogue → meeting hall"),
    # Disabled by default: these are OET-RV wording, but often wrong in theological or church-history discussion
    #   (e.g., 'infant baptism', 'baptism by sprinkling', 'the new covenant', 'the Christian church')
    (False, ('TOSN',), r'\bbaptized\b', 'immersed', "baptized → immersed"),
    (False, ('TOSN',), r'\bbaptizing\b', 'immersing', "baptizing → immersing"),
    (False, ('TOSN',), r'\bbaptize(s?)\b', r'immerse\1', "baptize → immerse"),
    (False, ('TOSN',), r'\bbaptism(s?)\b', r'immersion\1', "baptism → immersion"),
    (False, ('TOSN',), r'\bChrist\b(?!ian|mas|ology|ological)', 'Messiah', "Christ → Messiah"),
    (False, ('TOSN',), r'\bdisciples\b', 'followers', "disciples → followers"),
    (False, ('TOSN',), r'\bcovenant(s?)\b', r'agreement\1', "covenant → agreement"),
    (False, ('TOSN',), r'\bHoly Spirit\b', 'holy spirit', "Holy Spirit → holy spirit"),
    ]

POSSESSIVE_RE = re.compile(r"(?:[’']s\b|[’'](?= [a-z]))") # ’s or (after s) a bare ’ followed by a lower-case word


def copySourceFolders() -> None:
    """
    Delete any previous copies and copy in the freshly downloaded folders.
    """
    for folderName in SOURCE_FOLDER_NAMES:
        sourcePath, destinationPath = DOWNLOADS_FOLDER / folderName, THIS_FOLDER / folderName
        if not sourcePath.is_dir():
            sys.exit(f"ERROR: Can't find downloaded folder '{sourcePath}' — did you unzip it there?")
        if destinationPath.exists():
            assert destinationPath.resolve() != sourcePath.resolve()
            shutil.rmtree(destinationPath)
        shutil.copytree(sourcePath, destinationPath)
        for filepath in destinationPath.rglob('*'): # Some downloaded files have Windows CRLF line endings
            if filepath.suffix.lower() in ('.txt','.xml') and b'\r\n' in (data := filepath.read_bytes()):
                filepath.write_bytes(data.replace(b'\r\n', b'\n')) # Normalise to LF (as git would anyway)
        print(f"  Copied '{sourcePath}' to '{destinationPath}'")
# end of copySourceFolders


def harvestEsfmExplanations() -> tuple[dict[str,Counter],Counter]:
    """
    Scan the OET-RV ESFM files for name explanations like 'Yeshua \\add !(Jesus; Grk. Yesus)\\add*'
        so that we can imitate the way each name is most commonly explained.

    Also counts how often each capitalised word (or hyphenated word) is used in the OET-RV text
        (outside of explanations), so we can tell if the OET-RV actually keeps a traditional name.

    Returns a dict with RV names as keys, and counters of the explanation (inside the parentheses) as values,
        plus a counter of words used in the OET-RV text.
    """
    explanations, wordCounts = defaultdict(Counter), Counter()
    explanationRE = re.compile(r"([A-Z][\w’'-]*)(?:\\\+?add\*)? \\\+?add !\(([^)]+)\)")
    for filepath in sorted(OET_RV_FOLDER.glob('OET-RV_*.ESFM')):
        text = re.sub(r'¦\d+', '', filepath.read_text(encoding='utf-8'))
        for match in explanationRE.finditer(text):
            rvName, explanation = match.group(1), match.group(2)
            if rvName[-2:] in ("'s",'’s'): # Ignore possessives (they're handled by our code)
                continue
            explanations[rvName][explanation] += 1
        # Now count words in the Bible text only (not in introductions, headings, comments, or footnotes)
        text = '\n'.join(line for line in text.splitlines()
                            if not re.match(r'\\(rem|i[a-z]*|li\d?|mt\d?|toc\d|h|id|usfm|ide|s\d?|r|d|ms\d?|mr|sr|cl)\b', line))
        text = re.sub(r'\\f .+?\\f\*|\\x .+?\\x\*', ' ', text) # Remove footnotes and cross-references
        text = explanationRE.sub(r'\1', text) # Remove explanations
        text = re.sub(r'\([^()]*\)', ' ', text) # Remove other parenthesised text (e.g., unmarked explanations)
        text = re.sub(r"[\w’']+/ ?([\w’']+)", r'\1', text) # Remove slashed explanations like Yakov/Jacob
        text = re.sub(r'\\[a-z0-9+]+\*?|[@&*≈~]', ' ', text).replace("'", '’') # Remove markers and OET-RV special characters
        wordCounts.update(re.findall(r"(?<![\w’'-])[A-Z][\w’']*(?:[- ][A-Z][\w’']*)*", text))
    print(f"  Found explanations for {len(explanations):,} names in the OET-RV ESFM files")
    return explanations, wordCounts
# end of harvestEsfmExplanations


def loadNames(esfmExplanations:dict[str,Counter], esfmWordCounts:Counter) -> dict[str,dict]:
    """
    Load the OET-RV names table and decide how to explain each name.

    Returns a dict with traditional names as keys.
    """
    rowsByTraditionalName = defaultdict(list)
    with open(NAMES_TABLE_FILEPATH, 'rt', encoding='utf-8', newline='') as tsvFile:
        for row in DictReader(tsvFile, delimiter='\t'):
            rowsByTraditionalName[row['TraditionalName'].strip()].append(row)

    def esfmCount(name:str) -> int:
        """ How often the OET-RV uses this name (including possessive and multi-word uses) """
        return sum(count for word,count in esfmWordCounts.items()
                    if word == name or word == f"{name}’s" or word.startswith(f'{name} ') or word.endswith(f' {name}'))

    names, skippedAmbiguous, skippedKept = {}, [], []
    esfmCount = lru_cache(maxsize=None)(esfmCount)
    for traditionalName, rows in rowsByTraditionalName.items():
        if not traditionalName or traditionalName in SKIP_NAMES \
        or '' in traditionalName.split('-'): # e.g., 'Beth-' name components
            continue
        rows = [row for row in rows if row['RVName'].strip() and row['RVName'].strip() != traditionalName
                    and '(0)' not in row['Comment']] # '(0)' entries are name components and titles
        if not rows: continue
        if len({row['RVName'] for row in rows}) > 1: # Same traditional name maps to different RV names
            flaggedRows = [row for row in rows if row['Explained'].strip()=='Y']
            if len(flaggedRows) != 1:
                skippedAmbiguous.append(f"{traditionalName}={'/'.join(row['RVName'] for row in rows)}")
                continue
            rows = flaggedRows # Use the main (explained) one
        row = rows[0]
        rvName = row['RVName'].strip()
        traditionalCount = esfmCount(traditionalName)
        if traditionalCount > MAX_TRADITIONAL_FRACTION * (traditionalCount + esfmCount(rvName)):
            skippedKept.append(traditionalName) # The OET-RV text often still uses the traditional form
            continue
        isFlagged = row['Explained'].strip() == 'Y'
        if EXPLAIN_ONLY_FLAGGED_NAMES and not isFlagged:
            explanation = None
        else:
            explanation = traditionalName # Default
            # See if the OET-RV ESFM files usually add a Greek form
            grkExplanations = Counter()
            for esfmExplanation,count in esfmExplanations.get(rvName, {}).items():
                if esfmExplanation.startswith(f'{traditionalName}; Grk. '):
                    grkExplanations[esfmExplanation] += count
                elif esfmExplanation == traditionalName:
                    grkExplanations[None] += count
            if grkExplanations:
                mostCommon = grkExplanations.most_common(1)[0][0]
                if mostCommon: explanation = mostCommon
        names[traditionalName] = {'rvName':rvName, 'explanation':explanation, 'flagged':isFlagged}
    print(f"  Loaded {len(names):,} names to change from {NAMES_TABLE_FILEPATH.name}")
    if skippedKept:
        print(f"  Skipped {len(skippedKept)} names still often used in OET-RV text: {', '.join(skippedKept)}")
    if skippedAmbiguous:
        print(f"  Skipped {len(skippedAmbiguous)} ambiguous names: {', '.join(skippedAmbiguous)}")
    return names
# end of loadNames


def makeNamesRegex(names:dict[str,dict]) -> re.Pattern:
    """
    Make one big regex that matches any of the traditional names (longest first).

    Parts after a hyphen can be either case, e.g., 'Abel-meholah' also matches 'Abel-Meholah'.
    """
    def namePattern(name:str) -> str:
        parts = name.split('-')
        return '-'.join([re.escape(parts[0])] + [f'[{p[0].upper()}{p[0].lower()}]{re.escape(p[1:])}' for p in parts[1:]])
    alternatives = '|'.join(namePattern(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<![\w’'-])({alternatives})(?![\w]|-\w)")
# end of makeNamesRegex


def possessive(name:str) -> str:
    """ Jesus -> Jesus’, John -> John’s, Grk. Yoannes -> Grk. Yoannes’ """
    return name + ('’' if name.endswith('s') else '’s')
# end of possessive


def matchCase(replacement:str, matchedText:str) -> str:
    if replacement.startswith('<') or not matchedText or not replacement: return replacement
    if matchedText[0].isupper(): return replacement[0].upper() + replacement[1:]
    return replacement
# end of matchCase


class ItemAdapter:
    """
    Keeps track of where each name was last explained (reset at each new <item>).
    """
    def __init__(self, names:dict[str,dict], namesRE:re.Pattern, scope:str, counts:Counter) -> None:
        self.names, self.namesRE, self.scope, self.counts = names, namesRE, scope, counts
        self.lowerNames = {name.lower():name for name in names}
        enabledRules = [(re.compile(regex), replacement, description)
                                    for enabled, scopes, regex, replacement, description in TERMINOLOGY_RULES
                                    if enabled and scope in scopes]
        self.markupRules = [rule for rule in enabledRules if '<' in rule[0].pattern]
        self.terminologyRules = [rule for rule in enabledRules if '<' not in rule[0].pattern]
        self.lastExplainedLine:dict[str,int] = {}
        self.lineNumber = 0

    def newItem(self) -> None:
        self.lastExplainedLine = {}

    def adaptLine(self, line:str) -> str:
        self.lineNumber += 1
        if '<item ' in line: self.newItem()
        line = self.adaptTerminology(line, self.markupRules)
        # Split into tags and text, keeping track of which text is inside elements that we shouldn't change
        pieces = re.split(r'(<[^>]+>)', line)
        skipStack:list[bool] = []
        for ix, piece in enumerate(pieces):
            if piece.startswith('<'):
                tagMatch = re.match(r'<(/?)(\w+)([^>]*?)(/?)>', piece)
                if not tagMatch: continue
                isClosing, tagName, attributes, isEmpty = tagMatch.groups()
                if isEmpty: continue
                if isClosing:
                    if skipStack: skipStack.pop()
                else:
                    classMatch = re.search(r'class="([^"]*)"', attributes)
                    classes = set(classMatch.group(1).split()) if classMatch else set()
                    skipStack.append(tagName in SKIP_ELEMENTS or bool(classes & SKIP_CLASSES))
            elif piece and not any(skipStack):
                pieces[ix] = self.adaptNames(self.adaptTerminology(piece, self.terminologyRules))
        return ''.join(pieces)
    # end of ItemAdapter.adaptLine

    def adaptTerminology(self, text:str, rules:list) -> str:
        for regex, replacement, description in rules:
            text, numChanges = regex.subn(lambda m: matchCase(m.expand(replacement), m.group(0)), text)
            if numChanges: self.counts[f'TERM\t{description}'] += numChanges
        return text

    def adaptNames(self, text:str) -> str:
        result, lastEnd = [], 0
        for match in self.namesRE.finditer(text):
            matchedName = match.group(1)
            traditionalName = matchedName if matchedName in self.names else self.lowerNames.get(matchedName.lower())
            if traditionalName is None or not matchedName[0].isupper(): continue
            info = self.names[traditionalName]
            rvName = info['rvName']
            # Possessives: ’s, or a bare ’ after a name ending in 's' (but not a closing quote)
            possessiveMatch = POSSESSIVE_RE.match(text, match.end())
            if possessiveMatch and len(possessiveMatch.group(0)) == 1 and not matchedName.endswith('s'):
                possessiveMatch = None
            endIndex = possessiveMatch.end() if possessiveMatch else match.end()
            # See if Tyndale already follows the name with a parenthesised alternative that we'd change to the same RV name
            alreadyExplainedMatch, alternativeName = re.compile(r" \(([\w’' -]+)\)").match(text, endIndex), None
            if alreadyExplainedMatch:
                alternative = alreadyExplainedMatch.group(1)
                if alternative == rvName: # e.g., 'Syria (Aram)'
                    endIndex = alreadyExplainedMatch.end()
                elif alternative != traditionalName and self.names.get(alternative, {}).get('rvName') == rvName: # e.g., 'Ahasuerus (Xerxes)'
                    endIndex, alternativeName = alreadyExplainedMatch.end(), alternative
                else: alreadyExplainedMatch = None
            self.counts[f"NAME\t{traditionalName} → {rvName}"] += 1
            rvText = rvName + ('’s' if possessiveMatch else '') # OET-RV uses 'Paulos's' (not 'Paulos'')
            if info['explanation'] is not None \
            and (alreadyExplainedMatch or self.lineNumber - self.lastExplainedLine.get(rvName, -9999) > EXPLAIN_WINDOW_LINES):
                self.lastExplainedLine[rvName] = self.lineNumber
                explanation = info['explanation']
                if alternativeName: # e.g., 'Ahashverosh (Ahasuerus/Xerxes)' like the OET-RV
                    explanation = explanation.replace(traditionalName, f'{traditionalName}/{alternativeName}', 1)
                if possessiveMatch: # e.g., 'Yeshua’s (Jesus’; Grk. Yesus’)'
                    explanation = '; '.join(possessive(part) for part in explanation.split('; '))
                rvText = f'{rvText} ({explanation})'
            result.append(text[lastEnd:match.start()])
            result.append(rvText)
            lastEnd = endIndex
        result.append(text[lastEnd:])
        return ''.join(result)
    # end of ItemAdapter.adaptNames
# end of ItemAdapter class


def adaptFile(filepath:Path, names:dict[str,dict], namesRE:re.Pattern, counts:Counter) -> None:
    scope = 'TOBD' if 'Dictionary' in str(filepath) else 'TOSN'
    adapter = ItemAdapter(names, namesRE, scope, counts)
    originalText = filepath.read_text(encoding='utf-8')
    newText = ''.join(adapter.adaptLine(line) for line in originalText.splitlines(keepends=True))
    if newText != originalText:
        filepath.write_text(newText, encoding='utf-8')
# end of adaptFile


def writeNotices(counts:Counter) -> None:
    enabledRules = [description for enabled, _scopes, _regex, _replacement, description in TERMINOLOGY_RULES if enabled]
    notice = f"""# Adaptation notice

This folder contains works adapted from the **Tyndale Open Study Notes** and the **Tyndale Open Bible Dictionary**.

> Adapted from Tyndale Open Study Notes. The original work by Tyndale House Publishers is available for free at http://www.tyndaleopenresources.com.
>
> Adapted from Tyndale Open Bible Dictionary. The original work by Tyndale House Publishers is available for free at http://www.tyndaleopenresources.com.

The original works are copyright © Tyndale House Publishers and licensed under
[CC BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/). These adaptations are released under the same licence.

## Changes made

These changes were made automatically by `adaptTyndaleResources.py` (version {PROGRAM_VERSION})
to match the [Open English Translation](https://github.com/Freely-Given-org/OpenEnglishTranslation--OET) Readers’ Version (OET-RV):

- Traditional (mostly NLT) forms of names were changed to the OET-RV forms from `OET-RV_names_table.tsv`.
  The traditional form is given in parentheses at the first use in each note or article
  (and again after about {EXPLAIN_WINDOW_LINES} paragraphs), imitating the OET-RV,
  e.g., ‘Yeshua (Jesus; Grk. Yesus)’ then just ‘Yeshua’.
- Other wording changes:
""" + ''.join(f"  - {description}\n" for description in dict.fromkeys(enabledRules) if not description.startswith('(')) + """
Bible references, links, titles, and Hebrew/Greek words were not changed.
See `adaptation_log.tsv` for the number of times each change was made.
"""
    (THIS_FOLDER / 'ADAPTATION_NOTICE.md').write_text(notice, encoding='utf-8')
    for readmePath in THIS_FOLDER.glob('*/_README.txt'):
        with open(readmePath, 'at', encoding='utf-8') as readmeFile:
            readmeFile.write("\n\nThis copy has been adapted for the Open English Translation Readers’ Version (OET-RV). See ../ADAPTATION_NOTICE.md for the changes made.\n")
    with open(THIS_FOLDER / 'adaptation_log.tsv', 'wt', encoding='utf-8') as logFile:
        logFile.write('Type\tChange\tCount\n')
        for key, count in sorted(counts.items(), key=lambda kc: (-kc[1], kc[0])):
            logFile.write(f'{key}\t{count}\n')
# end of writeNotices


def main() -> None:
    print(f"{PROGRAM_NAME} v{PROGRAM_VERSION} ({LAST_MODIFIED_DATE})")
    copySourceFolders()
    names = loadNames(*harvestEsfmExplanations())
    namesRE = makeNamesRegex(names)
    counts = Counter()
    for folderName in SOURCE_FOLDER_NAMES:
        for filepath in sorted((THIS_FOLDER / folderName).rglob('*.xml')):
            adaptFile(filepath, names, namesRE, counts)
            print(f"  Adapted {filepath.relative_to(THIS_FOLDER)}")
    writeNotices(counts)
    numNameChanges = sum(count for key, count in counts.items() if key.startswith('NAME'))
    numTermChanges = sum(count for key, count in counts.items() if key.startswith('TERM'))
    print(f"  Made {numNameChanges:,} name changes and {numTermChanges:,} terminology changes (see adaptation_log.tsv)")
# end of main

if __name__ == '__main__':
    main()
# end of adaptTyndaleResources.py
