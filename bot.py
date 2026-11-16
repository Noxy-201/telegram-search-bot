import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

dp = Dispatcher()

class Base:
    def __init__(self):
        self.url = ""
        self.source = ""
        self.headers = {
            "User-Agent": (
                "TelegramSearchBot/1.0 "
                "(mailto:akakijivanov52@gmail.com) httpx"
            ),
            "Accept": "application/json",
        }

    def parse_response(self, data):
        return []

    def get_params(self, query: str) -> dict:
        return {}

    async def fetch(self, query):
        current_params = self.get_params(query)
        async with httpx.AsyncClient(headers= self.headers) as client:
            try:
                response = await client.get(self.url, params= current_params, timeout= 10)
                response.raise_for_status()
                raw_data = response.json()
                return self.parse_response(raw_data)


            except (httpx.TimeoutException, httpx.HTTPStatusError):
                print(f"{self.source} недоступен")
                return None

            except Exception:
                print(f"{self.source} недоступен")
                return None

class Wiki(Base):
    def __init__(self):
        super().__init__()
        self.url = "https://en.wikipedia.org/w/api.php"
        self.source = "Wikipedia"

    def parse_response(self, data: dict) -> list:
        pages = data.get("query", {}).get("pages", {})

        results = []
        for page in pages.values():
            results.append({"title": page.get("title"),
                   "description": page.get("extract", "Описание отсутствует"),
                   "url": page.get("fullurl"),
                   "source": "Wikipedia",
                   "extra" : {}
            })

        return results

    def get_params(self, query: str) -> dict:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": 3,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "exchars": 200,
            "inprop": "url"
        }
        return params

class GitHub(Base):
    def __init__(self):
        super().__init__()
        self.url = "https://api.github.com/search/repositories"
        self.source = "GitHub"

    def parse_response(self, data : dict) -> list:

        results = []
        for page in data["items"]:
            results.append({"title": page.get("full_name"),
                    "description": page.get("description"),
                    "url": page.get("html_url"),
                    "source": "GitHub", "extra": {
                    "stars": page.get("stargazers_count"),
                    "language": page.get("language")
                }})

        return results

    def get_params(self, query: str) -> dict:
        params = {
            "q" : query,
            "per_page" : 3
        }
        return params

class StackOverflow(Base):
    def __init__(self):
        super().__init__()
        self.url = "https://api.stackexchange.com/2.3/search/advanced"
        self.source = "Stack Overflow"

    def get_params(self, query: str) -> dict:
        params = {
            "site": "stackoverflow",
            "q" : query,
            "pagesize" : 3
        }
        return params

    def parse_response(self, data : dict) -> list:
        items = data.get("items", [])

        results = []
        for item in items:
            results.append({"title": item.get("title"),
                    "description": "",
                    "url": item.get("link"),
                   "source": "Stack OverFlow", "extra": {
                    "answer_count": item.get("answer_count"),
                    "rating": item.get("score"),
                    "is_answered": item.get("is_answered")
                }})

        return results

class SearchService:
    def __init__(self):
        self.sem = asyncio.Semaphore(5)

    async def search(self, user_query) -> list:
        async with self.sem:
            wiki = Wiki()
            git_hub = GitHub()
            stack_over_flow = StackOverflow()

            responses = await asyncio.gather(
                wiki.fetch(user_query),
                git_hub.fetch(user_query),
                stack_over_flow.fetch(user_query)
            )

            results = []

            for name, response in zip(["Wikipedia", "GitHub", "Stack Overflow"], responses):
                if response is not None:
                    results.extend(response)
                else:
                    results.append({
                        "title": f"Сервис {name} недоступен",
                        "description": "",
                        "url": "",
                        "source": ""
                    })

            return results

search_service = SearchService()
@dp.message(F.text)
async def any_text_message( message: Message):
    results = await search_service.search(message.text)

    if not results:
        await message.answer("Ничего не найдено")
        return

    results_all = []
    for result in results:
        extra = "\n".join(f"{key}: {value}" for key, value in result.get('extra', {}).items())
        text = (
            f"{result['title']}\n"
            f"{result['description']}\n"
            f"{result['url']}\n"
            f"{result['source']}\n"
            f"{extra}"
        )
        results_all.append(text)

    final = "\n\n".join(results_all)
    await message.answer(final)

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        error = "No token provided"
        raise ValueError(error)
    bot = Bot(token= token)

    try:
        await dp.start_polling(bot)
    finally:
        print("bot stopped")

if __name__ == "__main__":
    asyncio.run(main())