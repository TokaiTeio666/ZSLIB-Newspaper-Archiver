"""
调试脚本：只打开一次浏览器，不关闭，逐步执行操作
运行后请在浏览器中完成登录，程序会自动继续
"""
import time
import re
import os
import json
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# 日志同时输出到文件和控制台
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

log_file = open(os.path.join(os.path.dirname(__file__), "debug_log.txt"), "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, log_file)
sys.stderr = Tee(sys.stderr, log_file)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# 初始化浏览器
log("正在打开浏览器...")
options = webdriver.EdgeOptions()
options.set_capability("ms:loggingPrefs", {"performance": "ALL"})
options.add_argument("--log-level=3")
options.add_experimental_option("excludeSwitches", ["enable-logging"])

driver = webdriver.Edge(options=options)
driver.implicitly_wait(10)
log("浏览器已打开")

try:
    # 第一步：打开报纸资源页
    log("正在打开广东省立中山图书馆报纸资源页...")
    driver.get("https://www.zslib.com.cn/Page/Page.html?t=bz")
    time.sleep(3)
    log(f"当前页面: {driver.title}, URL: {driver.current_url}")

    # 第二步：点击近代报纸数据库
    log("正在定位并点击'中国历史文献总库·近代报纸数据库'...")
    main_window = driver.current_window_handle

    # 关闭可能的登录弹窗
    try:
        link = driver.find_element(
            By.XPATH,
            "//a[contains(text(), '近代报纸数据库') and not(contains(@class, 'tags01'))]"
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", link)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", link)
        log("已点击标题链接")
    except Exception as e:
        log(f"点击标题链接失败: {e}")

    # 第三步：等待登录或进入数据库
    log("等待页面响应（如弹出登录窗口请扫码登录）...")
    db_window = None
    login_popup_detected = False
    login_popup_closed = False

    # 第一轮：检测登录弹窗或数据库窗口
    for i in range(30):
        time.sleep(2)
        # 检查是否有新窗口（数据库窗口）
        for handle in driver.window_handles:
            if handle != main_window:
                try:
                    driver.switch_to.window(handle)
                    title = driver.title
                    url = driver.current_url
                    if "报纸库" in title or "nlcpress" in url or "PaperSearch" in url:
                        db_window = handle
                        log(f"检测到数据库窗口: {title}")
                        break
                except Exception:
                    continue
        if db_window:
            break
        # 检查当前窗口是否已跳转
        try:
            driver.switch_to.window(main_window)
            if "报纸库" in driver.title or "nlcpress" in driver.current_url:
                db_window = main_window
                log("当前窗口已跳转到数据库")
                break
        except Exception:
            pass
        # 检查当前页面是否有登录弹窗
        if not login_popup_detected:
            try:
                driver.switch_to.window(main_window)
                login_boxes = driver.find_elements(By.CSS_SELECTOR, ".login_boxb_k, [class*=login_box], [class*=LoginBox]")
                for box in login_boxes:
                    if box.is_displayed():
                        login_popup_detected = True
                        log("检测到页面登录弹窗，请扫码登录...")
                        break
                if not login_popup_detected:
                    qr_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '扫码') or contains(@class, 'qrcode') or contains(@class, 'QRCode')]")
                    for qr in qr_elements:
                        if qr.is_displayed():
                            login_popup_detected = True
                            log("检测到扫码登录元素，请扫码登录...")
                            break
            except Exception:
                pass
        # 如果检测到登录弹窗，检查是否已关闭
        if login_popup_detected and not login_popup_closed:
            try:
                driver.switch_to.window(main_window)
                login_boxes = driver.find_elements(By.CSS_SELECTOR, ".login_boxb_k, [class*=login_box], [class*=LoginBox]")
                any_visible = any(box.is_displayed() for box in login_boxes)
                if not any_visible:
                    login_popup_closed = True
                    log("登录弹窗已关闭，登录成功！正在再次点击进入数据库...")
                    # 登录成功后再次点击链接
                    try:
                        link = driver.find_element(
                            By.XPATH,
                            "//a[contains(text(), '近代报纸数据库') and not(contains(@class, 'tags01'))]"
                        )
                        driver.execute_script("arguments[0].click();", link)
                        log("已再次点击标题链接")
                    except Exception as e:
                        log(f"再次点击失败: {e}")
            except Exception:
                pass

    # 如果登录弹窗已关闭但还没进入数据库，继续等待
    if login_popup_closed and not db_window:
        log("等待数据库窗口打开...")
        for i in range(20):
            time.sleep(2)
            for handle in driver.window_handles:
                try:
                    driver.switch_to.window(handle)
                    if "报纸库" in driver.title or "nlcpress" in driver.current_url:
                        db_window = handle
                        log(f"检测到数据库窗口: {driver.title}")
                        break
                except Exception:
                    continue
            if db_window:
                break

    # 如果还是没有数据库窗口，回到主窗口再点一次
    if not db_window:
        log("未检测到数据库窗口，回到主窗口重试点击...")
        try:
            driver.switch_to.window(main_window)
            time.sleep(1)
            link = driver.find_element(
                By.XPATH,
                "//a[contains(text(), '近代报纸数据库') and not(contains(@class, 'tags01'))]"
            )
            driver.execute_script("arguments[0].click();", link)
            log("已再次点击标题链接")
            time.sleep(10)
            # 再次检查数据库窗口
            for handle in driver.window_handles:
                try:
                    driver.switch_to.window(handle)
                    if "报纸库" in driver.title or "nlcpress" in driver.current_url:
                        db_window = handle
                        log(f"检测到数据库窗口: {driver.title}")
                        break
                except Exception:
                    continue
        except Exception as e:
            log(f"重试点击失败: {e}")

    # 切换到数据库窗口
    if db_window:
        driver.switch_to.window(db_window)
        log(f"已切换到数据库页面: {driver.title}")
        log(f"数据库URL: {driver.current_url}")
    else:
        log("错误：未能进入数据库，请手动在浏览器中操作，然后按回车继续...")
        input()
        # 用户操作后，检查当前窗口
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                if "报纸库" in driver.title or "nlcpress" in driver.current_url:
                    db_window = handle
                    log(f"用户操作后检测到数据库窗口: {driver.title}")
                    break
            except Exception:
                continue

    time.sleep(3)

    # 第四步：搜索
    log("正在执行搜索...")
    log(f"搜索页面: {driver.title}, URL: {driver.current_url}")

    # 确保在主文档
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    # 找到搜索框
    search_input = None
    try:
        search_input = driver.find_element(By.ID, "searchkeyword")
        log(f"通过ID找到搜索框: {search_input.tag_name}")
    except Exception:
        try:
            search_input = driver.find_element(By.XPATH, "//input[contains(@class, 'inp_srh')]")
            log("通过class找到搜索框")
        except Exception as e:
            log(f"未找到搜索框: {e}")

    if search_input:
        # 点击激活
        try:
            search_input.click()
            time.sleep(0.5)
        except Exception:
            pass

        # 用JavaScript设置值
        try:
            driver.execute_script(
                "arguments[0].focus(); arguments[0].value = '茂名'; "
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true})); "
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                search_input
            )
            time.sleep(1)
            actual = search_input.get_attribute("value") or ""
            log(f"搜索框当前值: {actual}")
        except Exception as e:
            log(f"JavaScript输入失败: {e}")
            try:
                search_input.clear()
                search_input.send_keys("茂名")
                log("标准输入成功")
            except Exception as e2:
                log(f"标准输入也失败: {e2}")

        # 点击搜索按钮
        try:
            search_btn = driver.find_element(By.XPATH, "//input[contains(@class, 'btn_srh') and contains(@value, '检索')]")
            log("找到搜索按钮")
            # 记录当前窗口
            handles_before = set(driver.window_handles)
            search_btn.click()
            log("已点击搜索按钮")

            # 等待新窗口（搜索结果在新窗口打开）
            log("等待搜索结果窗口...")
            new_window = None
            for _ in range(15):
                time.sleep(1)
                current_handles = set(driver.window_handles)
                new_handles = current_handles - handles_before
                if new_handles:
                    new_window = new_handles.pop()
                    log("检测到搜索结果新窗口")
                    break
                # 也可能在当前窗口跳转
                try:
                    if "PaperSearch" in driver.current_url or "检索" in driver.title:
                        log("当前窗口已跳转到搜索结果页")
                        break
                except Exception:
                    pass

            if new_window:
                driver.switch_to.window(new_window)
                log(f"已切换到搜索结果窗口: {driver.title}")
        except Exception as e:
            log(f"点击搜索按钮失败: {e}")

    time.sleep(5)
    log(f"搜索后页面: {driver.title}, URL: {driver.current_url}")

    # 保存搜索结果页HTML
    try:
        html_path = os.path.join(os.path.dirname(__file__), "search_result_debug.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log(f"搜索结果HTML已保存: {html_path}")
    except Exception as e:
        log(f"保存HTML失败: {e}")

    # 第五步：解析搜索结果
    log("正在解析搜索结果...")
    records = []

    # 查找"阅读"链接
    try:
        read_links = driver.find_elements(By.XPATH, "//a[contains(text(), '阅读') and not(contains(text(), '整报'))]")
        log(f"找到 {len(read_links)} 个'阅读'链接")

        for i, link in enumerate(read_links[:5]):  # 只处理前5条
            try:
                url = link.get_attribute("href") or ""
                # 向上找记录行
                row = link
                row_text = ""
                for _ in range(8):
                    try:
                        row = row.find_element(By.XPATH, "..")
                        row_text = row.text.strip()
                        if re.search(r"\d{4}-\d{1,2}-\d{1,2}", row_text) and "版" in row_text:
                            break
                    except Exception:
                        break

                log(f"记录 {i+1}: {row_text[:100]}")
                records.append({"url": url, "text": row_text})
            except Exception as e:
                log(f"解析记录 {i+1} 失败: {e}")
    except Exception as e:
        log(f"查找阅读链接失败: {e}")

    # 如果没找到阅读链接，打印页面信息
    if not records:
        log("未找到记录，打印页面链接信息...")
        try:
            all_links = driver.find_elements(By.TAG_NAME, "a")
            log(f"页面共有 {len(all_links)} 个链接")
            for link in all_links[:20]:
                text = link.text.strip()
                href = link.get_attribute("href") or ""
                if text and len(text) > 1:
                    log(f"  链接: text='{text[:30]}', href='{href[:80]}'")
        except Exception as e:
            log(f"打印链接信息失败: {e}")

    log("\n" + "=" * 50)
    log("调试阶段完成！浏览器保持打开状态")
    log(f"共解析到 {len(records)} 条记录")
    log("请查看浏览器和日志文件 debug_log.txt")
    log("=" * 50)

    # 不关闭浏览器，等待用户操作
    input("\n按回车键关闭浏览器...")

except Exception as e:
    log(f"发生错误: {e}")
    import traceback
    log(traceback.format_exc())
    log("浏览器保持打开状态，按回车关闭...")
    input()
finally:
    try:
        driver.quit()
    except Exception:
        pass
