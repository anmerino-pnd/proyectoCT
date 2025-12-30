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

def get_full_loaded_screenshot(url: str) -> str:
    options = ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--hide-scrollbars")
    # Es vital desactivar la aceleración por hardware en headless para capturas grandes
    options.add_argument("--disable-gpu") 
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(url)
        time.sleep(4) # Espera inicial de carga

        # -----------------------------------------------------------
        # PASO 1: FORZAR EL RENDERIZADO (Truco de CSS)
        # Inyectamos estilos para obligar a que las barras de scroll internas desaparezcan
        # y el contenido se expanda completamente. Esto arregla el problema de "capas".
        # -----------------------------------------------------------
        driver.execute_script("""
            var style = document.createElement('style');
            style.type = 'text/css';
            style.innerHTML = 'body, html { height: auto !important; overflow: visible !important; }';
            document.getElementsByTagName('head')[0].appendChild(style);
        """)
        
        # -----------------------------------------------------------
        # PASO 2: CALCULAR DIMENSIONES REALES
        # Usamos una métrica compuesta para asegurar que abarque todo
        # -----------------------------------------------------------
        metrics = driver.execute_script("""
            return {
                width: Math.max(document.body.scrollWidth, document.body.offsetWidth, document.documentElement.clientWidth, document.documentElement.scrollWidth, document.documentElement.offsetWidth),
                height: Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight)
            };
        """)
        
        print(f"Dimensiones detectadas: {metrics['width']}x{metrics['height']}")

        # -----------------------------------------------------------
        # PASO 3: USAR CDP PARA LA CAPTURA
        # Esto le habla directo al núcleo de Chrome, ignorando el viewport visible
        # -----------------------------------------------------------
        
        # Ajustamos el dispositivo virtual al tamaño total del contenido
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'mobile': False,
            'width': metrics['width'],
            'height': metrics['height'],
            'deviceScaleFactor': 1,
            'screenOrientation': {'angle': 0, 'type': 'portraitPrimary'},
        })
        
        # Tomamos la captura usando el comando nativo de DevTools
        result = driver.execute_cdp_cmd('Page.captureScreenshot', {
            'format': 'png',
            'fromSurface': True, 
            'captureBeyondViewport': True
        })
        
        return result['data'] # Esto ya es el string base64
        
    finally:
        driver.quit()