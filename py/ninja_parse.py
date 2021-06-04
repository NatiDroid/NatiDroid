import os
import re
import json

'''
rule g.cc.cc
    command = ${g.cc.relPwd} ${g.config.CcWrapper}${ccCmd} -c ${cFlags} -MD -MF ${out}.d -o ${out} ${in}
    depfile = ${out}.d
    deps = gcc
    
    
build $
        out/soong/.intermediates/system/core/libbinderwrapper/libbinderwrapper/android_arm_armv7-a-neon_cortex-a15_shared_core/obj/system/core/libbinderwrapper/real_binder_wrapper.o $
        : g.cc.cc system/core/libbinderwrapper/real_binder_wrapper.cc | $
        ${ccCmd}
    description = ${m.libbinderwrapper_android_arm_armv7-a-neon_cortex-a15_shared_core.moduleDesc}clang++ real_binder_wrapper.cc${m.libbinderwrapper_android_arm_armv7-a-neon_cortex-a15_shared_core.moduleDescSuffix}
    cFlags = -Isystem/core/libbinderwrapper/include -Isystem/core/libbinderwrapper ${g.config.ArmClangThumbCflags} ${g.config.ArmClangCflags} ${g.config.CommonClangGlobalCflags} ${g.config.DeviceClangGlobalCflags} ${g.config.ArmToolchainClangCflags} ${g.config.ArmClangArmv7ANeonCflags} ${g.config.ArmClangCortexA15Cflags} -Iframeworks/native/libs/binder/include -Isystem/core/base/include -Isystem/core/libutils/include -Isystem/core/libbacktrace/include -Isystem/core/libsystem/include -Isystem/core/libcutils/include -Iexternal/libchrome -Iexternal/googletest/googletest/include -Iexternal/libcxx/include -Iexternal/libcxxabi/include ${g.config.CommonGlobalIncludes} ${g.config.ArmIncludeFlags} ${g.config.CommonNativehelperInclude} ${m.libbinderwrapper_android_arm_armv7-a-neon_cortex-a15_shared_core.cflags} ${m.libbinderwrapper_android_arm_armv7-a-neon_cortex-a15_shared_core.cppflags} ${g.config.NoOverrideClangGlobalCflags}
    ccCmd = ${g.config.ClangBin}/clang++
'''

# project_path = '/android-8.0.0_r34'
# ninja_file2 = 'build-aosp_arm64.ninja'
# ninja_file = 'build-aosp_arm64.ninja'

