import re
import sys
from os import walk, pardir
from os.path import abspath, dirname, join, basename, exists

folder = abspath(dirname(sys.argv[0]))
root_folder = abspath(join(folder, pardir))
html_folder = abspath(join(root_folder, "cleanHTML_TD"))
output_folder = abspath(join(root_folder, "cleanHTML_TD_normalized"))


def make_p_one_lines(txt):
    return re.sub("(?P<firsthalf><p.*)(?<!</p>)\s?\n(?P<secondhalf>.*</p>)", "\g<firsthalf>\g<secondhalf>", txt)

def remove_spans(txt):
    txt = re.sub('(?:<span style=[^>]*\">){2}(.*)(?:</span>){2}', r'\1',txt)
    return re.sub('(?:<span style=[^>]*\">)(.*)(?:</span>)', r'\1',txt)

def remove_x01(txt):
    return re.sub('\x01','',txt)
def check_text(play):
    return '<span' in play

if __name__ == "__main__":
    for file in list(map(lambda f: join(html_folder, f), next(walk(html_folder), (None, None, []))[2])):
        fileName = basename(file)
        playText = open(file, "r", encoding="utf-8")
        outputFile = open(join(output_folder, fileName), "w", encoding="utf-8")
        full_text = playText.read()
        full_text = make_p_one_lines(full_text)
        full_text = remove_spans(full_text)
        full_text = remove_x01(full_text)
        outputFile.writelines(full_text)
        print(fileName)
