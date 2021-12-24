import re
import pandas as pd
from tqdm import tqdm

# Чтение данных
def text_to_lines(path = "vol_7.txt"):
    start = 'УКАЗАТЕЛЬ ИМЕН АВТОРОВ ПРОИЗВЕДЕНИЙ ХУДОЖЕСТВЕННОЙ ЛИТЕРАТУРЫ'
    flag = False
    lines = []
    i = 1
    with open(path) as f:
        cur_text = ''
        for line in f:
            #удаление лишних пробелов
            line = re.sub(r'\s+', ' ', line).rstrip()
            i += 1
            # проверки на то, что является строкой для парсинга
            if line.strip().startswith(start): 
                flag = True
                continue
            if line.strip().startswith("Часть I") or not flag or len(line.strip()) <= 1:
                continue
            if re.match(r'[А-Яа-яёЁ]',line):
                if cur_text:
                    lines.append((i, cur_text))
                cur_text = line.strip()
            else:
                cur_text += (" " + line.strip())
    return lines

#regexps
name='(?P<name>([’\'а-яА-ЯёЁa-zABCDEFGHJKLMNOPQRSTUWYZ.°\.,:;\s\-*\(\)\?!\[\]/»«]+))'
name2='(?P<name2>([’\'а-яА-ЯёЁa-zABCDEFGHJKLMNOPQRSTUWYZ.°\.,:;\s\-*\(\)\?!\[\]/»«]+))'
numbers='(?P<numbers>((III|II|IV|VI|I|V|1|И)(\s)*(\-|—)(\s)*(\d)+(a|а)?(\s)*(\(доп.\))?(\s)*((,|\.|\-|—|;)*(\s)*(\d)+(a|а)?(\s)*(\(доп.\))?(\s)*)*(;)?(\s)*)+)'
date='(?P<years>(\d{1,4}(\-|—)\d{1,4}?\s*(в\.|вв\.)\s*(до н\. э\.)|(\d{3,4}))\s*(или)\s*(ок\.)?\s*(([XIV]+(\s)*(в\.|вв\.)?)|\d{3,4}\s*(\-|—)\s*\d+|\d+\s*(\-|—)|(\d+))|(\(|\[)?(\d{3,4})(\[\?\]|\[!\]|\?|\[\d\?\]|\/\d)?(\s)*((\-x г\.|\-х г\.|x г\.|х г\.|\-x гг\.|\-х гг\.|x гг\.|х гг\.|\-x|\-х|x|х|-е гг\.|-e гг\.|-е г\.|-e г\.|-е))?(\)|\])?(\s)*(\-|—)(\s)*(ок\.|oк\.|после)?(\s)*(\(|\[)?(\d+)(\[\?\]|\[!\]|\?|\[\d\?\]|\/\d)?(\s)*((\-x г\.|\-х г\.|x г\.|х г\.|\-x гг\.|\-х гг\.|x гг\.|х гг\.|\-x|\-х|x|х|-е гг\.|-e гг\.|-е г\.|-e г\.|-е))?(\)|\])?(\s)*|(\(|\[)?(\d{3,4})(\[\?\]|\[!\]|\?|\[\d\?\]|\/\d)?(\s)*((\-x г\.|\-х г\.|x г\.|х г\.|\-x гг\.|\-х гг\.|x гг\.|х гг\.|\-x|\-х|x|х|-е гг\.|-e гг\.|-е г\.|-e г\.|-е))?(\)|\])?(\s)*(\-|—)|(\-|—)(\s)*(ок\.|oк\.|после)?(\s)*(\(|\[)?(\d{3,4})(\[\?\]|\[!\]|\?|\[\d\?\]|\/\d)?(\s)*((\-x г\.|\-х г\.|x г\.|х г\.|\-x гг\.|\-х гг\.|x гг\.|х гг\.|\-x|\-х|x|х|-е гг\.|-e гг\.|-е г\.|-e г\.|-е))?(\)|\])?(\s)*|\d{2}((\-|—)\d{2})?(\s)*((\-x|\-х|x|х|\-x г\.|\-х г\.|x г\.|х г\.|\-x гг\.|\-х гг\.|x гг\.|х гг\.|-е гг\.|-е|-e гг\.|-е г\.|-e г\.))(\s)*([XIV]+(\s)*(в\.|вв\.))|(ок\.)?\s*\d{3,4}(\-|—)(\[\?\]|\[!\]|\?|\[\d\?\]|\/\d)|(ок\.)?\s*(\[\?\]|\[!\]|\?|\[\d\?\]|\/\d)(\-|—)(ок\.)?\s*\d{3,4}|(ок\.)?\s*(([XIV]+(\s)*(в\.|вв\.))|(конца|середины|начала|1-й половины|2-й половины|2-ой пол.|1-ой пол.|II половины|I половины)?(\s)*([XIV]+(\s)*(в\.|вв\.)?)(\s)*(\-|—)(\s)*(конца|середины|начала|1-й половины|2-й половины|2-ой пол.|1-ой пол.|II половины|I половины)?(\s)*([XIV]+(\s)*(в\.|вв\.))|(конца|середины|начала|1-й половины|2-й половины|2-ой пол.|1-ой пол.|II половины|I половины)?(\s)*([XIV]+(\s)*(в\.|вв\.))))'

