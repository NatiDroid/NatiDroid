from pprint import pprint
from clang.cindex import CursorKind, Index, CompilationDatabase, TypeKind, TokenKind
from collections import defaultdict
import sys
import json
import os.path
from clang.cindex import Config
import ccsyspath
import numpy as np
# from helper_local import get_file, find_c_or_cpp, find_files, find_command, find_command_star_node, get_cpp_files_path
from helper import get_file, find_c_or_cpp, find_files, find_command, find_command_star_node, get_cpp_files_path, \
    find_command_all_cpp
import re
import pickle
import copy
from util import get_tu, get_cursor, get_cursors

# import shelve

project_path = '/hci/chaoran_data/android-7.0.0_r33/'
clang_prepath = 'prebuilts/clang/host/linux-x86/clang-2690385/'
clang_lib_path = project_path + clang_prepath + 'lib64/libc++.so'
clang_lib_path = '/hci/chaoran_data/android-7.0.0_r33/out/host/linux-x86/lib64/libclang.so'
print(clang_lib_path)
Config.set_library_file(clang_lib_path)
init_arg_config = '-isystem/hci/chaoran_data/android-7.0.0_r33/prebuilts/clang/host/linux-x86/clang-2690385/lib64/clang/3.8/include'
aosp_ver = '7.0'
h_list = None

CursorKind.IF_CONDITION = CursorKind(8625)


