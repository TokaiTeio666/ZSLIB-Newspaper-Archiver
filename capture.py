import time
import requests
from io import BytesIO
from PIL import Image
from selenium.webdriver.common.by import By
import json

def get_hd_url(driver):
    # 获取所有性能日志
    logs = driver.get_log('performance')
    for entry in logs:
        log = json.loads(entry['message'])['message']
        # 寻找网络响应事件
        if log['method'] == 'Network.responseReceived':
            url = log['params']['response']['url']
            # 匹配高清图接口关键词
            if "GetEBookPageForOriImg" in url:
                return url
    return None

def capture(url,driver):
    # 1. 启动浏览器
    driver.get(url)
    driver.implicitly_wait(10)
    try:
        driver.switch_to.frame("frame1")
    except:
        print("未发现详情页 iframe，尝试直接定位...")
    # 2. 获取网页上的元素（红框和底图容器）
    # 注意：这里我们取 imgp 的宽度，它是 Canvas 渲染的基础参考宽度
    time.sleep(3) # 等待渲染
    linebox = driver.find_element(By.CLASS_NAME, "linebox")
    img_display_element = driver.find_element(By.CLASS_NAME, "imgp")

    # 获取网页显示的尺寸
    display_width = img_display_element.size['width']
    box_loc = linebox.location
    box_size = linebox.size
    img_container_loc = img_display_element.location

    # 3. 获取高清原图 URL
    img_url =get_hd_url(driver)
    response = requests.get(img_url)
    origin_img = Image.open(BytesIO(response.content))

    # 4. 【核心】自动计算比例
    # 比例 = 原图实际宽度 / 网页显示宽度
    scale = origin_img.width / display_width
    print(f"检测到原图分辨率: {origin_img.width}x{origin_img.height}")
    print(f"网页显示宽度: {display_width}, 自动计算比例为: {scale:.4f}")

    # 5. 计算原图上的裁剪坐标
    # 逻辑：(红框坐标 - 容器坐标) * 比例
    real_left = (box_loc['x'] - img_container_loc['x']) * scale
    real_top = (box_loc['y'] - img_container_loc['y']) * scale
    real_width = box_size['width'] * scale
    real_height = box_size['height'] * scale

    # 6. 裁剪并保存
    crop_img = origin_img.crop((real_left, real_top, real_left + real_width, real_top + real_height))
    return crop_img
