import os
import re
import json
import xlrd
import subprocess


def call(args, timeout):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=timeout)

        return out
    except subprocess.TimeoutExpired:
        print('*** time out ***', timeout, 's')
        p.kill()
        out, err = p.communicate()
        print(out)
        return out

def arcade_mapping_new_AOSP_7_analysis():
    list = []
    with open('arcade_mapping_new_AOSP_7.json', 'r') as file_obj:
        a = json.load(file_obj)['array']
        total = len(a)
        for i, tem in enumerate(a):
            if i>=0:
                print(str(i) + '/' + str(total))
                method = tem['method']
                print()
                class_str = method.split(':')[0]

                class_str_split = class_str.split('.')
                arg1 = class_str_split[-1]
                print(arg1)
                arg2 = ''
                for temmm in class_str_split[:-1]:
                    arg2 = arg2 + temmm + '.'
                print(arg2)
                print(method)
                
                cmd_args = ['java', '-jar', 'soottest2.jar', arg1, arg2, method]
                print(cmd_args)
                timeout = 60 * 5

                call(cmd_args, timeout)
                
arcade_mapping_new_AOSP_7_analysis()
