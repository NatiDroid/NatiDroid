import os.path
import numpy as np
import ccsyspath
from clang.cindex import Config
from clang.cindex import Index
import json

def get_file(base, extension):
    for root, ds, fs in os.walk(base):
        for f in fs:
            if f.endswith(extension):
                fullname = os.path.join(root, f)
                yield fullname


def find_files(path, extension):
    filename = 'tem/'+path.replace('/','_')+'_' + extension + '_list.npy'
    if not os.path.exists(filename):
        list = []
        for i in get_file(path, extension):
            list.append(i)
        list = np.array(list)
        np.save(filename, list)

    list = np.load(filename)
    return list

def find_c_or_cpp(filename, pre_fix):
    list = []
    filename = '/' + os.path.basename(filename)

    filename = filename.replace('.h', '.c')
    c_list = find_files(pre_fix, '.c')
    for tem in c_list:
        if filename in tem:
            list.append(tem)

    filename = filename.replace('.c', '.cpp')
    cpp_list = find_files(pre_fix, '.cpp')
    for tem in cpp_list:
        if filename in tem:
            list.append(tem)
    return list

def get_cpp_files_path():
    list = []
    with open('tem/build-aosp_arm64.json') as file_obj:
        js = json.load(file_obj)
        list.extend(js)

    with open('tem/out_build_ninja.json') as file_obj:
        js = json.load(file_obj)
        list.extend(js)

    return list

def find_command_star_node(filename):
    list = []
    with open('tem/build-aosp_arm64.json') as file_obj:
        js = json.load(file_obj)
        cpp = filename.replace('.h', '.cpp')
        c = filename.replace('.h', '.c')
        for tem in js:
            if cpp in tem['source'] or c in tem['source']:
                list.append(tem)
    with open('tem/out_build_ninja.json') as file_obj:
        js = json.load(file_obj)
        cpp = filename.replace('.h', '.cpp')
        c = filename.replace('.h', '.c')
        for tem in js:
            if cpp in tem['source'] or c in tem['source']:
                list.append(tem)

        return list

def find_command(file, pre_fix):
    print(file)
    list = []
    with open('tem/build-aosp_arm64.json') as file_obj:
        js = json.load(file_obj)
        filename = '/' + os.path.basename(file)
        cpp = filename.replace('.h', '.cpp')
        c = filename.replace('.h', '.c')
        for tem in js:
            if cpp in tem['source'] or c in tem['source']:
                list.append(tem)
    with open('tem/out_build_ninja.json') as file_obj:
        js = json.load(file_obj)
        filename = '/' + os.path.basename(file)
        cpp = filename.replace('.h', '.cpp')
        c = filename.replace('.h', '.c')
        for tem in js:
            if cpp in tem['source'] or c in tem['source']:
                list.append(tem)
    best_score = 0
    best_command = None
    for tem in list:
        a_ls = tem['source'].split('/')
        b_ls = file.replace(pre_fix, '').split('/')
        min_len = min(len(a_ls), len(b_ls))
        score = 0
        for i in range(min_len):
            if a_ls[i] == b_ls[i]:
                score = score + 1
        if score > best_score:
            best_score = score
            best_command = tem
    return best_command

if __name__ == '__main__':
    h_list = find_files('/android/android-8.0.0_r34', '.h')
    c_list = find_files('/android/android-8.0.0_r34', '.c')


    with open('tem.json', 'w') as file_obj:
        json.dump(a, file_obj)