class file_analyser():
    def __init__(self):
        self.CALLGRAPH = defaultdict(list)
        self.FULLNAMES = {}
        self.pro_path = ''
        self.ENDNODE = []
        self.show_loc = False
        self.print_all_node = False

        self.html_log = []
        self.current_depth = 0

        self.found_permission_method = []

        self.node_start = {}
        self.file_tu = {}

        self.analyzed_cpp = set()

    def save(self):
        obj1 = pickle.dumps(self.CALLGRAPH)
        with open("tem/save/self.CALLGRAPH", "ab")as f:
            f.write(obj1)

    def load(self):
        f = open("tem/save/self.CALLGRAPH", "rb")
        while 1:
            try:
                obj = pickle.load(f)
                self.CALLGRAPH = obj
            except:
                break
        f.close()

    def get_diag_info(self, diag):
        return {
            'severity': diag.severity,
            'location': diag.location,
            'spelling': diag.spelling,
            'ranges': diag.ranges,
            'fixits': diag.fixits
        }

    def fully_qualified(self, c):
        if c is None:
            return ''
        elif c.kind == CursorKind.TRANSLATION_UNIT or c.kind == CursorKind.IF_CONDITION:
            return ''
        else:
            res = self.fully_qualified(c.semantic_parent)
            if res != '':
                return res + '::' + c.spelling
            return c.spelling

    def fully_qualified_pretty(self, c):
        if c is None:
            return ''
        elif c.kind == CursorKind.TRANSLATION_UNIT or c.kind == CursorKind.IF_CONDITION:
            return ''
        else:
            res = self.fully_qualified(c.semantic_parent)
            return_name = c.displayname
            # Need to process template functions
            # Remove the <> after the function name
            # '^[a-zA-Z0-9_^\(]+(::[a-zA-Z0-9_^\(]+)+<>\(' Full function name match
            # No class name matching
            for tem in re.findall('^[a-zA-Z0-9_^\(]+<>\(', return_name):
                return_name = return_name.replace(tem, tem.replace('<>(', '('))
            # Remove <XXXX> in the parameter list
            for tem in re.findall('<[^\(]+?>', return_name):
                return_name = return_name.replace(tem, '<>')

            if res != '':
                return res + '::' + return_name
            # Prevent the replacement of the Binder method, but the missing const in the parameters results in the failure to match
            return return_name

    def is_excluded(self, node, xfiles, xprefs):
        if not node.extent.start.file:
            return False

        for xf in xfiles:
            if node.extent.start.file.name.startswith(xf):
                return True

        fqp = self.fully_qualified_pretty(node)

        for xp in xprefs:
            if fqp.startswith(xp):
                return True

        return False

    def is_template(self, node):
        return hasattr(node, 'type') and node.type.get_num_template_arguments() != -1

    def get_all_children(self, node, list=[], level=0):
        for child in node.get_children():
            list.append([level, child])
            self.get_all_children(child, list, level + 1)

    def get_para_index(self, para, method_index, children):
        para_index = -1
        for i in range(method_index, len(children)):
            if children[i][1].kind == CursorKind.PARM_DECL:
                para_index = para_index + 1
                if children[i][1].displayname == para:
                    return para_index
        print('Parameter not found')

    def get_para_class_by_name(self, para, node):
        para_index = -1
        children = []
        self.get_all_children(node, children, level=0)
        found = False
        for i in range(len(children)):
            if children[i][1].kind == CursorKind.PARM_DECL:
                para_index = para_index + 1
                if found:
                    print('found|', children[i][1].kind, children[i][1].displayname)
                if found and children[i][1].kind == CursorKind.TYPE_REF and children[i][1].displayname != '':
                    return children[i][1].displayname
                if children[i][1].displayname == para:
                    found = True
        return None

    def get_method_index(self, index, children):
        print('*** get_method_index ***')
        for i in range(index, 0, -1):
            if children[i][1].kind == CursorKind.FUNCTION_TEMPLATE or \
                    children[i][1].kind == CursorKind.CONSTRUCTOR or \
                    children[i][1].kind == CursorKind.CXX_METHOD or \
                    children[i][1].kind == CursorKind.FUNCTION_DECL:
                return i
        print('Function not found')

    def get_method_index_var(self, index, method, children):
        method_str = self.fully_qualified_pretty(method.referenced)
        print('Looking for', method_str,'the first', index,'parameters')
        last_level = 10e10
        para_index = -1
        for i, tem in enumerate(children):
            if tem[1].kind == CursorKind.CALL_EXPR and tem[1].displayname in method_str:
                if self.fully_qualified_pretty(tem[1].referenced) == method_str:
                    last_level = tem[0]

            if tem[0] < last_level:
                last_level = 10e10
                para_index = -1

            if tem[0] > last_level:
                if tem[1].kind == CursorKind.DECL_REF_EXPR:
                    para_index = para_index + 1
                    if para_index == index:
                        return tem[1].displayname, 'local', i
                if tem[1].kind == CursorKind.MEMBER_REF_EXPR:
                    para_index = para_index + 1
                    if para_index == index:
                        return tem[1].displayname, 'global', i
        print('The variable passed in by calling the function was not found')
        return None, 'no_caller', -1

    def method_inner_para_class(self, index, node):
        children = []
        self.get_all_children(node, children, level=0)

        para_index = -1
        for i, tem in enumerate(children):
            print(tem[0], ' ' * tem[0], tem[1].kind, tem[1].displayname)
            if tem[1].kind == CursorKind.PARM_DECL:
                para_index = para_index + 1
                if para_index == index:
                    local_var = tem[1].displayname
                    return_class = self.find_var_local(local_var, children, node)
                    return return_class

    def find_var(self, var, file, DEBUG=False):
        print('\n*** var ***')
        print('in', file,'find in', var)
        # There is no variable assignment in the header file, so replace the analysis in the .h file with the analysis
        # in the .cpp file (there may be potential problems, it is best to analyze both)
        if file.endswith('.h'):
            file = file[:-1] + 'cpp'
        node = self.node_start[file]
        children = []
        self.get_all_children(node, children, level=0)
        last_level = 10e10
        assign_mode = False
        assign_stmt = []
        call_mode_last_level = 10e10
        call_node = None
        call_mode_para_index = -1
        current_fun_node = None
        for i, tem in enumerate(children):
            if DEBUG:
                print(tem[0], 'line 213|', ' ' * tem[0], tem[1].kind, tem[1].displayname)
            if tem[1].kind == CursorKind.CXX_METHOD:
                current_fun_node = tem[1]
            '''
            NativeRemoteDisplay(const sp<IRemoteDisplay>& display,
            const sp<NativeRemoteDisplayClient>& client) :
            mDisplay(display), mClient(client) {
            }

            ===
             mDisplay is determined by display
             display is the 0th parameter of this method
             Find the type of the 0th parameter of this method
            '''
            if last_level == 10e10 and call_mode_last_level == 10e10:
                if DEBUG:
                    print(tem[0], 'line 226|', ' ' * tem[0], tem[1].kind, tem[1].displayname)
                if tem[1].kind == CursorKind.MEMBER_REF and tem[1].displayname == var:
                    if children[i + 2][1].kind == CursorKind.DECL_REF_EXPR:
                        para = children[i + 2][1].displayname
                        member_sp_mode = False
                        print('Find passed parameters', para,'incoming, index', i)
                        method_index = self.get_method_index(i, children)
                        para_index = self.get_para_index(para, method_index, children)
                        print('What is the parameter', para_index,'parameter')
                        # Find the variable name of the xth parameter that calls this function
                        method = children[method_index][1]
                        r, scope, var_index = self.get_method_index_var(para_index, method, children)
                        if scope == 'global':
                            print('.line 211')
                            return_class = self.find_var(r, file)
                        elif scope == 'local':
                            parent_method_index = self.get_method_index(var_index, children)
                            parent_method = children[parent_method_index][1]
                            print('.line 216')
                            return_class = self.find_var_local(r, children, parent_method)
                        elif scope == 'no_caller':
                            print('no caller, does not analyze')
                            return 'no_caller'
                        else:
                            print('unhandled scope.')
                        return return_class

            # assignment
            if call_mode_last_level == 10e10:
                if DEBUG:
                    print(tem[0], 'line 254|', ' ' * tem[0], tem[1].kind, tem[1].displayname)

                if var == tem[1].displayname:
                    # CursorKind.MEMBER_REF_EXPR mDrm
                    print('.line 236')
                    print('*** found var ***')
                    last_level = tem[0]
                    print(tem[0], 'var|', ' ' * tem[0], tem[1].kind, tem[1].displayname, tem[1].location)

                if tem[0] > last_level:
                    print(tem[0], 'var|', ' ' * tem[0], tem[1].kind, tem[1].displayname, tem[1].location)

                    if 'operator=' in tem[1].displayname:
                        print('assign_mode = True')
                        # 赋值
                        assign_mode = True
                        print()
                    elif assign_mode and tem[1].kind == CursorKind.CALL_EXPR:
                        # get return var class
                        print('invoke method: get return class |||', tem[1].kind)
                        fun_str = self.fully_qualified_pretty(tem[1].referenced)
                        print('DEBUG ', fun_str)
                        if 'interface_cast' in fun_str:
                            # gAudioFlinger = interface_cast<IAudioFlinger>(binder);
                            for tem_i in range(i + 1, len(children)):
                                print(children[tem_i][0], 'interface_cast|', ' ' * children[tem_i][0],
                                      children[tem_i][1].kind, children[tem_i][1].displayname,
                                      children[tem_i][1].location)
                            exit(2)
                        print(fun_str, tem[1].location)
                        strinfo = re.compile('<.{0,}?>')
                        fun_str_revised = strinfo.sub('<>', fun_str)
                        print('fun_str_revised (remove the <...> template content):', fun_str_revised)
                        if self.has_no_ignore_fun(fun_str_revised):
                            entry_funs, entry_fun_vs = self.search_fun(fun_str_revised)
                        else:
                            return 'END'

                        assert len(entry_fun_vs) == 1, 'No function found or too many functions ' + tem[1].referenced.displayname
                        print('.line 170')
                        return_class = self.get_return(entry_fun_vs[0], node)
                        print(return_class)

                        if return_class != None:
                            return return_class
                        pass
                    elif assign_mode and tem[1].kind == CursorKind.DECL_REF_EXPR:
                        print('line 323 Assigned by the variable on the right', tem[1].displayname)
                        print('Function where the variable is located:', current_fun_node.displayname)
                        children_current_fun_node = []
                        self.get_all_children(current_fun_node, children_current_fun_node, level=0)
                        return self.find_var_local(tem[1].displayname, children, current_fun_node)

                if tem[0] < last_level:
                    last_level = 10e10

            # Member variable not found. Look for the variable assigned by parameter passing
            '''
            3     CursorKind.CALL_EXPR waitForSensorService
            4      CursorKind.UNEXPOSED_EXPR waitForSensorService
            5       CursorKind.DECL_REF_EXPR waitForSensorService
            4      CursorKind.UNARY_OPERATOR 
            5       CursorKind.MEMBER_REF_EXPR mSensorServer
            '''
            '''
            This variable is passed into a function (pass by reference)
            In this function this variable is assigned
            '''
            if last_level == 10e10:
                if DEBUG:
                    print(tem[0], 'line 317|', ' ' * tem[0], tem[1].kind, tem[1].displayname)
                if tem[1].kind == CursorKind.CALL_EXPR and ('operator->' in tem[1].displayname or
                                                            'operator!=' in tem[1].displayname or
                                                            'operator==' in tem[1].displayname or
                                                            'operator=' in tem[1].displayname or
                                                            'sp' in tem[1].displayname or
                                                            'asBinder' in tem[1].displayname):
                    call_mode_last_level = 10e10
                    call_node = None
                    call_mode_para_index = -1

                if tem[1].kind == CursorKind.CALL_EXPR and 'operator->' not in tem[
                    1].displayname and 'operator!=' not in tem[1].displayname and 'operator==' not in tem[
                    1].displayname and 'operator=' not in tem[1].displayname and 'sp' not in tem[
                    1].displayname and 'asBinder' not in tem[1].displayname:

                    call_mode_last_level = tem[0]
                    call_node = tem[1]
                    call_mode_para_index = -1

                # The first subtree is not needed, otherwise the method in var.
                # method() will be used as the first parameter, which is actually not
                if tem[0] == call_mode_last_level + 1:
                    if tem[1].displayname == call_node.displayname or tem[1].displayname == 'operator==':
                        children_ignore = True
                    else:
                        children_ignore = False
                if tem[0] > call_mode_last_level and not children_ignore and (
                        tem[1].kind == CursorKind.MEMBER_REF_EXPR or tem[1].kind == CursorKind.DECL_REF_EXPR):
                    if tem[1].displayname != call_node.displayname and 'operator->' not in tem[1].displayname and \
                            children[i - 1][1].kind != CursorKind.CALL_EXPR and 'operator->' not in children[i - 1][
                        1].displayname \
                            :
                        call_mode_para_index = call_mode_para_index + 1
                        if tem[1].displayname == var:
                            # Enter a method, which parameter is assigned in the method
                            print('.line 318')
                            print('Enter a method, the first few parameters are assigned in the method')
                            print('FUN:', call_node.kind, call_node.displayname, call_node.location)
                            print('Para index:', call_mode_para_index)
                            if 'getService' in call_node.displayname:
                                print('Find the passed str, go to the function to look up the table')
                                service_names = []
                                self.print_childrens(call_node, service_names, 0)
                                print(service_names)
                                service_name = None
                                for tem in service_names:
                                    if tem[0] != '' and service_names != 'None' and 'permisson.' not in service_names:
                                        service_name = tem[0]
                                print(service_name)
                                class_str = self.service_str_trans(service_name)
                                print(class_str)
                                return class_str
                            call_node_referenced = call_node.referenced
                            print(call_node_referenced.kind, call_node_referenced.displayname,
                                  call_node_referenced.location)
                            method_full = self.fully_qualified_pretty(call_node.referenced)
                            print(call_node.referenced.kind, method_full)
                            # Return the variable class name directly
                            if call_node.referenced.kind == CursorKind.CONSTRUCTOR:
                                return_class = self.fully_qualified(call_node.referenced.semantic_parent)
                                print(return_class)
                                return return_class
                            # Replace IxxxService:: directly with xxxService::
                            tema = re.findall(r'I[a-zA-Z]+?Service::', method_full)
                            for temb in tema:
                                print(temb)
                                method_full = method_full.replace(temb, temb[1:])
                            print(method_full)
                            if (call_node.displayname != 'GetLongField'):
                                entry_funs, entry_fun_vs = self.search_fun(method_full)
                                print('.lin3 325')
                                # Enter a method, which parameter is assigned in the method
                                return_class = self.method_inner_para_class(call_mode_para_index, entry_fun_vs[0])
                                print('\n', return_class)
                                return return_class
                            exit(7)
                            call_node_referenced = call_node.referenced

                if tem[0] < call_mode_last_level:
                    call_mode_last_level = 10e10
                    call_node = None
                    call_mode_para_index = -1

    def service_str_trans(self, str):
        str = str.strip('"')
        if str == 'sensorservice':
            return 'android::SensorService'
        elif str == 'permission':
            return 'android::PermissionService'
        elif str == 'SurfaceFlinger':
            self.extend_h_analysis('frameworks/SurfaceFlinger_hwc1.cpp', '7.0', True, project_path, fuzzy=True)
            return 'android::SurfaceFlinger'

    def getService(self, index, children):
        print('*** getService ***')
        var = None
        start2find_var = False
        print(children[index][1].location)
        for i in range(index, index + 30):
            tem = children[i]
            print(tem[0], ' ' * tem[0], tem[1].kind, tem[1].displayname)
        ignore = False
        ini_level = children[index][0]
        for i in range(index, len(children)):
            if children[i][0] == ini_level + 1:
                if children[i][1].displayname == 'getService':
                    ignore = True
                else:
                    ignore = False
            if not ignore and children[i][1].kind == CursorKind.DECL_REF_EXPR and children[i][
                1].displayname != 'getService':
                var = children[i][1].displayname
                print('.line 396 ')
                print('var:', var)
                break
            if children[i][1].kind == CursorKind.STRING_LITERAL:
                print('.line 399 ')
                print('service_string', children[i][1].displayname)
                return_class = self.service_str_trans(children[i][1].displayname)
                print('return_class:', return_class)
                return return_class
        for i in range(0, index):
            if children[i][1].kind == CursorKind.VAR_DECL and children[i][1].displayname == var:
                print('.line 404 ')
                print('found var', var)
                start2find_var = True
            if start2find_var and children[i][1].kind == CursorKind.STRING_LITERAL:
                print('.line 407 ')
                print('service_string', children[i][1].displayname)
                return_class = self.service_str_trans(children[i][1].displayname)
                print('return_class:', return_class)
                return return_class

    def find_var_local(self, str, children, parent_node, so_far=None, DEBUG=True):
        print('\n****** find_var_local ******')
        if str == 'player':
            print('sssss')
        print('find var:', str, '| at', self.fully_qualified_pretty(parent_node), parent_node.location)
        declare_mode = False
        assign_left = False
        assign_mode = False
        last_level = 10e10
        assign_mode_last_level = 10e10
        for i, tem in enumerate(children):
            if tem[1].kind == CursorKind.PARM_DECL and tem[1].displayname == str:
                for i2 in range(i, len(children)):
                    # Know the number of parameters, find the method of passing in this parameter, and get the type of that parameter assignment
                    if children[i2][1].kind == CursorKind.TYPE_REF and children[i2][1].displayname.startswith('class '):
                        return_class = children[i2][1].displayname
                        return_class = return_class.replace('class ', '')
                        return_class = return_class.replace('::I', '::')
                        print('.line 490')
                        print('return_class:', return_class)
                        return 'END'

            if tem[1].kind == CursorKind.CALL_EXPR and tem[1].displayname == 'getService':
                # If the input parameter of the function has the variable to be found
                tem_level = tem[0]
                print('getService tem_level =', tem_level)
                for tem_i in range(i + 1, len(children)):
                    print('getService|', ' ' * children[tem_i][0], children[tem_i][1].kind,
                          children[tem_i][1].displayname)
                    if children[tem_i][0] <= tem_level:
                        break
                    if children[tem_i][1].kind == CursorKind.DECL_REF_EXPR and children[tem_i][1].displayname == str:
                        print('.line 458 Parameter gets a service class')
                        return_class = self.getService(i, children)
                        return return_class

            if DEBUG:
                print(tem[0], 'full|', ' ' * tem[0], tem[1].kind, tem[1].displayname)

            if tem[1].displayname == str:
                if tem[1].kind == CursorKind.VAR_DECL:
                    declare_mode = True
                    last_level = tem[0]
                elif tem[1].kind == CursorKind.DECL_REF_EXPR:
                    # Find the left side of the equal sign
                    assign_left = True
                    '''
                    7 full|         CursorKind.COMPOUND_STMT 
                    8 full|          CursorKind.CALL_EXPR operator=
                    9 full|           CursorKind.UNARY_OPERATOR 
                    10 full|            CursorKind.UNEXPOSED_EXPR server
                    11 full|             CursorKind.DECL_REF_EXPR server
                    9 full|           CursorKind.UNEXPOSED_EXPR operator=
                    10 full|            CursorKind.DECL_REF_EXPR operator=
                    9 full|           CursorKind.UNEXPOSED_EXPR s
                    10 full|            CursorKind.DECL_REF_EXPR s
                    '''
                    for tem_i in range(i - 1, 0, -1):
                        if children[tem_i][1].kind == CursorKind.CALL_EXPR and children[tem_i][
                            1].displayname == 'operator=':
                            assign_mode_last_level = children[tem_i][0]
                            break
                    print('assign_mode_last_level =', assign_mode_last_level)
                    print('*** found var ***')
                    print(tem[0], 'var 468|', ' ' * tem[0], tem[1].kind, tem[1].displayname)

            if declare_mode and tem[0] < last_level:
                declare_mode = False
                last_level = 10e10
            if declare_mode and tem[0] > last_level:
                if tem[1].kind == CursorKind.CALL_EXPR and declare_mode and tem[1].displayname != '' and tem[
                    1].displayname != 'sp':
                    print('****** CursorKind.CALL_EXPR ******')
                    print(tem[1].referenced.displayname)
                    method_full = self.fully_qualified_pretty(tem[1].referenced)
                    print(tem[1].referenced.kind, method_full)
                    if tem[1].referenced.kind == CursorKind.CONSTRUCTOR:
                        return_class = self.fully_qualified(tem[1].referenced.semantic_parent)
                        print(return_class)
                        return return_class
                    # Replace IxxxService:: directly with xxxService::
                    print('.line 575 Replace IxxxService:: directly with xxxService::')

                    tema = re.findall(r'I[A-Z][a-z][a-zA-Z]+?::', method_full)
                    for temb in tema:
                        print(temb)
                        method_full = method_full.replace(temb, temb[1:])
                    print(method_full)
                    print(tem[1].displayname, tem[1].displayname != 'GetLongField')
                    if (tem[1].displayname != 'GetLongField'):
                        entry_funs, entry_fun_vs = self.search_fun(method_full)
                        print('.line 237')
                        if len(entry_funs) == 0:
                            print('.line 614 Unprocessed block out')
                            return 'END'
                        return_class = self.get_return(entry_fun_vs[0], parent_node, level=tem[0] + 1)
                        print('\n', return_class)

                        return return_class
                    # Find the type of this variable in children

            # When the left side is found, the non-subtree exits
            if assign_left and tem[0] < assign_mode_last_level:
                assign_left = False
                assign_mode_last_level = 10e10

            # When you find the left, see if you find the right
            if assign_left and tem[0] >= assign_mode_last_level:
                print(tem[0], 'var(find right)|', ' ' * tem[0], tem[1].kind, tem[1].displayname)

                if 'operator=' in tem[1].displayname:
                    # assignment
                    assign_mode = True

                elif assign_mode and tem[1].kind == CursorKind.CXX_NEW_EXPR:
                    print('.line 424')
                    print(children[i + 1][1].kind)
                    if children[i + 1][1].kind == CursorKind.TYPE_REF:
                        assert children[i + 1][1].displayname.startswith('class ')
                        return_class = children[i + 1][1].displayname[6:]
                        print('.line 429')
                        print(return_class)
                        return return_class
                elif assign_mode and tem[1].kind == CursorKind.CALL_EXPR:
                    print('.line 434')
                    print('invoke method: get return class |||', tem[1].kind)
                    fun_str = self.fully_qualified_pretty(tem[1].referenced)
                    print('DEBUG ', fun_str)
                    print(fun_str, tem[1].location)
                    if 'interface_cast' in fun_str:
                        for tem_i in range(i + 1, len(children)):
                            print(children[tem_i][0], 'interface_cast|', ' ' * children[tem_i][0],
                                  children[tem_i][1].kind, children[tem_i][1].displayname)
                            if children[tem_i][1].kind == CursorKind.TYPE_REF:
                                return_class = children[tem_i][1].displayname
                                return_class = return_class.replace('class ', '')
                                return_class = return_class.replace('::I', '::')
                                print('.line 574')
                                print(return_class)
                                return return_class
                    strinfo = re.compile('<.{0,}?>')
                    fun_str_revised = strinfo.sub('<>', fun_str)
                    print('fun_str_revised(Remove <...> template content):', fun_str_revised)
                    print('.line 437')
                    if self.has_no_ignore_fun(fun_str_revised):
                        entry_funs, entry_fun_vs = self.search_fun(fun_str_revised)
                    else:
                        return 'END'
                    # print(entry_fun_vs[0].location)
                    assert len(entry_fun_vs) == 1, 'No function found or too many functions ' + tem[1].referenced.displayname
                    print('.line 444')
                    return_class = self.get_return(entry_fun_vs[0], parent_node)
                    print(return_class)
                    # exit(2)

                    # assign_mode = False
                    if return_class != None:
                        return return_class
                    pass

                elif assign_mode and tem[1].kind == CursorKind.DECL_REF_EXPR:
                    print('Assigned by the variable on the right', tem[1].displayname)
                    return self.find_var_local(tem[1].displayname, children, parent_node)

    def get_return(self, node, parent_node, level=0, debug=False):
        print('\n*** get_return ***\n', node.kind, self.fully_qualified_pretty(node), node.location)

        # If the function points to the Binder, modify it to a real function
        method_full = self.fully_qualified_pretty(node)
        if 'android::hardware::' in method_full or '::asInterface' in method_full:
            return

        # TO If IxxxService:: replace directly
        # Replace IxxxService:: directly with xxxService::
        # ::IDrm:: YES ::IPCThreadState:: NO
        r_final = re.findall(r'::I[A-Z][a-z].+?::', method_full)
        if len(r_final) > 0 and self.has_no_ignore_fun(method_full):
            tema = re.findall(r'I[a-zA-Z]+?Service::', method_full)
            if self.not_has_ignore_fun_Ixx(method_full) and len(tema) > 0:
                print('Before replacement', method_full)

                for temb in tema:
                    print(temb)
                    method_full = method_full.replace(temb, temb[1:])
                print('After replacement', method_full)
                k_list, v_list = self.search_fun_list_full(method_full)
                print('.line 267')
                print('LINK to the next method:')
                print(method_full)
                print('change to', k_list[0], v_list[0].location)
                print('.line 548')
                print('*** Continue to print call graph**** as normal')
                node = v_list[0]
            elif self.not_has_ignore_fun_Ixx(self.fully_qualified_pretty(node)):
                print('.line 269')
                return_class = self.link_binder(parent_node, node)
                if return_class == 'no_caller':
                    print('no_caller, Return the class in sp')
                    exit(8)
                print('.line 277')
                print('LINK to the next method:')
                print(self.fully_qualified_pretty(parent_node), '=>')
                print(self.fully_qualified_pretty(node))
                fun_str = return_class + '::' + node.displayname
                print('change to', fun_str)
                strinfo = re.compile('<.{0,}?>')
                fun_str_revised = strinfo.sub('<>', fun_str)
                print('fun_str_revised(Remove <...> template content):', fun_str_revised)
                print('function in self.CALLGRAPH:', fun_str_revised in self.CALLGRAPH)
                if self.has_no_ignore_fun(fun_str_revised) and 'END' not in return_class:
                    k_list, v_list = self.search_fun_list_full(fun_str_revised)
                else:
                    return 'END'
                print('.line 573')
                print('*** 继续正常打印call graph****')
                print(k_list[0], v_list[0].location, '=> ...')
                node = v_list[0]
            elif '::getService' in self.fully_qualified_pretty(node):
                print('Ignore the Binder of the implicit Service for now')
                return 'END'
            else:
                print('*** ignore IServiceManager:: method ****', self.fully_qualified_pretty(node))

        children = []
        self.get_all_children(node, children, level=level)
        TEMPLATE_REF_list = []

        return_mode = False
        last_return_level = 10e10
        single_var_return = True

        for tem in children:
            if debug:
                print(tem[0], ' ' * tem[0], tem[1].kind, tem[1].displayname, end='')
            type = tem[1].type
            if debug:
                print('|type:', type.kind, end='')

            if tem[1].kind == CursorKind.RETURN_STMT:
                return_mode = True
                last_return_level = tem[0]

            if tem[0] < last_return_level:
                return_mode = False
                last_return_level = 10e10
            if tem[0] > last_return_level:
                if tem[1].kind == CursorKind.MEMBER_REF_EXPR:
                    print('.line 325')
                    print('*** return CursorKind.MEMBER_REF_EXPR ***')
                    return_class = self.find_var(tem[1].displayname, tem[1].location.file.name)
                    assert return_class is not None
                    return return_class
                elif tem[1].kind == CursorKind.CONDITIONAL_OPERATOR:
                    single_var_return = False
                elif tem[1].kind == CursorKind.DECL_REF_EXPR and single_var_return:
                    print('\n****** CursorKind.DECL_REF_EXPR ******')
                    print(tem[1].displayname)
                    print('.line 343')
                    if tem[1].displayname:
                        return_class = self.find_var_local(tem[1].displayname, children, node)
                    assert return_class is not None
                    # Find the type of this variable in children
                    return return_class
            # Don't use call_expr for template functions like sp
            if tem[1].kind == CursorKind.TEMPLATE_REF:
                if tem[1].displayname not in TEMPLATE_REF_list:
                    TEMPLATE_REF_list.append(tem[1].displayname)

            if tem[1].kind == CursorKind.CALL_EXPR and tem[1].displayname not in TEMPLATE_REF_list:
                if tem[1].referenced is not None and return_mode:
                    return_mode = False
                    last_return_level = 10e10
                    print('.line 347')
                    return_class = self.get_return(tem[1].referenced, parent_node, level=tem[0] + 1)
                    print('\n*** END END END analyze_fun ***')
                    if return_class != None:
                        return return_class

            elif tem[1].kind == CursorKind.INTEGER_LITERAL:
                value = tem[1].get_tokens()
                if debug:
                    for v in value:
                        print('', v.spelling, end='')

            elif type.kind == TypeKind.RECORD:
                value = type.spelling
                if debug:
                    print('', value, end='')
                if return_mode:
                    return type.spelling

            elif (tem[1].kind == CursorKind.TYPE_REF and type.kind == TypeKind.UNEXPOSED):
                if debug:
                    print(type.spelling, end='')

            if debug:
                print()

    def get_caller(self, last, current, so_far=None, debug=True):

        print('\n*** get_caller ***\nsearch in method:', last.kind, last.displayname, last.location)
        print('to find', current.displayname)
        children = []
        self.get_all_children(last, children, level=0)
        TEMPLATE_REF_list = []

        found_CALL_EXPR = False
        found_operator = False
        CALL_EXPR = ''
        last_level = 10e10
        for tem in children:
            if debug:
                print(tem[0], ' ' * tem[0], tem[1].kind, tem[1].displayname, end='')

            if tem[1].kind == CursorKind.CALL_EXPR and tem[1].referenced is not None and tem[
                1].referenced.displayname == current.displayname:
                found_CALL_EXPR = True
                CALL_EXPR = tem[1].displayname
                print('found_CALL_EXPR = True')
                last_level = tem[0]
            if tem[0] < last_level:
                found_CALL_EXPR = False
                found_operator = False
                last_level = 10e10
            if tem[0] > last_level and found_CALL_EXPR and not found_operator and tem[1].displayname == 'operator->':
                print('found_operator = True')
                found_operator = True
            if tem[0] > last_level and found_operator and tem[1].kind == CursorKind.MEMBER_REF_EXPR:
                return tem[1].displayname, 'global'
            if tem[0] > last_level and found_operator and tem[1].kind == CursorKind.DECL_REF_EXPR:
                if tem[1].displayname == CALL_EXPR:
                    '''
                    6        CursorKind.CALL_EXPR getBuiltInDisplay
                    7         CursorKind.MEMBER_REF_EXPR getBuiltInDisplay
                    8          CursorKind.CALL_EXPR operator->
                    9           CursorKind.UNEXPOSED_EXPR 
                    10            CursorKind.UNEXPOSED_EXPR 
                    11             CursorKind.CALL_EXPR getComposerService
                    12              CursorKind.UNEXPOSED_EXPR getComposerService
                    13               CursorKind.DECL_REF_EXPR getComposerService
                    '''
                    print('.line 864')
                    return '', 'no_caller'
                if tem[1].displayname != 'interface_cast':
                    print('.line 862')
                    return tem[1].displayname, 'local'
                else:
                    print('\t Ignore interface_cast without terminating')
                    continue
            if debug:
                print()

        # No call in var -> xxx format was found
        return None, 'no_caller'

    def link_binder(self, last, current, so_far=None):
        # Used to find the function actually pointed to by Bind
        print('\n******* link_binder ******')
        print('|last:', last.kind, last.displayname)

        print('.line 426')
        r, scope = self.get_caller(last, current, so_far)
        print('\nr, scope:', r, scope)
        print('\n******* link_binder children ENDENDEND******')
        file = last.location.file.name

        return_class = None
        if scope == 'global':
            print('.line 432')
            return_class = self.find_var(r, file)
        elif scope == 'local':
            children = []
            print('.line 436')
            self.get_all_children(last, children)
            return_class = self.find_var_local(r, children, last, so_far)
        elif scope == 'no_caller':
            print('no caller, does not analyze')
            return 'no_caller'

        else:
            print('unhandled scope.')
        print('.line 447')
        print('link_binder:', return_class)

        if return_class is None:
            return 'no_caller'
        return return_class

    def _get_num_comparision_operator(self, cursor):
        count = 0
        tem = ''
        for token in cursor.get_tokens():
            tem = tem + token.spelling + ' '
        tem = tem[:-1]
        COMPARISION_OPERATORS = ['==', '<=', '>=', '<', '>', '!=', '&&', '||']
        for temCOMPARISION_OPERATORS in COMPARISION_OPERATORS:
            tem = tem.replace(temCOMPARISION_OPERATORS, temCOMPARISION_OPERATORS + '@@')
        ori_tem = tem.split('@@')
        for tem in ori_tem:
            if '(' in tem and ')' in tem:
                count = count + 1
        return count

    def _contain_comparision_operator(self, cursor):
        COMPARISION_OPERATORS = ['==', '<=', '>=', '<', '>', '!=', '&&', '||']
        for token in cursor.get_tokens():
            if token.spelling in COMPARISION_OPERATORS:
                return True
        return False


    def _return_condition(self, cursor, debug=True):
        ooo = cursor.get_tokens()
        str = ''
        for tem in ooo:
            if debug:
                print('|', tem.kind, tem.spelling, end=' ')
            str = str + tem.spelling + ' '

        return str[:-1]

    def _get_binop_operator(self, cursor, get_left_right=False):

        children = list(cursor.get_children())

        operator_min_begin = (children[0].location.line,
                              children[0].location.column)
        operator_max_end = (children[1].location.line,
                            children[1].location.column)
        left = children[0].displayname
        if children[0].kind == CursorKind.CALL_EXPR:
            left = left + ' ( )'
        right = children[1].displayname
        if children[1].kind == CursorKind.CALL_EXPR:
            right = right + ' ( )'

        for token in cursor.get_tokens():
            if (operator_min_begin < (token.extent.start.line,
                                      token.extent.start.column) and
                    operator_max_end >= (token.extent.end.line,
                                         token.extent.end.column)):
                if get_left_right:
                    return left, token.spelling, right
                else:
                    return token.spelling
        if get_left_right:
            return None, None, None
        else:
            return None

    def _analyze_switch(self, cursor, debug=False):
        case_flag = False
        return_flag = False
        switch_flag = False
        switch_var = None
        cond = {}
        tokens = cursor.get_tokens()
        for tem in tokens:
            if debug:
                print('|', tem.kind, tem.spelling, end=' ')

            if tem.kind == TokenKind.KEYWORD and tem.spelling == 'switch':
                switch_flag = True
            elif tem.kind == TokenKind.IDENTIFIER and switch_flag:
                switch_flag = False
                switch_var = tem.spelling
            elif tem.kind == TokenKind.KEYWORD and tem.spelling == 'case':
                case_flag = True
            elif tem.kind == TokenKind.IDENTIFIER and case_flag:
                case_flag = False
                cond[tem.spelling] = None
            elif tem.kind == TokenKind.KEYWORD and tem.spelling == 'return':
                return_flag = True
            elif tem.kind == TokenKind.IDENTIFIER and return_flag:
                return_flag = False
                keys = cond.keys()
                for key in keys:
                    if cond[key] == None:
                        cond[key] = tem.spelling
            elif tem.kind == TokenKind.KEYWORD and tem.spelling == 'default':
                cond[tem.spelling] = None

        if debug:
            print()
            print('=============cond======\n', cond)
        return switch_var, cond

    def _get_fun_con(self, cursor, debug=True):
        print('|||||||||||cursor|||', cursor.kind, cursor.displayname, cursor.location)
        ori_cursor = cursor
        cursor = cursor.referenced
        fun_str = self.fully_qualified_pretty(cursor)
        str_return_cond = fun_str
        print(fun_str)
        return_cond = []
        print('.line 1060', cursor.location.file.name)

        tem_head = cursor.location.file.name
        if tem_head.endswith('.h'):
            print('.line 1066 方法在.h中定义 需要扩展分析cpp', tem_head)
            c_cpp_list = find_command(tem_head, version_prefix='7.0', compdb=True, project_path=project_path)

            if c_cpp_list is not None and project_path + c_cpp_list['file'] not in self.analyzed_cpp:

                next_file = project_path + c_cpp_list['file']
                self.analyzed_cpp.add(next_file)
                print('.line 1074', next_file)

                if not (
                        'MediaClock.cpp' in next_file or 'AString.cpp' in next_file or 'MediaSync.cpp' in next_file or 'MediaBuffer.cpp' in next_file):
                    print('pass: ', next_file)

                    ninja_args = c_cpp_list['command'].split()[1:]
                    ninja_args = self.parse_ninja_args(ninja_args)

                    if 'clang++' in c_cpp_list['command'].split()[0]:
                        self.load_cfg(self.index, 'clang++', next_file, ninja_args)
                    else:
                        self.load_cfg(self.index, 'clang', next_file, ninja_args)

            k_list, v_list = self.search_fun_list_full(self.fully_qualified_pretty(cursor))
            found = False
            for v_list_tem in v_list:
                if not v_list_tem.location.file.name.endswith('.h'):
                    print(k_list)
                    print(v_list[0].displayname)
                    print(v_list[0].kind)
                    print(v_list[0].location)
                    cursor = v_list[0]
                    found = True
                    break
            if not found:
                print('_get_fun_con||No method in cpp')
                print(str_return_cond)
                return str_return_cond

        if debug:
            print('.line 1079 |||||||||||cursor.referenced|||', cursor.kind, cursor.displayname, cursor.location)
        children = []
        self.get_all_children(cursor, children, level=0)
        print('.line 1082 len(children):', len(children))
        mode = None
        for child in children:
            node = child[1]
            if node.kind == CursorKind.SWITCH_STMT:
                mode = 'switch'
                break
            if 'checkCallingPermission' in node.displayname or 'checkPermission' in node.displayname:
                mode = 'permission'
                break
        if mode == 'switch':
            for child in children:
                node = child[1]
                if debug:
                    print('.line 1096 |||||||||||', node.kind, node.displayname, node.location)

                if node.kind == CursorKind.SWITCH_STMT:
                    var, conds = self._analyze_switch(node)
                    for key in conds.keys():
                        if conds[key] == 'true':
                            return_cond.append(key)

            str_return_cond = ''
            for tem in return_cond:
                str_return_cond = str_return_cond + var + ' == ' + tem + ' || '
            str_return_cond = str_return_cond[:-4]
        elif mode == 'permission':
            for child in children:
                node = child[1]
                if debug:
                    print('.line 1112|||||||permission||||', node.kind, node.displayname)
                if (
                        'checkCallingPermission' in node.displayname or 'checkPermission' in node.displayname) and node.kind == CursorKind.CALL_EXPR:
                    str_return_cond = self.getPermission(node)

        if debug:
            print('.line 1117 ', str_return_cond)

        return str_return_cond

    def _get_fun_in_condition(self, cursor, num=1, debug=False):
        children = []
        self.get_all_children(cursor, children, level=0)
        funs = []
        for child in children:
            level = child[0]
            node = child[1]
            if debug:
                print('|', level, ' ' * level, node.kind, node.displayname)
            if node.kind == CursorKind.CALL_EXPR:
                method = node.referenced

                funs.append(node)
                if debug:
                    print('&&& Added a node', node.kind, node.displayname, node.location)
                    print('&&& node.referenced', method.kind, method.displayname, method.location)
                    children = []
                    self.get_all_children(method, children, level=0)
                    print('len(children)', len(children))
                if len(funs) >= num:
                    return funs
        return funs

    def _if_contains_elif(self, cursor, debug=False):
        if cursor is None:
            return False
        children = []
        self.get_all_children(cursor, children, level=0)
        for child in children:
            level = child[0]
            node = child[1]
            if node.kind == CursorKind.IF_STMT:
                return True
        return False

    def _is_secure_condition(self, cursor, debug=False):
        if cursor is None:
            return False
        children = []
        self.get_all_children(cursor, children, level=0)
        for child in children:
            level = child[0]
            node = child[1]
            if debug:
                print('|', level, ' ' * level, node.kind, node.displayname)
            if 'PERMISSION_DENIED' in node.displayname:
                return True
            if 'checkPermission' in node.displayname:
                return True
        return False

    def _get_unaryop_operator(self, cursor, debug=True):
        for tem in cursor.get_tokens():
            if debug:
                print('|', tem.kind, tem.spelling, end=' ')

        children = list(cursor.get_children())
        operator_min_begin = (children[0].location.line,
                              children[0].location.column)

        left = children[0].displayname
        if children[0].kind == CursorKind.CALL_EXPR:
            left = left + ' ( )'

        for token in cursor.get_tokens():
            if operator_min_begin > (token.extent.start.line,
                                     token.extent.start.column):
                return left, token.spelling

        return None, None

    def show_info(self, node, cur_fun=None, depth=0, print_node=False, if_stmt=None, last_node=None,
                  case_identifier=[''], case_mode=[False], case_level=[10e10]):

        fun_str = self.fully_qualified_pretty(node)

        # debug
        if node.location.file and (self.print_all_node or print_node) and self.pro_path in node.location.file.name:
            print('\n1358|%2d' % depth + ' ' * depth, node.kind, node.spelling, '|current case_identifier:',
                  case_identifier[0], end='')


        if node.kind == CursorKind.IF_STMT:
            if_stmt = node

        # path start
        if node.kind == CursorKind.FUNCTION_TEMPLATE or node.kind == CursorKind.CONSTRUCTOR:
            cur_fun = node
            fun_str = self.fully_qualified_pretty(cur_fun)
            # No or location is in cpp
            if fun_str not in self.FULLNAMES.keys() or cur_fun.location.file.name.endswith('.cpp'):
                self.FULLNAMES[fun_str] = cur_fun

        if node.kind == CursorKind.CXX_METHOD or \
                node.kind == CursorKind.FUNCTION_DECL:
            cur_fun = node
            fun_str = self.fully_qualified_pretty(cur_fun)
            if fun_str not in self.FULLNAMES.keys() or cur_fun.location.file.name.endswith('.cpp'):
                self.FULLNAMES[fun_str] = cur_fun

        # A call is found in a function, then add this function -> the mapping of the calling function to the call graph
        if node.kind == CursorKind.CALL_EXPR:

            if node.referenced:
                fun_str = self.fully_qualified_pretty(cur_fun)
                if cur_fun is not None and self.pro_path in cur_fun.location.file.name:
                    self.CALLGRAPH[fun_str].append(node)

        # case add to graph
        if node.kind == CursorKind.CASE_STMT:
            case_identifier[0] = ''
            case_mode[0] = True
            case_level[0] = depth

        elif case_mode[0] and depth <= case_level[0]:
            case_mode[0] = False
            case_level[0] = 10e10

        elif case_mode[0] and depth > case_level[0] and node.kind == CursorKind.UNEXPOSED_EXPR:
            case_identifier[0] = node.spelling
            case_mode[0] = False
            case_level[0] = 10e10

        # add if to graph
        if node.kind == CursorKind.BINARY_OPERATOR and self._is_secure_condition(if_stmt):
            if self._contain_comparision_operator(node):
                condition = self._return_condition(node)
                print('\n***', condition, '*** CursorKind.BINARY_OPERATOR')
                print(self._if_contains_elif(if_stmt))
                # Transform node to exist as a conditional branch
                confition_funs = self._get_fun_in_condition(node, self._get_num_comparision_operator(node))

                if self._if_contains_elif(if_stmt):
                    node._if_contain_functions = confition_funs
                    node._displayname = '==CONDITION==' + case_identifier[0] + '*!(' + condition + ') &&'
                    print(node._displayname)

                else:

                    node._if_contain_functions = confition_funs
                    node._displayname = '==CONDITION==' + case_identifier[0] + '*' + condition
                    print(node._displayname)
                    # exit(0)
                node._spelling = node._displayname
                node._referenced = node
                # node._kind_id = 8625

                # Add the condition in the graph
                fun_str = self.fully_qualified_pretty(cur_fun)
                if cur_fun is not None and self.pro_path in cur_fun.location.file.name:
                    # Find the function call (node) in a function (fun_str), join the call graph
                    self.CALLGRAPH[fun_str].append(node)

                if_stmt = None


        elif node.kind == CursorKind.UNARY_OPERATOR and self._is_secure_condition(if_stmt):

            # Get function
            # Get operator
            left, binop = self._get_unaryop_operator(node)
            if left and binop:
                condition = binop + ' ' + left
                print('\n***', condition, '*** CursorKind.UNARY_OPERATOR')
                # Transform node to exist as a conditional branch
                confition_funs = self._get_fun_in_condition(node)

                node._if_contain_functions = confition_funs
                node._displayname = '==CONDITION==' + case_identifier[0] + '*' + condition
                node._spelling = node._displayname
                print(node._displayname)

                node._referenced = node
                fun_str = self.fully_qualified_pretty(cur_fun)
                if cur_fun is not None and self.pro_path in cur_fun.location.file.name:
                    # Find the function call (node) in a function (fun_str), join the call graph
                    self.CALLGRAPH[fun_str].append(node)

            if_stmt = None


        for c in node.get_children():
            self.show_info(c, cur_fun, depth=depth + 1, print_node=print_node, if_stmt=if_stmt, last_node=node,
                           case_identifier=case_identifier, case_mode=case_mode, case_level=case_level)

    def pretty_print(self, n):
        v = ''

        if self.show_loc:
            return self.fully_qualified_pretty(n) + v + "|" + str(n.location)
        else:
            return self.fully_qualified_pretty(n) + v

    def search_fun(self, fun_name):
        return self.search_fun_list_full(fun_name)

    def search_fun_list_full(self, fun_name):
        fun_name = fun_name.replace('const ', '')
        fun_name = fun_name.replace('struct ', '')
        fun_name = fun_name.replace('_t', '')
        fun_names = fun_name.split('(')
        fun_names[1] = re.sub('([a-zA-Z0-9]+? )([a-zA-Z0-9]+?::)+', '', fun_names[1])
        fun_name = fun_names[0] + '(' + fun_names[1]
        print('*** search for fun %s ***\n' % fun_name)
        full_fun_name = re.sub('\(.+?\)', r'', fun_name)
        print(full_fun_name)
        k_list = []
        v_list = []
        for k, v in self.FULLNAMES.items():
            k4match = k
            k4match = k4match.replace('const ', '')
            k4match = k4match.replace('struct ', '')
            k4match = k4match.replace('_t', '')
            k4matchs = k4match.split('(')
            k4matchs[1] = re.sub('([a-zA-Z0-9]+? )([a-zA-Z0-9]+?::)+', '', k4matchs[1])
            k4match = k4matchs[0] + '(' + k4matchs[1]
            if full_fun_name in k4match:
                print('search_fun_list_full Found similar fun -> \n' + k4match)
            if fun_name in k4match:
                print('search_fun_list_full Found fun -> ' + k)
                k_list.append(k)
                v_list.append(v)

        return k_list, v_list

    def search_fun_list(self, fun_name):
        list = []
        for k, v in self.FULLNAMES.items():
            if fun_name in k:
                print('Found fun -> ' + k)
                list.append(v)
        return list

    def getPermission(self, node):
        print(node.kind, node.spelling)
        if node is None:
            return None

        # get_tokens
        for tem in node.get_tokens():
            if 'permission.' in tem.spelling:
                return tem.spelling

        if self.pro_path in node.location.file.name:
            if node.kind == CursorKind.DECL_REF_EXPR:
                node = node.referenced

            if node is None:
                return None

            if node.kind == CursorKind.STRING_LITERAL:
                if 'permission.' in node.spelling:
                    return node.spelling

            for n in node.get_children():
                if n is not None:
                    print('.line 1564 ', node.kind, node.spelling)
                    return_str = self.getPermission(n)
                    if return_str:
                        return return_str
        return None

    def get_para(self, node):
        if node is None:
            return 'None'

        if self.pro_path in node.location.file.name:
            if node.kind == CursorKind.DECL_REF_EXPR:
                node = node.referenced

            if node is None:
                return 'None'

            if node.kind == CursorKind.STRING_LITERAL:
                if node.spelling != '""':
                    return node.spelling

            for n in node.get_children():
                return_str = self.get_para(n)
                if return_str is not None:
                    return return_str
        return 'None'

    def print_childrens(self, node, service_names, depth):
        if node is not None and node.location.file is not None and self.pro_path in node.location.file.name:
            for n in node.get_children():
                print('1664| %2d' % depth + ' ' * depth, n.kind, n.spelling, end=' | ')
                ooo = n.get_tokens()
                tokens_key = []
                tokens_val = []
                for tem in ooo:
                    tokens_key.append(tem.spelling)
                    tokens_val.append(tem)
                for token in tokens_key:
                    print(token, end='')

                if n.kind == CursorKind.DECL_REF_EXPR and 'getServiceName' in tokens_key:
                    key_name = ''
                    for tem in self.FULLNAMES.keys():
                        if 'getServiceName' in tem:
                            key_name = tem
                    tem_node = self.FULLNAMES[key_name]
                    service_name = self.get_para(tem_node)
                    # The binding of the binder's characters and the cpp file is required
                    print(" " + service_name, end='')
                    service_names.append([service_name, n.location.file.name])
                elif n.kind == CursorKind.DECL_REF_EXPR and 'getService' in tokens_key:
                    key_name = ''
                    for tem in self.FULLNAMES.keys():
                        if 'getService' in tem:
                            key_name = tem
                    tem_node = self.FULLNAMES[key_name]
                    service_name = self.get_para(tem_node)
                    # The binding of the binder's characters and the cpp file is required
                    print(" " + service_name, end='')
                    service_names.append([service_name, n.location.file.name])

                print()

                if n.kind == CursorKind.STRING_LITERAL:
                    service_name = n.spelling
                    service_names.append([n.spelling, n.location.file.name])

                if n.kind == CursorKind.DECL_REF_EXPR:
                    n = n.referenced

                    if n is not None:
                        print('%2d' % depth + ' ' * depth, n.kind, n.spelling, end=' | ')
                        if n.kind == CursorKind.ENUM_CONSTANT_DECL:
                            print('!!!!!!!!CursorKind.ENUM_CONSTANT_DECL', node.spelling)
                            service_names.append([node.spelling, n.location.file.name])
                        ooo = n.get_tokens()
                        for tem in ooo:
                            print(tem.spelling, end=' ')

                        print()
                if n is not None:
                    self.print_childrens(n, service_names, depth=depth + 1)

    def get_print_ndoe(self, fun_name, so_far, graphs, depth=0):
        found = False
        for k, v in self.CALLGRAPH.items():
            for f in v:
                f = f.referenced
                # Child node found
                if self.fully_qualified_pretty(f) == fun_name or self.fully_qualified(f) == fun_name:
                    if k in so_far:
                        continue
                    so_far.append(k)
                    # Return to the parent node
                    found = True
                    self.get_print_ndoe(k, so_far, graphs, depth + 1)
        if found == False:
            graphs.append(so_far)

    def has_no_ignore_fun(self, str):
        # The list does not exist, return True
        # Existing one returns False
        # Ignore the Binder-related classes at the bottom of the system
        ignore_fun_list = ['Binder', 'IInterface', 'setListener', 'sp', 'IServiceManager', 'IPermissionController']
        for tem_ignore in ignore_fun_list:
            if tem_ignore + '::' in str:
                return False
        return True

    def not_has_ignore_fun_Ixx(self, str):
        # The list does not exist, return True
        # Existing one returns False
        # Ignore the Ixxx system related classes at the bottom of the system
        ignore_fun_list = ['IServiceManager', 'IMemory']
        for tem_ignore in ignore_fun_list:
            if tem_ignore + '::' in str:
                return False
        return True

    def _replace_condition_fun(self, ori, replace):
        COMPARISION_OPERATORS = ['==', '<=', '>=', '<', '>', '!=', '&&', '||']
        tem = ori
        for temCOMPARISION_OPERATORS in COMPARISION_OPERATORS:
            tem = tem.replace(temCOMPARISION_OPERATORS, temCOMPARISION_OPERATORS + '@@')
        ori_tem = tem.split('@@')
        print('++++++++++')
        print('ori_tem', ori_tem)
        ori_tem_only_fun = []
        tem = ''
        for k, v in enumerate(ori_tem):
            tem = tem + v
            if '(' in v and ')' in v:
                ori_tem_only_fun.append(tem)
                tem = ''

        print(ori)
        print(ori_tem)
        print(len(replace))
        print(replace)
        print(len(ori_tem_only_fun))
        print(ori_tem_only_fun)

        return_str = ''
        assert len(replace) == len(ori_tem_only_fun), len(replace) + len(ori_tem_only_fun)
        for k, v in enumerate(replace):
            if v:
                print('th', k,'items,','to be replaced with', v)
                print('Before replacement', ori_tem_only_fun[k])
                if 'strncmp' in ori_tem_only_fun[k]:
                    print('Intercepted', ori_tem_only_fun[k])
                elif 'std::__1' not in v:
                    ori_tem_only_fun[k] = re.sub(r'[a-zA-Z0-9_]+ \(.+\)', '(' + v + ')', ori_tem_only_fun[k])
                print('After replacement', ori_tem_only_fun[k])
            return_str = return_str + ori_tem_only_fun[k]
        print('Ultimately adopted conditions', return_str)
        print('======')

        return return_str

    def I_find_no_I(self, h):
        # Find the header file location of the file without I
        # Remove the I in the complete directory and find the full path of cpp without I.
        # Find the path of h in the cpp header without I
        temmm = re.findall(r'I[a-zA-Z]+?Service', h)
        h = h.replace(temmm[0], temmm[0][1:])
        f = os.path.basename(h).replace('.h', '.cpp')
        print('The cpp file you are looking for', f)
        h_no_I = ''
        for tem in self.file_tu.keys():
            if f in tem:
                print(tem)
                for temm in self.file_tu[tem].get_includes():
                    include_path = temm.include.name
                    print(include_path)
                    if '/' + f.replace('.cpp', '.h') in include_path:
                        h_no_I = include_path
        print(h_no_I)

        return h_no_I

    def extract_onTransact(self, node, identifier, conditions, depth=0, case_mode=False, case_level=10e10):
        if node is not None and node.location.file is not None and self.pro_path in node.location.file.name:
            for n in node.get_children():
                print('1818| %2d' % depth + ' ' * depth, n.kind, n.spelling, end=' | ')
                print()
                print(
                    'case_mode and depth > case_level and n.kind == CursorKind.DECL_REF_EXPR and n.spelling == identifier',
                    case_mode and depth > case_level and n.kind == CursorKind.DECL_REF_EXPR and n.spelling == identifier)
                print('case_mode and depth > case_level', case_mode and depth > case_level)
                print('n.kind == CursorKind.DECL_REF_EXPR', n.kind == CursorKind.DECL_REF_EXPR)
                print('n.spelling == identifier', n.spelling == identifier)
                if n.kind == CursorKind.CASE_STMT:
                    case_mode = True
                    case_level = depth
                    print('case_mode changed', case_mode)
                    print('case_level changed', case_level)
                elif case_mode and depth <= case_level:
                    case_mode = False
                    case_level = 10e10
                    print('case_mode changed', case_mode)
                    print('case_level changed', case_level)
                elif case_mode and depth > case_level and n.kind == CursorKind.DECL_REF_EXPR and n.spelling == identifier:
                    print('.line 1831 find case \'s conditions')
                    self.print_childrens(node, conditions, depth + 2)
                    so_far = []
                    self.print_calls(self.fully_qualified_pretty(node), so_far, node, conditions, depth=depth + 1)

                if n is not None:
                    self.extract_onTransact(n, identifier, conditions, case_mode=case_mode, case_level=case_level,
                                            depth=depth + 1)

    def onTransact(self, identifier, onTransact_class):
        print(identifier)
        print(onTransact_class)
        k_list, v_list = self.search_fun_list_full(onTransact_class + '::onTransact(')
        node = None
        for tem_v_list in v_list:
            print(tem_v_list.location.file.name)
            if tem_v_list.location.file.name.endswith('.cpp'):
                print('Find the onTransact method：', tem_v_list.kind, self.fully_qualified_pretty(tem_v_list),
                      tem_v_list.location.file.name)
                node = tem_v_list
        if node:
            print('=============查找onTransact中的conditions====')
            print('.line 1837', node.kind, self.fully_qualified_pretty(node), node.location)
            conditions = []

            so_far = []
            self.print_calls(self.fully_qualified_pretty(node), so_far, node, conditions, depth=0)
            print('conditions', conditions)
            conditions_new = []
            print(identifier + '*')
            for tem in conditions:
                print(tem)
                if identifier + '*' in tem and 'err' not in tem:
                    tem = tem.replace(identifier + '*', '')
                    tem = tem.replace('PermissionCache :: ', '')
                    conditions_new.append(tem)
            print('conditions_new', conditions_new)

            return conditions_new

    def print_calls(self, fun_name, so_far, last_node, permission_strs, depth=0):
        if fun_name in self.CALLGRAPH:
            for f in self.CALLGRAPH[fun_name]:
                node = f
                f = f.referenced
                # string is ignored
                if (f.location.file is not None and self.pro_path in f.location.file.name):
                    log = self.pretty_print(f)
                    current_depth = depth
                    if '==CONDITION==' in log:
                        print(log)
                        speci_conds = []
                        str_con = log.replace('==CONDITION==', '')
                        for fun in node._if_contain_functions:
                            if 'check' in log and 'Permission' in self.pretty_print(fun):
                                speci_conds_tem = self.getPermission(fun)
                                speci_conds_tem = speci_conds_tem.replace(' PermissionCache :: ', '')
                                speci_conds.append(speci_conds_tem)
                                print('******* permission check', speci_conds_tem)

                            else:
                                speci_conds_tem = self._get_fun_con(fun)
                                speci_conds_tem = speci_conds_tem.replace(' PermissionCache :: ', '')
                                speci_conds.append(speci_conds_tem)
                                print('******* speci_conds_tem', speci_conds_tem)

                        if len(speci_conds) > 0:

                            str_con = self._replace_condition_fun(str_con, speci_conds)
                        print('|||[%s]' % str_con)
                        permission_strs.append(str_con)

                    elif 'addService' in log:
                        print('%2d' % current_depth, ' ' * (depth + 1) + log)
                        print('***')
                        if self.extract_service_str:
                            self.print_childrens(node, permission_strs, current_depth + 2)
                        print('***')
                    elif 'getService' in log:
                        print('%2d' % current_depth, ' ' * (depth + 1) + log)
                        print('***')
                        if self.extract_service_str:
                            self.print_childrens(node, permission_strs, current_depth + 2)
                        print('***')
                    elif 'writeInterfaceToken' in log:
                        print('%2d' % current_depth, ' ' * (depth + 1) + log)
                        print('***')
                        if self.extract_service_str:
                            self.print_childrens(node, permission_strs, current_depth + 2)
                        print('***')
                    else:
                        if 'instantiate' in log:
                            oo = 0
                        print('%2d' % current_depth, ' ' * (depth + 1) + log)

                    self.html_log.append([depth, log])

                    if f in so_far:
                        continue
                    so_far.append(f)

                    # ::IDrm:: YES  ::IPCThreadState:: NO
                    r_final = re.findall(r'::I[A-Z][a-z].+?::', log)
                    print(log)

                    if len(r_final) > 0 and self.has_no_ignore_fun(
                            self.fully_qualified_pretty(last_node)) and self.has_no_ignore_fun(
                            self.fully_qualified_pretty(f)):
                        print('\n\n###### binder start ######')
                        print('original FROM:', self.fully_qualified_pretty(last_node), last_node.location)
                        print(last_node.location.file.name)
                        print('last_node.location.file.name.endswith(\'.h\')',
                              last_node.location.file.name.endswith('.h'))
                        # If the function is from .h, you need to check whether there is a cpp file with the same name,
                        # whether there is this function in the cpp file with the same name, if any, please refer to the
                        # analysis in cpp
                        if last_node.location.file.name.endswith('.h'):
                            print('The method is the method in .h, replace it with the method in cpp')
                            k_list, v_list = self.search_fun_list_full(self.fully_qualified_pretty(last_node))
                            for tem_v_list in v_list:
                                print(tem_v_list.location.file.name)
                                if tem_v_list.location.file.name.endswith('.cpp'):
                                    print('replace last_node with the method in cpp:', tem_v_list.kind,
                                          self.fully_qualified_pretty(tem_v_list), tem_v_list.location.file.name)
                                    last_node = tem_v_list

                        method_full = self.fully_qualified_pretty(f)
                        print('original TO:', method_full, f.location)

                        if 'android::hardware::' in method_full:
                            print('*** END OF CALL because found android::hardware:: TOO DEEP***')
                            continue
                        elif 'checkPermission' in method_full:
                            print('*** END OF CALL because found checkPermission()')
                            continue
                        elif 'getMediaPlayerService' in method_full:
                            print('*** END OF CALL because found IMediaDeathNotifier::getMediaPlayerService')
                            continue
                        # TO If IxxxService:: replace directly
                        # Replace IxxxService:: directly with xxxService::
                        tema = re.findall(r'I[a-zA-Z]+?Service::', method_full)

                        if 'Service::' in method_full:
                            head_file_re = f.location.file.name
                            print(head_file_re)
                            h_no_I = self.I_find_no_I(head_file_re)
                            self.extend_h_analysis(h_no_I, aosp_ver, True, project_path)
                            print('.line 1903')

                        if self.not_has_ignore_fun_Ixx(method_full) and len(tema) > 0:
                            print('.line 1983')
                            print('替换前', method_full)
                            # if 'AudioPolicyService::createAudioPatch' in method_full:
                            #     print('.line 1908')
                            #     head_file_re = f.location.file.name
                            #     print(head_file_re)
                            #     h_no_I = self.I_find_no_I(head_file_re)
                            #     self.extend_h_analysis(h_no_I, '7.0', True, project_path)
                            # exit(0)
                            for temb in tema:
                                print(temb)
                                method_full = method_full.replace(temb, temb[1:])
                            print('替换后', method_full)
                            k_list, v_list = self.search_fun_list_full(method_full)
                            assert len(v_list) == 1, '没有找到或找到多个方法，请检查'
                            print('.line 806')
                            print('LINK到下一个方法:')
                            print(self.fully_qualified_pretty(last_node), '=>')
                            print(method_full)
                            print('更改为', k_list[0], v_list[0].location)
                            if v_list[0] in so_far:
                                continue
                            so_far.append(v_list[0])
                            print('.line 1233')
                            print('*** 继续正常打印call graph****')
                            self.print_calls(k_list[0], so_far, v_list[0], permission_strs, depth + 1)
                        elif self.not_has_ignore_fun_Ixx(self.fully_qualified_pretty(f)):
                            print('.line 2010')
                            return_class = self.link_binder(last_node, f, so_far)
                            print('.line 2012')
                            print('return_class', return_class)

                            print('==========Find the variable name of the first parameter of transact in Ixxx::xx===========')
                            if return_class != 'END' and return_class != 'no_caller':

                                print('解析', f.location.file.name)
                                self.extend_h_analysis(f.location.file.name, '7.0', True, project_path, fuzzy=True)

                                Ixx_method_cpp_k = None
                                Ixx_method_cpp_v = None
                                function_transact = self.fully_qualified_pretty(f)
                                function_transact = function_transact.split('(')[0].split('::')[-1]
                                print('now starting', function_transact)
                                k_list, v_list = self.search_fun_list_full(function_transact + '(')
                                for i, tem_v_list in enumerate(v_list):
                                    print(tem_v_list.location.file.name)
                                    if tem_v_list.location.file.name.endswith('.cpp'):
                                        print('cahnge to', k_list[i], v_list[i].location)
                                        Ixx_method_cpp_k = k_list[i]
                                        Ixx_method_cpp_v = v_list[i]
                                if Ixx_method_cpp_k:
                                    transacts = []
                                    self.print_childrens(Ixx_method_cpp_v, transacts, 0)
                                    print('.line 2015', transacts)
                                    transact = transacts[0][0]
                                    print('.line 2017', transact)
                                    conditions = self.onTransact(transact, return_class)
                                    permission_strs.extend(conditions)

                            print('==========END===========')

                            if return_class == 'no_caller':
                                print('no_caller, no analysis')
                                continue
                            print('Find the end, LINK to the next method:')
                            print(self.fully_qualified_pretty(last_node), '=>')
                            print(self.fully_qualified_pretty(f))
                            fun_str = return_class + '::' + f.displayname
                            print('change to', fun_str)
                            strinfo = re.compile('<.{0,}?>')
                            fun_str_revised = strinfo.sub('<>', fun_str)
                            print('fun_str_revised(Remove <...> template content):', fun_str_revised)
                            print('function in self.CALLGRAPH:', fun_str_revised in self.CALLGRAPH)
                            if self.has_no_ignore_fun(fun_str_revised) and 'END' not in return_class:
                                k_list, v_list = self.search_fun_list_full(fun_str_revised)
                            else:
                                continue
                            if v_list[0] in so_far:
                                continue
                            so_far.append(v_list[0])
                            print('.line 1260')
                            print('*** Continue printing normally: call graph****')
                            print(k_list[0], v_list[0].location, '=> ...')

                            self.print_calls(k_list[0], so_far, v_list[0], permission_strs, depth + 1)
                        else:
                            print('*** ignore IServiceManager:: method ****', self.fully_qualified_pretty(f))

                    elif self.fully_qualified_pretty(f) in self.CALLGRAPH:
                        self.print_calls(self.fully_qualified_pretty(f), so_far, f, permission_strs,
                                         depth + 1)
                    else:
                        self.print_calls(self.fully_qualified(f), so_far, f, permission_strs,
                                         depth + 1)

        else:
            if last_node is not None and last_node not in self.ENDNODE:
                self.ENDNODE.append(last_node)

    def extend_h_analysis(self, file, version_prefix, compdb=False, project_path='/Volumes/android/android-8.0.0_r34/',
                          fuzzy=False):

        if fuzzy:
            c_cpp_lists = [find_command(file, version_prefix=version_prefix, compdb=compdb, project_path=project_path)]
        else:
            c_cpp_lists = find_command_all_cpp(file, version_prefix=version_prefix, compdb=compdb,
                                               project_path=project_path)
        for i, c_cpp_list in enumerate(c_cpp_lists):

            print('额外分析', i, '/', len(c_cpp_lists))
            if c_cpp_list is not None and project_path + c_cpp_list['file'] not in self.analyzed_cpp:

                next_file = project_path + c_cpp_list['file']
                self.analyzed_cpp.add(next_file)
                print('.line 2039', next_file)

                if 'MediaClock.cpp' in next_file or 'AString.cpp' in next_file or 'MediaSync.cpp' in next_file or 'MediaBuffer.cpp' in next_file:
                    print('pass: ', next_file)
                    continue

                ninja_args = c_cpp_list['command'].split()[1:]
                ninja_args = self.parse_ninja_args(ninja_args)

                if 'clang++' in c_cpp_list['command'].split()[0]:
                    self.load_cfg(self.index, 'clang++', next_file, ninja_args)
                else:
                    self.load_cfg(self.index, 'clang', next_file, ninja_args)

            else:
                print(file, '*.h has implement or *.cpp name is different')

    def read_compile_commands(self, filename):
        if filename.endswith('.json'):
            with open(filename) as compdb:
                return json.load(compdb)
        else:
            return [{'command': '', 'file': filename}]

    def read_args(self, args):
        db = None
        clang_args = []
        excluded_prefixes = []
        excluded_paths = ['/usr']
        i = 0
        while i < len(args):
            if args[i] == '-x':
                i += 1
                excluded_prefixes = args[i].split(',')
            elif args[i] == '-p':
                i += 1
                excluded_paths = args[i].split(',')
            elif args[i][0] == '-':
                clang_args.append(args[i])
            else:
                db = args[i]
            i += 1
        return {
            'db': db,
            'clang_args': clang_args,
            'excluded_prefixes': excluded_prefixes,
            'excluded_paths': excluded_paths
        }

    def check_file(self, file):
        if not os.path.exists(file):
            raise Exception("FILE DOES NOT EXIST: \"" + file + "\"")
        return file

    def check_path(self, path):
        if not os.path.exists(path):
            raise Exception("PATH DOES NOT EXIST: \"" + path + "\"")
        return path

    def is_include_in_set(self, path, set):
        for tem in set:
            print(str(tem, encoding="utf-8"), path)
            if path not in str(tem):
                return True
        return False

    def collect_cfg(self, index, file, args):
        tu = index.parse(file, args)
        for d in tu.diagnostics:
            if d.severity == d.Error or d.severity == d.Fatal:
                print(d)
            else:
                print(d)
        print('Analyzing:', file)
        self.node_start = tu.cursor
        self.file_tu = tu
        self.show_info(tu.cursor)

    def parse_ninja_args(self, ninja_args):
        for i in range(len(ninja_args)):

            if '-I' in ninja_args[i] and len(ninja_args[i]) > 2:

                ninja_args[i] = ninja_args[i].replace('-I', '-I' + project_path)
            if i > 0 and ninja_args[i - 1] == '-I' or ninja_args[i - 1] == '-isystem' or ninja_args[i - 1] == '-o' or \
                    ninja_args[i - 1] == '-MF':
                ninja_args[i] = project_path + ninja_args[i]
            if '-fsanitize-blacklist=' in ninja_args[i]:
                ninja_args[i] = ninja_args[i].replace('-fsanitize-blacklist=', '-fsanitize-blacklist=' + project_path)

        return ninja_args

    def load_cfg_normal(self, index, file, args):

        syspath = ccsyspath.system_include_paths(
            '/hci/chaoran_data/android-7.0.0_r33/prebuilts/clang/host/linux-x86/clang-2690385/bin/clang++')
        sysincargs = ['-I' + str(inc, encoding="utf8") for inc in syspath]
        args = args + sysincargs

        tu = index.parse(file, args)
        for d in tu.diagnostics:
            if d.severity == d.Error or d.severity == d.Fatal:
                print(d)
                raise Exception('aaaaaaaaaaaaaaaaaa')
            else:
                print(d)

        self.node_start[file] = tu.cursor
        self.file_tu[file] = tu
        self.show_info(tu.cursor)
        return tu

    def load_cfg(self, index, compiler, file, ninja_args):
        print(compiler)

        if 'clang++' in compiler:

            init_args = [init_arg_config]

            ninja_args = init_args + ninja_args
            for i in range(len(ninja_args)):
                if '\\' in ninja_args[i]:
                    print(ninja_args[i])
                    # Add double quotation marks on both sides of the double quotation mark in the flag to be correctly recognized
                    ninja_args[i] = '"' + ninja_args[i] + '"'
                    print(ninja_args[i])
                if '-DAAUDIO_API=\'__attribute__((visibility("default")))\'' in ninja_args[i]:

                    ninja_args[i] = "-DAAUDIO_API=__attribute__((visibility(\"default\")))"

                ninja_args[i] = ninja_args[i].replace(r'"-DPACKED=\"\""', '-DPACKED=""')
        ast_path = 'ast'+aosp_ver+'/' + file.replace('/', '_') + '.ast'
        tu = None

        ninja_args = ninja_args[:-1]


        if os.path.exists(ast_path):
            tu = index.read(ast_path)
        else:
            tu = index.parse(file, ninja_args)


        for d in tu.diagnostics:
            if d.severity == d.Error or d.severity == d.Fatal:
                print(d)
                if 'use of undeclared identifier' in str(d) or 'file not found' in str(d):
                    return None
                raise Exception('exception line 2422')
            else:
                print(d)

        if not os.path.exists(ast_path):
            print('save:', ast_path)
            tu.save(ast_path)

        self.node_start[file] = tu.cursor
        self.file_tu[file] = tu
        self.show_info(tu.cursor)

        return tu

    def get_node_from_child(self, fun_name):
        for k, v in self.CALLGRAPH.items():
            for f in v:
                f = f.referenced
                # Child node found
                if self.fully_qualified_pretty(f) == fun_name or self.fully_qualified(
                        f) == fun_name:
                    return f
        return None

    def extract_jni_fun(self, file_str, pro_path, ninja_args, show_loc=False, print_all_node=True):

        self.show_loc = show_loc
        self.print_all_node = print_all_node
        index = Index.create(1)
        file = self.check_file(file_str)
        self.pro_path = pro_path

        ninja_args = self.parse_ninja_args(ninja_args)
        args = ninja_args
        tu = self.load_cfg(index, 'clang++', file, args)

        not_sys_include_paths = []
        for tem in tu.get_includes():
            include_path = tem.include.name
            if self.pro_path + 'frameworks' in include_path:
                print(include_path)

    def run(self, file_str, pro_path, ninja_args, entry_funs=None, IS_AOSP=True, extend_analyze=True, show_loc=False,
            print_all_node=False, generate_html=False, anti_search=False, only_preprocess=False):
        print('--- run ---')
        self.show_loc = show_loc
        self.print_all_node = print_all_node
        index = Index.create(1)
        self.index = index
        file = self.check_file(file_str)
        self.pro_path = pro_path

        tu = None
        args = None

        if IS_AOSP:
            ninja_args = self.parse_ninja_args(ninja_args)
            args = ninja_args
            tu = self.load_cfg(index, 'clang++', file, args)
        else:
            tu = self.load_cfg_normal(index, file, ninja_args)


        for tem in tu.get_includes(0):
            include_path = tem.include.name

            if IS_AOSP:
                if self.pro_path + 'frameworks' in include_path:
                    print('include file', include_path)

        not_sys_include_paths = []
        for tem in tu.get_includes():
            include_path = tem.include.name

            if IS_AOSP:
                if self.pro_path + 'frameworks' in include_path:
                    not_sys_include_paths.append(include_path)
                    # Join xxService search when IxxService
                    r = re.findall(r'I.+?Service\.h', include_path)
                    if len(r) > 0:
                        aaa = include_path.replace(r[0], r[0][1:])
                        not_sys_include_paths.append(aaa)

                    r = re.findall(r'I.+?Client\.h', include_path)
                    if len(r) > 0:
                        aaa = include_path.replace(r[0], r[0][1:])
                        not_sys_include_paths.append(aaa)

                    r = re.findall(r'I.+?Client\.h', include_path)
                    if len(r) > 0:
                        aaa = include_path.replace(r[0], r[0][1:-8]) + '.h'
                        not_sys_include_paths.append(aaa)

                    not_sys_include_paths.append(include_path.replace('Manager.h', 'Service.h'))

                    r = re.findall(r'I.+?\.h', include_path)
                    if len(r) > 0 and 'Service' not in include_path:
                        not_sys_include_paths.append(include_path.replace(r[0], r[0][1:]))

            else:
                if self.pro_path in include_path:
                    not_sys_include_paths.append(include_path)

        new_not_sys_include_paths = []
        for not_sys_include_path in not_sys_include_paths:
            if not_sys_include_path not in new_not_sys_include_paths:
                new_not_sys_include_paths.append(not_sys_include_path)
        not_sys_include_paths = new_not_sys_include_paths

        i = 0
        if extend_analyze:
            print('===========ALL INCLUDE FILE=============')

            not_sys_include_paths = set(not_sys_include_paths)
            print(not_sys_include_paths)
            print('===========SEARCH INCLUDE FILE=============')
            for tem in not_sys_include_paths:
                i = i + 1
                print('***************')
                print('Loading CFG ... ', i, '/', len(not_sys_include_paths))

                if IS_AOSP:

                    c_cpp_list = find_command(tem, version_prefix='7.0', compdb=True, project_path=project_path)

                    if c_cpp_list is not None and project_path + c_cpp_list['file'] not in self.analyzed_cpp:

                        next_file = project_path + c_cpp_list['file']
                        self.analyzed_cpp.add(next_file)
                        print('.line 2297', next_file)

                        if 'MediaClock.cpp' in next_file or 'AString.cpp' in next_file or 'MediaSync.cpp' in next_file or 'MediaBuffer.cpp' in next_file:
                            print('pass: ', next_file)
                            continue

                        ninja_args = c_cpp_list['command'].split()[1:]
                        ninja_args = self.parse_ninja_args(ninja_args)

                        if 'clang++' in c_cpp_list['command'].split()[0]:
                            self.load_cfg(index, 'clang++', next_file, ninja_args)
                        else:
                            self.load_cfg(index, 'clang', next_file, ninja_args)
                    else:
                        print(tem, '*.h has implement or *.cpp name is different')
                else:
                    cpp = tem.replace('.h', '.cpp')
                    c = tem.replace('.h', '.c')

                    if (os.path.exists(cpp)):
                        print("*.cpp:", cpp)
                        if cpp != file_str:
                            self.load_cfg_normal(index, cpp, ninja_args)
                        else:
                            print('skip to analyze itself')
                    elif (os.path.exists(c)):
                        print("*.c:", c)
                        if c != file_str:
                            self.load_cfg_normal(index, c, ninja_args)
                        else:
                            print('skip to analyze itself')
                    else:
                        print(tem, '*.h has implement or *.cpp name is different')

        if anti_search == False:
            print('====print CFG=====')
            collect_all_fun = False
            if entry_funs is None or len(entry_funs) == 0:
                collect_all_fun = True
            for tem in self.CALLGRAPH:
                if collect_all_fun:
                    pass

            html = ''
            for entry_fun_part in entry_funs:
                entry_funs, entry_fun_vs = self.search_fun(entry_fun_part)
                for i in range(len(entry_funs)):
                    entry_fun = entry_funs[i]
                    entry_fun_v = entry_fun_vs[i]
                    if entry_fun in self.CALLGRAPH:
                        print('----entry_fun----')
                        print(entry_fun)

                        self.html_log = []
                        permission_strs = []
                        so_far = []
                        so_far.append(entry_fun_v)
                        self.print_calls(entry_fun, so_far, entry_fun_v, permission_strs)
                        print('permission_str', permission_strs)
                        for permission_str in permission_strs:
                            self.found_permission_method.append([entry_fun, permission_str])
                            print('FOUND ', entry_fun, ' ::: ', permission_str)

                        if generate_html:
                            html = html + '<ul><li>' + entry_fun.replace('>', '&gt;').replace('<', '&lt;')
                            last_depth = -1
                            for tem in self.html_log:
                                depth = tem[0]
                                o = tem[1].replace('>', '&gt;').replace('<', '&lt;')
                                if depth > last_depth:
                                    html = html + '\n' + '\t' * depth + '<ul>\n'
                                elif depth == last_depth:
                                    html = html + '</li>\n'
                                elif depth < last_depth:
                                    for temmm in range(last_depth, depth, -1):
                                        html = html + '</li>\n' \
                                               + ('\t' * temmm) + '</ul>\n'
                                    html = html + ('\t' * depth) + '</li>\n'

                                html = html + ('\t' * depth) + '<li>' + o

                                last_depth = depth

                            for temmm in range(last_depth, -1, -1):
                                # if temmm==0:
                                html = html + '</li>\n' + ('\t' * temmm) + '</ul>'
                                # else:
                                #     html = html + '</li>\n' \
                                #            + ('\t' * temmm) + '</ul>\n' \
                                #            + ('\t' * temmm) + '</li>\n'
                            html = html + '</li></ul>'
            if generate_html:
                html = '''
                    <!DOCTYPE html>
                    <html>

                      <head>
                        <meta charset="utf-8" />
                        <title>no title</title>
                        <style>ul li ul { display:none; }</style>
                        <script src="http://ajax.aspnetcdn.com/ajax/jQuery/jquery-1.8.0.js"></script>
                        <script type="text/javascript">$(function() {

                            $("li:has(ul)").click(function(event) {
                              if (this == event.target) {
                                if ($(this).children().is(':hidden')) {
                                  $(this).css({
                                    cursor: 'pointer',
                                    'list-style-type': 'none',
                                    'background': 'url(../img/minus.png) no-repeat 0rem 0.1rem',
                                    'background-size': '1rem 1rem',
                                    'text-indent': '2em'
                                  }).children().show();
                                } else {
                                  $(this).css({
                                    cursor: 'pointer',
                                    'list-style-type': 'none',
                                    'background': 'url(../img/plus.png) no-repeat 0rem 0.1rem',
                                    'background-size': '1rem 1rem',
                                    'text-indent': '2em'
                                  }).children().hide();
                                }
                              }
                              return false;
                            }).css('cursor', 'pointer').click();
                            $('li:not(:has(ul))').css({
                              cursor: 'default',
                              'list-style-type': 'none',
                              'text-indent': '2em'
                            });

                            $('li:has(ul)').css({
                              cursor: 'pointer',
                              'list-style-type': 'none',
                              'background': 'url(../img/minus.png) no-repeat 0rem 0.1rem',
                              'background-size': '1rem 1rem',
                              'text-indent': '2em'
                            });
                            $('li:has(ul)').hover(function() {
                              $(this).css("color", "blue");
                            },
                            function() {
                              $(this).css("color", "black");
                            });
                          });</script>
                      </head>

                      <body>
                ''' + html
                html = html + '''
                    </body>
                    </html>
                '''
                path2save = 'tem/html/' + file_str.replace('/', '_') + '/all.html'
                if not os.path.exists('tem/html/' + file_str.replace('/', '_') + '/'):
                    os.makedirs('tem/html/' + file_str.replace('/', '_') + '/')
                with open(path2save, 'w') as file_obj:
                    print('output:', 'file:///Users/chaoranli/PycharmProjects/test/' + path2save)
                    file_obj.writelines(html)
                    import webbrowser
                    webbrowser.open('file:///Users/chaoranli/PycharmProjects/test/' + path2save)
            tu.save('tem/test_unit')

            print('===========Total permission=============')
            permission_tem = ''
            for [method, permission] in self.found_permission_method:
                if isinstance(permission, list):
                    if permission[0] != None and permission[0] != 'None':
                        i_tem = permission[1].find('*')
                        if i_tem != -1:
                            output_tem = permission[1][i_tem + 1:]
                        else:
                            output_tem = permission[1]
                        print('FOUND ', method, ' ::: ', '[%s]' % permission[0], output_tem)
                elif permission:
                    permission_tem = permission_tem + ' ' + permission
                    if not permission.endswith('&&'):
                        if permission_tem != None and permission_tem != 'None':
                            i_tem = permission_tem.find('*')
                            if i_tem != -1:
                                output_tem = permission_tem[i_tem + 1:]
                            else:
                                output_tem = permission_tem
                            print('FOUND ', method, ' ::: ', '[%s]' % output_tem)
                        permission_tem = ''


        # Reverse search
        else:
            print('====Reverse search results====')
            anti_list = []
            for entry_fun_part in entry_funs:
                entry_fun_list = self.search_fun(entry_fun_part)
                for entry_fun in entry_fun_list:
                    if self.get_node_from_child(entry_fun) is not None:
                        print(entry_fun)

                        self.html_log = []
                        permission_strs = []
                        graphs = []
                        self.get_print_ndoe(entry_fun, list(), graphs)

                        for i in range(len(graphs)):
                            graphs[i].append(entry_fun)

                        print(graphs)
                        anti_list.append(graphs)
            return anti_list


