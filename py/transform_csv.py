import csv
import re
import json

json_list = []
with open('csv/Java_permission.csv', 'r') as f:
    reader = csv.reader(f)
    print(type(reader))
    line = 0
    for row in reader:
        line = line + 1
        if line==1:
            continue
        api = row[0]
        api = api.strip().strip('<').strip('>').strip('"')
        print('------------------')
        print(api)
        class_name = api.split(':')[0]
        print(class_name)
        rest = api.split(':')[1]
        tem = re.findall("\S+?\(", rest)
        method = tem[0]
        print(method)
        json_list.append({"class_name": class_name, "method_name": method})
with open('csv/Java_permission.json', 'w') as file_obj:
    json.dump({"array": json_list}, file_obj)