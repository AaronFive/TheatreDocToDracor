import os, sys, requests, json, xmltodict
from os.path import abspath, dirname, join

folder = abspath(dirname(sys.argv[0]))
dracor_folder = abspath(join(join(folder, os.pardir), "corpusDracor"))
dracor_link = "https://dracor.org/api/corpora/fre"
plays_link = '/'.join([dracor_link, 'play'])

def load_datas(link):
    """load datas from the chosen link.

    Args:
        link (string): chosen

    Returns:
        dict: Dictionnary with database from the URL.
    """
    return json.loads(requests.get(link, 'metrics').content)

def get_header(xml):
    """Extract the header from a XML. file.

    Args:
        xml (string): The XML file.

    Returns:
        string: The header of the XML file.
    """
    return ''.join([xml.partition('<text>')[0], '</TEI>'])

def get_actual_meta_datas(path):
    """Get all the meta-datas of the header of each plays in the folder of Dracor corpus'.

    Args:
        path (string): The folder that contains all the files we want.

    Returns:
        list: A list of dictionnaries form of all the XML files.
    """
    from os import walk
    contents = []
    files = list(map(lambda f: join(path, f), next(walk(path), (None, None, []))[2]))
    for file in files:
        with open(file) as f:
            contents.append(xmltodict.parse(get_header(f.read())))
    return contents


def get_title(content):
    """Get the title from a play

    Args:
        content (dict): All the contents of a play.

    Returns:
        string: The title of the play.
    """
    s = content.get('TEI').get('teiHeader').get('fileDesc').get('titleStmt').get('title')
    if type(s) is list:
        return list(s[0].values())[1]
    else:
        return list(s.values())[1]

def contains_pen(d):
    """Check if the name of an author have a nickname ('pen')

    Args:
        d (dict): All the elements of the name of the author.

    Returns:
        bool: True if 'pen' is in the values of the dictionnary, False then.
    """
    return 'pen' in d.values()

def l_contains_pen(l):
    """Check if the name of an author have a nickname ('pen'), when he has many persNames tags.

    Args:
        l (list): All the elements of the name of the author, with many persNames tags.

    Returns:
        bool: True if 'pen' is in the values of one of the dictionnaries, False then.
    """
    return any(contains_pen(d) for d in filter(lambda d: isinstance(d, dict), l))

def l_find_pen(l):
    """Find the nickname of an author who has one

    Args:
        l (list): All the elements of the name of the author.

    Returns:
        int: The index of the nickname in the list.
    """
    for i in range(len(l)):
        if isinstance(l[i], dict) and 'pen' in l[i].values():
            return i
    return len(l)

def get_sort(persName):
    """Find the name used with the attribute '@sort'=1 and give it a priority.

    Args:
        persName (any): All the personal names of the authors.

    Returns:
        any: The name linked with the attribute, None if it's not exists.
    """
    if isinstance(persName, dict):
        surnames = persName.get('surname')
        if type(surnames) is list:
            for surname in surnames:
                if(isinstance(surname, dict)) and surname.get('@sort') == '1':
                    return surname.get('#text')
    return None

def get_preserve(persNames):
    """Find the name used with the attribute '@xml:space'='preserve' and give it a priority.

    Args:
        persName (any): All the personal names of the authors.

    Returns:
        any: The name linked with the attribute, None if it's not exists.
    """
    if type(persNames) is list and len(persNames) == 2:
        persName, d = persNames
        if(isinstance(d, dict)) and d.get('@xml:space') == 'preserve' and type(persName) is str:
            return persName
    elif(isinstance(persNames, dict)) and persNames.get('@xml:space') == 'preserve':
        surname = persNames.get('surname')
        if type(surname) is str:
            return surname
        return get_sort(surname)
    return None

def get_pseudonym(persNames):
    """Find the name used with the attribute '@type'='pseudonym' and give it a priority.

    Args:
        persName (any): All the personal names of the authors.

    Returns:
        any: The name linked with the attribute, None if it's not exists.
    """
    if type(persNames) is list:
        for persName in persNames:
            if(isinstance(persName, dict)) and persName.get('@type') == 'pseudonym':
                pseudo = persName.get('#text')
                if pseudo is None:
                    return persName.get('surname')
                return pseudo
    elif(isinstance(persNames, dict)) and persNames.get('@type') == 'pseudonym':
        return persNames.get('surname')
    return None

