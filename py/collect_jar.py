# coding=utf-8

import os
import re
import json
from shutil import copyfile

version = '7.0'
project_path = '/android-7.0.0_r33/out/target/common/obj/JAVA_LIBRARIES'



def findAllFile(base):
    dirs = os.listdir(base)
    for dir in dirs:
        for f in os.listdir(base+'/'+dir):
            if(f=='classes.jar'):
                copyfile(base+'/'+dir+'/'+f, 'jar' + version + '/'+dir+'.jar')
                print('jar_list.add(BASE + "%s");'% (''+dir+'.jar'))


def find():
    findAllFile(project_path)

if __name__ == '__main__':
    find()
    pass