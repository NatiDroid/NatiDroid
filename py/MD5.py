#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import hashlib
import os

def md5(file_name):
    # file_name = "test.py"
    with open(file_name, 'rb') as fp:
        data = fp.read()
    file_md5 = hashlib.md5(data).hexdigest()
    return file_md5

def findAllFile(base, extension):
    for root, ds, fs in os.walk(base):
        for f in fs:
            if f.endswith('.' + extension):
                fullname = os.path.join(root, f)
                yield fullname

md5s = []
MD5_same = []
for file in findAllFile('sysapp/7.0', 'apk'):
    print(file)
    tem = md5(file)
    if tem not in md5s:
        md5s.append(tem)
    else:
        print(file, tem)
        MD5_same.append([file, tem])

for file in findAllFile('/android-7.0.0_r33/out/target/product/generic_arm64/system/app', 'apk'):
    print(file)
    tem = md5(file)
    if tem not in md5s:
        md5s.append(tem)
    else:
        print(file, tem)
        MD5_same.append([file, tem])

for file in findAllFile('/android-7.0.0_r33/out/target/product/generic_arm64/system/priv-app', 'apk'):
    print(file)
    tem = md5(file)
    if tem not in md5s:
        md5s.append(tem)
    else:
        print(file, tem)
        MD5_same.append([file, tem])

print('============================================')
for tem in MD5_same:
    print(tem)
print(len(MD5_same))