"""
测试脚本：直接指定搜索关键词，将日志同时输出到控制台和文件
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

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

log_file = open(os.path.join(os.path.dirname(__file__), "run_log.txt"), "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, log_file)
sys.stderr = Tee(sys.stderr, log_file)

from scraper import NewspaperScraper

if __name__ == '__main__':
    search_str = "茂名"
    print(f"搜索关键词: {search_str}")
    scraper = NewspaperScraper(search_str, output_dir="采集结果")
    scraper.run()
    print("程序结束")
    log_file.close()
