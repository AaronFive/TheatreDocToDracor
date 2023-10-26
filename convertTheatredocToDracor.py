#!/usr/sfw/bin/python
# -*- coding: utf-8 -*-

import os, re, sys
import pickle
from os import walk, pardir
from os.path import abspath, dirname, join, basename, exists
from datetime import date

import editdistance as editdistance
import gender_guesser.detector as gender

"""
    theatredocToBibdramatique, a script to automatically convert 
    HTML theater plays from théâtre-documentation.com
    to XML-TEI as on http://bibdramatique.huma-num.fr/
    Copyright (C) 2021 Philippe Gambette

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser Public License for more details.

    You should have received a copy of the GNU Lesser Public License
    along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
# The folder containing this script must contain a subfolder named corpusTD
# containing plays downloaded from théâtre-documentation.com

# Get the current folder
folder = abspath(dirname(sys.argv[0]))
root_folder = abspath(join(folder, pardir))
html_folder = abspath(join(root_folder, "cleanHTML_TD_normalized"))
Dracor_Folder = abspath(join(root_folder, "corpusTD_v2"))
clean_Dracor_Folder = abspath(join(root_folder, "corpusTD_cast_ok"))

if not exists(Dracor_Folder):
    os.system("mkdir {0}".format(Dracor_Folder))

### temporaire
# date_file = open(join(root_folder, 'datesTD.txt'), 'w')
# count_date = 0
###temporaire

mois = {
    'janvier': '01',
    'fevrier': '02',
    'mars': '03',
    'avril': '04',
    'mai': '05',
    'juin': '06',
    'juillet': '07',
    'aout': '08',
    'septembre': '09',
    'octobre': '10',
    'novembre': '11',
    'decembre': '12',
}

genres = ["tragedie", "comedie", "tragicomedie", "tragi-comedie", "farce", "vaudeville", "proverbe", "pastorale",
          "comedie musicale", "dialogue", "monologue"]
good_genre = {"tragedie": "Tragédie", "comedie": "Comédie", "tragicomedie": "Tragi-Comédie", "farce": "Farce",
              "vaudeville": "Vaudeville", "proverbe": "Proverbe", "pastorale": "Pastorale", "dialogue": "Dialogue",
              "comedie musicale": "Comédie Musicale", "dialogue": "Dialogue", "monologue": "Monologue"}


# DEBUG
def log(name, value):
    print(f'{name} : {value} ')


def notify_file(file):
    """Notify the user with the conversion of the input file.

    Args:
        file (str): Name of the file to convert.
    """
    print("Converting file " + file)
    # date_file.writelines(basename(file).replace(".html", '') + "\t")


# UTILS
def format_date_AAAAMMJJ(res):
    day = res[0].replace('<sup>er</sup>', '')
    if len(day) == 1:
        day = '0' + day
    return '-'.join(
        [res[2].replace('l', '1').replace('|', '1'),
         mois[res[1].lower().replace('é', 'e').replace('août', 'aout').replace('levrier', 'fevrier').replace('fevier',
                                                                                                             'fevrier')],
         day.replace('l', '1').replace('|', '1').replace('premier', '01')
         ])


def format_date_AAAAMM(res):
    return '-'.join(
        [res[1],
         mois[res[0].lower().replace('é', 'e').replace('août', 'aout').replace('levrier', 'fevrier').replace('fevier',
                                                                                                             'fevrier')]
         ])


def remove_html_tags_and_content(s):
    s = s.replace(u'\xa0', u' ')
    return re.sub('<[^>]+>', '', s)


def remove_html_tags(s):
    s = s.replace(u'\xa0', u' ')
    s = re.sub('<[^>]+>|</.*>', '', s)
    return s


def min_dict(d):
    """Returns (key_min, val_min) such that val_min is minimal among values of the dictionnary"""
    val_min = 100
    key_min = None
    for x in d:
        if d[x] < val_min:
            val_min = d[x]
            key_min = x
    return key_min, val_min


def normalize_line(line):
    # l = re.sub(r'</?span[^>]*>', '', line)
    l = line.replace("\xa0", ' ').replace('<a href="#_ftn1" name="_ftnref1" title="" id="_ftnref1">[1]</a>', '')
    return l.strip('\n')


def standard_line(playText):
    return list(map(normalize_line, playText))


def clean_scene_name(s):
    s = s.replace('</span>', '')
    s = re.sub('<span.*>', '', s)
    s = re.sub('\[\d{1,4}]', '', s)
    s = re.sub('<strong>|</strong>', '', s)
    s = remove_html_tags(s)
    if not s:
        return s
    if s[0] == ' ':
        s = s[1:]
    if s[-1] == ",":
        s = s[:-1]
    if s[-1] == ' ':
        s = s[:-1]
    if s in ['Notes', 'Variantes', 'PDF'] or 'PDF' in s:
        return ''
    s = s.strip()
    return s


def is_list_of_scenes(lst):
    """Checks if lst is a list of scenes of the form [['Acte 1,[Scène première, Scène II,...], [Acte 2, [Scène première, Scène II,...],...]
    Typically used on counters["sceneList]"""
    res = len(lst) > 0
    for x in lst:
        res = res and len(x) == 2 and x[1] and all(['Scène' in s for s in x[1]])
    return res


def normalize_character_name(s):
    if s and s[-1] == ".":
        s = s[:-1]
    clean_character_name = s.lower().replace("*", "")
    clean_character_name = re.sub("[\[\]\)\(]", "", clean_character_name)
    clean_character_name = remove_html_tags_and_content(clean_character_name)
    clean_character_name = re.sub("\A | \Z", "", clean_character_name)
    clean_character_name = re.sub(" +", "-", clean_character_name)
    return clean_character_name.strip()


# METADATA COLLECTION
def extract_sources(allPlays, fileSources):
    """Extract sources from each play

    Args:
        allPlays (TextIOWrapper): File with all the plays.
        fileSources (set): Empty set to fill with all sources.

    Returns:
        TextIOWrapper: Return allPlays.
    """
    for playLine in allPlays:
        res = re.search("([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\n", playLine)
        if res:
            fileSources[res.group(1)] = res.group(2)
    return allPlays


def get_source(fileSources, fileName):
    """Get the source from a file.

    Args:
        fileSources (dict): Dictionnary with files' name in key and their sources in values.
        fileName (str): Name of the file we want the source.

    Returns:
        str : The name of the source of the input file.
    """
    if fileName in fileSources:
        return fileSources[fileName]
    return ""


def get_title_and_author(line):
    """Extract the title and the author from a play

    Args:
        line (str): Line of the play with the title and the author's name.

    Returns:
        tuple: Tuple of strings with the title, the forename and the surname of the author.
    """
    title = ""
    author = ""
    persNames = ""
    forename = ""
    surname = ""

    res = re.search("<title>(.*) | théâtre-documentation.com</title>", line.replace(")", ""))
    if res:
        title = res.group(1)

        res2 = re.search(r"^(.*) \((.*)$", title)
        if res2:
            title = res2.group(1)
            author = res2.group(2).strip('| ')

            persNames = author.split(' ')
            forename = list(filter(lambda s: not s.isupper(), persNames))
            surname = list(filter(lambda s: s.isupper(), persNames))
    return title, forename, surname


def get_genre_versification_acts_number(playText):
    """Get the type of the play, and if it's in prose or in verses.

    Args:
        playText (TextIOWrapper): Text Contents of a play.

    Returns:
        _tuple_: Tuple of strings. The genre of the play, and the type of writing (verses or prose). Return [indéfini] if it's undefined.
    """
    res_genre, vers_prose, act_number = '[indéfini]', '[indéfini]', -1
    for l in standard_line(playText):
        res = re.search('<p>(.*)</p>', l)
        if res:
            content = res.group(1).lower().replace('é', 'e')
            if content == ' ':
                break
            for genre in genres:
                if genre in content:
                    res_genre = good_genre[genre]
                    break
            if 'prose' in content:
                vers_prose = 'prose'
            elif 'vers' in content:
                vers_prose = 'vers'
            act_number_string = re.search(r'(un|deux|trois|quatre|cinq|six|sept) actes?', content)
            if act_number_string:
                act_number = act_number_string.group(1)
                numbers_dict = {'un': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6, 'sept': 7}
                act_number = numbers_dict[act_number]
    return res_genre, vers_prose, act_number


def get_dates(playText):
    """Get the date of writing, the date of printing and the date of first performance of the play, and the line of context for each of them.

    Args:
        playText (TextIOWrapper): Text Contents of a play.

    Returns:
        tuple: Return a tuple of 6 strings :
            - Date of writing
            - Date of printing
            - Date of first performance
            - Line of date of writing
            - Line of date of printing
            - Line of date of first performance
    """
    # global count_date
    line_written = "[vide]"
    line_print = "[vide]"
    line_premiere = "[vide]"
    date_written = "[vide]"
    date_print = "[vide]"
    date_premiere = "[vide]"
    is_written = False
    is_print = False
    is_premiere = False

    for l in standard_line(playText):

        if re.search(".*<strong><em>Personnages.*</em></strong>.*", l) or re.search(
                '<p align="center" style="text-align:center"><b><i>Personnages.*</span></i></b></p>', l) or (
                True in (is_written, is_print, is_premiere) and l == '<p> </p>'):
            break

        if re.search("<p>Non représenté[^0-9]*</p>", l):
            line_premiere = l.replace("<p>", "").replace("</p>", "")
            break

        if not is_written and not is_print:
            res = re.search("<p>.*[ÉéEe]crit en ([0-9]+).* et [op]ublié.* en ([0-9]+).*</p>", l)
            if res:
                line_written = l.replace('<p>', '').replace('</p>', '')
                line_print = l.replace('<p>', '').replace('</p>', '')
                date_written, date_print = res.groups()
                is_written, is_print = True, True

        if not is_written:
            res = re.search("<p>.*[ÉéEe]crit[e]? (.*)</p>", l)
            if res:
                line_written = l.replace('<p>', '').replace('</p>', '')
                res2 = re.search(".*le ([0-9]+) ([^ ]+) ([0-9]+).*", res.group(1))
                if res2:
                    date_written = format_date_AAAAMMJJ(res2.groups())
                    is_written = True
                else:
                    res2 = re.search(".*en ([0-9]+).*", res.group(1))
                    res3 = re.search(".*en ([^0-9 ]+) ([0-9]+).*", res.group(1))
                    if res2:
                        date_written = res2.group(1)
                        is_written = True
                    elif res3:
                        date_written = format_date_AAAAMM(res3.groups())
                        is_written = True

        if not is_premiere and not is_print:
            res = re.search(
                "<p>Publié.* ([0-9]+) et représenté.* ([0-9]+|1<sup>er</sup>|premier) ([^ ]+) ([0-9]+).*</p>", l)
            res2 = re.search("<p>Publié.* ([0-9]+) et représenté.* ([0-9]+).*</p>", l)
            if res or res2:
                is_print, is_premiere = True, True
                if res:
                    date_print, date_premiere = res.group(1), format_date_AAAAMMJJ(res.groups()[1:])

                elif res2:
                    date_print, date_premiere = res2.group(1), res2.group(2)
                is_print, is_premiere = True, True
                line_print, line_premiere = l.replace("<p>", "").replace("</p>", ""), l.replace("<p>", "").replace(
                    "</p>", "")

        date_line = re.search("<p>.*([Rr]eprésenté.*)</p>", l)
        date_line2 = re.search("<p>.*(fut joué.*)</p>", l)
        if (date_line or date_line2) and not is_premiere:
            if date_line2:
                date_line = date_line2
            date_line = date_line.group(1)
            res = re.search(".* ([l\|]?[0-9]+|1<sup>er</sup>|premier)[ ]+([^ ]+) ([l\|]?[0-9]+).*", date_line)
            res2 = re.search(".* ([0-9]+|1<sup>er</sup>|premier)[ ]+([^ ]+) ([0-9]+).*" * 2, date_line)
            double_words_res = re.search(
                ".* ([l\|]?[0-9]+|1<sup>er</sup>|premier)[ ]+([^ ]+)[ ]+([^ ]+) ([l\|]?[0-9]+).*", date_line)
            between_years_res = re.search(".* ([0-9]+)-([0-9]+).*", date_line)
            line_premiere = date_line
            if res:
                if res2:
                    date_premiere = format_date_AAAAMMJJ(res2.groups())
                else:
                    date_premiere = format_date_AAAAMMJJ(res.groups())
                is_premiere = True
            elif double_words_res:
                if double_words_res.group(2).replace('é', 'e') in mois:
                    groups = (double_words_res.group(1), double_words_res.group(2), double_words_res.group(4))
                else:
                    groups = (double_words_res.group(1), double_words_res.group(3), double_words_res.group(4))
                date_premiere = format_date_AAAAMMJJ(groups)
                is_premiere = True
            elif between_years_res:
                date_premiere = between_years_res.groups()
                is_premiere = True
            else:
                res = re.search(".* en ([0-9]+).*", date_line)
                res2 = re.search(".* en ([0-9]+).*" * 2, date_line)
                res3 = re.search(".* en ([0-9]+).*" * 3, date_line)
                if res:
                    if res2 is not None:
                        res = res2
                        if res3 is not None:
                            res = res3
                    date_premiere = res.group(1)
                    is_premiere = True
                else:
                    res = re.search(".* (en|le|de) ([^ ]+) ([0-9]+).*", date_line)
                    weird_res = re.search(".* (en|le|de)([0-9]+) ([^ ]+) ([0-9]+).*", date_line)
                    if res:
                        res2 = re.search("([0-9]+)(.*)", res.group(2))
                        if res2:
                            date_premiere = format_date_AAAAMMJJ(res2.groups() + res.groups()[2:])
                        elif res:
                            date_premiere = format_date_AAAAMM(res.groups()[1:])
                        is_premiere = True
                    elif weird_res:
                        date_premiere = format_date_AAAAMMJJ(weird_res.groups()[1:])
                        is_premiere = True

        if not is_print:
            res = re.search("<p>([0-9]+).*</p>", l)
            res2 = re.search("<p>Imprimée en ([0-9]+).*</p>", l)
            res3 = re.search("<p>Non représentée[,\.] ([0-9]+).*</p>",
                             l.replace('<a href="#_ftn1" name="_ftnref1" title="" id="_ftnref1">[1]</a>', ''))

            if res or res2 or res3:
                if res is None:
                    res = res2
                    if res2 is None:
                        res = res3
                if len(res.group(1)) == 4:
                    date_print = res.group(1)
                    line_print = l.replace("<p>", "").replace("<p>", "")
                    is_print = True

        if date_line is None:
            date_line = ""

    # if not (is_print or is_premiere or is_written):
    #     count_date += 1

    if not is_written:
        line_written = "[vide]"

    # date_file.writelines(line_written + '\t' + line_print + '\t' + line_premiere + '\t')

    # date_file.writelines(date_written + '\t')

    # date_file.writelines(date_print + '\t')

    # date_file.writelines(str(date_premiere) + "\n")

    return date_written, date_print, date_premiere, line_written, line_print, line_premiere


def find_summary(line, ul):
    """Detect if a line of the file is the start of the summary, with the tag <ul> of a HTML file, if it exists.

    Args:
        line (str) : The line where we try to detect the start of the summary.
        ul (int) : The number of ul tags found in the entire file.

    Returns:
        bool: True only if the line is the tag "<ul>".
    """
    if line == "<ul>":
        ul += 1
        return True
    return False


def extract_from_summary(line, ul):
    """Extract the datas from summary to count the number of acts and find an eventual dedicace in the play.

    Args:
        line (str) : The line where we try to detect the start of the summary.
        ul (int) : The number of ul tags found in the entire file.

    Returns:
        Match[str]: Return the datas extracted by the regex search function, None if it found nothing.
    """
    if line == "<ul>":
        ul += 1
        return True
    if line == "</ul>":
        ul -= 1
        return ul
    res = re.search("<li class=\"toc-level-([0-9])\"><a href=\"(.*)\"><strong>(.*)</strong></a></li>", line)
    if res:
        level = res.group(1)
        text = res.group(3)
        if level == 1:
            if "ACTE" in text:
                counters["actsInPlay"] += 1
            elif text != "PRÉFACE" and text != "PDF":
                counters["dedicace"] = True
    return res


def find_dedicace(line):
    """Extract the content of a dedicace in a play from a line if it has it.

    Args:
        line (str): The line where we're looking for a dedicace.

    Returns:
        str: The content of the dedicace if it exists in the line, None then.
    """
    res = re.search('<h1 class="rtecenter" style="color:#cc0066;" id=".*"><strong>(.*)</strong></h1>', line)
    if res:
        return res.group(1)
    return None


# METADATA WRITING
def write_title(outputFile, title):
    """Write the extracted title in the output file in XML.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        title (str): Title of a file.

    Returns:
        str: The same title.
    """
    if title:
        outputFile.writelines("""<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:lang="fre">
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">""" + title + """</title>""")
    return title


def write_type(outputFile, genre):
    """Write the extracted genre in the output file in XML.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        genre (str): Genre of a play.
    """
    if genre != '[indéfini]':
        outputFile.writelines("""
                <title type="sub">""" + genre + """</title>""")


def write_author(outputFile, author):
    """Write the author's name in the output file in XML.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        author (str): Author of the play.
    
    Returns:
        bool: True if the author's name have at least a forename or a surname, False then.
    """
    forename, surname = author
    if forename or surname:
        outputFile.writelines("""
            <author>
                <persName>""")
        if forename:
            for name in forename:
                if name in ['de', "d'"]:
                    outputFile.writelines("""
                    <linkname>""" + name + """</linkname>""")
                elif name in ['Abbé']:  # TODO identifier d'autres rolename
                    outputFile.writelines(f"""
                    <rolename>{name}</rolename>""")
                else:
                    outputFile.writelines(f"""
                    <forename>{name}</forename>""")
        if surname:
            for name in surname:
                if name in ['DE', "D'"]:
                    outputFile.writelines("""
                    <linkname>""" + name.lower() + """</linkname>""")
                else:
                    outputFile.writelines("""
                    <surname>""" + ''.join([name[0], name[1:].lower()]) + """</surname>""")

        outputFile.writelines("""
                </persName>
            </author>
                        <editor>Adrien Roumégous, dans le cadre d'un stage de M1 Informatique encadré par Aaron Boussidan et Philippe Gambette.</editor>
            </titleStmt>""")
        return True
    return False


def write_source(outputFile, source):
    """Write the source of the play in the output file in XML.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        source (str): Source of the play.
    """
    outputFile.writelines(f"""
            <publicationStmt>
                <publisher xml:id="dracor">DraCor</publisher>
                <idno type="URL">https://dracor.org</idno>
                <idno type="dracor" xml:base="https://dracor.org/id/">fre[6 chiffres]</idno>
                <idno type="wikidata" xml:base="http://www.wikidata.org/entity/">Q[id]</idno>
                <availability>
                    <licence>
                        <ab>CC BY-NC-SA 4.0</ab>
                        <ref target="https://creativecommons.org/licenses/by-nc-sa/4.0/">Licence</ref>
                    </licence>
                </availability> 
            </publicationStmt>
            <sourceDesc>
                <bibl type="digitalSource">
                    <name>Théâtre Documentation</name>
                    <idno type="URL"> {source} </idno>
                    <availability>
                        <licence>
                            <ab>loi française n° 92-597 du 1er juillet 1992 et loi n°78-753 du 17 juillet 1978</ab>
                            <ref target="http://théâtre-documentation.com/content/mentions-l%C3%A9gales#Mentions_legales">Mentions légales</ref>
                        </licence>
                    </availability>
                    <bibl type="originalSource">""")


def write_dates(outputFile, date_written, date_print, date_premiere, line_premiere):
    """Write the date of writing, the date of printing and the date of first performance of the play, and the line of context for each of them in an output file in XML.

    Args: 
        outputFile (TextIOWrapper): Output file to generate in XML.
        date_written (str): Date of writing of the play.
        date_print (str): Date of printing of the play.
        date_premiere (str): Date of first performance of the play.
        line_premiere (str): Line where the date of the first performance is written.
    """
    if date_written != "[vide]":
        outputFile.writelines("""
                        <date type="written" when=\"""" + date_written + """\">""")

    if date_print != "[vide]":
        outputFile.writelines("""
                        <date type="print" when=\"""" + date_print + """\">""")

    if date_premiere != "[vide]":
        if type(date_premiere) is str:
            outputFile.writelines("""
                        <date type="premiere" when=\"""" + date_premiere + """\">""" + line_premiere + """</date>""")
        else:
            outputFile.writelines("""
                        <date type="premiere" notBefore=\"""" + date_premiere[0] + """\" notAfter=\"""" + date_premiere[
                1] + """\" >""" + line_premiere + """</date>""")

    outputFile.writelines("""
                        <idno type="URL"/>
                    </bibl>
                </bibl>""")


def write_end_header(outputFile, genre, vers_prose):
    # TODO : Generate a better listPerson
    """Write the end of the header of a XML file

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        genre (str) : The genre of the converted play.
        vers_prose (str) : The type of the converted play, in verses or in prose.
    """
    outputFile.writelines(f"""
            </sourceDesc>
        </fileDesc>
        <profileDesc>
            <particDesc>
                <listPerson>""")

    for charaid, charaname in zip(counters["characterIDList"], counters["characterFullNameList"]):
        outputFile.writelines(f"""
                        <person xml:id="{charaid}" sex="SEX">
                            <persName>{charaname}</persName>
                        </person>""")
    # TODO : Get character sex from character name
    # TODO : Add Pastorale,Dialogue code and more genres ?
    wikidata_codes = {'Tragi-Comédie': 192881,
                      'Farce': 193979, 'Tragédie': 80930, 'Comédie': 40831,
                      'Vaudeville': 186286, 'Farce': 193979, "Proverbe": 2406762, 'Pastorale': 0000, "Dialogue": 00000}
    if genre in wikidata_codes:
        wikicode = wikidata_codes[genre]
    else:
        if genre != '[indéfini]':
            print(f"UNKNOW GENRE : {genre}")
        wikicode = None
    wikicode_part = ["", f"""
                <classCode scheme="http://www.wikidata.org/entity/">[Q{wikicode}]</classCode>"""]
    outputFile.writelines(f"""
                </listPerson>
            </particDesc>
            <textClass>
            <keywords scheme="http://theatre-documentation.fr"> <!--extracted from "genre" and "type" elements-->
                    <term> {genre}</term>
                    <term> {vers_prose} </term>
                </keywords>{wikicode_part[wikicode is not None]}
            </textClass>
        </profileDesc>
        <revisionDesc>
            <listChange>
                <change when="{date.today()}">(mg) file conversion from source</change>
            </listChange>
        </revisionDesc>
   </teiHeader>""")


def write_start_text(outputFile, title, genre, date_print):
    """Write the start of the text body of a XML file.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        title (str) : The title of the converted play.
        genre (str) : The genre of the converted play.
        date_print (str) : The date of printing of the converted play.
    """
    outputFile.writelines("""
    <text>
    <front>
        <docTitle>
            <titlePart type="main">""" + title.upper() + """</titlePart>""")
    if genre:
        outputFile.writelines("""
            <titlePart type="sub">""" + genre.upper() + """</titlePart>
        </docTitle>""")
    if date_print:
        outputFile.writelines("""
        <docDate when=\"""" + date_print + """\">[Date Print Line]</docDate>
        """)


def write_performance(outputFile, line_premiere, date_premiere):
    """Write the performance tag of the chosen XML file.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        line_premiere (str) : line of the play where the date of the first performance is written.
        date_premiere (str) : The date of the first performance of the converted play.
    """
    if date_premiere != '[vide]':
        if type(date_premiere) is tuple:
            date_premiere = '-'.join(date_premiere)
        outputFile.writelines("""
        <performance>
            <ab type="premiere">""" + line_premiere + """</ab><!--@date=\"""" + date_premiere + """\"-->
        </performance>""")


# def write_dedicace(outputFile, copy_playtext, author):
#     """Write the dedicace sentence of a play in its XML version.
#
#     Args:
#         outputFile (TextIOWrapper): Output file to generate in XML.
#         copy_playtext (TextIOWrapper) : Content of the input file in HTML.
#         author (tuple) : The author's name (tuple of string).
#     """
#     d = False
#     header = True
#     authorList = [i for i in author[0].extend(author[1]) if i not in ["de", "d'"]]
#     for line in copy_playtext:
#         dedicace = find_dedicace(line)
#         if dedicace:
#             outputFile.writelines("""
#         <div type="dedicace">
#                 <opener>
#                     <salute>""" + dedicace + """</salute>
#                 </opener>""")
#             d = True
#         if d:
#             res = re.search('<p>(.*)</p>')
#             if res:
#                 l = res.group(1)
#                 if l != ' ':
#                     if header:
#                         outputFile.writelines("""
#         <head>""" + l + """</head>""")
#                         header = False
#                     elif any([i in l for i in authorList]):
#                         outputFile.writelines("""
#         <signed>""" + l + """</signed>
# 	</div>""")
#                         return
#                     else:
#                         outputFile.writelines("""
#         <p>""" + l + """</p>""")

# TODO : Add <signed>
def write_dedicace(dedicace, dedicaceHeader, file):
    file.writelines(f"""
    <div type="dedicace">
            <opener>
                <salute> {dedicaceHeader}</salute>
            </opener>""")
    for index,line in enumerate(dedicace):
        # if index == len(dedicace)-1 and
        file.writelines(f"""
        <p> {line} </p>""")
    file.writelines(f"""
    </div>""")


## Collecting body of play
def try_saving_lines(outputFile, line):
    """Look if the read line is in <p></p> tags. If yes, authorize the copy of the lines contents of the HTML file in the XML output file.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        line (str): Line to read.

    Returns:
        bool: True if the line is in <p></p> tags.
    """
    res = re.search("<p>(.*)</p>", line)
    if res:
        outputFile.writelines("<p>" + res.group(1) + "</p>\n")
    return bool(res)


def start_character_block(line, characterBlock):
    """Check if we have to save the next lines as characters names of a play.

    Args:
        line (str): line to read
        characterBlock (bool): Actual situation of saving of characters.

    Returns:
        bool: True if a line with "Personnage" is written in the line, or written before.
    """
    return characterBlock or re.search("<strong><em>Personnages</em></strong>", line) or re.search(
        '<p align="center" style="text-align:center"><b><i>(<span style="letter-spacing:-\.3pt">)?Personnages(</span>)?</i></b></p>',
        line)


def end_character_block(characterBlock, line):
    """Detect if all the characters of a play were saved.

    Args:
        characterBlock (bool): Flag to know if lines are still composed by characters.
        line (str): line to read.

    Returns:
        tuple: the boolean of all the characters, but also the actual line.
    """
    if characterBlock:
        res = re.search("<h[1,2]", line)
        if res:
            characterBlock = False
            # print("Character list: " + str(counters["characterIDList"]))
        else:
            res = re.search("<p>(.*)</p>", line)
            if res:
                name = res.group(1)
                if len(name) == 1:
                    if counters["characterIDList"]:
                        characterBlock = False
                        print("Character list: " + str(counters["characterIDList"]))
                    return characterBlock, None
                character = name
                res = re.search("([^,]+)(,.*)", character)
                if res:
                    character = remove_html_tags_and_content(res.group(1))
                    role = remove_html_tags_and_content(res.group(2))
                else:
                    character = remove_html_tags_and_content(character)
                    role = ""
                if len(character) > 2 and character != "\xa0":
                    counters["characterFullNameList"].append(character)
                    clean_character_name = normalize_character_name(character)
                    counters["characterIDList"].append(clean_character_name)
                    counters["roleList"].append(role)
    return characterBlock, line


def find_scene_list(line, sceneList, inSceneList):
    """Finds the declaration of scenes at the beginning of the play and returns the list of scenes
        Args:
        line (str): line to read.
        sceneList(list): The list of scenes of the play. Elements are of the form ['Act Name',['Scene 1',...'Scene N']]
        inSceneList(bool): flag to know if we are reading a declaration of scenes

    Returns:
        list: Updated sceneList
        bool: Updated inSceneList"""
    # When inSceneList is true, we are currently reading the list of scenes. It is set at True when the "<div
    # class='toc-list'>" is found, and then fed forward sceneList is the list of scenes currently constructed
    if line is None and not inSceneList:
        return [], False
    elif line.strip() in [None, ''] and inSceneList:
        return sceneList, True
    if not inSceneList and line == "<div class='toc-list'>":
        return sceneList, True
    elif inSceneList and line in ['<ul>', '</ul>', '</li>']:
        return sceneList, True
    regex_act = r"<li class=\"toc-level-1\"><a href=[^>]*>(?:<strong>)?(?P<actename>[^<]+)(?:</strong>)?</a>"
    regex_scene = "<li class=\"toc-level-2\"><a href=.*><strong>(.+)</strong></a></li>|<li class=\"toc-level-1\"><a " \
                  "href=.*>(.*Scène.*)</a>"
    regex_scene_type = "[Jj]ournée|[Ss]cène|[Tt]ableau|[Ee]ntrée"
    regex_preface = "Préface|PREFACE|PRÉFACE"
    regex_dedicace = r"\A *À|\A *AU|.* À M\. .*"
    act_line = re.search(regex_act, line)
    scene_line = re.search(regex_scene, line)
    if act_line and act_line.group('actename') and inSceneList and "Scène" not in act_line.group(1):
        act_line = act_line.group('actename')
        act_line = clean_scene_name(act_line)
        if re.search(regex_dedicace, act_line):
            counters["dedicaceFound"] = True
            counters["dedicaceHeader"] = act_line
        elif re.search(regex_preface, act_line):
            counters["prefaceFound"] = True
            counters["prefaceHeader"] = act_line
        elif act_line:
            if not counters["noActPlay"]:
                sceneList.append([act_line, []])
            else:
                print("WARNING : ACT FOUND IN A NO ACT PLAY ? Treating it as a scene")
                sceneList.append(act_line)
        return sceneList, True
        # TODO:  Privilege
        # <div type="preface">
        # <head>Préface</head>
        #		<div type="docImprint">
    # 	<div type="privilege">
    #             <head>EXTRAIT DU PRIVILÈGE DU ROI</head>
    # 		<p>Par Grâce et privilège du Roi, donné à Paris le 19 janvier 1660, signé par le Roi en son conseil, Mareschal, il est permis à Guillaume de Luynes, Marchand-Libraire de notre bonne ville de Paris de faire imprimer, vendre, et débiter les Précieuses ridicules fait par le sieur Molière, pendant cinq années et défenses sont faites à tous autres de l'imprimer, ni vendre d'autre édition de celle de l'exposant, à peine de deux mille livres d'amende, de touts dépens, dommage et intérêts, comme il est porté plus amplement par les dites lettres.</p>
    # 		<p>Et le dit Luynes a fait part du privilège ci-dessus à Charles de Cercy et Claude Barbin, marchands-libraires, pour en jouir suivant l'accord fait entre-eux.</p>
    # 	</div><!--@id="1660-01-19"-->
    # 	<div type="printer">
    #             <p>À PARIS, chez Guilaume de LUYNES, Libraire juré au Palais, dans la Salle des Merciers, à la Justice.</p>
    #         </div><!--@id="LUYNES"-->
    # 	<div type="acheveImprime">
    #             <p>Achevé d'imprimer pour la première fois le 29 janvier 1660. Les exemplaires ont été fournis.</p>
    #         </div><!--@id="1660-01-29"-->
    # </div>
    if scene_line and inSceneList:
        if scene_line.group(1):
            scene_line = clean_scene_name(scene_line.group(1))
        else:
            scene_line = clean_scene_name(scene_line.group(2))
        if re.search(regex_dedicace, scene_line):
            counters["dedicaceFound"] = True
            counters["dedicaceHeader"] = scene_line
            return sceneList, True
        elif re.search(regex_preface, scene_line):
            counters["prefaceFound"] = True
            counters["prefaceHeader"] = scene_line
            return sceneList, True
        if sceneList:
            if scene_line:
                sceneList[-1][1].append(scene_line)
            return sceneList, True
        elif re.search(regex_scene_type, scene_line):
            # This is handling the case of plays with no acts but some scenes. We create a virtual unique act containing all scenes.
            sceneList.append(["Acte unique", [scene_line]])
        else:
            pass  # This is probably also a dedicace, or a line we don't know how to categorize. Throwing it away for now
        return sceneList, True
    if sceneList and inSceneList:
        return sceneList, False
    return [], False


def find_begin_act(line, counters, playContent):
    """Try to find the beginning of an act in a play and convert it in the XML file associated if it find it.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        line (str): line to read.
        counters (dict): Dictionnary with all the counters of the script.

    Returns:
        tuple: the line (str) and the refreshed counter (dict).
    """
    # Checking to see if this is a h1 header
    act_header = re.search(".*<h1[^>]*>(.*)</h1>", line)
    if act_header:
        # Creating the list of potential act names : they can either be regular act names or more unusual ones,
        # If they are unusual, they should be declared in the list of scenes at the beginning of the play
        act_header_string = act_header.group(1)
        acts_type = 'ACTE|JOURNÉE|TABLEAU|PARTIE|PROLOGUE|Prologue|ÉPOQUE|Partie|Tableau'  # Regular act names
        if counters["sceneList"] and not counters["noActPlay"]:
            acts_type = '|'.join(
                [acts_type] + [clean_scene_name(x[0].replace('*', '')) for x in counters["sceneList"] if
                               x[0] not in acts_type])  # acts declared in the beginning
        act_header_type = re.search(acts_type, act_header_string)
        if act_header_type:
            # Found a new act!
            counters["actsInPlay"] += 1
            counters["scenesInAct"] = 0
            act = act_header.group(1).replace("<strong>", "").replace("</strong>", "")
            act_number = re.search("ACTE (.*)", act)
            if act_number:
                counters["actNb"] = act_number.group(1)
            else:
                counters["actNb"] = act.replace(" ", "-").lower()
            if counters["noActPlay"]:  # Treating it as if it were a scene
                playContent.append({"sceneNumber": None, "sceneName": act, "repliques": [], "speakers_text": None,
                                    "speakers_ids": None})
            else:
                playContent.append({"actNumber": None, "actName": act, "Scenes": [], "actStageIndications": None})
    return line, counters, playContent


def find_begin_scene(line, counters, playContent):
    """Try to find the beginning of a scene in a play and convert it in the XML file associated if it find it.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
        line (str): line to read.
        counters (dict): Dictionnary with all the counters of the script.

    Returns:
        tuple: the line (str) and the refreshed counter (dict).
    """
    regex_scenes = "|".join(
        [".*<h2 .*<strong>(?P<h2strong>.*)</strong>.*</h2>", ".*<h2.*>(?P<h2normal>Scène.*)</h2>",
         "<h1.*>(?P<h1>.*Scène.*)</h1>"])
    res = re.search(regex_scenes, line)
    if res:
        # counters["characterLines"] = []
        # counters["repliquesinScene"] = 0
        # counters["charactersinScene"] = ""
        # if not (counters["scenelessPlayBeginningWritten"]):
        #     scene = "Scène 1"
        if res.group('h2strong') is not None:
            scene = res.group('h2strong')
        elif res.group('h2normal') is not None:
            scene = res.group('h2normal')
        else:
            scene = res.group('h1')
        scene_number = re.search("Scène (.*)", scene)
        if scene_number:
            scene_number = scene_number.group(1)
        else:
            scene_number = scene.replace(" ", "-").lower()
        counters["scenesInAct"] += 1
        new_scene = {"sceneName": scene, "sceneNumber": scene_number, "speakers_text": None, "speakers_ids": None,
                     "repliques": []}
        if playContent:
            if "actName" in playContent[-1]:  # We are inside an act
                playContent[-1]["Scenes"].append(new_scene)
            elif counters["noActPlay"]:  # This is a play with no act, only scenes
                playContent.append(new_scene)
            else:
                raise ValueError(f"Ill-formed playContent : {playContent}")
        else:
            # There are no acts or scenes yet : this is the first scene of a play with no scene
            if not counters["sceneList"] or type(counters["sceneList"][0] == str):
                counters["noActPlay"] = True
                playContent.append(new_scene)
            else:
                pass
                # TODO : this happens when we read text unexpectedly before the beginning of the act, but we know there should be an act
    return line, counters, playContent


def find_character(line, counters, playContent):
    """Find a character name in a line from a play text and stock it in the counters dict.

    Args:
        line (str): line to read in the play.
        counters (dict): Dictionnary with all the counters of the script.

    Returns:
        dict: The refreshed counter
    """
    # In theatre doc, character declarations can be of the form  :
    # <p align="center" style="text-align:center"><span style="font-size:10.0pt"><span style="letter-spacing:-.3pt">ROBERT.</span></span></p>
    # This regex captures this and simpler version (without spans)
    # res = re.search("<p align=.center[^>]+>(?:<[^>]*>)*([^<>]*)(?:<[^>]*>)*</p>", line)
    added_character = False
    res = re.search("<p align=.*center[^>]*>(.*)</p>", line)
    character_type = None
    character_name = None
    if res and res.group(1) != "\xa0" and "Personnages" not in res.group(1):
        character_name = res.group(1)
        special_characters = re.search("(TOUS|TOUTES|ENSEMBLE|CHOEUR|CHŒUR)", character_name)
        number_of_characters = len(character_name.split(","))  # Checking to see whether this is multiple characters
        # This is a declaration of characters occuring in the scene (TODO: or multiple characters speaking or special chars)
        # if special_characters:
        #     character_type = "Special"
        # elif number_of_characters >=2:
        #     character_type = "Multiple"
        # else:
        #     character_type = "Simple"
        if playContent:
            if "actName" in playContent[-1]:  # There's an act
                scenes = playContent[-1]["Scenes"]
            else:  # There's only scenes
                scenes = playContent
            if not scenes:  # We are not in a scene, so this is not a character name, but probably a stage indication, like a location
                playContent[-1]["actStageIndication"] = character_name
            else:
                current_scene = scenes[-1]
                if not (current_scene["repliques"]) or current_scene["repliques"][-1]["type"] != "Speaker":
                    current_scene["repliques"].append({"type": "Speaker", "content": character_name})
                    added_character = True
                else:
                    # When reading multiple succesives lists of characters, we have to decide why this happens
                    if len(current_scene["repliques"]) == 1 and current_scene["speakers_text"] is None:
                        # If there was already just one speaker in the scene, then it was the list of speakers.
                        # We update it accordingly
                        current_scene["speakers_text"] = current_scene["repliques"][-1]["content"]
                        current_scene["repliques"].pop()
                        current_scene["repliques"].append({"type": "Speaker", "content": character_name})
                        added_character = True
                    elif '<em>' in character_name:
                        # If there's an <em>, it's probably a stage indication
                        current_scene["repliques"].append(
                            {"type": "Stage", "content": remove_html_tags(character_name)})
                    else:
                        # If all else fails, we still write it down
                        print(
                            f'Warning : Two consecutive char names ? {character_name} and {current_scene["repliques"][-1]["content"]}')
                        current_scene["repliques"].append({"type": "Dialogue", "content": character_name})
                        added_character = True
    return counters, playContent, added_character


def speaker_currently_detected(playContent, alreadyDetected):
    """Checks if the last thing detected in the text currently is a speaker
        Returns the list where to append the next replique"""
    if not playContent:
        return False, None
    else:
        curr_elem = playContent[-1]
        if "actName" in curr_elem and curr_elem["Scenes"]:  # There's an act with a scene
            curr_scene = curr_elem["Scenes"][-1]
        elif "sceneName" in curr_elem:  # There's no act
            curr_scene = curr_elem
        else:
            return False, None
        if curr_scene["repliques"]:
            if alreadyDetected or (curr_scene["repliques"][-1]["type"] == "Speaker"):
                return True, curr_scene["repliques"]
            else:
                return False, None
        else:
            return False, None


def find_text(line, counters, playContent, scene):
    res = re.search("<p[^>]*>(.*)</p>", line)
    if res:
        playLine = res.group(1).replace("\xa0", " ")
        if playLine != " ":
            res = re.search("<em>(.*)</em>", playLine)
            # playLine = remove_html_tags(playLine)
            new_line = {"content": playLine}
            if res:  # This is stage direction
                new_line["type"] = "Stage"
            else:  # this is dialogue
                new_line["type"] = "Dialogue"
            scene.append(new_line)


def correct_character_id(characterId, counters, characters_in_scene, max_distance=3):
    """Given a character identifier, tries to find the correct character id, by comparing it with know legal ids,
    using edit distance and the list of characters present in the scene."""
    # even when normalizing character names, we often find ids that are not declared
    # this part aims at correcting that by checking if the name is part of a known id,
    # or if a known id is part of it
    # If everything fails, (which happens often), we use edit distance to find the closest one
    old_characterId = characterId
    # if len(characterId) >= 15:
    #     print(characterId)
    if characterId not in counters['characterIDList']:
        if characterId not in counters["undeclaredCharacterIDs"]:
            # print(f"Warning : unknown character id {characterId}")
            edit_distances = dict()
            for true_id in counters["characterIDList"]:
                if re.search(true_id, characterId) or re.search(characterId, true_id):
                    counters["undeclaredCharacterIDs"][characterId] = true_id
                    characterId = true_id
                    print(f"Guessed {true_id} for {old_characterId}")
                    break
                else:
                    distance = editdistance.eval(characterId, true_id)
                    edit_distances[true_id] = distance
            # characterID has not been guessed with subchains
            if old_characterId not in counters["undeclaredCharacterIDs"]:
                closest_id, closest_distance = min_dict(edit_distances)
                if (closest_id in characters_in_scene and closest_distance <= 5) or closest_distance <= max_distance:
                    print(f"{old_characterId} : Guessed {closest_id}, distance {closest_distance} ")
                    counters["undeclaredCharacterIDs"][characterId] = closest_id
                else:
                    # print(f"Could not guess {characterId} (best guess {closest_id})")
                    counters["undeclaredCharacterIDs"][characterId] = characterId
                    counters["unguessed_id"] = True
        else:
            characterId = counters["undeclaredCharacterIDs"][characterId]
    return characterId


def identify_character_ids(scene, counters):
    """Take a scene and tries to guess the correct ID for speakers appearing in the scene.
    Also corrects the text of speakers"""
    # First establish id of characters in scene
    speakers_text = []
    if scene["speakers_text"]:
        speakers = scene["speakers_text"]
        speakers = re.sub('puis|et', ',', speakers)  # Trying to get rid of delimiters
        speakers = remove_html_tags_and_content(speakers)  # Getting rid of stage indications
        speakers_text = speakers.split(',')
    scene["speaker_ids"] = set()
    for speaker in speakers_text:
        character = remove_html_tags_and_content(speaker)
        character_id = normalize_character_name(character)
        corrected_id = correct_character_id(character_id, counters, [], 3)
        if corrected_id in counters['characterIDList']:
            scene["speaker_ids"].add(corrected_id)
    for replique in scene["repliques"]:
        if replique["type"] == "Speaker":
            character = replique["content"]

            # character is the actual character name, from which we strip html tags.
            # clean_character will be used to get the corresponding id
            # Checking if the character name is preceded by a comma, indicating an action on stage.
            # Dracor convention seems to be to include it as a content of the speaker tag and not in <stage>,
            # so we follow this rule
            has_stage_direction = re.search("([^,<]+)(?:,.*|<em>.*</em>.*)", character)
            if has_stage_direction:
                character = has_stage_direction.group(1)
            character = remove_html_tags_and_content(character)
            clean_character = character
            # Removing ending dot if it exists
            characterId = normalize_character_name(clean_character)
            guessed_charactedId = correct_character_id(characterId, counters, scene["speaker_ids"])
            replique["characterId"] = guessed_charactedId


### Writing body of play
def write_character(outputFile):
    """Write the saved characters of a play in the associated XML file.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
    """
    outputFile.writelines("""
        <castList>
                    <head> ACTEURS </head>""")
    for i, character in enumerate(counters["characterIDList"]):
        outputFile.writelines(f"""
            <castItem>
                    <role corresp="#{character}">{counters["characterFullNameList"][i]} </role>{counters["roleList"][i]}</castItem>"""
                              )
    outputFile.writelines("""
        </castList>""")


# TODO: Add writing of "actStageIndication"
def write_act_beginning(act_number, act_header, file):
    file.writelines(f"""
           <div type="act" xml:id=\"{act_number}\">
           <head> {act_header} </head>""")


def write_act_end(file):
    file.writelines("""</div>""")


def write_scene_beginning(scene_number, scene_header, file):
    file.writelines(f"""
        <div type="scene" xml:id=\" {scene_number} \">
            <head> {scene_header} </head>""")


def write_scene(scene, replique_number, file):
    """Writes all dialogue, speakers, and stage direction to the output file. Also returns the current number of repliques"""
    scene_started = False
    for replique in scene["repliques"]:
        if replique["type"] == "Speaker":
            # Checking for first replique
            if scene_started:
                file.writelines("""
                </sp>""")
            else:
                scene_started = True
            character = remove_html_tags(replique["content"])
            characterId = replique["characterId"]
            file.writelines(f"""
        <sp who=\"#{characterId}\">
            <speaker> {character} </speaker>""")
            # Checking for last replique
            if scene["repliques"][-1] == replique:
                file.writelines("""
                </sp>""")
        # TODO : Add xml id ? xml:id=\"{counters["actNb"] + str(counters["scenesInAct"]) + "-" + str(counters["repliquesinScene"])}
        if replique["type"] == "Dialogue":
            replique_number += 1
            outputFile.writelines(f"""
                        <l n=\"{replique_number}\"> {remove_html_tags(replique["content"])}</l>""")
        # TODO : add xml id ? xml:id=\"l""" + str(counters["linesInPlay"])
        if replique["type"] == "Stage":
            direction = replique["content"]
            outputFile.writelines(f"""
            <stage>{direction}</stage>""")
    return replique_number


def write_scene_end(outputFile):
    outputFile.writelines("""</div>""")


def write_play(outputFile, playContent, counters):
    act_number = 0
    replique_number = 0
    if counters["noActPlay"]:
        for scene in playContent:
            scene_number = scene["sceneNumber"]
            scene_header = scene["sceneName"]
            write_scene_beginning(scene_number, scene_header, outputFile)
            replique_number = write_scene(scene, replique_number, outputFile)
            write_scene_end(outputFile)
    else:
        for act in playContent:
            act_number += 1
            # Collecting things to write
            if not act["actNumber"]:
                act_number_string = str(act_number)
            else:
                act_number_string = act["actNumber"]
            if not act["actName"]:
                act_name = f"ACTE {act_number_string}"
            else:
                act_name = remove_html_tags_and_content(act["actName"])
            write_act_beginning(act_number_string, act_name, outputFile)
            for scene in act["Scenes"]:
                scene_number = scene["sceneNumber"]
                scene_header = scene["sceneName"]
                write_scene_beginning(scene_number, scene_header, outputFile)
                replique_number = write_scene(scene, replique_number, outputFile)
                write_scene_end(outputFile)
            write_act_end(outputFile)


def write_end(outputFile):
    """Write the end of the XML output file.

    Args:
        outputFile (TextIOWrapper): Output file to generate in XML.
    """
    outputFile.writelines("""
         <p>FIN</p>
      </div>
      </div>
   </body>
</text>
</TEI>""")


def get_and_write_metadata(counters, outputFile, findSummary, saveBegin):
    # get and write title
    title, forename, surname = get_title_and_author(line)
    if write_title(outputFile, title):
        # get and write type of play:
        copy_playtext = open(file, "r", encoding="utf-8")
        genre, vers_prose, act_number = get_genre_versification_acts_number(copy_playtext)
        if act_number == 1:
            counters["oneActPlay"] = True
            counters["actsInPlay"] = 1
        if act_number != -1:
            counters["actsDeclaredNumber"] = act_number
        write_type(outputFile, genre)
        # get and write author
        author = forename, surname
        if write_author(outputFile, author):
            # get and write source
            write_source(outputFile, source)

        # get and write date
        copy_playtext.close()
        copy_playtext = open(file, "r", encoding="utf-8")
        date_written, date_print, date_premiere, line_written, line_print, line_premiere = get_dates(
            copy_playtext)

        write_dates(outputFile, date_written, date_print, date_premiere, line_premiere)
        write_end_header(outputFile, genre, vers_prose)
        write_start_text(outputFile, title, genre, date_print)
        write_performance(outputFile, line_premiere, date_premiere)
        copy_playtext.close()

    # TODO : delete this part when dedicace detection works properly
    # try find dedicace in play
    # if not findSummary:
    #     findSummary = find_summary(line, ul)
    # else:
    #     findSummary = extract_from_summary(line, ul)
    # # starting saving lines
    # if not saveBegin:
    #     saveBegin = try_saving_lines(outputFile, line)
    # else:
    #     # find and print dedicace
    #     if counters['dedicace']:
    #         if find_dedicace(line):
    #             copy_playtext.close()
    #             copy_playtext = open(file, "r", encoding="utf-8")
    #             write_dedicace(outputFile, copy_playtext, author)
    return counters, findSummary, saveBegin


def find_dedicace_or_preface_start(line, counters, inBlock, headerType):
    if inBlock:
        return True
    dedicace_header = re.search(".*<h1[^>]*>(.*)</h1>", line)
    if dedicace_header:
        header_text = clean_scene_name(dedicace_header.group(1))
        if header_text == counters[headerType]:
            inBlock = True
    return inBlock


def find_dedicace_or_preface_content(line, counters, type):
    res = re.search("<p[^>]*>(.*)</p>", line)
    if res:
        contentLine = res.group(1).replace("\xa0", " ")
        if contentLine != " ":
            counters[type].append(contentLine)
    regex_act = ".*<h1[^>]*>(.*)</h1>"
    regex_scene = "|".join(
        [".*<h2 .*<strong>(?P<h2strong>.*)</strong>.*</h2>", ".*<h2.*>(?P<h2normal>Scène.*)</h2>",
         "<h1.*>(?P<h1>.*Scène.*)</h1>"])
    newActOrScene = re.search(f"{regex_scene}|{regex_act}", line)
    return not newActOrScene


if __name__ == "__main__":

    # stats temporary
    castnotWritten = 0
    noact = 0
    undeclared_character = 0
    unguessed_character = 0
    totalplays = 0
    sceneList_ok = 0
    possible_secnes_and_acts_strings = set()
    number_of_acts_correctly_declared = 0
    stats = open('stats_characters.txt', 'w+')

    # Declaration of flags and counters.
    documentNb = 0
    findSummary = False
    saveBegin = False
    characterBlock = False
    ul = 0
    characterBlockLastLine = None

    # prepare the list of file sources
    fileSources = {}
    allPlays = extract_sources(open("PlaysFromTheatreDocumentation.csv", "r", encoding="utf-8"), fileSources)
    # Generate an XML-TEI file for every HTML file of the corpus
    for file in list(map(lambda f: join(html_folder, f), next(walk(html_folder), (None, None, []))[2])):
        notify_file(file)

        # Find source
        fileName = basename(file)
        source = get_source(fileSources, fileName)

        playText = open(file, "r", encoding="utf-8")
        outputFile = open(join(Dracor_Folder, fileName.replace("html", "xml")), "w", encoding="utf-8")

        # reset parameters

        counters = {
            "charactersinScene": "",
            "repliquesinScene": 0,
            "linesInPlay": 0,
            "linesInScene": 0,
            "scenesInAct": 0,
            "actsInPlay": 0,
            "noActPlay": False,
            "oneActPlay": False,
            "scenelessPlay": False,
            "scenelessPlayBeginningWritten": False,
            "characterLines": [],
            "characterIDList": [],
            "characterFullNameList": [],
            "roleList": [],
            "actNb": "",
            "sceneNb": "",
            "dedicace": [],
            "dedicaceFound": False,
            "dedicaceHeader": False,
            "dedicaceFinished": False,
            "preface": [],
            "prefaceFound": False,
            "prefaceHeader": False,
            "prefaceFinished": False,
            "undeclaredCharacterIDs": dict(),
            "sceneList": [],
            "actsDeclaredNumber": -1,  # temp
            "unguessed_id": False  # temporary, delete later
        }
        # Reading the file a first time to find the characters
        inSceneList = False
        sceneList = []
        for index, line in enumerate(standard_line(playText)):
            # starting character block
            characterBlock = start_character_block(line, characterBlock)

            # Ending character block
            # We remember the ending line of the character block for the future
            # We do so by checking if the list of characters grows
            old_nb_char = len(counters["characterFullNameList"])
            characterBlock, line = end_character_block(characterBlock, line)
            new_nb_char = len(counters["characterFullNameList"])
            if old_nb_char != 0 and new_nb_char == old_nb_char and characterBlockLastLine is None:
                characterBlockLastLine = index

            # Getting scene list
            if not counters["sceneList"]:
                sceneList, inSceneList = find_scene_list(line, sceneList, inSceneList)
                # We detect that we have finished reading the scene List when some scenes have already been collected
                # and the flag inSceneList goes to false
                if sceneList and not inSceneList:
                    counters["sceneList"] = sceneList
                    if len(sceneList) == 1:
                        if sceneList[0][0] == 'Acte unique':
                            counters["oneActPlay"] = True
        playText.close()

        # Reading the file a second time to get metadata, text, and write output
        playText = open(file, "r", encoding="utf-8")
        playContent = []
        characterBlockFinished = False
        speaker_already_detected = False
        inDedicace, inPreface = False, False
        for index, line in enumerate(playText):
            if index == characterBlockLastLine:
                characterBlockFinished = True
            # Getting all metadata :
            counters, findSummary, saveBegin = get_and_write_metadata(counters, outputFile, findSummary, saveBegin)

            # Some text can be before the beginning of the play : a dedicace, or a preface.
            # Dedicace
            if counters["dedicaceFound"] and not counters["dedicaceFinished"]:
                if inDedicace:
                    inDedicace = find_dedicace_or_preface_content(line, counters, "dedicace")
                    if not inDedicace:  # If we have finished reading the dedicace
                        counters["dedicaceFinished"] = True
                inDedicace = find_dedicace_or_preface_start(line, counters, inDedicace, "dedicaceHeader")

            # Preface
            if counters["prefaceFound"] and not counters["prefaceFinished"]:
                if inPreface:
                    inPreface = find_dedicace_or_preface_content(line, counters, "preface")
                    if not inPreface:  # If we have finished reading the preface
                        counters["prefaceFinished"] = True
                inPreface = find_dedicace_or_preface_start(line, counters, inPreface, "prefaceHeader")

            # Now we read the whole text to find the body of the play. We are constructing a list called playContent
            # containing the whole play. It is structured as follows: playContent is either a list of acts or a list
            # of scenes.
            # An act is a dictionnary with the following keys :
            # "actNumber", "actName", "actStageIndications" (stage indications that may be placed outside of scenes), and "Scenes"
            # Scenes is a list of scenes. A scene is a dict structured with the following keys :
            # "sceneName", "sceneNumber", "speakers_text" (the string with the declaration of characters),
            # "speakers_ids" (the id of said speakers), "repliques"
            # "repliques" is a list of repliques. A replique is a dict with the following keys :
            # "type", which can either be "Dialogue","Speaker", or "Stage"
            # "content", which contains the actual content of the replique
            # If the type is Speaker, there is an additional key "characterId", containing the Id of the character speaking
            if (not counters["dedicaceFound"] or counters["dedicaceFinished"]) and (
                    not counters["prefaceFound"] or counters["prefaceFinished"]):
                line, counters, playContent = find_begin_act(line, counters, playContent)
                line, counters, playContent = find_begin_scene(line, counters, playContent)

                # Also Handling case of plays with no scenes:
                # No list of scene is present at the beginning, but a list of character has been done
                if not counters["sceneList"] and counters["characterIDList"]:
                    character_names_string = '|'.join(counters["characterFullNameList"])
                    if re.match(f"<p align=.*center[^>]*>(<span style=.*>)?.*</p>", line):
                        counters["scenelessPlay"] = True
                # We start reading the text once at least an act or a scene has been found
                # Or if it has been established that there is no scenes in the play
                # And we are done reading the cast of characters (or, there are none)
                if (playContent or counters["scenelessPlay"]) and (
                        characterBlockFinished or not counters["characterFullNameList"]):
                    # Getting character declaration
                    # speaker_detected
                    counters, playContent, added_character = find_character(line, counters, playContent)
                    # Getting text
                    speaker_already_detected, current_scene = speaker_currently_detected(playContent,
                                                                                         speaker_already_detected)
                    if speaker_already_detected and not added_character:
                        find_text(line, counters, playContent, current_scene)

        # Since characters names often have typos or are not exactly as described, we now correct those names
        # We also establish the list of characters speaking per scene
        print("correcting characters")
        if counters["noActPlay"]:
            for scene in playContent:
                identify_character_ids(scene, counters)
        else:
            for act in playContent:
                for scene in act["Scenes"]:
                    identify_character_ids(scene, counters)
        print("finished correcting characters")

        # Writing dedicace
        if counters["dedicaceFound"]:
            if not counters["dedicaceFinished"]:
                raise ValueError("Dedicace detected at the beginning but not collected")
            else:
                write_dedicace(counters["dedicace"], counters["dedicaceHeader"], outputFile)
        # Writing preface
        # TODO : do the same for preface writing

        # Writing play
        write_play(outputFile, playContent, counters)
        write_end(outputFile)

        # Stats collection, temporary
        if counters["sceneList"]:
            sceneList_ok += 1
            for x in counters["sceneList"]:
                possible_secnes_and_acts_strings.add(x[0])
                for y in x[1]:
                    possible_secnes_and_acts_strings.add(y)
        if len(counters["characterIDList"]) == 0:
            castnotWritten += 1
        if counters["actsInPlay"] == 0:
            noact += 1
            # if counters["sceneList"]:
            #     print(f'Play with no act but scene list : {file}'
            #           f'{counters["sceneList"]}')
            # else:
            #     print(f'Play with no act but no scene list : {file}')
        if len(counters["undeclaredCharacterIDs"]) > 0:
            undeclared_character += 1
        if counters["unguessed_id"]:
            unguessed_character += 1
        if counters["actsInPlay"] == counters["actsDeclaredNumber"]:
            number_of_acts_correctly_declared += 1
        totalplays += 1

    # date_file.close()

    #  print("Number of plays without date :", count_date)
    stats.writelines(f"""Total number of plays : {totalplays}
    Plays with no acts found : {noact}
    Plays with no cast of character found : {castnotWritten}
    Plays with unknow character ids found : {undeclared_character}
    Among those, plays where at least one character could not be guessed : {unguessed_character}
    Act number declared corresponding to act number found : {number_of_acts_correctly_declared}
    Scene List found : {sceneList_ok}""")
    print(f"Casts not written: {castnotWritten} sur {totalplays}")

# Plan :
# Une fois que toutes les métadonnées sont collectées :
# Parcourir la pièce, et garder les actes, scènes, et dialogues en mémoire
# Une fois qu'on arrive au bout du fichier : tout écrire

# Comment garder le texte en mémoire ?
# Il faut garder l'ordre : liste
# [ ('Acte Name', [('Scene Name',[(speakername, speaker id),[réplique 1, réplique 2,...]),(),...],(),()]),()...]
# Pour écrire : juste parcourir la liste et écrire au fur et à mesure
# Pour la liste des speakers dans la scène :
# On peut comparer la liste des speakers déclarés avec la liste des speakers collectés et deviner parmis ceux là
# Il faut deviner les speakers id ultérieurement ?
# Quand on trouve un speaker : si l'id est connu on le garde, si il est inconnu on le met en None
# Phase de correction : pour chaque None, on regarde l'id obtenu en normalisant juste, et on le compare par rapport à la liste des ids correspondants aux persos de la scène

# REMINDER : Stuff to write between acts :
# if counters["actsInPlay"] == 0:
#     outputFile.writelines("""
# </front>
# <body>""")
# end the previous scene of the previous act
# outputFile.writelines("""
# </sp>
# </div>""")

# Don't forget to handle plays with no acts or no scenes
# if not counters["castWritten"]:
#     write_character(outputFile)
#     counters["castWritten"] = True
# outputFile.close()

# Reminder : Stuff to write scenes
# if counters["scenesInAct"] == 1:
#     if counters["oneActPlay"]:
#         counters["actsInPlay"] = 1
#         # TODO : Vérifier que cette écriture est correcte pour le début de l'acte
#         write_act("1", "ACTE 1", outputFile)
#     write_scene(counters["actNb"] + str(counters["scenesInAct"]), scene + counters["charactersinScene"],
#                 outputFile)
#     if counters["scenelessPlay"] and not (counters["scenelessPlayBeginningWritten"]):
#         counters["scenelessPlayBeginningWritten"] = True
# else:
#     outputFile.writelines("""
#    </sp>
# </div>""")
#     write_scene(str(counters["actNb"]) + str(counters["scenesInAct"]), scene, outputFile)

# METADATA ADRIEN (now in function, delete if it works)
# # get and write title
# title, forename, surname = get_title_and_author(line)
# if write_title(outputFile, title):
#     # get and write type of play:
#     copy_playtext = open(file, "r", encoding="utf-8")
#     genre, vers_prose, act_number = get_genre_versification_acts_number(copy_playtext)
#     if act_number == 1:
#         counters["oneActPlay"] = True
#         counters["actsInPlay"] = 1
#     if act_number != -1:
#         counters["actsDeclaredNumber"] = act_number
#     write_type(outputFile, genre)
#     # get and write author
#     author = forename, surname
#     if write_author(outputFile, author):
#         # get and write source
#         write_source(outputFile, source)
#
#     # get and write date
#     copy_playtext.close()
#     copy_playtext = open(file, "r", encoding="utf-8")
#     date_written, date_print, date_premiere, line_written, line_print, line_premiere = get_dates(
#         copy_playtext)
#
#     write_dates(outputFile, date_written, date_print, date_premiere, line_premiere)
#
#     write_end_header(outputFile, genre, vers_prose)
#     write_start_text(outputFile, title, genre, date_print)
#
#     write_performance(outputFile, line_premiere, date_premiere)
#
# # try find dedicace in play
# if not findSummary:
#     findSummary = find_summary(line, ul)
# else:
#     findSummary = extract_from_summary(line, ul)
#
# # starting saving lines
# if not saveBegin:
#     saveBegin = try_saving_lines(outputFile, line)
# else:
#     # find and print dedicace
#     if counters['dedicace']:
#         if find_dedicace(line):
#             copy_playtext.close()
#             copy_playtext = open(file, "r", encoding="utf-8")
#             write_dedicace(outputFile, copy_playtext, author)

# def write_text(outputFile, line, counters):
#     """Write the text from a HTML file's line in the XML associated file.
#
#     Args:
#         outputFile (TextIOWrapper): Output file to generate in XML.
#         line (str): line to read in the play.
#         counters (dict): Dictionnary with all the counters of the script.
#
#     Returns:
#         dict: The refreshed counter
#     """
#     res = re.search("<p>(.*)</p>", line)
#     if res and not characterBlock:
#         playLine = res.group(1).replace("\xa0", " ")
#         if playLine != " ":
#             # log('sceneless',counters["scenelessPlay"])
#             # log("pbg",counters["scenelessPlayBeginningWritten"])
#             if counters["scenelessPlay"] and not counters["scenelessPlayBeginningWritten"]:
#                 print('scenelessstart')
#                 find_begin_scene(outputFile, line, counters)
#             if len(counters["characterLines"]) > 1:
#                 character = counters["characterLines"].pop(0)
#                 outputFile.writelines("""
#         <stage>""" + character + """</stage>""")
#             if len(counters["characterLines"]) > 0:
#                 if counters["repliquesinScene"] > 0:
#                     outputFile.writelines("""
#       </sp>""")
#                 character = counters["characterLines"].pop(0)
#                 counters["repliquesinScene"] += 1
#
#                 # character is the actual character name, from which we strip html tags.
#                 # clean_character will be used to get the corresponding id
#                 character = remove_html_tags_and_content(character)
#                 clean_character = character
#                 # Checking if the character name is preceded by a comma, indicating an action on stage.
#                 # Dracor convention seems to be to include it as a content of the speaker tag and not in <stage>,
#                 # so we follow this rule
#                 has_stage_direction = re.search("([^,]+),.*", clean_character)
#                 if has_stage_direction:
#                     clean_character = has_stage_direction.group(1)
#                 # Removing ending dot if it exists
#                 if clean_character[-1] == ".":
#                     clean_character = clean_character[:-1]
#                 characterId = normalize_character_name(clean_character)
#
#                 # even when normalizing character names, we often find ids that are not declared
#                 # this part aims at correcting that by checking if the name is part of a known id,
#                 # or if a known id is part of it
#                 # If everything fails, (which happens often), we use edit distance to find the closest one
#                 old_characterId = characterId
#                 if characterId not in counters['characterIDList']:
#                     if characterId not in counters["undeclaredCharacterIDs"]:
#                         # print(f"Warning : unknown character id {characterId}")
#                         edit_distances = dict()
#                         for true_id in counters["characterIDList"]:
#                             if re.search(true_id, characterId) or re.search(characterId, true_id):
#                                 counters["undeclaredCharacterIDs"][characterId] = true_id
#                                 characterId = true_id
#                                 print(f"Guessed {true_id} for {old_characterId}")
#                                 break
#                             else:
#                                 distance = editdistance.eval(characterId, true_id)
#                                 edit_distances[true_id] = distance
#                         # characterID has not been guessed with subchains
#                         if old_characterId not in counters["undeclaredCharacterIDs"]:
#                             closest_id, closest_distance = min_dict(edit_distances)
#                             if closest_distance <= 5:
#                                 print(f"{old_characterId} : Guessed {closest_id}, distance {closest_distance} ")
#                                 counters["undeclaredCharacterIDs"][characterId] = closest_id
#                             else:
#                                 # print(f"Could not guess {characterId} (best guess {closest_id})")
#                                 counters["undeclaredCharacterIDs"][characterId] = characterId
#                                 counters["unguessed_id"] = True
#                     else:
#                         characterId = counters["undeclaredCharacterIDs"][characterId]
#
#                 # if characterId == "":
#                 #     print(line)
#                 #     print("entering characterId if")
#                 #     # print("Character not found: " + character)
#                 #     res = re.search("([^,.<]+)([.,<].*)", character)
#                 #     if res:
#                 #         characterId = res.group(1).lower()
#                 #         # remove spaces in last position
#                 #         res = re.search("^(.*[^ ])[ ]+$", characterId)
#                 #         if res:
#                 #             characterId = res.group(1)
#                 #         characterId = characterId.replace(" ", "-")
#                 #         # print("Chose characterId " + characterId)
#                 outputFile.writelines(f"""
#             <sp who=\"#{characterId}\" xml:id=\"{counters["actNb"] + str(counters["scenesInAct"]) + "-" + str(
#                     counters["repliquesinScene"])}\">
#                 <speaker> {character} </speaker>""")
#
#             # Checking whether this line is dialogue or stage directions
#             res = re.search("<em>(.*)</em>", playLine)
#             if res:
#                 outputFile.writelines(f"""
#             <stage>{remove_html_tags_and_content(playLine)} </stage>""")
#             else:
#                 outputFile.writelines("""
#             <l n=\"""" + str(counters["linesInPlay"]) + """\" xml:id=\"l""" + str(
#                     counters["linesInPlay"]) + """\">""" + remove_html_tags_and_content(playLine) + """</l>""")
#                 counters["linesInPlay"] += 1
#                 counters["linesInScene"] += 1
#
#     return counters
