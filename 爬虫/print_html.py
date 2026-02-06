import requests
'''
获取当前页面html文件
'''
url=input()
x = requests.get(url)
print(x.text)