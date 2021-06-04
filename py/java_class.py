# coding=utf-8

import os
import re
import json

def findAllFile(base, extension):
    for root, ds, fs in os.walk(base):
        for f in fs:
            if f.endswith('.' + extension) and 'tests/' not in root and 'test/' not in root:

                    fullname = os.path.join(root, f)
                    yield fullname

def get_class(path):
    with open(path, 'r', encoding='UTF-8') as file:
        # Convert encoding to achieve correct output format
        lines = file.readlines()

        analyze_this_file = False
        for i, line in enumerate(lines):
            if 'ServiceManager.getService(' in line:
                analyze_this_file = True
        if not analyze_this_file:
            return None

        # Find left and right braces
        left_pos = []
        pair = []
        package = ''
        package_finded = False
        service_line = -1
        ignore_mode = False
        for i, line in enumerate(lines):
            line = line.strip()

            tem_r = re.findall("/\*.+?\*/", line)
            for r in tem_r:
                line = line.replace(r, '')
            # Remove the string
            tem_r = re.findall(r"\".{0,}?[^\\]\"", line)
            for r in tem_r:
                line = line.replace(r, '')
            tem_r = re.findall(r'\'.{0,}?[^\\]\'', line)
            for r in tem_r:
                line = line.replace(r, '')
            tem_r = re.findall(r'//.+', line)

            for r in tem_r:
                line = line.replace(r, '')
            if '/*' in line:
                ignore_mode = True
            if '*/' in line:
                ignore_mode = False
                tem_r = re.findall(".+?\*/", line)
                for r in tem_r:
                    line = line.replace(r, '')

            if ignore_mode:
                continue

            lines[i] = line

            if 'package ' in line and not package_finded:
                package_finded = True
                package = line.strip().replace('package ', '').replace(';', '')

            if ' ServiceManager.getService(' in line or line.startswith('ServiceManager.getService('):
                service_line = i

            pos1 = find_all(line, '{')
            pos2 = find_all(line, '}')
            # Process the position of {} in this bank first
            # If yes} first check if there is any before this line {if there is no pop previous, if yes, then pair next
            # The remaining {join pos

            goon = True
            while goon:
                goon = False
                for end_pos in pos2:
                    for start_pos in pos1:
                        if start_pos < end_pos:
                            pos1.remove(start_pos)
                            pos2.remove(end_pos)
                            pair.append([i, i])
                            goon = True


            for tem in pos1:
                left_pos.append(i)

            for tem in pos2:
                # If there is} in this line, it can only be closed before its index {
                if len(left_pos) == 0:
                    raise Exception('miss {')
                pos = left_pos.pop()
                pair.append([pos, i])

        if len(left_pos) !=0:
            raise Exception('miss }')

        # search class
        classes = {}
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('*') or line.startswith('//') or line.startswith('/*'):
                continue
            if ' class ' in line and '"' not in line or line.startswith('class '):

                line_index_tem = i
                class_cache = line
                while line_index_tem < len(lines) and len(find_all(lines[line_index_tem], '{'))==0:
                    line_index_tem = line_index_tem + 1
                    class_cache = class_cache + ' ' +lines[line_index_tem]

                class_cache = class_cache.replace('\n', '')
                a = re.findall(r"class[ ][a-zA-Z0-9_]+[ <{]", class_cache)

                class_name = a[0].strip()
                class_name = class_name.replace('class ', '').replace('{', '').replace('<', '').strip()

                for tem in pair:
                    left = tem[0]
                    right = tem[1]

                    if left == line_index_tem:
                        print(class_name, left, right)
                        classes[class_name] = [left, right]


        def find_outer_class(keys, dic, c_key, visited):
            if len(visited) == len(keys):
                return ''
            start = dic[c_key][0]
            end = dic[c_key][1]
            outer = None
            for k in keys:
                if classes[k][0] < start and classes[k][1] > end:
                    outer = k
                    visited.append(outer)
            if outer != None:
                return find_outer_class(keys, dic, outer, visited) + '$' + outer
            return ''

        full_name_list = []
        keys = classes.keys()
        for k in keys:
            outer_class = find_outer_class(keys, classes, k, [k])
            full_class = outer_class + '$' + k
            if full_class.startswith('$'):
                full_class = full_class[1:]
            full_name_list.append([full_class, package + '.', classes[k][0], classes[k][1]])

        min_line_num = 10e10
        best = None
        for tem in full_name_list:
            if service_line > tem[2] and service_line < tem[3] and tem[3] - tem[2] < min_line_num:
                min_line_num = tem[3] - tem[2]
                best = tem

        return best



def find_all(str, par):
    start = 0
    poses = []
    while True:
        index = str.find(par, start)
        start = index + 1

        if index!= -1:
            poses.append(index)
        else:
            break

    return poses

def save():

    list = []

    base = '/Volumes/android/android-8.0.0_r34/frameworks/'
    java_files = findAllFile(base, 'java')
    for f in java_files:
        r = get_class(f)
        if r!= None:
            print()
            print(f)
            print('String filePath = "%s";' % f)
            print('String mainClassStrLast = "' + r[0] + '";')
            print('String mainClassStr = "' + r[1] + '" + mainClassStrLast;')
            print('CppLink.run(mainClassStrLast, mainClassStr);')
            list.append({'last': r[0],
                         'base': r[1],
                         'file_path':f})

    base = '/Volumes/android/android-8.0.0_r34/sdk/'
    java_files = findAllFile(base, 'java')
    for f in java_files:
        r = get_class(f)
        if r != None:
            print()
            print('String filePath = "%s";' % f)
            print('String mainClassStrLast = "' + r[0] + '";')
            print('String mainClassStr = "' + r[1] + '" + mainClassStrLast;')
            print('CppLink.run(mainClassStrLast, mainClassStr);')
            list.append({'last': r[0],
                         'base': r[1],
                         'file_path': f})

    print('FOUND:', len(list))
    json_str = json.dumps({'array': list})
    with open('java_class/java_class.json', 'w', encoding='UTF-8') as file:
        file.write(json_str)

def load():
    file = open('java_class/java_class.json', 'r', encoding='UTF-8')
    json_str = file.read()
    json_obj = json.loads(json_str)
    array = json_obj['array']
    total = len(array)
    print('total:', total)
    i = 0
    for obj in array:
        i = i + 1
        print()
        print(i, '/', total)
        last = obj['last'].replace('$', '\$')
        base = obj['base'].replace('$', '\$')
        print(obj['file_path'])
        print(last)
        print(base)
        cmd = 'java -jar /Users/xxx/IdeaProjects/aosp_java_analyser/out/artifacts/findCppLink/findCppLink.jar "%s" "%s" > %s' % (last, base, "log/"+base+last+'.txt')
        print(cmd)
        os.system(cmd)

if __name__ == '__main__':
    # save()
    load()
    pass