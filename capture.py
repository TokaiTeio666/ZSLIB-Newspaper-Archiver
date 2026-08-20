import time
import base64
from io import BytesIO
from PIL import Image
from selenium.webdriver.common.by import By
import re


def download_image_bytes(driver, url):
    """
    通过浏览器 fetch 下载图片字节，自动携带会话 cookies 并穿透 VPN。
    返回 bytes 或 None。
    """
    js = """
    const url = arguments[0];
    const done = arguments[arguments.length - 1];
    fetch(url, {credentials: 'include'})
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob(); })
      .then(b => {
        const fr = new FileReader();
        fr.onload = () => done(fr.result);
        fr.onerror = () => done(null);
        fr.readAsDataURL(b);
      })
      .catch(() => done(null));
    """
    try:
        data_url = driver.execute_async_script(js, url)
    except Exception as e:
        print(f"浏览器 fetch 下载失败: {e}")
        return None
    if not data_url or ',' not in data_url:
        return None
    return base64.b64decode(data_url.split(',', 1)[1])


def get_image_urls(driver):
    """
    从详情页 DOM 直接读取中图/高清大图绝对 URL（不依赖性能日志）。
    返回 (middle_url, large_url)，任一可能为 None。
    """
    js = """
    var mid = null, large = null;
    var lp = document.getElementById('LayoutPic');
    if (lp && lp.src) mid = lp.src;
    var ll = document.getElementById('layoutLargePhotoURL');
    if (ll && ll.value) large = ll.value;
    return {middle: mid, large: large};
    """
    try:
        info = driver.execute_script(js) or {}
    except Exception as e:
        print(f"读取图片URL失败: {e}")
        return None, None

    middle_url = info.get('middle')
    large_url = info.get('large')

    # 优先：由已加载的中图绝对 URL 替换 IMG_MIDDLE -> IMG_LARGE_PATH，
    # 保证路径、VPN 前缀、;vpn_img 标记与浏览器实际加载完全一致。
    if middle_url and 'IMG_MIDDLE' in middle_url:
        large_url = middle_url.replace('IMG_MIDDLE', 'IMG_LARGE_PATH')

    # 兜底：相对 URL 用 urljoin 解析
    if large_url and not large_url.startswith('http'):
        from urllib.parse import urljoin
        try:
            large_url = urljoin(driver.current_url, large_url)
        except Exception:
            pass

    return middle_url, large_url


def parse_layout_area(driver):
    """
    读取 #layoutArea 红框坐标（形如 "219,207,219,236,174,236,174,207"），
    返回包围盒 (minX, minY, maxX, maxY) 或 None。
    """
    try:
        val = driver.execute_script(
            "var el = document.getElementById('layoutArea'); return el ? el.value : '';"
        )
    except Exception as e:
        print(f"读取 layoutArea 失败: {e}")
        return None
    if not val:
        return None
    nums = [float(x) for x in val.replace(';', ',').split(',') if x.strip() != '']
    if len(nums) < 4:
        return None
    xs = nums[0::2]
    ys = nums[1::2]
    return (min(xs), min(ys), max(xs), max(ys))


def get_display_size(driver):
    """
    读取红框所在坐标系的显示尺寸（canvas 缓冲尺寸，即红框绘制空间）。
    红框坐标(layoutArea)位于该显示空间（约 359x500），而非中图固有像素空间。
    返回 (width, height) 或 None。
    """
    js = """
    var c = document.getElementById('diagonal');
    if (c && c.width && c.height) return {w: c.width, h: c.height};
    var pb = document.querySelector('.paperBox');
    if (pb) return {w: pb.offsetWidth, h: pb.offsetHeight};
    var lp = document.getElementById('LayoutPic');
    if (lp) { var r = lp.getBoundingClientRect(); return {w: r.width, h: r.height}; }
    return null;
    """
    try:
        r = driver.execute_script(js)
    except Exception as e:
        print(f"读取显示尺寸失败: {e}")
        return None
    if r and r.get('w') and r.get('h'):
        return (float(r['w']), float(r['h']))
    return None