def concat_authors_in_list(persNames):
    """Recursive function working with concat_author_in_dico. Join the names in the list of some persNames (dict).

    Args:
        persName (list): Some personal names of the authors in a list.

    Returns:
        string: The name (or a part of it) of the author.
    """
    if (l_contains_pen(persNames)):
        pen_dico = l_find_pen(persNames)
        name = persNames[pen_dico].get('#text')
        if name is not None:
            return name
        else:
            return persNames[pen_dico].get('surname')
    return ' '.join(list(map(
        lambda d: 
            concat_authors_in_list(d) if type(d) is list 
            else concat_author_in_dico(d), 
            persNames)))

def concat_author_in_dico(persNames):
    """Recursive function working with concat_author_in_list. Join the names in the dict of some persNames.

    Args:
        persName (list): Some personal names of the authors in a list.

    Returns:
        string: The name (or a part of it) of the author.
    """
    if persNames is None or type(persNames) is str:
        return persNames
    pseudo = get_pseudonym(persNames)
    if pseudo is not None:
        return pseudo    
    preserve = get_preserve(persNames)
    if preserve is not None:
        return preserve
    if type(persNames) is list:
        return concat_authors_in_list(persNames)
    sort = get_sort(persNames)
    if not sort is None:
        return sort
    return concat_authors_in_list(list(filter(lambda value: value != 'nobility', persNames.values())))


def get_authors(content):
    """Extract the name of the author of a play.

    Args:
        content (OrderedDict): Content of all the datas from a play.

    Returns:
        any: A string of the name of the author, or a list if they are many.
    """
    authors = content.get('TEI').get('teiHeader').get('fileDesc').get('titleStmt').get('author')
    if type(authors) is str:
        return authors
    if type(authors) is list:
        res = list(filter(lambda author: author is not None, map(concat_author_in_dico, map(
            lambda d:
                d if d is None or type(d) is str
                else d.get('persName') if d.get('persName') is not None
                else d.get('#text'),
            authors))))   
        if len(res) == 1:
            res = res[0]
        return res        
    persName = authors.get('persName')
    if persName is None:
        return authors.get('#text')
    return concat_author_in_dico(persName)

def choose_year(writtenYear, printYear, premiereYear):
    """Follow the DraCor Algorithm to choose a normalized year to date a play.
    click on https://dracor.org/doc/faq/#normalized-year to look how works the algorithm.

    Args:
        writtenYear (str): The year when the play was written
        printYear (str): The year when the play was printed
        premiereYear (str): The year of the first performance of the play.

    Returns:
        str: The normalized year.
    """
    res = None
    if printYear is None:
        res = int(premiereYear)
    elif premiereYear is None:
        res = int(printYear)
    else:
        res = min(int(premiereYear), int(printYear))
    if writtenYear is not None and res - int(writtenYear) > 10:
        return writtenYear
    return str(res)


def get_year(content):
    """Extract the normalized year from a play.

    Args:
        content (OrderedDict): The contents from the play.

    Returns:
        str: The normalized year from the play.
    """
    dates = content.get('TEI').get('teiHeader').get('fileDesc').get('sourceDesc').get('bibl').get('bibl').get('date')
    all_dates = {'written': None, 'print': None, 'premiere': None}
    if type(dates) is list:
        for date in dates:
            typ = date.get('@type')
            if typ in all_dates.keys():
                year = date.get('@when')
                if year is None:
                    year = date.get('@notAfter')
            all_dates[typ] = year.split('-')[0]
        return choose_year(all_dates['written'], all_dates['print'], all_dates['premiere'])
    res = dates.get('@when')
    if res is None:
        res = dates.get('@notAfter')
    return res

def replace_de(name):
    """fix the problem of xmltodict problem and replace the linkname 'de' at the good place
    Exemple : Savinien de Cyrano de Bergerac was returned as Savinien de de Cyrano Bergerac (because the two 'de' were at the same list in the contents of the play.)

    Args:
        name (str): The name of the author.

    Returns:
        str: The name fixed if we had the 'de' problem.
    """
    if ' de' in name:
        l = name.split(' ')
        if l[-1] == 'de':
            l[-1], l[-2] = l[-2], l[-1]
        for i in range(len(l) - 1):
            if l[i] == 'de' and l[i + 1] == 'de':
                l[i + 1], l[i + 2] = l[i + 2], l[i + 1]
                i += 2
        name = ' '.join(l)
    return name

def extract_important_datas(contents):
    """Extract all the important datas from the header of all plays. The titles, the authors and the years.

    particular case because this one have two names, very difficult to generalize this case. Bernard Le Bouyer de Fontenelle or Bernard Le Bouvier de Fontenelle.


    Args:
        contents (OrderedDict): The contents of all plays we already have in the folder.

    Returns:
        list: The list of all the importants datas from each play.
    """
    res = [{
        'title': get_title(content),
        'authors': get_authors(content), 
        'yearNormalized': get_year(content)} 
        for content in contents]  
    for data in res:
        if type(data['authors']) is str and 'Fontenelle' in data['authors']:
            data['authors'] = 'Fontenelle'
        data['authors'] = replace_de(data['authors'])
    return res

