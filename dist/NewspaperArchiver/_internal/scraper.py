import time
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from save_to_word import save_to_separate_word


class NewspaperScraper:
    def __init__(self, search_str, output_dir="采集结果", log_callback=None):
        self.search_str = search_str
        self.output_dir = output_dir
        self.log = log_callback or print
        self.driver = None
        self._stop = False

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self.log(f"开始搜索: {self.search_str}")

            options = webdriver.EdgeOptions()
            options.set_capability("ms:loggingPrefs", {"performance": "ALL"})
            options.add_argument("--log-level=3")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])

            self.driver = webdriver.Edge(options=options)
            self.driver.implicitly_wait(10)
            self.driver.get("https://www.zslib.com.cn/Page/Page.html?t=sw")

            element = self.driver.find_element(
                By.XPATH,
                "//a[contains(@onclick, '2bebc42e-6b8b-4e38-87cf-86d97f7a600e')]",
            )
            element.click()

            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//a[contains(@onclick, '2bebc42e-6b8b-4e38-87cf-86d97f7a600e')]",
                    )
                )
            )
            self.log("请在 10 秒内完成手机扫码登录...")
            time.sleep(10)
            element.click()
            time.sleep(2)

            all_handles = self.driver.window_handles
            self.driver.switch_to.window(all_handles[-1])
            self.log(f"当前页面: {self.driver.title}")
            time.sleep(5)

            button = self.driver.find_element(By.ID, "bz")
            button.click()
            time.sleep(2)

            searchText = self.driver.find_element(By.ID, "txtBaseSearchValue")
            searchText.clear()
            searchText.send_keys(self.search_str)
            time.sleep(2)

            searchButton = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "btnsearchimg"))
            )
            searchButton.click()

            target_frame = self.driver.find_elements(By.ID, "BriefList")[1]
            self.driver.switch_to.frame(target_frame)

            page_num = 1
            while not self._stop:
                self.log(f"正在处理第 {page_num} 页...")
                self.driver.switch_to.default_content()
                try:
                    target_frame = self.driver.find_elements(By.ID, "BriefList")[1]
                    self.driver.switch_to.frame(target_frame)
                except Exception as e:
                    self.log(f"未能切换到结果列表 iframe: {e}")
                    break

                rows = self.driver.find_elements(
                    By.XPATH, "//div[@class='retTable']//table/tbody/tr"
                )
                current_page_data = []
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) > 2:
                        name = cols[1].text.strip()
                        info = cols[2].text.strip()
                        try:
                            link_el = row.find_element(
                                By.XPATH, ".//a[contains(@href, 'boxId')]"
                            )
                            url = link_el.get_attribute("href")
                            current_page_data.append((name, info, url))
                        except Exception:
                            continue

                for i, (name, info, url) in enumerate(current_page_data):
                    if self._stop:
                        break
                    self.log(f"  采集: {name} {info}")
                    save_to_separate_word(
                        name, info, url, self.driver, i, self.output_dir
                    )

                if self._stop:
                    break

                try:
                    page_info = self.driver.find_element(By.CLASS_NAME, "pagin")
                    page_text = page_info.text
                    match = re.search(r"(\d+)/(\d+)", page_text)
                    if match:
                        current_p = int(match.group(1))
                        total_p = int(match.group(2))
                        self.log(f"页码状态: {current_p} / {total_p}")
                        if current_p >= total_p:
                            self.log("已采集到最后一页，任务结束。")
                            break
                    else:
                        self.log("未提取到页码数值，尝试检查按钮...")

                    next_button = self.driver.find_element(By.ID, "btnNext")
                    next_button.click()
                    page_num += 1
                    time.sleep(3)
                except Exception as e:
                    self.log(f"翻页出错或已无下一页: {e}")
                    break

            if self._stop:
                self.log("用户手动停止。")
            else:
                self.log("所有采集任务已完成。")

        except Exception as e:
            self.log(f"采集过程出错: {e}")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
