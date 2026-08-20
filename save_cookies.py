"""
保存登录状态脚本
运行后会打开浏览器，请手动完成登录，登录成功后按回车保存cookies
"""
import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By


def save_cookies():
    options = webdriver.EdgeOptions()
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Edge(options=options)
    driver.implicitly_wait(10)

    print("正在打开广东省立中山图书馆报纸资源页...")
    driver.get("https://www.zslib.com.cn/Page/Page.html?t=bz")
    time.sleep(3)

    print("\n" + "=" * 60)
    print("请在浏览器中完成以下操作：")
    print("1. 点击'中国历史文献总库·近代报纸数据库'")
    print("2. 完成扫码登录")
    print("3. 登录成功后，回到本程序按回车键保存登录状态")
    print("=" * 60 + "\n")

    input("登录完成后按回车键继续...")

    # 保存所有cookies
    cookies = driver.get_cookies()
    cookie_path = os.path.join(os.path.dirname(__file__), "cookies.json")
    with open(cookie_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    print(f"\n已保存 {len(cookies)} 个cookies到: {cookie_path}")
    print("当前页面URL:", driver.current_url)
    print("当前页面标题:", driver.title)

    # 也保存当前URL，方便后续直接访问
    url_path = os.path.join(os.path.dirname(__file__), "last_url.txt")
    with open(url_path, "w", encoding="utf-8") as f:
        f.write(driver.current_url)
    print(f"已保存当前URL到: {url_path}")

    driver.quit()
    print("\n登录状态保存完成！")


if __name__ == "__main__":
    save_cookies()
