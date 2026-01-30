# steam_crawler/spiders/steam_spider.py
import scrapy  # Основной модуль Scrapy для создания пауков и запросов
from scrapy.spiders import CrawlSpider, Rule # CrawlSpider паук для рекурсивного обхода; Rule — правило обхода
from scrapy.linkextractors import LinkExtractor # Инструмент для извлечения ссылок со страниц
from steam_crawler.items import SteamGameItem # Импорт структуры данных (Item) для хранения информации об игре


class SteamCrawlSpider(CrawlSpider):
    name = 'steam_top_sellers'
    allowed_domains = ['store.steampowered.com']
    start_urls = ['https://store.steampowered.com/search/?filter=topsellers']

    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 1000,  # Остановка после ~1000 элементов
        'DOWNLOAD_DELAY': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36',
    }
    # Куки для автоматического прохождения возрастной проверки на Steam
    age_check_cookies = {
        'birthtime': '197053200',   # 31 марта 1976
        'mature_content': '1'
    }
    # Правила автоматического обхода сайта: как извлекать ссылки и что с ними делать
    rules = (
        Rule(                 # Правило 1: извлекать ссылки на страницы игр из результатов поиска
            LinkExtractor(
                allow=r'/app/\d+/',   # Только URL вида /app/12345/ (цифровой ID игры)
                restrict_css='#search_resultsRows'  # Искать ссылки только внутри блока результатов поиска
            ),
            callback='parse_game',   # Вызывать метод parse_game для обработки каждой найденной страницы игры
            follow=False,             # Не следовать по другим ссылкам на странице игры 
            process_request='add_age_check_cookies'  # Перед отправкой запроса добавить куки для обхода age check
        ),
        Rule(                # Правило 2: переходить по пагинации (следующие страницы поиска)
            LinkExtractor(
                restrict_css='.search_pagination_right a'  # Извлекать ссылки на "следующие страницы" в блоке пагинации
            ),
            follow=True,    # Продолжать обход по этим ссылкам (рекурсивно)
            process_request='add_age_check_cookies'  # Также добавлять куки к запросам пагинации (на всякий случай)
        ),
    )

    def add_age_check_cookies(self, request, response):  # Обработчик для добавления кук к каждому генерируемому запросу
        request.cookies.update(self.age_check_cookies)
        return request

    def start_requests(self): # метод, чтобы возвращать (или генерировать) объекты запросов 
        for url in self.start_urls: # Запускаем стартовые URL с куками
            yield scrapy.Request(
                url=url,
                cookies=self.age_check_cookies,
                dont_filter=True
            )

    
    def parse_game(self, response):   # Метод обработки страницы отдельной игры
        # Пропускаем agecheck-страницы
        if 'agecheck' in response.url:
            return

        item = SteamGameItem()  # Создаём новый элемент данных (игру)
        item['url'] = response.url  # Сохраняем URL страницы игры (для отладки и анализа)
        item['title'] = response.css('div.apphub_AppName::text').get(default='').strip()  # Название игры из заголовка
        

        # Извлечение даты выхода из блока .date
        release_raw = response.css('div.date::text').get()
        item['release_date'] = release_raw.strip() if release_raw else ''  # Очищаем от пробелов или оставляем пустым

         # Извлечение разработчика: ищем <b>Developer:</b>, затем первую ссылку после него
        developer = response.xpath(
            '//div[@class="dev_row"]/b[text()="Developer:"]/following-sibling::a[1]/text()'
        ).get(default='').strip()
        # Извлечение издателя: аналогично для <b>Publisher:</b>
        publisher = response.xpath(
            '//div[@class="dev_row"]/b[text()="Publisher:"]/following-sibling::a[1]/text()'
        ).get(default='').strip()

        item['developer'] = developer  # Сохраняем разработчика
        item['publisher'] = publisher  # Сохраняем издателя

       # Извлечение всех пользовательских тегов (Steam показывает 20 самых популярных)
        all_tags = response.css('div.glance_tags a.app_tag::text').getall()
        item['tags'] = [tag.strip() for tag in all_tags if tag.strip()]  # Очистка от лишних пробелов и пустых строк

        yield item