def find_fun_cpp(path, search_str):
    if not os.path.exists(path):
        return None
    try:
        file = open(path, 'r', encoding='UTF-8')
        # Convert encoding to achieve correct output format
        lines = file.readlines()
    except Exception as e:
        file = open(path, 'r', encoding='latin1')
        # Convert encoding to achieve correct output format
        lines = file.readlines()
    finally:
        file.close()
    analyze_this_file = False
    line_num = []
    for i, line in enumerate(lines):
        if search_str in line:
            analyze_this_file = True
            line_num.append(i + 1)
    if not analyze_this_file:
        return None
    else:
        return line_num


def reverse_search(list, fun_name, full_name, past):
    found_list = {}
    for tem in list:
        if tem['source'] in past:
            continue
        if 'test' in tem['source'].lower() or 'tests' in tem['source'].lower() or 'armv7' in tem['source'].lower():
            continue
        # if 'ICameraDeviceUser' in tem['source']:
        #     print(tem['source'])
        # 返回行数 [{source:'xxxx.cpp', content:{...}}]
        r = find_fun_cpp('/Volumes/android/android-8.0.0_r34/' + tem['source'], fun_name)
        if r is not None:
            found_list[tem['source']] = [tem, r]
            past.append(tem['source'])

    for k, tem in found_list.items():
        print(tem[0]['source'], tem[1])

        cpp = tem[0]
        main_file_analyser = file_analyser()
        # analyze cpp
        file = '/Volumes/android/android-8.0.0_r34/' + cpp['source']

        pro_path = '/Volumes/android/android-8.0.0_r34/'
        ninja_args = cpp['content']['flags']

        entry_funs = [full_name]

        graphs_file = main_file_analyser.run(file, pro_path, ninja_args, entry_funs, extend_analyze=False,
                                             anti_search=True)
        for graphs in graphs_file:
            for graph in graphs:
                if len(graph) < 2:
                    continue
                parent_node_name = graph[0]

                node_list = main_file_analyser.search_fun_list(parent_node_name)
                if len(node_list) == 0:
                    continue
                node = node_list[0]
                child_node_name = node.spelling
                print('最父节点搜索，简单函数：', child_node_name + '(', '完整函数：', parent_node_name)
                reverse_search(list, child_node_name + '(', parent_node_name, past)



