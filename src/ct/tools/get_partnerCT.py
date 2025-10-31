import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

def _get_base_chrome_options() -> ChromeOptions:
    """Retorna opciones base reutilizables"""
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--hide-scrollbars")
    #options.add_argument("--force-device-scale-factor=2")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return options

def _get_page_height(url: str) -> int:
    options = _get_base_chrome_options()  
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    driver.get(url=url)
    
    height = driver.execute_script(
        "return Math.max( document.body.scrollHeight, document.body.offsetHeight, "
        "document.documentElement.clientHeight, document.documentElement.scrollHeight, "
        "document.documentElement.offsetHeight )"
    )
    
    driver.quit()  # Usa quit() en lugar de close()
    return height

def get_screenshot(url: str) -> str:
    page_height = _get_page_height(url)
    
    options = _get_base_chrome_options()  # ✅ Nueva instancia
    options.add_argument(f"--window-size=1920,{page_height}")
    
    driver = webdriver.Chrome(options=options)
    driver.get(url=url)
    time.sleep(5)
    
    screenshot_as_base64 = driver.get_screenshot_as_base64()
    
    driver.quit()
    return screenshot_as_base64