def process_soong_ninja():

    def process_ninja(command, dic):
        while '${' in command:
            a = re.findall("\${.*?}", command)
            for tem in a:
                tem_key = tem.replace('${', '').replace('}', '')
                command = command.replace(tem, dic[tem_key])
        return command

    json_list = []

    # Load configuration items
    file = open(project_path + '/out/soong/build.ninja', 'r')
    global_dic = {}

    rule_dic_all = {}
    rule_small = {}
    rule_name = ''
    rule_mode = False

    build_mode = False
    build_cache_mode = False
    build_cache = ''
    build_small = {}

    pass_mode = False
    while True:
        line = file.readline()
        if line:
            if not line.strip().startswith('#'):
                line = line.replace('\n', '')

                if line.startswith('default '):
                    # default temporarily not processed
                    pass_mode = True
                elif pass_mode:
                    if line.endswith('$'):
                        continue
                    else:
                        pass_mode = False
                        continue
                # end of rule mode
                elif line == '' and rule_mode:
                    rule_mode = False

                    rule_dic_all[rule_name] = rule_small

                # end of build mode
                elif line == '' and build_mode:
                    '''
                    build output0 output1 | output2 output3: rule_name $
                            input0 input1 $
                            | input2 input3 $
                            || input4 input5
                    '''
                    build_mode = False
                    aa = build_cache
                    build_cache = build_cache.split(':')
                    build_output = build_cache[0].strip()
                    rule_name = build_cache[1].strip().split(' ', 1)[0]
                    if len(build_cache[1].strip().split(' ', 1)) == 2:
                        build_input = build_cache[1].strip().split(' ', 1)[1]
                        if len(build_input.strip().split('||')) == 2:
                            build_input_implicit_order_only = build_input.strip().split('||')[1]

                        build_input_explicit = build_input.strip().split('||')[0].strip().split('|', )[0]
                        if len(build_input.strip().split('||')[0].strip().split('|', )) == 2:
                            build_input_implicit = build_input.strip().split('||')[0].strip().split('|', )[1]
                        build_small['in'] = build_input_explicit
                    if rule_name .startswith('g.cc'):
                        rule_command = rule_dic_all[rule_name]['command']
                    else:
                        rule_command = rule_name


                    build_output_explicit = build_output.strip().split('|', )[0]
                    if len(build_output.strip().split('|', )) == 2:
                        build_output_implicit = build_output.strip().split('|', )[1]


                    build_small['out'] = build_output_explicit
                    rule_command0=rule_command
                    # Remove the output, avoid rewriting the out file in aosp and speed it up
                    rule_command = rule_command.replace('-MD -MF ${out}.d', '').replace('-o ${out}', '')
                    # rule_command1=rule_command
                    if rule_name != 'g.cc.ld':
                        # 替换
                        while '${' in rule_command:
                            a = re.findall("\${.*?}", rule_command)
                            for tem in a:
                                tem_key = tem.replace('${', '').replace('}', '')
                                if tem_key in build_small.keys():
                                    rule_command = rule_command.replace(tem, build_small[tem_key])
                                elif tem_key in global_dic.keys():
                                    rule_command = rule_command.replace(tem, global_dic[tem_key])
                                else:
                                    raise Exception('bbbbbbbb')

                    rule_command_split = rule_command.split()
                    while len(rule_command_split)>0:
                        if ('bin/clang' in rule_command_split[0] or 'bin/clang++' in rule_command_split[0]):

                            content = {'source': rule_command_split[-1], 'content': {'compiler': rule_command_split[0], 'source': rule_command_split[-1], 'flags': rule_command_split[1:-1]}}
                            json_list.append(content)
                            break
                        else:
                            rule_command_split = rule_command_split[1:]
                # Start rule
                elif line.startswith('rule '):
                    rule_mode = True
                    rule_small = {}
                    rule_name = line.replace('rule', '').strip()
                # Configuration items in rule
                elif (line.startswith(' ') or line.startswith('\t')) and rule_mode:
                    pair = line.split('=', 1)
                    key = pair[0].strip()
                    value = pair[1].strip()
                    rule_small[key] = value
                # End rule


                elif line.startswith('build '):
                    build_mode = True
                    build_cache_mode = True
                    build_cache = line[:-1].replace('build ', '')
                    if not line.endswith('$'):
                        build_cache_mode = False
                    build_small = {}
                elif build_mode and build_cache_mode:
                    if line.endswith('$'):
                        build_cache = build_cache + line[:-1]
                    else:
                        build_cache = build_cache + line
                        build_cache_mode = False

                elif (line.startswith(' ') or line.startswith('\t')) and build_mode and not build_cache_mode:
                    pair = line.split('=', 1)
                    key = pair[0].strip()
                    value = pair[1].strip()
                    build_small[key] = value

                elif '=' in line:
                    pair = line.split('=', 1)
                    if '.' in pair[0]:
                        key = pair[0].strip()
                        value = pair[1].strip()
                        # print(key + '=' + value)
                        if key in global_dic.keys():
                            raise Exception('duplicate key')
                        global_dic[key] = value

        else:
            break

    print(len(global_dic.keys()))
    print(len(json_list))

    with open('tem/out_build_ninja.json', 'w') as file_obj:
        json.dump(json_list, file_obj)

    # # out/soong/.intermediates/frameworks/base/core/jni/libandroid_runtime/android_arm64_armv8-a_shared_core/obj/frameworks/base/core/jni/android_hardware_Camera.o $
    # #         : g.cc.cc frameworks/base/core/jni/android_hardware_Camera.cpp
    # out_conf = 'out/soong/.intermediates/frameworks/base/core/jni/libandroid_runtime/android_arm64_armv8-a_shared_core/obj/frameworks/base/core/jni/android_hardware_Camera222.o'
    # in_conf = 'frameworks/base/core/jni/android_hardware_Camera.cpp'
    # dic['out'] = out_conf
    # dic['in'] = in_conf
    #
    #
    # cFlags = '-Iframeworks/base/core/jni -Iframeworks/base/core/jni/include -Iframeworks/base/core/jni/android/graphics -Ibionic/libc/private -Iexternal/skia/include/private -Iexternal/skia/src/codec -Iexternal/skia/src/core -Iexternal/skia/src/effects -Iexternal/skia/src/image -Iexternal/skia/src/images -Iframeworks/base/media/jni -Ilibcore/include -Isystem/media/camera/include -Isystem/media/private/camera/include -Iframeworks/base/core/jni  ${g.config.Arm64ClangCflags} ${g.config.CommonClangGlobalCflags} ${g.config.DeviceClangGlobalCflags}  -Iexternal/giflib -Ibionic/libc/seccomp/include -Iexternal/selinux/libselinux/include -Iexternal/pcre/include -Isystem/core/libpackagelistparser/include -Iexternal/boringssl/src/include -Isystem/core/libgrallocusage/include -Isystem/core/libmemtrack/include -Iframeworks/base/libs/androidfw/include -Isystem/core/libappfuse/include -Isystem/core/base/include -Ilibnativehelper/include -Ilibnativehelper/platform_include -Isystem/core/liblog/include -Isystem/core/libcutils/include -Isystem/core/debuggerd/include -Isystem/core/debuggerd/common/include -Isystem/core/libutils/include -Isystem/core/libbacktrace/include -Isystem/core/libsystem/include -Iframeworks/native/libs/binder/include -Iframeworks/native/libs/ui/include -Iframeworks/native/libs/nativebase/include -Ihardware/libhardware/include -Isystem/media/audio/include -Iframeworks/native/libs/arect/include -Iframeworks/native/libs/math/include -Iframeworks/native/libs/graphicsenv/include -Iframeworks/native/libs/gui/include -Iframeworks/native/opengl/libs/EGL/include -Iframeworks/native/opengl/include -Iframeworks/native/libs/nativewindow/include -Isystem/libhidl/transport/token/1.0/utils/include -Isystem/libhidl/base/include -Isystem/libhidl/transport/include -Iout/soong/.intermediates/system/libhidl/transport/manager/1.0/android.hidl.manager@1.0_genc++_headers/gen -Iout/soong/.intermediates/system/libhidl/transport/base/1.0/android.hidl.base@1.0_genc++_headers/gen -Isystem/libhwbinder/include -Iout/soong/.intermediates/hardware/interfaces/graphics/common/1.0/android.hardware.graphics.common@1.0_genc++_headers/gen -Iout/soong/.intermediates/hardware/interfaces/media/1.0/android.hardware.media@1.0_genc++_headers/gen -Iout/soong/.intermediates/hardware/interfaces/graphics/bufferqueue/1.0/android.hardware.graphics.bufferqueue@1.0_genc++_headers/gen -Iframeworks/native/libs/sensor/include -Iframeworks/av/camera/include -Iframeworks/av/camera/include/camera -Isystem/media/camera/include -Iout/soong/.intermediates/frameworks/av/camera/libcamera_client/android_arm64_armv8-a_shared_core/gen/aidl -Iexternal/skia/include/android -Iexternal/skia/include/c -Iexternal/skia/include/codec -Iexternal/skia/include/config -Iexternal/skia/include/core -Iexternal/skia/include/effects -Iexternal/skia/include/encode -Iexternal/skia/include/gpu -Iexternal/skia/include/gpu/gl -Iexternal/skia/include/pathops -Iexternal/skia/include/ports -Iexternal/skia/include/svg -Iexternal/skia/include/utils -Iexternal/skia/include/utils/mac -Iexternal/sqlite/dist -Iexternal/sqlite/android -Iframeworks/native/vulkan/include -Ihardware/libhardware_legacy/include -Iexternal/icu/icu4c/source/common -Iframeworks/av/media/libmedia/aidl -Iframeworks/av/media/libmedia/include -Iout/soong/.intermediates/hardware/interfaces/media/omx/1.0/android.hardware.media.omx@1.0_genc++_headers/gen -Iexternal/sonivox/arm-wt-22k/include -Iexternal/icu/icu4c/source/i18n -Iframeworks/av/media/libstagefright/foundation/include -Iout/soong/.intermediates/frameworks/av/drm/libmediadrm/libmediadrm/android_arm64_armv8-a_shared_core/gen/aidl -Isystem/libhidl/libhidlmemory/include -Iout/soong/.intermediates/system/libhidl/transport/memory/1.0/android.hidl.memory@1.0_genc++_headers/gen -Iout/soong/.intermediates/frameworks/av/media/libmedia/libmedia/android_arm64_armv8-a_shared_core/gen/aidl -Iframeworks/av/media/libaudioclient/include -Iexternal/libjpeg-turbo -Isystem/core/libusbhost/include -Iexternal/harfbuzz_ng/src -Iexternal/zlib -Iexternal/pdfium/public -Iframeworks/av/media/img_utils/include -Isystem/netd/include -Iframeworks/minikin/include -Iexternal/freetype/include -Isystem/core/libprocessgroup/include -Isystem/media/radio/include -Isystem/core/libnativeloader/include -Isystem/core/libmemunreachable/include -Isystem/libvintf/include -Iframeworks/base/libs/hwui -Iout/soong/.intermediates/frameworks/base/libs/hwui/libhwui/android_arm64_armv8-a_static_core/gen/proto/frameworks/base/libs/hwui -Iout/soong/.intermediates/frameworks/base/libs/hwui/libhwui/android_arm64_armv8-a_static_core/gen/proto -Iexternal/protobuf/src -Iframeworks/rs/cpp -Iframeworks/rs -Iout/soong/.intermediates/frameworks/base/libs/hwui/libhwui/android_arm64_armv8-a_shared_core/gen/proto/frameworks/base/libs/hwui -Iout/soong/.intermediates/frameworks/base/libs/hwui/libhwui/android_arm64_armv8-a_shared_core/gen/proto -Iexternal/libcxx/include -Iexternal/libcxxabi/include ${g.config.CommonGlobalIncludes} ${g.config.Arm64IncludeFlags} ${g.config.CommonNativehelperInclude} ${m.libandroid_runtime_android_arm64_armv8-a_shared_core.cflags} ${m.libandroid_runtime_android_arm64_armv8-a_shared_core.cppflags} ${g.config.NoOverrideClangGlobalCflags}'
    # cFlags = process_ninja(cFlags)
    # dic['cFlags'] = cFlags
    #
    #
    # ccCmd = '${g.config.ClangBin}/clang++'
    # ccCmd = process_ninja(ccCmd)
    # dic['ccCmd'] = ccCmd
    #
    #
    # command = '${g.cc.relPwd} ${g.config.CcWrapper}${ccCmd} -c ${cFlags} -MD -MF ${out}.d -o ${out} ${in}'
    # command = process_ninja(command)
    # print(command)
    #
    #
    # b = os.popen(command)
    # text2 = b.read()
    # print(text2)
    # b.close()