# Парсинг указателя
reg_expression = f'{name}{date}*{name2}*{numbers}?'

lines = text_to_lines()
data = pd.DataFrame(columns = ['line_i', 'name', 'years', 'name2', 'numbers', 'not_parsed'])
for line_ind, line in tqdm(lines):
    line = line.replace(" 1—", " I—")
    while True:
        m = re.match(reg_expression, line)
        if m and m.group('name'):# and m.group('numbers'):
            name = m.group("name")
            years = m.group("years")
            name2 = m.group("name2")
            numbers = m.group("numbers")
            data.loc[len(data)] =  [line_ind, name, years, name2, numbers, '']
            line = line[len(m[0]):]
        else:
            if line:
                if len(data) > 0:
                    data.iloc[-1, -1] = line
                else:
                    data.loc[len(data), "not_parsed"] = line                   
            break
data.to_csv("authors.csv", index=False)


# Чистка данных

data['possible_mistakes'] = data['numbers'].apply(lambda x: True if (str(x).find("—") == -1 and str(x).find("-") == -1) or ("I" not in x and "X" not in x and "V" not in x) else False)
data['possible_mistakes'] = data.apply(lambda x: True if len(x) <= 4 or x.not_parsed != ""  else x.possible_mistakes, axis=1)
data['name'] = data['name'].apply(lambda x: str(x).strip())

#data.to_csv("authors_comments.csv", index=False)
#data = pd.read_csv("authors_comments.csv")
data.fillna("", inplace=True)

## Периоды

period = ['начала', "конца", "середины", "П-ой половины", "II-ой половины", "первой половины", "второй половины", " ок. "]
def find_period(x):
    for i, p in enumerate(period):
        if x.find(p) > 0:
            return i
    return -1

def change_name(x, i):
    if i == -1:
        return x
    return str(x).replace(period[i], "")

def change_years(x, i):
    if i == -1:
        return x
    return f'{period[i]} {x}'

data['temp'] = data['name'].apply(find_period)
data['name'] = data.apply(lambda x: change_name(x['name'], x['temp']), axis=1)
data['years'] = data.apply(lambda x: change_years(x['years'], x['temp']), axis=1)


period = ['-x г.', '-х г.', 'x г.', 'х г.', '-x гг.','-х гг.', 'x гг.', 'х гг.', '-x ',
          '-х ', 'x ', 'х ', 'е гг.', '-e гг.', '-е г.', '-e г.', '-е ', '-e ', ' в. ', ' вв. ']

def find_period2(x):
    for i, p in enumerate(period):
        if x.find(p) >= 0:
            return i
    return -1

def change_name2(x, i):
    if i == -1:
        return x
    return str(x).replace(period[i], "")

def change_years2(x, i):
    if i == -1:
        return x
    return f'{x} {period[i]}'

data['temp'] = data['name2'].apply(find_period2)
data['name2'] = data.apply(lambda x: change_name2(x['name2'], x['temp']), axis=1)
data['years'] = data.apply(lambda x: change_years2(x['years'], x['temp']), axis=1)

## Псевдонимы

def find_pseudo(x):
    ind0 = max(x.find("псевд.:"),  x.find("Псевд.:"))
    if ind0 > 0:
        return x[ind0:]

    ind1 = max(x.find("псевд."), x.find("псевд,"), x.find("Псевд."), x.find("Псевд,"))
    if ind1 > 0:
        return x[:ind1+6]
    
    ind2 = x.find("Коллективный псевдоним")
    if ind2 > 0:
        return x[:ind2+len("Коллективный псевдоним")]
    
    ind3 = max(x.find("писали под коллективным псевдонимом"), x.find("писала под коллективным псевдонимом"),
               x.find("писал под коллективным псевдонимом"))
    if ind3 > 0:
        return x[ind3:]    
    
    return ""

def fix_name(name, temp):
    # пустой или случай с проблемами в падежах, если удалить
    if temp == "" or temp.find("Коллективный псевдоним") > 0:
        return name
    return name.replace("Подлинное имя автора:", "").replace(temp, "")

data['temp'] = data['name'].apply(find_pseudo)
data['name2'] = data['name2'] + " " + data['temp']
data['name'] = data.apply(lambda x: fix_name(x['name'], x['temp']), axis=1)

data['not_parsed'] = data['not_parsed'].apply(lambda x: x.strip() if len(x.strip()) > 1 else "")
data['possible_mistakes'] = data['numbers'].apply(lambda x: True if (str(x).find("—") == -1 and str(x).find("-") == -1) or ("I" not in x and "X" not in x and "V" not in x) else False)
data['possible_mistakes'] = data.apply(lambda x: True if len(x) <= 4 or x.not_parsed != ""  else x.possible_mistakes, axis=1)
data[['line_i', 'name', 'years', 'name2', 'numbers', 'not_parsed','possible_mistakes']].to_csv("authors_clean.csv", index=False)

