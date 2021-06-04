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

def extract_servicename_from_log(path):
    with open(path, 'r', encoding='UTF-8') as file:  # 转换编码以实现正确输出中文格式
        lines = file.readlines()

        analyze_this_file = False
        for i, line in enumerate(lines):
            if 'SEARCH FROM FUNCTION WHICH CONTAINS getService()' in line:
                # print(line.split("["))
                tem = line.split("[")[-1].strip()
                tem = tem[:-1]
                print(tem)

if __name__ == '__main__':
    paths = findAllFile('log/', 'txt')
    for path in paths:
        extract_servicename_from_log(path)