def extract_datas_plays(plays):
    """Extract all the important datas from the plays found in the Dracor website. Thr title, the author(s) and the year.

    Args:
        plays (OrderedDict): The dictionnary with all the datas of the plays from Dracor.

    Returns:
        list: The list of all the importants datas from each play.
    """
    return [{
        'title': play.get('title'),
        'authors': play.get('authors'), 
        'yearNormalized': play.get('yearNormalized')} 
        for play in plays]

def extend_nickname(names):
    """private function to put in a list the nickname of an author at the same level as the fullname and the  shortname.

    Args:
        names (list): Some different names of an author : [fullname, shortname, [pseudonyms]]. The pseudonym can be None.

    Returns:
        list: The same list with this new syntax : [fullname, shortname, pseudonym1, pseudonym2] etc. If The author has not pseudonym, then it's [fullname, shortname].
    """
    if names[2] is not None:
        tmp = names[:2]
        tmp.extend(names[2])
        names = tmp
    else:
        names.pop(2)
    return names

def equals_authors(old, new):
    """Check if two plays have the same authors.

    Args:
        old (any): The author(s) of a play from the local folder. str -> one author, list -> many authors.
        new (any): The author of a play from Dracor. str -> one author, list -> many authors.

    Returns:
        bool: The answer about the unicity of the authors from the two plays.
    """
    if type(old) is str and type(new[0]) is str:
        new_tmp = extend_nickname(new.copy())
        return old in new_tmp or new_tmp[0] in old
    if type(old) is list and type(new[0]) is list and len(old) == len(new):
        new_tmp = list(map(extend_nickname, new.copy()))
        return all(map(lambda name, names: name in names or any(
            names[0] in n or names[1] in n for n in old
            ), old, new_tmp))
    return False

def is_duplicate(old, new):
    """look if two plays are duplicates

    Args:
        old (dict): play from folder.
        new (dict): play from DraCor.

    Returns:
        bool: answer if a play is the duplicate of the other.
    """
    return old.get('title') == new.get('title') and old.get('yearNormalized') == new.get('yearNormalized') and equals_authors(old.get('authors'), new.get('authors'))

def have_duplicate(plays, new):
    """Check if a new play have duplicates in the local repository.

    Args:
        plays (list): The contents plays from the local repository.
        new (dict): The content of the new play.

    Returns:
        _type_: answer of the existence of duplicates of new in plays.
    """
    new['authors'] = list(filter(lambda t: None not in t[:2], map(lambda author: [author['fullname'], author['shortname'], author.get('alsoKnownAs')], new['authors'])))
    if len(new['authors']) == 1:
        new['authors'] = new['authors'][0]
    return any(is_duplicate(play, new) for play in plays)

def print_news(old, news):
    """Display all the new plays from Dracor not yet in the repository.

    Args:
        old (list): contents from the local repository
        news (list): contents from the DraCor Website.
    """
    for new in news:
        if not have_duplicate(old, new):
            print(new, "\n")

def detect_news(old, news):
    """Return a list of plays not yet in our DraCor's folder.

    Args:
        old (list): List of all the datas in the DraCor's folder.
        news (list):  List of all the datas in DraCor.

    Returns:
        _list_: List of the plays not yet in the Dracor's folder.
    """
    return list(filter(lambda new: not have_duplicate(old, new), news))
    
def display(datas):  # just to display the datas
    for data in datas:
        print(data, "\n")

def load_tei(plays):
    """Write the content from the selected plays in XML-TEI and put it in the DraCor's folder.
    Args:
        plays (_type_): Plays to generate in the folder.
    """
    for play in plays:
        link = '/'.join([plays_link, play['name'], 'tei'])
        r = requests.get(link, 'metrics')
        file = abspath((join(dracor_folder, play['name'] + '.xml')))
        with open(file, 'w') as f:
            f.write(r.text)
        f.close()

if __name__ == "__main__":
    data_dic = load_datas(dracor_link)
    plays = data_dic.get('dramas')
    datas = extract_important_datas(get_actual_meta_datas(dracor_folder))
    new_datas = extract_datas_plays(plays)

    load_tei(detect_news(datas, plays))
    print("Actuellement : {datas} pièces\nTrouvé en ligne : {new_datas} pièces".format(datas = str(len(datas)), new_datas = str(len(new_datas))))
    

