# steam_crawler/items.py
import scrapy

class SteamGameItem(scrapy.Item): # (scrapy.Item —  контейнер для структурированных данных)
    title = scrapy.Field()          # Название игры
    release_date = scrapy.Field()   # Дата выхода (в виде строки, например: "15 Oct, 2020")
    developer = scrapy.Field()      # Разработчик
    publisher = scrapy.Field()      # Издатель
    tags = scrapy.Field()           # Список тегов (все, включая скрытые по "+")
    url = scrapy.Field()            # URL страницы игры (для отладки и группировки)