def process_out_ninja():
    file = open(project_path + '/out/' + ninja_file, 'r')
    json_list = []
    while True:
        line = file.readline()

        if line:
            line = line.strip()
            # A new line
            if '#' not in line and line.startswith('command') and (line.endswith('.cpp"') or line.endswith('.c"')):
                command = line.replace('command = /bin/bash -c ', '').strip('"').strip()

                while '\$$(' in command:
                    a = re.findall('\$\((.*?)\)', command)
                    for tem in a:
                        cat_command = project_path + '/' + tem.replace('cat ', '')

                        b = os.popen('cat ' + cat_command)
                        text2 = b.read().replace('\n',' ')

                        if 'No such file or directory' in text2:
                            raise Exception(command)
                        b.close()
                        command = command.replace('\$$('+tem+')', text2)

                command = re.sub(r'-MF (.*?)\.d', " ", command)
                command = re.sub(r'-o (.*?)\.o', " ", command)
                command = command.replace('-MD', ' ')
                command = command.replace('-fdebug-prefix-map=\$$PWD/=', ' ')
                # bash and ninja
                command = command.replace(r'\\', '\\').replace(r'\"', '"').replace(r'\\', '\\').replace(r'\\', '\\')
                if 'frameworks/native/opengl/libagl/egl.cpp' in command:
                    iiii=0

                command = command.split()
                print('======try to find======')
                while len(command) > 0:
                    if ('bin/clang' in command[0] or 'bin/clang++' in command[0]):
                        print('======got it======')
                        compiler = command[0]
                        flags = command[1:]
                        source = flags[-1]
                        flags = flags[:-1]
                        print('=======compiler======')
                        print(compiler)
                        print('=======source======')
                        print(source)
                        print('=======flags======')
                        print(flags)
                        content = {'source': source,
                                   'content': {'compiler': compiler, 'source': source, 'flags': flags}}
                        json_list.append(content)
                        break
                    else:
                        command = command[1:]

        else:
            break
    file.close()

    with open('tem/build-aosp_arm64.json', 'w') as file_obj:
        json.dump(json_list, file_obj)

if __name__ == '__main__':
    process_soong_ninja()
    # process_out_ninja()