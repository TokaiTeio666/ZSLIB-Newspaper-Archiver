from selenium import webdriver

wd = webdriver.Edge()  # 指定 Edge 浏览器，会自动下载驱动

wd.get('https://www.byhy.net')

input('按回车退出')