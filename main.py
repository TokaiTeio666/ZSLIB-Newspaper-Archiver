from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from save_to_word import save_to_separate_word
import os
import re

output_dir = "采集结果"
# 如果文件夹不存在则创建
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print("你要搜索的信息，按回车确认")
searchStr=input()

options = webdriver.EdgeOptions()
# 开启性能日志监控
options.set_capability('ms:loggingPrefs', {'performance': 'ALL'})
driver = webdriver.Edge(options=options)
driver.implicitly_wait(10)
driver.get('https://www.zslib.com.cn/Page/Page.html?t=sw')
element = driver.find_element(By.XPATH, "//a[contains(@onclick, '2bebc42e-6b8b-4e38-87cf-86d97f7a600e')]")
element.click()

element = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//a[contains(@onclick, '2bebc42e-6b8b-4e38-87cf-86d97f7a600e')]"))
)
print("请在 10 秒内完成手机扫码登录...")
time.sleep(10)
element.click()
time.sleep(2)

all_handles = driver.window_handles
driver.switch_to.window(all_handles[-1])
print(driver.title)
time.sleep(5)
button=driver.find_element(By.ID,'bz')
button.click()
time.sleep(2)
searchText=driver.find_element(By.ID,'txtBaseSearchValue')
searchText.clear()
searchText.send_keys(searchStr)
time.sleep(2)

searchButton = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.ID, "btnsearchimg"))
)
searchButton.click()

target_frame = driver.find_elements(By.ID, "BriefList")[1]
driver.switch_to.frame(target_frame)

mainWindow = driver.current_window_handle

# 定位到结果表格的所有行 (跳过表头，通常从 tr 索引 1 或 2 开始)
rows = driver.find_elements(By.XPATH, "//div[@class='retTable']//table/tbody/tr")
target_links = driver.find_elements(By.XPATH, "//div[@class='retTable']//table/tbody/tr/td[3]/a[contains(@href, 'boxId')]")
ButtonNext = driver.find_element(By.ID, "btnNext")

# 为了防止在循环中因为页面跳转导致 row 对象失效，我们先提取所有必要的信息
data_list = []
page_num = 1
while True:
    print(f"正在处理第 {page_num} 页...")
    # 1. 确保进入结果列表所在的 iframe
    driver.switch_to.default_content()
    try:
        # 根据您之前的代码，结果通常在第二个 ID 为 BriefList 的 iframe 中
        target_frame = driver.find_elements(By.ID, "BriefList")[1]
        driver.switch_to.frame(target_frame)
    except Exception as e:
        print(f"未能切换到结果列表 iframe: {e}")
        break

    # 2. 预提取当前页的所有行数据信息，防止详情页跳转导致 StaleElement 报错
    rows = driver.find_elements(By.XPATH, "//div[@class='retTable']//table/tbody/tr")
    current_page_data = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) > 2:
            name = cols[1].text.strip()
            info = cols[2].text.strip()
            try:
                # 寻找包含 boxId 的详情页链接
                link_el = row.find_element(By.XPATH, ".//a[contains(@href, 'boxId')]")
                url = link_el.get_attribute("href")
                current_page_data.append((name, info, url))
            except:
                continue

    # 3. 遍历处理当前页的每一条数据
    for i,(name, info, url) in enumerate(current_page_data):
        # 调用 save_to_separate_word 逻辑（内部需包含 driver.back() 返回列表）
        save_to_separate_word(name, info, url, driver,i, output_dir)

    # 4. 执行翻页操作
    try:
        # 定位“下一页”按钮
        next_button = driver.find_element(By.ID, "btnNext")

        # 判断是否已到末页：检查按钮是否包含特定的禁用类名或属性
        page_info = driver.find_element(By.CLASS_NAME, "pagin")
        page_text = page_info.text
        match = re.search(r"(\d+)/(\d+)", page_text)
        if match:
            current_p = int(match.group(1))
            total_p = int(match.group(2))

            print(f"页码状态: {current_p} / {total_p}")

            if current_p >= total_p:
                print("🎉 已成功采集到最后一页，任务圆满结束。")
                break
        else:
            # 如果没找到正则匹配，备选方案：检查按钮状态
            print("未提取到页码数值，尝试检查按钮...")

        # 点击下一页
        next_button.click()
        page_num += 1

        # 等待新页面加载（iframe 内容刷新）
        time.sleep(5)
    except Exception as e:
        print(f"翻页过程中出错或已无下一页: {e}")
        break
print("所有采集任务已完成。")
driver.quit()




