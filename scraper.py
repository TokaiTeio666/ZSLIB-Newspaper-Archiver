import time
import re
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from save_to_word import save_to_separate_word


class NewspaperScraper:
    def __init__(self, search_str, output_dir="采集结果", log_callback=None, headless=False):
        self.search_str = search_str
        self.output_dir = output_dir
        self.log = log_callback or print
        self.driver = None
        self._stop = False
        self.headless = headless
        self._implicit_wait = 2
        self.cookies_path = os.path.join(os.path.dirname(__file__), "cookies.json")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def stop(self):
        self._stop = True

    def quit(self):
        """立即停止并关闭浏览器驱动（可在任意线程调用，用于退出/停止时确保 driver.quit 生效）"""
        self._stop = True
        driver = self.driver
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    def run(self):
        try:
            self.log(f"开始搜索: {self.search_str}")

            options = webdriver.EdgeOptions()
            options.set_capability("ms:loggingPrefs", {"performance": "ALL"})
            options.add_argument("--log-level=3")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-popup-blocking")
            options.page_load_strategy = "eager"
            options.unhandled_prompt_behavior = "accept"
            if self.headless:
                options.add_argument("--headless=new")
                options.add_argument("--window-size=1920,1080")

            self.driver = webdriver.Edge(options=options)
            self.driver.implicitly_wait(self._implicit_wait)
            start_time = time.time()

            # ========== 第一步：打开报纸资源页 ==========
            self.log("正在打开广东省立中山图书馆报纸资源页...")
            self.driver.get("https://www.zslib.com.cn/Page/Page.html?t=bz")
            time.sleep(3)

            # 加载已保存的cookies
            self._load_cookies()

            # ========== 第二步：点击进入近代报纸数据库 ==========
            self.log("正在定位并点击'中国历史文献总库·近代报纸数据库'...")
            main_window = self.driver.current_window_handle
            self._click_modern_newspaper_link()

            # ========== 第三步：等待登录，登录后再次点击 ==========
            self.log("等待页面响应（如弹出登录窗口请扫码登录）...")
            db_window = None
            login_popup_detected = False
            login_popup_closed = False
            login_popup_start_time = None
            reclick_count = 0

            for i in range(60):
                if self._stop:
                    break
                time.sleep(1)
                # 检查是否有数据库窗口
                for handle in self.driver.window_handles:
                    if handle != main_window:
                        try:
                            self.driver.switch_to.window(handle)
                            if "报纸库" in self.driver.title or "nlcpress" in self.driver.current_url or "PaperSearch" in self.driver.current_url:
                                db_window = handle
                                self.log(f"检测到数据库窗口: {self.driver.title}")
                                break
                        except Exception:
                            continue
                if db_window:
                    break
                # 检查当前窗口是否已跳转
                try:
                    self.driver.switch_to.window(main_window)
                    if "报纸库" in self.driver.title or "nlcpress" in self.driver.current_url:
                        db_window = main_window
                        self.log("当前窗口已跳转到数据库")
                        break
                except Exception:
                    pass
                # 检测登录弹窗
                if not login_popup_detected:
                    try:
                        self.driver.switch_to.window(main_window)
                        login_boxes = self.driver.find_elements(By.CSS_SELECTOR, ".login_boxb_k")
                        for box in login_boxes:
                            if box.is_displayed():
                                login_popup_detected = True
                                login_popup_start_time = time.time()
                                self.log("检测到页面登录弹窗，请扫码登录...")
                                break
                    except Exception:
                        pass
                # 如果检测到登录弹窗，检查是否已关闭
                if login_popup_detected and not login_popup_closed:
                    try:
                        self.driver.switch_to.window(main_window)
                        login_boxes = self.driver.find_elements(By.CSS_SELECTOR, ".login_boxb_k")
                        any_visible = False
                        for box in login_boxes:
                            try:
                                if box.is_displayed():
                                    style = box.get_attribute("style") or ""
                                    if "display: none" not in style and "display:none" not in style:
                                        any_visible = True
                                        break
                            except Exception:
                                continue
                        elapsed = time.time() - login_popup_start_time if login_popup_start_time else 0
                        if not any_visible:
                            login_popup_closed = True
                            self.log("登录弹窗已关闭，登录成功！正在再次点击进入数据库...")
                            time.sleep(1)
                            self._click_modern_newspaper_link()
                            reclick_count += 1
                        elif elapsed > 90 and reclick_count < 2:
                            # 超时，用JavaScript关闭登录弹窗，然后再次点击
                            self.log(f"登录超时（{elapsed:.0f}秒），强制关闭弹窗并再次点击...")
                            try:
                                self.driver.execute_script(
                                    "var boxes = document.querySelectorAll('.login_boxb_k'); "
                                    "boxes.forEach(function(b){ b.style.display='none'; });"
                                )
                            except Exception:
                                pass
                            time.sleep(1)
                            self._click_modern_newspaper_link()
                            reclick_count += 1
                            login_popup_start_time = time.time()  # 重置计时
                    except Exception as e:
                        self.log(f"  登录弹窗检测异常: {e}")

            # 如果已再次点击但还没进入数据库，继续等待
            if login_popup_closed and not db_window:
                self.log("等待数据库窗口打开...")
                for i in range(20):
                    if self._stop:
                        break
                    time.sleep(1)
                    for handle in self.driver.window_handles:
                        try:
                            self.driver.switch_to.window(handle)
                            if "报纸库" in self.driver.title or "nlcpress" in self.driver.current_url:
                                db_window = handle
                                self.log(f"检测到数据库窗口: {self.driver.title}")
                                break
                        except Exception:
                            continue
                    if db_window:
                        break

            # ========== 第四步：切换到数据库窗口 ==========
            self.log("正在查找数据库页面...")
            if db_window:
                self.driver.switch_to.window(db_window)
                self.log(f"已切换到数据库页面: {self.driver.title}")
                self.log(f"当前URL: {self.driver.current_url}")
                # 保存最新的cookies
                self._save_cookies()
            else:
                self.log("未找到独立的数据库窗口，使用当前窗口...")
                if "报纸库" not in self.driver.title and "nlcpress" not in self.driver.current_url:
                    self.log("警告：未能进入数据库，请手动在浏览器中操作...")
                    time.sleep(15)
                    db_window = self._find_database_window()
                    if db_window:
                        self.driver.switch_to.window(db_window)
                        self._save_cookies()

            time.sleep(3)

            if self._stop:
                return

            # ========== 第五步：搜索 ==========
            self.log("正在执行搜索...")
            self._perform_search()

            # ========== 第六步：采集结果 ==========
            self.log("开始遍历搜索结果...")
            self._collect_results()

            if self._stop:
                self.log("用户手动停止。")
            else:
                self.log("所有采集任务已完成。")

        except Exception as e:
            self.log(f"采集过程出错: {e}")
            import traceback
            self.log(traceback.format_exc())
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass

    def _click_modern_newspaper_link(self):
        """点击近代报纸数据库标题链接"""
        try:
            link = self.driver.find_element(
                By.XPATH,
                "//a[contains(text(), '近代报纸数据库') and not(contains(@class, 'tags01'))]"
            )
            # 滚动到元素位置
            self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
            time.sleep(0.5)
            # 优先使用JavaScript点击（绕过元素遮挡）
            self.driver.execute_script("arguments[0].click();", link)
            self.log("已点击标题链接（JavaScript方式）")
            return True
        except Exception as e:
            self.log(f"点击标题链接失败: {e}")

        # 备选：点击"登录浏览"按钮
        try:
            btns = self.driver.find_elements(
                By.XPATH,
                "//a[contains(text(), '登录浏览')]"
            )
            for btn in btns:
                try:
                    parent = btn.find_element(By.XPATH, "..")
                    for _ in range(5):
                        if "近代报纸数据库" in parent.text and "华侨" not in parent.text:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(0.5)
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.log("已点击'登录浏览'按钮（JavaScript方式）")
                            return True
                        parent = parent.find_element(By.XPATH, "..")
                except Exception:
                    continue
        except Exception as e:
            self.log(f"点击'登录浏览'按钮失败: {e}")

        self.log("点击入口失败")
        return False

    def _find_database_window(self):
        """遍历所有窗口，找到近代报纸数据库的窗口"""
        for handle in self.driver.window_handles:
            try:
                self.driver.switch_to.window(handle)
                title = self.driver.title
                url = self.driver.current_url
                # 数据库窗口的特征：标题包含"报纸"，或URL包含nlcpress/bz
                if ("报纸" in title and "资源" not in title) or "nlcpress" in url or "bz." in url:
                    self.log(f"找到数据库窗口: title={title}, url={url}")
                    return handle
            except Exception:
                continue
        return None

    def _perform_search(self):
        """在近代报纸数据库页面执行搜索"""
        time.sleep(3)
        self.log(f"搜索页面标题: {self.driver.title}")
        self.log(f"搜索页面URL: {self.driver.current_url}")

        # 确保在主页面
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

        # 先在主页面找搜索框
        search_input = self._find_search_input()

        # 如果主页面找不到，尝试切换到iframe
        if search_input is None:
            self.log("主页面未找到搜索框，尝试切换到iframe...")
            search_input = self._find_search_input_in_frames()

        if search_input is None:
            self.log("无法定位搜索框，打印页面信息用于调试...")
            self._debug_page_info()
            raise Exception("无法定位搜索输入框")

        # 打印搜索框信息
        self.log(f"搜索框: tag={search_input.tag_name}, id={search_input.get_attribute('id')}, "
                 f"name={search_input.get_attribute('name')}, type={search_input.get_attribute('type')}, "
                 f"readonly={search_input.get_attribute('readonly')}, disabled={search_input.get_attribute('disabled')}")

        # 点击激活
        try:
            search_input.click()
            time.sleep(1)
        except Exception:
            pass

        # 输入关键词（优先用JavaScript，最可靠）
        input_ok = False
        try:
            self.driver.execute_script(
                "arguments[0].focus(); arguments[0].value = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true})); "
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                search_input, self.search_str
            )
            time.sleep(1)
            # 验证输入是否成功
            actual_value = search_input.get_attribute("value") or ""
            if self.search_str in actual_value:
                input_ok = True
                self.log(f"JavaScript输入成功，当前值: {actual_value}")
            else:
                self.log(f"JavaScript输入后值不匹配，当前值: {actual_value}")
        except Exception as e:
            self.log(f"JavaScript输入失败: {e}")

        # 备选：标准输入
        if not input_ok:
            try:
                search_input.clear()
                time.sleep(0.5)
                search_input.send_keys(self.search_str)
                time.sleep(1)
                input_ok = True
                self.log("标准输入成功")
            except Exception as e:
                self.log(f"标准输入失败: {e}")

        if not input_ok:
            raise Exception("无法在搜索框中输入关键词")

        # 点击搜索按钮（搜索结果会在新窗口打开，因为表单target="_blank"）
        search_btn = self._find_search_button()
        if search_btn:
            self.log("点击搜索按钮...")
            # 记录当前窗口
            handles_before = set(self.driver.window_handles)
            try:
                search_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", search_btn)

            # 等待新窗口打开
            self.log("等待搜索结果窗口打开...")
            new_window = None
            for _ in range(15):
                time.sleep(1)
                current_handles = set(self.driver.window_handles)
                new_handles = current_handles - handles_before
                if new_handles:
                    new_window = new_handles.pop()
                    self.log(f"检测到搜索结果新窗口")
                    break
                # 也可能在当前窗口跳转
                try:
                    if "PaperSearch" in self.driver.current_url or "检索" in self.driver.title:
                        self.log("当前窗口已跳转到搜索结果页")
                        break
                except Exception:
                    pass

            if new_window:
                self.driver.switch_to.window(new_window)
                self.log(f"已切换到搜索结果窗口: {self.driver.title}")
        else:
            self.log("未找到搜索按钮，按回车搜索...")
            try:
                search_input.send_keys(Keys.RETURN)
            except Exception:
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));",
                    search_input
                )

        time.sleep(5)
        self.log(f"搜索完成，当前页面: {self.driver.title}")
        self.log(f"搜索结果URL: {self.driver.current_url}")

        # 切回默认内容
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

    def _find_search_input(self):
        """定位搜索输入框"""
        # 策略1：通过ID（近代报纸数据库的搜索框ID是 searchkeyword）
        for id_val in ["searchkeyword", "txtBaseSearchValue", "searchValue", "keyword",
                        "searchKey", "searchText", "query", "searchInput", "txtSearch", "inputKey"]:
            try:
                el = self.driver.find_element(By.ID, id_val)
                if el.is_displayed():
                    return el
            except Exception:
                continue

        # 策略2：通过class（近代报纸数据库的搜索框class是 inp_srh）
        try:
            el = self.driver.find_element(By.XPATH, "//input[contains(@class, 'inp_srh')]")
            if el.is_displayed():
                return el
        except Exception:
            pass

        # 策略3：通过name
        for name_val in ["keyword", "searchKey", "query", "searchValue", "wd", "key"]:
            try:
                el = self.driver.find_element(By.NAME, name_val)
                if el.is_displayed():
                    return el
            except Exception:
                continue

        # 策略4：通过placeholder
        try:
            el = self.driver.find_element(
                By.XPATH,
                "//input[contains(@placeholder, '输入') or contains(@placeholder, '搜索') "
                "or contains(@placeholder, '关键字') or contains(@placeholder, '检索') "
                "or contains(@placeholder, '请输入')]"
            )
            if el.is_displayed():
                return el
        except Exception:
            pass

        # 策略5：找页面中第一个可见的文本输入框
        try:
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                itype = (inp.get_attribute("type") or "text").lower()
                if itype in ["text", "search", ""] and inp.is_displayed() and inp.is_enabled():
                    return inp
        except Exception:
            pass

        return None

    def _find_search_input_in_frames(self):
        """遍历所有iframe查找搜索框"""
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.log(f"找到 {len(iframes)} 个iframe，逐个查找搜索框...")
            for i, iframe in enumerate(iframes):
                try:
                    self.driver.switch_to.default_content()
                    self.driver.switch_to.frame(iframe)
                    time.sleep(1)
                    el = self._find_search_input()
                    if el:
                        self.log(f"在第 {i+1} 个iframe中找到搜索框")
                        return el
                except Exception as e:
                    self.log(f"第 {i+1} 个iframe查找失败: {e}")
                    continue
            # 切回主页面
            self.driver.switch_to.default_content()
        except Exception:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
        return None

    def _find_search_button(self):
        """定位搜索按钮"""
        # 策略1：通过class（近代报纸数据库的搜索按钮class是 btn_srh，value是"检索"）
        try:
            el = self.driver.find_element(
                By.XPATH,
                "//input[contains(@class, 'btn_srh') and contains(@value, '检索')]"
            )
            if el.is_displayed():
                return el
        except Exception:
            pass

        try:
            el = self.driver.find_element(By.XPATH, "//input[contains(@class, 'btn_srh')]")
            if el.is_displayed():
                return el
        except Exception:
            pass

        # 策略2：通过ID
        for id_val in ["btnsearchimg", "btnSearch", "searchBtn", "btnsearch",
                        "searchButton", "btn_query", "queryBtn", "btnQuery", "btnSearchimg"]:
            try:
                el = self.driver.find_element(By.ID, id_val)
                if el.is_displayed():
                    return el
            except Exception:
                continue

        # 策略2：通过value文本
        try:
            el = self.driver.find_element(
                By.XPATH,
                "//input[@type='submit' or @type='button']"
                "[contains(@value, '检索') or contains(@value, '搜索') or contains(@value, '查询')]"
            )
            if el.is_displayed():
                return el
        except Exception:
            pass

        # 策略3：通过button文本
        try:
            el = self.driver.find_element(
                By.XPATH,
                "//button[contains(text(), '检索') or contains(text(), '搜索') or contains(text(), '查询')]"
            )
            if el.is_displayed():
                return el
        except Exception:
            pass

        # 策略4：通过链接文本
        try:
            el = self.driver.find_element(
                By.XPATH,
                "//a[contains(text(), '检索') or contains(text(), '搜索') or contains(text(), '查询')]"
            )
            if el.is_displayed():
                return el
        except Exception:
            pass

        return None

    def _load_cookies(self):
        """加载已保存的cookies（只加载与当前域名匹配的cookies）"""
        if not os.path.exists(self.cookies_path):
            self.log("未找到已保存的cookies，将使用全新登录")
            return False
        try:
            with open(self.cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            current_url = self.driver.current_url
            count = 0
            for cookie in cookies:
                try:
                    cookie_domain = cookie.get("domain", "")
                    # 只加载与当前域名匹配的cookies
                    if cookie_domain and cookie_domain not in current_url:
                        continue
                    # 移除可能导致问题的字段
                    cookie_copy = cookie.copy()
                    cookie_copy.pop("sameSite", None)
                    cookie_copy.pop("storeId", None)
                    cookie_copy.pop("id", None)
                    self.driver.add_cookie(cookie_copy)
                    count += 1
                except Exception:
                    continue
            self.log(f"已加载 {count} 个cookies（当前域名: {current_url}）")
            if count > 0:
                # 刷新页面使cookies生效
                self.driver.refresh()
                time.sleep(3)
            return count > 0
        except Exception as e:
            self.log(f"加载cookies失败: {e}")
            return False

    def _save_cookies(self):
        """保存所有窗口的cookies（遍历所有窗口，合并不同域名的cookies）"""
        try:
            all_cookies = []
            seen = set()
            current_handle = self.driver.current_window_handle

            for handle in self.driver.window_handles:
                try:
                    self.driver.switch_to.window(handle)
                    time.sleep(0.5)
                    cookies = self.driver.get_cookies()
                    for cookie in cookies:
                        # 用name+domain作为唯一标识
                        key = f"{cookie.get('name')}@{cookie.get('domain')}"
                        if key not in seen:
                            seen.add(key)
                            all_cookies.append(cookie)
                except Exception:
                    continue

            # 切回原窗口
            try:
                self.driver.switch_to.window(current_handle)
            except Exception:
                pass

            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(all_cookies, f, ensure_ascii=False, indent=2)
            self.log(f"已保存 {len(all_cookies)} 个cookies（来自所有窗口）到: {self.cookies_path}")
        except Exception as e:
            self.log(f"保存cookies失败: {e}")

    def _debug_page_info(self):
        """打印页面调试信息"""
        try:
            self.log(f"页面标题: {self.driver.title}")
            self.log(f"页面URL: {self.driver.current_url}")
            # 统计iframe
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.log(f"iframe数量: {len(iframes)}")
            for i, iframe in enumerate(iframes):
                self.log(f"  iframe[{i}]: id={iframe.get_attribute('id')}, name={iframe.get_attribute('name')}, src={iframe.get_attribute('src')}")
            # 统计input
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            self.log(f"input数量: {len(inputs)}")
            for i, inp in enumerate(inputs[:10]):
                self.log(f"  input[{i}]: id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, "
                         f"type={inp.get_attribute('type')}, placeholder={inp.get_attribute('placeholder')}, "
                         f"visible={inp.is_displayed()}")
        except Exception as e:
            self.log(f"打印调试信息失败: {e}")

    def _dismiss_popup(self):
        """自动关闭原生 alert/confirm/prompt 及常见 HTML 提示层，返回是否处理了弹窗"""
        # 1. 原生 alert/confirm/prompt：switch_to.alert 不受隐式等待影响，秒返回
        try:
            alert = self.driver.switch_to.alert
            txt = (alert.text or "").strip()
            self.log(f"检测到浏览器弹窗，已自动处理: {txt[:80]}")
            try:
                alert.accept()
            except Exception:
                try:
                    alert.dismiss()
                except Exception:
                    pass
            return True
        except Exception:
            pass

        # 2. layui 弹层（近代报纸数据库常用）：只点可见弹层内的确认按钮，避免误点页面普通按钮
        try:
            self.driver.implicitly_wait(0)
            layers = self.driver.find_elements(By.XPATH, "//div[contains(@class,'layui-layer')]")
            for layer in layers:
                try:
                    if not layer.is_displayed():
                        continue
                    btns = layer.find_elements(
                        By.XPATH,
                        ".//a[contains(@class,'layui-layer-btn0') or contains(@class,'layui-layer-btn1')]"
                    )
                    for btn in btns:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.log("已关闭页面提示弹窗")
                            return True
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            self.driver.implicitly_wait(self._implicit_wait)
        return False

    def _open_detail(self, link, href, search_window, existing):
        """打开详情页，尽量复用已有详情窗口（避免每次新开窗口抢焦点、也更省时）"""
        is_real_url = bool(href) and href.startswith("http") and "javascript" not in href.lower()

        # 已有详情窗口且拿到真实 URL：直接在详情窗口内跳转，不新开窗口
        if existing and is_real_url:
            try:
                self.driver.switch_to.window(existing)
                self.driver.get(href)
                return existing
            except Exception:
                self.log("    复用详情窗口失败，改为新开窗口")
                existing = None

        # 点击链接（可能新开窗口，也可能在当前窗口跳转）
        try:
            self.driver.switch_to.window(search_window)
        except Exception:
            pass
        handles_before = set(self.driver.window_handles)
        try:
            self.driver.execute_script("arguments[0].click();", link)
        except Exception:
            try:
                link.click()
            except Exception:
                pass

        new_window = None
        for _ in range(15):
            time.sleep(0.5)
            new_handles = set(self.driver.window_handles) - handles_before
            if new_handles:
                new_window = new_handles.pop()
                self.log("    检测到详情页新窗口")
                break

        if new_window:
            # 若已有详情窗口且与新窗口不同，关闭旧的，避免窗口越积越多
            if existing and existing != new_window:
                try:
                    self.driver.switch_to.window(existing)
                    self.driver.close()
                except Exception:
                    pass
            return new_window

        if existing:
            return existing
        return None

    def _collect_results(self):
        """遍历搜索结果页，采集每条记录（复用详情窗口，减少新开窗口）"""
        page_num = 1
        detail_window = None
        while not self._stop:
            self.log(f"正在处理第 {page_num} 页...")
            self._dismiss_popup()
            time.sleep(1)

            # 解析当前页的记录信息
            records = self._parse_result_list()
            if not records:
                self.log("当前页未解析到记录，等待后重试...")
                time.sleep(2)
                records = self._parse_result_list()

            if not records:
                self.log("仍未解析到记录，任务结束。")
                break

            self.log(f"当前页解析到 {len(records)} 条记录")

            # 记录搜索结果窗口
            search_window = self.driver.current_window_handle

            for i, record in enumerate(records):
                if self._stop:
                    break
                self._dismiss_popup()
                name = record.get("name", "")
                info = record.get("info", "")
                title = record.get("title", "")
                self.log(f"  采集 [{i+1}/{len(records)}]: {name} {info} {title}")

                try:
                    # 每次重新定位"阅读"链接，避免页面变动导致元素失效(stale)
                    self.driver.switch_to.window(search_window)
                    read_links = self.driver.find_elements(
                        By.XPATH,
                        "//a[contains(text(), '阅读') and not(contains(text(), '整报'))]"
                    )
                    if i >= len(read_links):
                        self.log("    链接索引超出范围，跳过")
                        continue

                    link = read_links[i]
                    href = link.get_attribute("href") or ""
                    detail_window = self._open_detail(link, href, search_window, detail_window)

                    if not detail_window:
                        self.log("    未检测到详情页窗口，跳过")
                        continue

                    self.driver.switch_to.window(detail_window)
                    time.sleep(2.0)
                    self.log(f"    详情页: {self.driver.title}")

                    # 调用保存函数（直接使用当前driver，不需要url）
                    save_to_separate_word(
                        name, info, self.driver, self.output_dir,
                        article_title=title
                    )
                except Exception as e:
                    self.log(f"    采集记录出错: {e}")
                    self._dismiss_popup()
                finally:
                    # 确保回到搜索结果窗口（先退出 iframe 再切窗口）
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
                    try:
                        self.driver.switch_to.window(search_window)
                    except Exception:
                        pass

            if self._stop:
                break

            has_next = self._go_to_next_page()
            if not has_next:
                self.log("已到最后一页，任务结束。")
                break

            page_num += 1
            time.sleep(1.5)

    def _parse_result_list(self):
        """解析近代报纸数据库的搜索结果列表（只解析文本信息，不获取URL）"""
        records = []

        # 通过"阅读"链接定位每条记录
        try:
            read_links = self.driver.find_elements(
                By.XPATH,
                "//a[contains(text(), '阅读') and not(contains(text(), '整报'))]"
            )
            self.log(f"找到 {len(read_links)} 个'阅读'链接")

            for link in read_links:
                try:
                    # 向上找记录行（可能需要多级）
                    row = link
                    row_text = ""
                    for _ in range(8):
                        try:
                            row = row.find_element(By.XPATH, "..")
                            row_text = row.text.strip()
                            # 行文本应该包含日期和版次
                            if re.search(r"\d{4}-\d{1,2}-\d{1,2}", row_text) and "版" in row_text:
                                break
                        except Exception:
                            break

                    # 解析记录信息
                    name, info, title = self._parse_modern_record(row_text, link)

                    # 只保存文本信息，不保存URL（URL通过点击链接获取）
                    records.append({"name": name, "info": info, "title": title})
                except Exception as e:
                    self.log(f"  解析记录失败: {e}")
                    continue

            if records:
                return records
        except Exception as e:
            self.log(f"通过'阅读'链接解析失败: {e}")

        # 备选：查找所有包含日期和版次的行
        try:
            rows = self.driver.find_elements(By.XPATH, "//tr")
            for row in rows:
                try:
                    row_text = row.text.strip()
                    if re.search(r"\d{4}-\d{1,2}-\d{1,2}", row_text) and "版" in row_text:
                        name, info, title = self._parse_modern_record(row_text, None)
                        records.append({"name": name, "info": info, "title": title})
                except Exception:
                    continue
            if records:
                return records
        except Exception:
            pass

        # 策略3：通用 - 查找所有包含日期的链接
        try:
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            seen_urls = set()
            for link in all_links:
                href = link.get_attribute("href") or ""
                if not href or href in seen_urls or "javascript" in href.lower() or "#" in href:
                    continue
                text = link.text.strip()
                if not text or len(text) < 2:
                    continue
                try:
                    parent = link.find_element(By.XPATH, "..")
                    parent_text = parent.text.strip()
                except Exception:
                    parent_text = ""
                full_text = text + " " + parent_text
                if re.search(r"\d{4}-\d{1,2}-\d{1,2}", full_text) and "版" in full_text:
                    name, info, title = self._parse_modern_record(full_text, link)
                    records.append({"name": name, "info": info, "title": title, "url": href})
                    seen_urls.add(href)
            if records:
                return records
        except Exception:
            pass

        return records

    def _parse_modern_record(self, row_text, link_element=None):
        """解析近代报纸数据库的单条记录"""
        name = ""
        info = ""
        title = ""

        # 提取日期（格式：1947-01-31）
        date_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", row_text)
        if date_match:
            year, month, day = date_match.group(1), date_match.group(2), date_match.group(3)
            # 提取版次（格式：第5版）
            edition_match = re.search(r"第(\d+)版", row_text)
            edition = f"第{edition_match.group(1)}版" if edition_match else ""
            info = f"{year}年{month}月{day}日 {edition}".strip()

            # 提取报纸名（日期之前的部分，通常是报纸名）
            date_pos = date_match.start()
            before_date = row_text[:date_pos].strip()
            # 按行分割，找报纸名
            lines = before_date.split("\n")
            for line in lines:
                line = line.strip()
                if line and "茂名" not in line and not re.match(r"^[\d\s\.\-、]+$", line):
                    # 报纸名通常是2-6个字，以"日报"、"报"结尾
                    if line.endswith("报") or "日报" in line or "时报" in line:
                        name = line
                        break
            if not name and lines:
                # 取最后一个非空行作为报纸名
                for line in reversed(lines):
                    line = line.strip()
                    if line and "茂名" not in line:
                        name = line
                        break

            # 提取篇名（通常在行的开头，带红色标签）
            # 篇名通常在"茂名"标签后面
            title_match = re.search(r"茂名\s+(.+?)(?:\n|$)", row_text)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # 尝试从链接元素获取篇名
                if link_element:
                    try:
                        # 篇名可能在阅读链接前面的兄弟元素中
                        prev = link_element.find_element(By.XPATH, "preceding::*[1]")
                        prev_text = prev.text.strip()
                        if prev_text and len(prev_text) > 1:
                            title = prev_text
                    except Exception:
                        pass

            # 如果还没有篇名，尝试从行文本中提取
            if not title:
                # 篇名通常在第一行，"茂名"标签后面
                first_line = row_text.split("\n")[0].strip()
                if "茂名" in first_line:
                    title = first_line.replace("茂名", "").strip()
                elif len(first_line) > 1 and not first_line.endswith("报"):
                    title = first_line

        return name, info, title

    def _go_to_next_page(self):
        """点击下一页"""
        for id_val in ["btnNext", "nextPage", "next", "nextBtn", "pageNext"]:
            try:
                btn = self.driver.find_element(By.ID, id_val)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    return True
            except Exception:
                continue

        try:
            btn = self.driver.find_element(
                By.XPATH,
                "//a[contains(text(), '下一页') or contains(text(), '下页')]"
                "[not(contains(@class, 'disabled'))]"
            )
            if btn.is_displayed():
                btn.click()
                return True
        except Exception:
            pass

        try:
            btn = self.driver.find_element(
                By.XPATH,
                "//*[contains(@class,'next') and not(contains(@class,'disabled'))]"
            )
            if btn.is_displayed():
                btn.click()
                return True
        except Exception:
            pass

        return False
