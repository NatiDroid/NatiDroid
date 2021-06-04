# -*- coding:UTF-8 -*-
from bs4 import BeautifulSoup
import requests

if __name__ == "__main__":
    package = 'vStudio.Android.Camera360'
    list = {}
    target = 'https://play.google.com/store/apps/details?id=' + package
    print(target)
    req = requests.get(url=target)
    html = req.text
    bf = BeautifulSoup(html)
    texts = bf.find_all('span', class_='T32cc UAO9ie')
    for text in texts:
        href = text.a.attrs['href']
        if '/store/apps/category/' in href:
            string = text.a.string
            print(string)
            list[package] = {'category': string}


    print(list)