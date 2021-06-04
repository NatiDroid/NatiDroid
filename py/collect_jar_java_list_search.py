# coding=utf-8

import os
import re
import json
from shutil import copyfile

def findAllFile(base):
    dirs = os.listdir(base)
    for dir in dirs:
        if dir=='.DS_Store':
            continue
        for f in os.listdir(base+'/'+dir):
            if(f.endswith('java-source-list')):
                with open(base+'/'+dir+'/'+f) as file:
                    for line in file.readlines():
                        if 'WifiDisplayAdapter.java' in line:
                            print('FOUND:', base+'/'+dir+'/'+f, line)


def find():
    project_path = '/android-7.0.0_r33/out/target/common/obj/JAVA_LIBRARIES'
    findAllFile(project_path)

if __name__ == '__main__':
    find()
    pass