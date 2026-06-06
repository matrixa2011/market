import asyncio
import sys
import re
import random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# Принудительно используем selector event loop для совместимости (на Linux не нужно, но оставим)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ---------- Генерация URL картинки WB ----------
def generate_wb_image_url(product_id: int) -> str:
    vol = product_id // 100000
    part = product_id // 1000
    vol_range = vol // 144
    basket = f"{vol_range + 1:02d}" if vol_range < 36 else "36"
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{product_id}/images/big/1.webp"

# ---------- WILDBERRIES ----------
async def parse_wildberries(query: str, browser, p_instance):
    products = []
    device = p_instance.devices['iPhone 13 Pro Max']
    context_options = {**device, "locale": "ru-RU", "timezone_id": "Europe/Moscow"}
    context = await browser.new_context(**context_options)
    page = await context.new_page()
    await stealth_async(page)
    try:
        url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={query}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(random.uniform(1, 2))
        await page.wait_for_selector('.product-card', timeout=15000)
        cards = await page.query_selector_all('.product-card')
        print(f"[WB] Найдено карточек: {len(cards)}")
        for card in cards[:15]:
            try:
                title_elem = await card.query_selector('.product-card__name')
                title = await title_elem.inner_text() if title_elem else "Товар WB"
                price_elem = await card.query_selector('.price__lower-price')
                if not price_elem:
                    price_elem = await card.query_selector('.product-card__price')
                price_text = await price_elem.inner_text() if price_elem else "0"
                price_match = re.search(r'(\d[\d\s]*)(?:₽|руб)?', price_text)
                price = int(re.sub(r'\s', '', price_match.group(1))) if price_match else 0
                if price == 0:
                    continue
                img_elem = await card.query_selector('img')
                img_url = await img_elem.get_attribute("src") if img_elem else ""
                if img_url and not img_url.startswith('http'):
                    img_url = "https:" + img_url
                link_elem = await card.query_selector('a')
                href = await link_elem.get_attribute("href") if link_elem else ""
                product_url = f"https://www.wildberries.ru{href}" if href and href.startswith('/') else href
                rating_elem = await card.query_selector('.product-card__rating')
                rating_text = await rating_elem.inner_text() if rating_elem else "4.5"
                rating_match = re.search(r'(\d+,\d+)', rating_text)
                rating = float(rating_match.group(1).replace(',', '.')) if rating_match else 4.5
                products.append({
                    "title": title.strip(),
                    "price": price,
                    "rating": rating,
                    "image_url": img_url,
                    "image": img_url,
                    "img": img_url,
                    "product_url": product_url
                })
            except Exception as e:
                print(f"[WB card error] {e}")
        print(f"[WB] Собрано товаров: {len(products)}")
    except Exception as e:
        print(f"[WB Error] {e}")
    finally:
        await context.close()
    return products[:12]

# ---------- OZON (Playwright, headless, мобильная эмуляция) ----------
async def parse_ozon(query: str, browser, p_instance):
    products = []
    device = p_instance.devices['iPhone 14 Pro Max']
    context_options = {
        **device,
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
        "geolocation": {"longitude": 37.6176, "latitude": 55.7558}
    }
    context = await browser.new_context(**context_options)
    page = await context.new_page()
    await stealth_async(page)
    try:
        url = f"https://www.ozon.ru/search/?text={query}&from_global=true"
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.uniform(3, 5))
        for _ in range(random.randint(3, 5)):
            await page.evaluate(f"window.scrollBy(0, {random.randint(300, 700)})")
            await asyncio.sleep(random.uniform(1.5, 2.5))
        await page.wait_for_selector('div.tile-root', timeout=25000)
        cards = await page.query_selector_all('div.tile-root')
        print(f"[Ozon] Найдено карточек: {len(cards)}")
        for card in cards[:25]:
            try:
                # Поиск цены
                price_elem = await card.query_selector('span:has-text("₽"), div:has-text("₽"), p:has-text("₽")')
                if not price_elem:
                    continue
                price_text = await price_elem.inner_text()
                clean = price_text.replace('\u2009', '').replace('\xa0', '').replace(' ', '').replace(',', '')
                price_match = re.search(r'(\d+)₽', clean)
                if not price_match:
                    price_match = re.search(r'(\d{3,6})', clean)
                if not price_match:
                    continue
                price = int(price_match.group(1))
                if price < 50:
                    continue
                # Ссылка
                link_elem = await card.query_selector('a[href*="/product/"]')
                if not link_elem:
                    continue
                href = await link_elem.get_attribute("href")
                full_url = f"https://www.ozon.ru{href.split('?')[0]}" if href else ""
                # Название
                title_elem = await card.query_selector('span[class*="title"], div[class*="title"], a[class*="title"]')
                if not title_elem:
                    title_elem = link_elem
                title = await title_elem.inner_text() if title_elem else "Товар Ozon"
                title = re.sub(r'\s+', ' ', title).strip()
                # Изображение
                img_elem = await card.query_selector('img')
                img_url = ""
                if img_elem:
                    img_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src")
                    if img_url and not img_url.startswith('http'):
                        img_url = "https:" + img_url
                products.append({
                    "title": title,
                    "price": price,
                    "rating": 4.8,
                    "image_url": img_url,
                    "image": img_url,
                    "img": img_url,
                    "product_url": full_url
                })
                if len(products) >= 10:
                    break
            except Exception as e:
                print(f"[Ozon card error] {e}")
        print(f"[Ozon] Собрано товаров: {len(products)}")
    except Exception as e:
        print(f"[Ozon Error] {e}")
    finally:
        await context.close()
    return products[:12]