def single():
    # example
    c_cpp_list = find_command_star_node('frameworks/av/media/libmedia/mediaplayer.cpp')
    entry_funs = ['MediaPlayer::attachNewPlayer(']

    c_cpp_list = c_cpp_list[0]
    main_file_analyser = file_analyser()
    file = '/Volumes/android/android-7.0.0_r34/' + c_cpp_list['source']
    pro_path = '/Volumes/android/android-7.0.0_r34/'
    ninja_args = c_cpp_list['content']['flags']
    main_file_analyser.run(file, pro_path, ninja_args, entry_funs=entry_funs, extend_analyze=True, anti_search=False,
                           print_all_node=False)

# AST variable tracker
def whole():
    start = False
    with open('jni7.0/jni.json') as file_obj:
        cpp_jni_list = json.load(file_obj)
        for cpp_jni in cpp_jni_list:

            entry_funs = []
            cpp = cpp_jni['cpp']
            print(cpp)
            vars = cpp_jni['pairs']
            for var in vars:
                for pair in var:
                    entry_funs.append(pair[-1] + '(')
            print(entry_funs)
            c_cpp_list = find_command_star_node(cpp.replace(project_path, ''), aosp_ver, compdb=True)
            c_cpp_list = c_cpp_list[0]

            file = project_path + c_cpp_list['file']

            pro_path = project_path
            ninja_args = c_cpp_list['command'].split()[1:]
            main_file_analyser = file_analyser()
            main_file_analyser.run(file, pro_path, ninja_args, entry_funs=entry_funs, extend_analyze=True,
                                   anti_search=False, print_all_node=False)


