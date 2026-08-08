from scraper import NewspaperScraper

if __name__ == '__main__':
    print("你要搜索的信息，按回车确认")
    searchStr = input()
    scraper = NewspaperScraper(searchStr, output_dir="采集结果")
    scraper.run()