def crop_from_large(driver, large_url, box):
    """
    下载高清大图，按「显示坐标空间 -> 高清大图固有尺寸」的比例缩放红框包围盒并精准裁剪。
    返回 PIL Image 或 None（None 时调用方走兜底路径）。
    """
    if not large_url:
        print("未获取到高清大图URL")
        return None

    disp_size = get_display_size(driver)
    if not disp_size:
        print("未获取到显示坐标空间尺寸")
        return None
    disp_w, disp_h = disp_size
    print(f"显示坐标空间尺寸: {disp_w}x{disp_h}")

    # 下载高清大图
    large_bytes = download_image_bytes(driver, large_url)
    if not large_bytes:
        print("下载高清大图失败")
        return None
    try:
        large_img = Image.open(BytesIO(large_bytes)).convert('RGB')
    except Exception as e:
        print(f"高清大图解析失败: {e}")
        return None
    print(f"高清大图尺寸: {large_img.width}x{large_img.height}")

    scale_x = large_img.width / disp_w
    scale_y = large_img.height / disp_h
    print(f"缩放比例: x={scale_x:.4f}, y={scale_y:.4f}")

    min_x, min_y, max_x, max_y = box
    crop_left = max(0, int(min_x * scale_x))
    crop_top = max(0, int(min_y * scale_y))
    crop_right = min(large_img.width, int(max_x * scale_x + 0.5))
    crop_bottom = min(large_img.height, int(max_y * scale_y + 0.5))

    # 健壮性校验：裁剪区域为空或覆盖过大，说明坐标空间假设错误
    if crop_right <= crop_left or crop_bottom <= crop_top:
        print("裁剪区域无效，坐标空间可能错误")
        return None
    if (crop_right - crop_left) / large_img.width > 0.95 and \
       (crop_bottom - crop_top) / large_img.height > 0.95:
        print("裁剪区域过大，坐标空间可能错误")
        return None

    crop_img = large_img.crop((crop_left, crop_top, crop_right, crop_bottom))
    print(f"高清原图红框裁剪成功，尺寸: {crop_img.size}")
    return crop_img


def ocr_text(crop_img):
    """
    可选的 OCR 增强接口（暂不集成，未安装依赖时静默返回空串）。
    后续如需接入 PaddleOCR/EasyOCR，在此实现并从裁剪图中识别正文。
    """
    return ""


def extract_article_text(driver):
    """
    从详情页提取文章文字信息（篇名、作者、正文等）
    近代报纸数据库详情页右侧通常显示篇名、作者等文字
    """
    text_info = {
        "title": "",
        "author": "",
        "content": "",
        "full_text": ""
    }

    # 策略1：查找常见的文字信息容器
    selectors = [
        "//div[contains(@class,'article-info')]",
        "//div[contains(@class,'text-info')]",
        "//div[contains(@class,'detail-info')]",
        "//div[contains(@class,'right-panel')]",
        "//div[contains(@class,'right-content')]",
        "//div[contains(@class,'info-panel')]",
        "//div[contains(@class,'meta')]",
        "//div[contains(@id,'info')]",
        "//div[contains(@id,'text')]",
        "//div[contains(@id,'article')]",
        "//td[contains(@class,'info')]",
        "//div[contains(@class,'title')]",
    ]

    for selector in selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for el in elements:
                if el.is_displayed():
                    text = el.text.strip()
                    if text and len(text) > 1:
                        text_info["full_text"] += text + "\n"
                        # 尝试提取标题
                        if not text_info["title"]:
                            title_el = el.find_elements(By.XPATH, ".//*[contains(@class,'title') or contains(@id,'title')]")
                            if title_el:
                                text_info["title"] = title_el[0].text.strip()
        except Exception:
            continue

    # 策略2：查找篇名、作者等标签
    try:
        labels = driver.find_elements(
            By.XPATH,
            "//*[contains(text(),'篇名') or contains(text(),'标题') or contains(text(),'作者') or contains(text(),'栏目')]"
        )
        for label in labels:
            try:
                # 获取标签后面的文本或兄弟元素
                parent = label.find_element(By.XPATH, "..")
                parent_text = parent.text.strip()
                if parent_text and parent_text not in text_info["full_text"]:
                    text_info["full_text"] += parent_text + "\n"
            except Exception:
                continue
    except Exception:
        pass

    # 策略3：如果右侧有独立的iframe，尝试切换进去提取
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            iframe_name = iframe.get_attribute("name") or ""
            iframe_id = iframe.get_attribute("id") or ""
            if any(kw in iframe_name + iframe_id for kw in ["text", "info", "detail", "right", "article"]):
                driver.switch_to.frame(iframe)
                time.sleep(1)
                body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
                if body_text:
                    text_info["full_text"] += body_text + "\n"
                driver.switch_to.default_content()
                break
    except Exception:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    # 从full_text中解析标题和作者
    full = text_info["full_text"].strip()

    # 过滤掉页面导航文字
    nav_keywords = [
        "报纸首页", "报纸简介", "区域导航", "拼音导航", "使用手册",
        "关于我们", "省立中山图书馆", "ENGLISH", "中文", "当前的位置",
        "版面导航", "查看当天其他报纸", ">>", "返回版面", "返回首页",
        "下一版", "上一版", "上一篇", "下一篇", "导航", "Copyright",
        "联系电话", "发行部", "All Rights", "国家图书馆出版社",
        "第.*版：", "版：\\d+$"
    ]

    if full:
        lines = [l.strip() for l in full.split("\n") if l.strip()]
        filtered_lines = []
        for line in lines:
            # 过滤掉包含导航关键词的行
            is_nav = False
            for kw in nav_keywords:
                if re.search(kw, line):
                    is_nav = True
                    break
            # 过滤掉纯数字或短文本（如"第5"、"一"、"二"等）
            if len(line) <= 2:
                is_nav = True
            # 过滤掉单独的日期导航（一、二、三、四、五、六、日）
            if re.match(r"^[一二三四五六日]$", line):
                is_nav = True
            # 过滤掉版次信息（如"第5版"）
            if re.match(r"^第\d+版$", line):
                is_nav = True
            if not is_nav:
                filtered_lines.append(line)

        lines = filtered_lines

        if lines:
            # 第一行通常是标题
            if not text_info["title"]:
                text_info["title"] = lines[0]
            # 查找作者
            for line in lines:
                author_match = re.search(r"作者[：:\s]+(.+)", line)
                if author_match:
                    text_info["author"] = author_match.group(1).strip()
                    break
            # 剩余作为内容
            content_lines = []
            for line in lines:
                if line != text_info["title"] and not re.match(r"^(作者|篇名|标题|栏目|版次|日期)[：:]", line):
                    content_lines.append(line)
            text_info["content"] = "\n".join(content_lines)

    print(f"提取到文字信息: 标题='{text_info['title']}', 作者='{text_info['author']}', 内容长度={len(text_info['content'])}")
    return text_info