def tranform_cond(tem):
    def find_all(str, par):
        start = 0
        poses = []
        while True:
            index = str.find(par, start)
            start = index + 1

            if index != -1:
                poses.append(index)
            else:
                break

        return poses

    ori_tem = tem
    tem = tem.replace(' ', '')

    update = True
    while '!(' in tem:
        for i in range(len(tem)):
            ###############################
            if update:
                update = False
                pair = []
                pos1 = find_all(tem, '(')
                pos2 = find_all(tem, ')')
                # (和)中间不能有任何其余(或)
                print(pos1, pos2)
                while len(pos1) > 0 and len(pos2) > 0:
                    left_pos = 0
                    found_left = 0
                    for i in range(len(tem)):
                        if tem[i] == '(':
                            found_left = found_left + 1
                        elif tem[i] == ')':
                            found_left = found_left - 1

                        if i in pos1:
                            left_pos = i
                        elif i in pos2:
                            # 括号左index 括号右index 层级
                            pair.append([left_pos, i, found_left])
                            pos1.remove(left_pos)
                            pos2.remove(i)
                            break

                print(pair)

                for i in range(len(tem)):
                    print('%3s' % tem[i], end='')
                print()
                for i in range(len(tem)):
                    print('%3s' % i, end='')
                print()

                opers = []
                level = 0
                for i in range(len(tem)):
                    if tem[i] == '(':
                        level = level + 1
                    elif tem[i] == ')':
                        level = level - 1
                    if (tem[i] == '&' and tem[i + 1] == '&') \
                            or (tem[i] == '|' and tem[i + 1] == '|') \
                            or (tem[i] == '!' and tem[i + 1] == '=') \
                            or (tem[i] == '=' and tem[i + 1] == '='):
                        print(i, level - 1, tem[i] + tem[i])
                        opers.append([i, level - 1, tem[i] + tem[i]])
                    elif tem[i] == '!' and tem[i + 1] != '(':
                        opers.append([i, level - 1, tem[i]])
            ###############################

            if i >= len(tem):
                break

            if tem[i] == '!' and (tem[i + 1] == '(' or (tem[i + 1] == ' ' and tem[i + 2] == '(')):
                update = True
                print('发现非括号', i)
                start = 0
                end = 0
                l = 0
                for temmm in pair:
                    if i + 1 == temmm[0] or i + 2 == temmm[0]:
                        start = temmm[0]
                        end = temmm[1]
                        l = temmm[2]
                print('start', start, 'end', end, 'level', l)

                found = None
                for oper in opers:
                    print(oper)
                    print(oper[2] == '||', oper[0] > start, oper[0] < end)
                    if oper[2] == '&&' and oper[0] > start and oper[0] < end:
                        found = oper
                        print('FOUND', oper)
                        tem = tem[:oper[0]] + '||' + tem[oper[0] + 2:]
                        print(tem)
                    elif oper[2] == '||' and oper[0] > start and oper[0] < end:
                        found = oper
                        print('FOUND', oper)
                        tem = tem[:oper[0]] + '&&' + tem[oper[0] + 2:]
                        print(tem)
                    elif oper[2] == '!' and oper[0] > start and oper[0] < end:
                        found = oper
                        print('FOUND', oper)
                        tem = tem[:oper[0]] + tem[oper[0] + 1:]
                        print(tem)

                if found:
                    print('FOUND true')
                    for oper in opers:
                        print(oper)
                        if (oper[1] >= level + 1 or oper[1] <= level + 1) and (
                                (start < oper[0] and oper[0] < found[0]) or (found[0] < oper[0] and oper[0] < end)):
                            if oper[2] == '!!':
                                tem = tem[:oper[0]] + '==' + tem[oper[0] + 2:]
                            elif oper[2] == '==':
                                tem = tem[:oper[0]] + '!=' + tem[oper[0] + 2:]

                tem = tem[:i] + tem[i + 2:]
                print(':', end - 3)
                print(tem[:end - 2], tem[end - 1:])
                tem = tem[:end - 2] + tem[end - 1:]
                print(tem)
    print(ori_tem)
    print('=>')
    print(tem)

if __name__ == '__main__':
    single()
    whole()