# ---------- ЯНДЕКС ----------
async def parse_yandex(query: str, browser, p_instance):
    products = []
    device = p_instance.devices['iPhone 13']
    context_options = {**device, "locale": "ru-RU", "timezone_id": "Europe/Moscow"}
    context = await browser.new_context(**context_options)
    page = await context.new_page()
    await stealth_async(page)
    try:
        url = f"https://market.yandex.ru/search?text={query}"
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        await page.evaluate("window.scrollBy(0, 600)")
        await asyncio.sleep(1)
        cards = await page.query_selector_all('article, [data-zone-name="product-snippet"]')
        print(f"[Yandex] Найдено элементов: {len(cards)}")
        seen = set()
        for card in cards[:20]:
            text = await card.inner_text()
            if len(text) < 15:
                continue
            href = await card.get_attribute("href")
            if not href:
                link = await card.query_selector('a')
                if link:
                    href = await link.get_attribute("href")
            if not href:
                continue
            full_url = href if href.startswith("http") else f"https://market.yandex.ru{href}"
            full_url = full_url.split('?')[0]
            if full_url in seen:
                continue
            seen.add(full_url)
            clean = text.replace('\u2009', '').replace('\xa0', '').replace(' ', '')
            price_match = re.search(r'(\d+)(?:₽|руб)', clean) or re.search(r'(\d{4,6})', clean)
            if not price_match:
                continue
            price = int(price_match.group(1))
            if price < 100:
                continue
            img = await card.query_selector('img')
            img_url = await img.get_attribute("src") if img else ""
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            title_text = lines[1] if len(lines)>1 and len(lines[0])<10 else lines[0]
            products.append({
                "title": title_text,
                "price": price,
                "rating": 4.7,
                "image_url": img_url,
                "image": img_url,
                "img": img_url,
                "product_url": full_url
            })
        print(f"[Yandex] Валидных товаров: {len(products)}")
    except Exception as e:
        print(f"[Yandex Error] {e}")
    finally:
        await context.close()
    return products[:12]

def filter_and_sort_top3(products):
    if not products:
        return []
    valid = [p for p in products if p.get('price', 0) > 0 and p.get('title')]
    valid.sort(key=lambda x: x['price'])
    return valid[:3]

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "results": None, "query": ""})

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, query: str):
    if not query.strip():
        return templates.TemplateResponse("index.html", {"request": request, "results": None, "query": ""})
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"]
        )
        try:
            wb_task = asyncio.wait_for(parse_wildberries(query, browser, p), timeout=28.0)
            ozon_task = asyncio.wait_for(parse_ozon(query, browser, p), timeout=35.0)
            yandex_task = asyncio.wait_for(parse_yandex(query, browser, p), timeout=22.0)
            wb_products, ozon_products, yandex_products = await asyncio.gather(
                wb_task, ozon_task, yandex_task, return_exceptions=True
            )
            if isinstance(wb_products, Exception):
                wb_products = []
            if isinstance(ozon_products, Exception):
                ozon_products = []
            if isinstance(yandex_products, Exception):
                yandex_products = []
        finally:
            await browser.close()
    results = {
        "Wildberries": filter_and_sort_top3(wb_products),
        "Ozon": filter_and_sort_top3(ozon_products),
        "Яндекс Маркет": filter_and_sort_top3(yandex_products)
    }
    return templates.TemplateResponse("index.html", {"request": request, "results": results, "query": query})