def capture(url, driver, output_dir="采集结果"):
    """
    访问详情页，截取红框部分的高清原图，并提取文字信息
    返回: (cropped_image, text_info)

    注意：当url为空时，直接使用当前driver所在的页面（已在详情页）
    """
    # 1. 打开详情页（如果提供了url）
    if url:
        driver.get(url)
        driver.implicitly_wait(5)
        time.sleep(2)
    else:
        # 直接使用当前页面，等待渲染
        driver.implicitly_wait(5)
        time.sleep(1)

    # 尝试切换到详情页iframe（排除导航iframe如treeframe）
    iframe_switched = False
    for iframe_id in ["frame1", "detailFrame", "contentFrame", "mainFrame", "readerFrame"]:
        try:
            iframe = driver.find_element(By.ID, iframe_id)
            if iframe.get_attribute("id") != "treeframe":
                driver.switch_to.frame(iframe)
                iframe_switched = True
                print(f"已切换到详情页iframe: {iframe_id}")
                break
        except Exception:
            continue

    if not iframe_switched:
        # 尝试切换到内容iframe（排除treeframe导航iframe）
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                iframe_id = iframe.get_attribute("id") or ""
                if iframe_id != "treeframe" and "navi" not in iframe_id.lower():
                    driver.switch_to.frame(iframe)
                    iframe_switched = True
                    print(f"已切换到内容iframe: {iframe_id}")
                    break
            if not iframe_switched:
                print("未发现内容iframe，直接在主文档中定位...")
        except Exception:
            print("未发现详情页iframe，直接在主文档中定位...")

    # 2. 提取文字信息（篇名/作者等，来自主文档）
    time.sleep(1)
    text_info = {"title": "", "author": "", "content": "", "full_text": ""}
    print("开始提取文字信息...")
    try:
        driver.switch_to.default_content()
        text_info = extract_article_text(driver)
    except Exception as e:
        print(f"提取文字信息时出错: {e}")

    # 3. 从 DOM 读取高清大图 URL 与红框坐标（确保在主文档）
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    print("从 DOM 读取高清大图 URL 与红框坐标...")
    middle_url, large_url = get_image_urls(driver)
    box = parse_layout_area(driver)

    if large_url:
        print(f"高清大图URL: {large_url[:100]}...")
    if box:
        print(f"红框包围盒: {box}")
    else:
        print("未找到红框坐标")

    # 4. 下载高清大图并精准裁剪
    if large_url and box:
        crop_img = crop_from_large(driver, large_url, box)
        if crop_img is not None:
            return crop_img, text_info

    # 5. 兜底：返回整个页面截图
    print("高清裁剪失败，使用页面截图兜底...")
    try:
        screenshot = driver.get_screenshot_as_png()
        fallback_img = Image.open(BytesIO(screenshot))
        return fallback_img, text_info
    except Exception as e:
        print(f"页面截图也失败: {e}")
        return None, text_info
