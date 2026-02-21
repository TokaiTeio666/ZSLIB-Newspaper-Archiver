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
    time.sleep(3)
    try:
        driver.switch_to.frame("frame1")
    except:
        print("未发现详情页 iframe，尝试直接定位...")
    # 2. 获取网页上的元素（红框和底图容器）
    display_width = 0
    start_time = time.time()
    while display_width <= 0 and (time.time() - start_time) < 10:  # 最多等10秒
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame("frame1")
            img_p = driver.find_element(By.CLASS_NAME, "imgp")
            display_width = img_p.size['width']
        except:
            pass
    if display_width <= 0:
        raise Exception("无法获取网页图片宽度，加载超时")

    linebox = driver.find_element(By.CLASS_NAME, "linebox")
    img_p = driver.find_element(By.CLASS_NAME, "imgp")

    left_px = float(linebox.value_of_css_property('left').replace('px', ''))
    top_px = float(linebox.value_of_css_property('top').replace('px', ''))
    # 获取网页显示的图片宽度
    display_width = img_p.size['width']
    # 3. 获取高清原图 URL
    img_url =get_hd_url(driver)
    response = requests.get(img_url)
    origin_img = Image.open(BytesIO(response.content))

    # 4. 【核心】自动计算比例
    # 比例 = 原图实际宽度 / 网页显示宽度
    scale = origin_img.width / display_width
    print(f"检测到原图分辨率: {origin_img.width}x{origin_img.height}")
    print(f"网页显示宽度: {display_width}, 自动计算比例为: {scale:.4f}")

    # 5. 计算原图上的裁剪坐标 (使用相对位移 * 比例)
    # 为了防止截图不全，我们稍微给 2-5 像素的 buffer
    real_left = left_px * scale
    real_top = top_px * scale
    real_width = linebox.size['width'] * scale
    real_height = linebox.size['height'] * scale

    # 6. 裁剪并保存
    crop_img = origin_img.crop((real_left, real_top, real_left + real_width, real_top + real_height))
    return crop_img
