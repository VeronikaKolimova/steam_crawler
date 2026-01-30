# steam_crawler/spiders/steam_spider.py
import scrapy  # Основной модуль Scrapy для создания пауков и запросов
from scrapy.spiders import CrawlSpider, Rule  # CrawlSpider паук для рекурсивного обхода; Rule — правило обхода
from scrapy.linkextractors import LinkExtractor  # Инструмент для извлечения ссылок со страниц
from steam_crawler.items import SteamGameItem  # Импорт структуры данных (Item) для хранения информации об игре


class SteamCrawlSpider(CrawlSpider):  # Класс спайдера, наследуемый от CrawlSpider для автоматического обхода ссылок
    name = 'steam_top_sellers'  # Уникальное имя спайдера для его запуска: scrapy crawl steam_top_sellers
    allowed_domains = ['store.steampowered.com']  # Парсить только этот домен и его поддомены
    start_urls = ['https://store.steampowered.com/search/?filter=topsellers']  # Начальный URL: топ продаж на Steam

    # Настройки, переопределяющие глобальные параметры Scrapy только для этого спайдера
    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 1000,  # Остановка после 1000 собранных игр
        'DOWNLOAD_DELAY': 1,  # Задержка 1 сек между запросами 
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,  # Случайное отклонение задержки (от 0.5 до 1.5 сек)Scrapy автоматически использует диапазон ±50% от DOWNLOAD_DELAY
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36',  # Имитация браузера, чтобы избежать блокировки
    }

    # Куки для автоматического прохождения возрастной проверки на Steam
    age_check_cookies = {
        'birthtime': '197053200',   # Unix-время для даты 31 марта 1976 года (пользователь старше 18 лет)
        'mature_content': '1'       # Флаг, подтверждающий согласие на просмотр взрослого контента
    }

    # Правила автоматического обхода сайта: как извлекать ссылки и что с ними делать
    rules = (
        # Правило 1: извлекать ссылки на страницы игр из результатов поиска
        Rule(
            LinkExtractor(
                allow=r'/app/\d+/',              # Только URL вида /app/12345/ (цифровой ID игры)
                restrict_css='#search_resultsRows'  # Искать ссылки только внутри блока результатов поиска
            ),
            callback='parse_game',               # Вызывать метод parse_game для обработки каждой найденной страницы игры
            follow=False,                        # Не следовать по другим ссылкам на странице игры 
            process_request='add_age_check_cookies'  # Перед отправкой запроса добавить куки для обхода age check
        ),
        # Правило 2: переходить по пагинации (следующие страницы поиска)
        Rule(
            LinkExtractor(
                restrict_css='.search_pagination_right a'  # Извлекать ссылки на "следующие страницы" в блоке пагинации
            ),
            follow=True,                         # Продолжать обход по этим ссылкам (рекурсивно)
            process_request='add_age_check_cookies'  # Также добавлять куки к запросам пагинации (на всякий случай)
        ),
    )

    def __init__(self, *args, **kwargs):  # Конструктор класса — инициализация при запуске спайдера
        super().__init__(*args, **kwargs)  # Вызов родительского конструктора
        self.items_collected = 0           # Счётчик собранных игр
        self.max_items = 1000              # Максимальное количество игр для сбора

    def add_age_check_cookies(self, request, response):  # Обработчик для добавления кук к каждому генерируемому запросу
        """Добавляет куки ко всем запросам, генерируемым правилами"""
        request.cookies.update(self.age_check_cookies)  # Добавляем birthtime и mature_content в cookies запроса
        return request  # Возвращаем изменённый запрос

    # метод, чтобы возвращать (или генерировать) объекты запросов 
    def start_requests(self):  # Переопределение метода: как начинать парсинг // спайдер наследуется от CrawlSpider
        """Запускаем стартовые URL с куками"""
        for url in self.start_urls:  # Для каждого URL из start_urls
            yield scrapy.Request(
                url=url,                          # Целевой URL
                cookies=self.age_check_cookies,   # Передаём куки сразу в первый запрос
                dont_filter=True                  # Не фильтровать дубликаты (на случай, если URL повторится)
            )

    def parse_game(self, response):  # Метод обработки страницы отдельной игры
        # Пропускаем обработку, если уже собрано 1000 игр
        if self.items_collected >= self.max_items:
            return  # Ничего не возвращаем — игра игнорируется

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

        # Извлечение всех пользовательских тегов (Steam всегда показывает ровно 20 самых популярных)
        all_tags = response.css('div.glance_tags a.app_tag::text').getall()
        item['tags'] = [tag.strip() for tag in all_tags if tag.strip()]  # Очистка от лишних пробелов и пустых строк

        self.items_collected += 1  # Увеличиваем счётчик собранных игр
        yield item  # Возвращаем элемент для сохранения (в JSON, CSV и т.д.)

    def _requests_to_follow(self, response):  # Внутренний метод CrawlSpider: какие ссылки генерировать дальше
        if self.items_collected >= self.max_items:
            return  # Если лимит достигнут — не генерировать новые запросы (останавливаем обход)
        yield from super()._requests_to_follow(response)  # Иначе — продолжаем как обычно